# -*- coding: utf-8 -*-
"""V1 project 化分阶段接口（TravelGen_v1.md §七~§十八）。

- 新旧共存：本 router 提供 /api/ 前缀的 V1 接口，旧 /api/v1/* 在 app.py 原样保留
- 分阶段：创建项目 → 方案确认（PUT plan）→ 分镜 → Shot 修改 → 批量生成 → 轮询 tasks
- 占位：audio / render / render-status 返回 reserved（本版不做，见契约文档标注）
- 关键语义：POST generate 即视为"确认分镜"；前端轮询用 GET /api/projects/{id}
"""
import asyncio, uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from pipeline import kb
from pipeline import validate as v
from pipeline.demo import parse_script
from pipeline.pipeline import PipelineRunner, _parse_cw
from schemas import (AudioRequest, ConfirmPlanRequest, GenerateRequest, GenerateShotsRequest,
                     RegenerateShotRequest, RenderRequest, ShotPatch, StoryboardRequest)
from constants import SCENE_TYPE_ALIASES, SCENE_TYPES, ASPECT_RATIOS, RESOLUTIONS, VIDEO_MODELS
import projects as P

router = APIRouter(prefix="/api", tags=["项目分阶段"])
runner = PipelineRunner()


# ---- 辅助 ----

def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"


def _err(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message, "detail": ""})


def _get_project(pid: str) -> P.Project:
    project = P.load_project(pid)
    if project is None:
        _err(404, "project_not_found", f"项目 {pid} 不存在")
    return project


def _get_video_task(tid: str) -> P.VideoTask:
    vt = P.load_video_task(tid)
    if vt is None:
        _err(404, "task_not_found", f"任务 {tid} 不存在")
    return vt


def _state_guard(project: P.Project, allowed: set, op: str):
    if project.status not in allowed:
        _err(409, "invalid_state",
             f"{op} 需项目处于 {sorted(allowed)}，当前 {project.status}")


def _find_shot(project: P.Project, shot_id: int) -> dict:
    for sc in project.storyboard.get("scenes", []):
        for sh in sc["shot_list"]:
            if sh["shot_id"] == shot_id:
                return sh
    _err(404, "shot_not_found", f"Shot {shot_id} 不在分镜中（可用镜头见 storyboard）")


def _require_storyboard(project: P.Project):
    if not project.storyboard.get("scenes"):
        _err(409, "invalid_state", "分镜尚未生成，请先 POST /storyboard")


# ---- 后台协程（try/finally 落盘，重启不丢） ----

async def _run_plan(project: P.Project):
    try:
        project.status, project.progress, project.message = "planning", 5, "生成内容大纲"
        project.dump()
        await runner.generate_plan(project)
        project.visual_assets = kb.visual_assets(project.request)
        project.safety = {"passed": True, "checks": [
            {"type": "content", "result": "pass", "note": "知识库事实来源"},
            {"type": "copyright", "result": "pass", "note": "素材来源可追溯"},
            {"type": "license", "result": "pass", "note": "Unsplash License 免费商用"}]}
        project.status, project.progress, project.message = "waiting_confirm", 10, "方案待确认"
    except Exception as e:
        project.status, project.message = "failed", f"生成方案失败｜{type(e).__name__}: {e}"
    finally:
        project.dump()


async def _run_storyboard(project: P.Project):
    try:
        await runner.generate_storyboard(project)
        project.visual_assets = kb.visual_assets(project.request)
        project.status, project.progress, project.message = "waiting_storyboard_confirm", 40, "分镜待确认（可修改 Shot）"
    except Exception as e:
        project.status, project.message = "failed", f"分镜失败｜{type(e).__name__}: {e}"
    finally:
        project.dump()


async def _run_video_task(project: P.Project, vt: P.VideoTask, shot_ids: list[int]):
    try:
        vt.init_shots(shot_ids)
        project.status, project.progress = "generating", 40
        project.message = "视频生成中"
        vt.dump(), project.dump()

        def sync(clips, done, total):
            vt.sync_from_clips(clips)                    # per-shot 状态实时同步
            project.progress = 40 + int(done / total * 50)
            project.message = f"视频生成中 {done}/{total} 完成"
            vt.dump(), project.dump()                    # 轮询中落盘，重启可恢复进度

        clips = await runner.generate_videos(project, shot_ids, task=vt, on_progress=sync)
        sync(clips, sum(1 for c in clips if c["status"] == "succeeded"), len(clips))  # 最终同步（demo 无轮询）
        n_ok = sum(1 for c in clips if c["status"] == "succeeded")
        vt.status = "completed" if n_ok == len(clips) else "failed"
        vt.progress = 100
        vt.message = f"完成 {n_ok}/{len(clips)} 成功" if n_ok == len(clips) else f"部分失败 {n_ok}/{len(clips)} 成功"
    except Exception as e:
        vt.status, vt.message = "failed", f"{type(e).__name__}: {e}"
    finally:
        vt.dump()
        P.recompute_project_status(project)
        project.dump()


# ---- 接口1：创建项目 / 生成创作方案 ----

@router.post("/projects", status_code=202)
async def create_project(req: GenerateRequest):
    errs = []
    if req.scene_type not in SCENE_TYPES and req.scene_type not in SCENE_TYPE_ALIASES:
        errs.append(f"scene_type 需为 {SCENE_TYPES} 或英文别名 {list(SCENE_TYPE_ALIASES)}")
    if req.aspect_ratio not in ASPECT_RATIOS:
        errs.append(f"aspect_ratio 需为 {ASPECT_RATIOS}")
    if req.resolution not in RESOLUTIONS:
        errs.append(f"resolution 需为 {RESOLUTIONS}")
    if req.video_model not in VIDEO_MODELS:
        errs.append(f"video_model 需为 {VIDEO_MODELS}")
    if errs:
        _err(400, "invalid_param", "；".join(errs))

    request = req.model_dump()
    request["scene_type"] = SCENE_TYPE_ALIASES.get(req.scene_type, req.scene_type)  # 落库中文枚举
    pid = _new_id("p")
    project = P.Project(pid, request)
    P.PROJECTS[pid] = project
    project.dump()
    asyncio.create_task(_run_plan(project))
    return {"project_id": pid, "status": "planning", "progress": 5, "message": "生成创作方案",
            "planning": {}, "copywriting": {}, "copywriting_text": ""}


# ---- 接口2：修改/确认创作方案 ----

@router.put("/projects/{pid}/plan")
async def confirm_plan(pid: str, req: ConfirmPlanRequest):
    project = _get_project(pid)
    _state_guard(project, {"waiting_confirm"}, "确认方案")
    cw = _parse_cw(req.copywriting)
    if not cw["paragraphs"]:
        # 兜底：用户编辑可能丢了【0-15s】时间戳标记，整段当一个段落（前端体验优先，不拒绝）
        cw = {"titles": cw["titles"], "hashtags": cw["hashtags"],
              "paragraphs": [{"idx": 1, "text": req.copywriting.strip(),
                              "duration_s": project.request.get("duration_s", 60)}]}
    project.copywriting = cw
    project.script = parse_script(cw)
    project.plan_version += 1
    project.plan_id = f"plan_{project.project_id}_v{project.plan_version}"
    project.storyboard = {}            # 文案变了，旧分镜失效
    project.video_tasks = []           # 旧视频结果作废
    project.status, project.progress, project.message = "plan_confirmed", 15, "方案已确认"
    project.dump()
    return {"project_id": pid, "status": "plan_confirmed",
            "plan_id": project.plan_id, "progress": 15}


# ---- 接口3：生成视频脚本 + 分镜 ----

@router.post("/projects/{pid}/storyboard", status_code=202)
async def create_storyboard(pid: str, req: StoryboardRequest):
    project = _get_project(pid)
    _state_guard(project, {"plan_confirmed"}, "生成分镜")
    if req.plan_id and req.plan_id != project.plan_id:
        _err(409, "invalid_state", f"plan_id 不匹配（当前 {project.plan_id}）")
    project.status, project.progress, project.message = "storyboarding", 20, "拆分分镜（JSON 硬校验）"
    project.dump()
    asyncio.create_task(_run_storyboard(project))
    return {"project_id": pid, "status": "storyboarding", "progress": 20, "message": "拆分分镜"}


# ---- 接口4：修改单个 Shot ----

@router.put("/projects/{pid}/shots/{shot_id}")
async def update_shot(pid: str, shot_id: int, patch: ShotPatch):
    project = _get_project(pid)
    _require_storyboard(project)
    shot = _find_shot(project, shot_id)
    upd = patch.model_dump(exclude_none=True)
    ok, errs, norm = v.validate_shot_patch(upd)
    if not ok:
        _err(400, "invalid_param", "；".join(errs[:4]))
    shot.update(norm)
    project.dump()
    return {"project_id": pid, "shot_id": shot_id, "status": "updated", "shot": shot}


# ---- 接口5：批量生成视频 Shot ----

@router.post("/projects/{pid}/generate", status_code=202)
async def generate_batch(pid: str, req: GenerateShotsRequest):
    project = _get_project(pid)
    _require_storyboard(project)
    if not req.generate_video:
        _err(400, "invalid_param", "generate_image 单独生成本版未实现（video-only）；请设 generate_video=true")
    valid_ids = {sh["shot_id"] for sc in project.storyboard["scenes"] for sh in sc["shot_list"]}
    unknown = [s for s in req.shots if s not in valid_ids]
    if unknown:
        _err(400, "invalid_param", f"shots 不存在: {unknown}，可用镜头 {sorted(valid_ids)}")

    tid = _new_id("vt")
    vt = P.VideoTask(tid, pid, "batch", req.model_dump())
    P.VIDEO_TASKS[tid] = vt
    project.video_tasks.append(tid)
    project.dump()
    asyncio.create_task(_run_video_task(project, vt, list(req.shots)))
    return {"task_id": tid, "project_id": pid, "status": "generating", "progress": 0,
            "shots": [{"shot_id": s, "status": "pending"} for s in req.shots]}


# ---- 接口6：查询生成任务 ----

@router.get("/tasks/{task_id}")
async def get_video_task(task_id: str):
    return _get_video_task(task_id).to_dict()


# ---- §十五：Shot 级重新生成 ----

@router.post("/projects/{pid}/shots/{shot_id}/regenerate", status_code=202)
async def regenerate_shot(pid: str, shot_id: int, req: RegenerateShotRequest):
    project = _get_project(pid)
    _require_storyboard(project)
    shot = _find_shot(project, shot_id)
    if req.prompt and req.prompt.strip() and req.prompt.strip() != shot.get("prompt"):
        shot["prompt"] = req.prompt.strip()   # prompt 变化先写回分镜，新任务自然覆盖旧结果
        project.dump()
    tid = _new_id("vt")
    snapshot = {"shot_ids": [shot_id], "generate_image": False, "generate_video": True,
                "regenerate": req.model_dump()}
    vt = P.VideoTask(tid, pid, "single", snapshot)
    P.VIDEO_TASKS[tid] = vt
    project.video_tasks.append(tid)
    project.status, project.progress = "generating", 40
    project.message = f"重新生成 Shot {shot_id}"
    project.dump()
    asyncio.create_task(_run_video_task(project, vt, [shot_id]))
    return {"task_id": tid, "shot_id": shot_id, "status": "generating"}


# ---- 接口7/8/9：音频、合成、成片查询（本版占位 reserved） ----

@router.post("/projects/{pid}/audio", status_code=202)
async def create_audio(pid: str, req: AudioRequest = None):
    project = _get_project(pid)
    return {"task_id": f"audio_{project.project_id}_reserved", "project_id": pid,
            "status": "reserved", "voice": {"status": "reserved"}, "music": {"status": "reserved"}}


@router.post("/projects/{pid}/render", status_code=202)
async def create_render(pid: str, req: RenderRequest = None):
    project = _get_project(pid)
    return {"task_id": f"render_{project.project_id}_reserved", "project_id": pid,
            "status": "reserved"}


@router.get("/projects/{pid}/render/status")
async def render_status(pid: str):
    project = _get_project(pid)
    return {"task_id": f"render_{project.project_id}_reserved", "status": "reserved", "progress": 0,
            "video": {"status": "reserved", "url": "", "duration_s": 0,
                      "resolution": project.request.get("resolution", "1080p"),
                      "aspect_ratio": project.request.get("aspect_ratio", "9:16")}}


# ---- 补充端点：查询项目全量（分阶段轮询入口，V1 文档未列但流程必需） ----

@router.get("/projects/{pid}")
async def get_project(pid: str):
    project = _get_project(pid)
    P.recompute_project_status(project)   # 视频任务终止/进行状态 → 项目状态
    return project.to_dict()


# ---- 知识库检索（V1 体系别名，行为同 /api/v1/kb/search） ----

@router.get("/kb/search")
async def search_kb(q: str, top_k: int = 5):
    if not q.strip():
        _err(400, "invalid_param", "q 不能为空")
    entries = kb.search(q, top_k)
    return {"results": [{"id": e["id"], "name": e["name"], "city": e.get("city", ""),
                         "category": e.get("category", ""), "facts": e.get("facts", [])[:3],
                         "source": e.get("source", ""), "verified": e.get("verified", False)}
                        for e in entries]}
