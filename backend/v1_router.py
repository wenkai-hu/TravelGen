# -*- coding: utf-8 -*-
"""Project 化分阶段接口：Master Audio → Storyboard → Segment → Render。

- 新旧共存：本 router 提供 /api/ 前缀的 V1 接口，旧 /api/v1/* 在 app.py 原样保留
- 分阶段：创建项目 → 搜图 → 方案确认 → 母带 → 分镜 → Segment 生成 → 回铺母带
- Shot 是 Segment 内可编辑的画面指令；实际生成和重生成的最小单位始终是 Segment
"""
import asyncio, uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from pipeline import (audio_pipeline, composer, kb, model_client, reference_search,
                      segment_planner, visual_rag, vlm_client)
from pipeline import validate as v
from pipeline.demo import parse_script
from pipeline.pipeline import PipelineRunner, _parse_cw
from schemas import (AudioRequest, ConfirmPlanRequest, ConfirmReferencesRequest,
                     GenerateRequest, GenerateShotsRequest, RegenerateSegmentRequest,
                     RegenerateShotRequest, RenderRequest, SegmentPatch, ShotPatch,
                     StoryboardRequest)
from constants import SCENE_TYPE_ALIASES, SCENE_TYPES, ASPECT_RATIOS, RESOLUTIONS, VIDEO_MODELS
from db.auth import get_current_user
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


def _owned_project(pid: str, username: str) -> P.Project:
    """归属校验：非本人项目一律 404（不暴露存在性）。旧数据 username 为空 → 视为垃圾，对所有人不可见。"""
    project = _get_project(pid)
    if project.username != username:
        _err(404, "project_not_found", f"项目 {pid} 不存在")
    return project


def _get_task(tid: str):
    task = P.load_any_task(tid)
    if task is None:
        _err(404, "task_not_found", f"任务 {tid} 不存在")
    return task


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


def _find_segment(project: P.Project, segment_id: str) -> dict:
    segment = segment_planner.find_segment(project.storyboard, segment_id)
    if segment is None:
        _err(404, "segment_not_found", f"Segment {segment_id} 不在当前 Storyboard 中")
    return segment


def _guard_shots_available(project: P.Project, shot_ids: list[int]):
    """项目允许并行任务，但同一 Shot 同一时刻只允许一个 Seedance 任务。"""
    busy = sorted(set(shot_ids) & P.active_video_shot_ids(project))
    if busy:
        _err(409, "shot_generating", f"Shot {busy} 正在生成，请勿重复提交")


def _guard_segments_available(project: P.Project, segment_ids: list[str]):
    busy = sorted(set(segment_ids) & P.active_segment_ids(project))
    if busy:
        _err(409, "segment_generating", f"Segment {busy} 正在生成，请勿重复提交")


def _invalidate_render(project: P.Project):
    """任何会改变当前画面结果的操作，都必须让旧成片退出权威状态。"""
    project.render = {"status": "none", "version": (project.render or {}).get("version", 0)}
    project.final_video = {"status": "none", "url": "", "preview_url": "", "duration_s": 0,
                           "resolution": project.request.get("resolution", "1080p"),
                           "aspect_ratio": project.request.get("aspect_ratio", "9:16")}


# ---- 后台协程（try/finally 落盘，重启不丢） ----

async def _run_plan(project: P.Project):
    try:
        project.status, project.progress, project.message = "planning", 8, "生成内容大纲"
        project.dump()
        await runner.generate_plan(project)
        project.visual_assets = visual_rag.public_visual_assets(project, kb.visual_assets(project.request))
        project.safety = {"passed": False, "checks": [
            {"type": "content", "result": "pass", "note": "知识库事实来源"},
            {"type": "copyright", "result": "review", "note": "已保留搜索来源页，发布前需人工复核"},
            {"type": "license", "result": "unknown", "note": "搜索结果不自动授予商用许可"}]}
        project.status, project.progress, project.message = "waiting_confirm", 10, "方案待确认"
    except Exception as e:
        project.status, project.message = "failed", f"生成方案失败｜{type(e).__name__}: {e}"
    finally:
        project.dump()


async def _run_audio_task(project: P.Project, task: P.AudioTask):
    try:
        project.status, project.progress, project.message = "audio_generating", 15, "正在生成完整旁白与背景音乐"
        task.progress, task.message = 10, "Edge-TTS 旁白测时"
        task.dump(), project.dump()
        result = await audio_pipeline.build_master_audio(
            project,
            voice=task.request.get("voice") or "zh-CN-XiaoxiaoNeural",
            music=task.request.get("music") or "ambient",
            mock=runner.mock_all,
        )
        task.result = result
        task.status, task.progress, task.message = "completed", 100, "Master audio 已生成"
        project.audio = result
        project.voice = {"status": "ready", **result.get("voice_profile", {}),
                         "url": result.get("voice_track_url", "")}
        project.music = {"status": "ready", "cues": result.get("music_cues", []),
                         "url": result.get("master_url", "")}
        project.status, project.progress, project.message = "audio_ready", 20, "完整音轨已生成，准备拆分画面"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = "音频生成失败"
        project.status, project.message = "failed", f"音频生成失败｜{task.error}"
        project.audio = {**(project.audio or {}), "status": "failed", "error": task.error}
    finally:
        task.dump(), project.dump()


async def _run_storyboard(project: P.Project):
    try:
        await runner.generate_storyboard(project)
        errors = segment_planner.validate_segment_plan(
            project.storyboard, int(project.audio.get("duration_ms", 0)))
        if errors:
            raise ValueError("Segment 规划校验失败：" + "；".join(errors[:6]))
        project.visual_assets = visual_rag.public_visual_assets(project, kb.visual_assets(project.request))
        project.status, project.progress, project.message = "waiting_storyboard_confirm", 40, "分镜待确认（可修改 Shot）"
    except Exception as e:
        project.status, project.message = "failed", f"分镜失败｜{type(e).__name__}: {e}"
    finally:
        project.dump()


async def _run_segment_task(project: P.Project, task: P.SegmentTask, segment_ids: list[str]):
    try:
        segments = [_find_segment(project, segment_id) for segment_id in segment_ids]
        task.init_segments(segments)
        project.status, project.progress, project.message = "generating", 45, "Segment 视频生成中"
        task.dump(), project.dump()

        def sync(clips, done, total):
            task.sync_from_clips(clips)
            project.progress = 45 + int(done / total * 35)
            project.message = f"Segment 视频生成中 {done}/{total} 完成"
            task.dump(), project.dump()

        clips = await runner.generate_segments(project, segment_ids, task=task, on_progress=sync)
        sync(clips, sum(1 for clip in clips if clip["status"] == "succeeded"), len(clips))
        ok = sum(1 for clip in clips if clip["status"] == "succeeded")
        task.status = "completed" if ok == len(clips) else "failed"
        task.progress = 100
        task.message = f"完成 {ok}/{len(clips)} 个 Segment"
        completed_ids = {clip["segment_id"] for clip in clips if clip["status"] == "succeeded"}
        for segment in project.storyboard.get("segments", []):
            if segment["segment_id"] in completed_ids:
                segment["status"] = "ready"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = f"Segment 生成失败｜{task.error}"
    finally:
        task.dump()
        P.recompute_project_status(project)
        project.dump()


async def _run_render_task(project: P.Project, task: P.RenderTask):
    try:
        project.status, project.progress, project.message = "composing", 90, "正在拼接画面并回铺 Master Audio"
        task.progress, task.message = 15, "校验 Segment 与音频版本"
        task.dump(), project.dump()
        version = int((project.render or {}).get("version", 0)) + 1
        result = await asyncio.to_thread(
            composer.compose_project, project, P.merge_segment_results(project), version)
        task.result = result
        task.status, task.progress, task.message = "completed", 100, "最终视频已生成"
        project.render = {"status": "completed", "version": version, "task_id": task.task_id}
        project.final_video = result
        project.status, project.progress, project.message = "completed", 100, "最终视频已生成"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = "最终合成失败"
        project.render = {**(project.render or {}), "status": "failed", "error": task.error}
        project.status, project.message = "video_ready", f"合成失败，可重试｜{task.error}"
    finally:
        task.dump(), project.dump()


async def _run_reference_search(project: P.Project):
    """创建项目后的第一阶段：联网搜图，等待用户确认，不提前生成 Plan。"""
    try:
        provider = model_client.load_image_search_config()
        project.status, project.progress, project.message = "searching_references", 2, "正在搜索景点实景图片"
        project.dump()
        candidates = []
        if provider:
            candidates = await asyncio.to_thread(
                reference_search.search_images,
                provider,
                project.request.get("city", ""),
                project.request.get("location", ""),
            )
        # 保留创建请求中用户主动附带的图片；同 URL 去重。
        candidates += [
            visual_rag.candidate_from_user_asset(
                asset, project.request.get("city", ""), project.request.get("location", ""))
            for asset in project.request.get("assets", []) if asset.get("url")
        ]
        unique, seen = [], set()
        for candidate in candidates:
            if candidate.get("image_url") and candidate["image_url"] not in seen:
                seen.add(candidate["image_url"])
                unique.append(candidate)
        if not unique:
            raise RuntimeError("没有搜索到图片候选，请检查百度千帆配置或换一个更具体的景点名称")
        project.reference_candidates = unique
        project.status, project.progress = "waiting_reference_confirm", 5
        project.message = f"找到 {len(unique)} 张候选图片，请确认真实景点图片"
    except Exception as e:
        project.status = "failed"
        project.message = f"搜索景点图片失败｜{type(e).__name__}: {e}"
    finally:
        project.dump()


async def _run_reference_analysis(project: P.Project, selected: list[dict]):
    """缓存用户确认图片 → 逐图 VLM → PlaceVisualProfile → 启动原 Plan 流程。"""
    provider = model_client.load_vlm_config()
    try:
        if not provider:
            raise RuntimeError("VLM provider 未配置")
        project.status, project.progress, project.message = "analyzing_references", 7, "正在理解实景参考图"
        project.dump()

        semaphore = asyncio.Semaphore(3)

        async def analyze_one(candidate):
            async with semaphore:
                try:
                    asset = await asyncio.to_thread(
                        visual_rag.cache_candidate,
                        project.project_id,
                        candidate,
                        project.request.get("city", ""),
                        project.request.get("location", ""),
                    )
                    asset["observation"] = await asyncio.to_thread(
                        vlm_client.analyze_image, provider, asset["local_path"])
                    asset["analysis_status"] = "completed"
                    return asset, None
                except Exception as exc:
                    return None, f"{type(exc).__name__}: {exc}"

        results = await asyncio.gather(*(analyze_one(candidate) for candidate in selected))
        assets, failures = [], []
        seen_assets = set()
        for candidate, (asset, error) in zip(selected, results):
            if asset and asset["asset_id"] not in seen_assets:
                seen_assets.add(asset["asset_id"])
                assets.append(asset)
            else:
                failures.append({"candidate_id": candidate.get("candidate_id"), "error": error})
        if not assets:
            raise RuntimeError("所有参考图均下载或分析失败")

        project.reference_assets = assets
        project.reference_version += 1
        project.visual_profile = visual_rag.build_visual_profile(
            project.request.get("city", ""), project.request.get("location", ""), assets)
        project.visual_profile["analysis_failures"] = failures
        project.visual_assets = visual_rag.public_visual_assets(project, kb.visual_assets(project.request))
        project.message = f"完成 {len(assets)}/{len(selected)} 张参考图分析，开始生成方案"
        project.dump()
    except Exception as e:
        project.status, project.progress = "waiting_reference_confirm", 5
        project.message = f"参考图分析失败，请重新选择｜{type(e).__name__}: {e}"
        project.dump()
        return

    await _run_plan(project)


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


# ---- 接口1：创建项目 / 搜索参考图 ----

@router.post("/projects", status_code=202)
async def create_project(req: GenerateRequest, user: str = Depends(get_current_user)):
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
    project = P.Project(pid, request, username=user)
    P.PROJECTS[pid] = project
    project.status, project.progress, project.message = "searching_references", 2, "正在搜索景点实景图片"
    project.dump()
    asyncio.create_task(_run_reference_search(project))
    return {"project_id": pid, "status": "searching_references", "progress": 2,
            "message": "正在搜索景点实景图片", "reference_candidates": []}


# ---- 接口1.1/1.2：查询候选 / 确认参考图 ----

@router.get("/projects/{pid}/references")
async def get_references(pid: str, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    return {
        "project_id": pid,
        "status": project.status,
        "progress": project.progress,
        "message": project.message,
        "request": project.request,
        "candidates": project.reference_candidates,
        "selected_assets": project.reference_assets,
        "visual_profile": project.visual_profile,
        "reference_version": project.reference_version,
    }


@router.post("/projects/{pid}/references/confirm", status_code=202)
async def confirm_references(pid: str, req: ConfirmReferencesRequest,
                             user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _state_guard(project, {"waiting_reference_confirm"}, "确认参考图")
    by_id = {candidate.get("candidate_id"): candidate for candidate in project.reference_candidates}
    ids = list(dict.fromkeys(req.reference_ids))
    unknown = [reference_id for reference_id in ids if reference_id not in by_id]
    if unknown:
        _err(400, "invalid_param", f"参考图不存在: {unknown}")
    selected = [by_id[reference_id] for reference_id in ids]
    project.status, project.progress, project.message = "analyzing_references", 7, "正在理解实景参考图"
    project.dump()
    asyncio.create_task(_run_reference_analysis(project, selected))
    return {
        "project_id": pid,
        "status": "analyzing_references",
        "progress": 7,
        "selected_reference_ids": ids,
    }


# ---- 接口2：修改/确认创作方案 ----

@router.put("/projects/{pid}/plan")
async def confirm_plan(pid: str, req: ConfirmPlanRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    recoverable_audio_failure = (project.status == "failed" and
                                 (project.audio or {}).get("status") == "failed")
    if project.status != "waiting_confirm" and not recoverable_audio_failure:
        _state_guard(project, {"waiting_confirm"}, "确认方案")
    cw = _parse_cw(req.copywriting)
    if not cw["paragraphs"]:
        # 兜底：用户编辑可能丢了【0-15s】时间戳标记，整段当一个段落（前端体验优先，不拒绝）
        cw = {"titles": cw["titles"], "hashtags": cw["hashtags"],
              "paragraphs": [{"idx": 1, "text": req.copywriting.strip(),
                              "duration_s": project.request.get("duration_s", 60)}]}
    # 发布素材保真：用户文本不含《》/# 时 _parse_cw 抓不到标题/标签，沿用确认前生成的（供成片发布展示）
    if cw["titles"] == ["无标题"] and project.copywriting.get("titles"):
        cw["titles"] = project.copywriting["titles"]
    if not cw["hashtags"] and project.copywriting.get("hashtags"):
        cw["hashtags"] = project.copywriting["hashtags"]
    project.copywriting = cw
    project.script = parse_script(cw)
    project.plan_version += 1
    project.plan_id = f"plan_{project.project_id}_v{project.plan_version}"
    project.storyboard = {}            # 文案变了，旧分镜失效
    project.video_tasks = []           # 旧视频结果作废
    project.audio = {"status": "none", "version": (project.audio or {}).get("version", 0)}
    project.audio_tasks = []
    project.segment_tasks = []
    project.render_tasks = []
    project.render = {"status": "none", "version": (project.render or {}).get("version", 0)}
    project.final_video = {"status": "none", "url": "", "preview_url": "",
                           "duration_s": 0,
                           "resolution": project.request.get("resolution", "1080p"),
                           "aspect_ratio": project.request.get("aspect_ratio", "9:16")}
    project.status, project.progress, project.message = "plan_confirmed", 15, "方案已确认"
    project.dump()
    return {"project_id": pid, "status": "plan_confirmed",
            "plan_id": project.plan_id, "progress": 15}


# ---- 接口3：生成视频脚本 + 分镜 ----

@router.post("/projects/{pid}/storyboard", status_code=202)
async def create_storyboard(pid: str, req: StoryboardRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    recoverable_storyboard_failure = (project.status == "failed" and
                                      (project.audio or {}).get("status") == "ready")
    if project.status != "audio_ready" and not recoverable_storyboard_failure:
        _state_guard(project, {"audio_ready"}, "生成分镜")
    if req.plan_id and req.plan_id != project.plan_id:
        _err(409, "invalid_state", f"plan_id 不匹配（当前 {project.plan_id}）")
    project.status, project.progress, project.message = "storyboarding", 20, "正在拆分分镜…"
    project.dump()
    asyncio.create_task(_run_storyboard(project))
    return {"project_id": pid, "status": "storyboarding", "progress": 20, "message": "正在拆分分镜…"}


# ---- 接口4：修改 Shot / Segment（修改后整个 Segment 失效） ----

@router.put("/projects/{pid}/shots/{shot_id}")
async def update_shot(pid: str, shot_id: int, patch: ShotPatch, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready", "completed"}, "修改分镜")
    shot = _find_shot(project, shot_id)
    segment = segment_planner.segment_for_shot(project.storyboard, shot_id)
    if segment:
        _guard_segments_available(project, [segment["segment_id"]])
    else:
        _guard_shots_available(project, [shot_id])
    upd = patch.model_dump(exclude_none=True)
    if "reference_asset_ids" in upd:
        ids = list(dict.fromkeys(upd["reference_asset_ids"]))
        if len(ids) > visual_rag.MAX_REFERENCES_PER_SHOT:
            _err(400, "invalid_param",
                 f"单个 Shot 最多绑定 {visual_rag.MAX_REFERENCES_PER_SHOT} 张参考图")
        valid_ids = {asset.get("asset_id") for asset in project.reference_assets
                     if asset.get("analysis_status") == "completed"}
        unknown = [asset_id for asset_id in ids if asset_id not in valid_ids]
        if unknown:
            _err(400, "invalid_param", f"参考图不存在或分析未完成: {unknown}")
        upd["reference_asset_ids"] = ids
    ok, errs, norm = v.validate_shot_patch(upd)
    if not ok:
        _err(400, "invalid_param", "；".join(errs[:4]))
    # 先校验修改后的 Segment 图片总数，避免 update 后才发现超限留下半成品。
    if segment and "reference_asset_ids" in norm:
        segment_refs = []
        for member_id in segment.get("shot_ids", []):
            refs = norm["reference_asset_ids"] if member_id == shot_id else _find_shot(project, member_id).get("reference_asset_ids", [])
            for asset_id in refs:
                if asset_id not in segment_refs:
                    segment_refs.append(asset_id)
        if len(segment_refs) > visual_rag.MAX_REFERENCES_PER_SEGMENT:
            _err(400, "invalid_param",
                 f"修改后 {segment['segment_id']} 共 {len(segment_refs)} 张参考图，超过 Segment 上限 {visual_rag.MAX_REFERENCES_PER_SEGMENT}")
    shot.update(norm)
    if "reference_asset_ids" in norm:
        shot["reference_roles"] = [
            {"asset_id": aid, "role": "identity_and_composition" if i == 0 else "detail"}
            for i, aid in enumerate(norm["reference_asset_ids"])
        ]
        shot["grounding_strength"] = "strong" if norm["reference_asset_ids"] else "none"
    if segment:
        segment = segment_planner.refresh_segment(project.storyboard, segment["segment_id"])
        segment["status"] = "stale"
        _invalidate_render(project)
        project.status, project.progress = "waiting_storyboard_confirm", 40
        project.message = f"{segment['segment_id']} 已修改，需要重新生成"
    project.dump()
    return {"project_id": pid, "shot_id": shot_id, "status": "updated", "shot": shot,
            "invalidated_segment_id": segment.get("segment_id") if segment else None}


@router.put("/projects/{pid}/segments/{segment_id}")
async def update_segment(pid: str, segment_id: str, patch: SegmentPatch,
                         user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready", "completed"}, "修改 Segment")
    segment = _find_segment(project, segment_id)
    _guard_segments_available(project, [segment_id])
    update = patch.model_dump(exclude_none=True)
    if "transition_note" in update:
        note = update["transition_note"].strip()
        if len(note) > 500:
            _err(400, "invalid_param", "transition_note 最多 500 字")
        segment["transition_note"] = note
    segment["status"] = "stale"
    _invalidate_render(project)
    project.status, project.progress = "waiting_storyboard_confirm", 40
    project.message = f"{segment_id} 已修改，需要重新生成"
    project.dump()
    return {"project_id": pid, "segment_id": segment_id, "status": "updated", "segment": segment}


# ---- 接口5：批量生成 Segment（旧 Storyboard 回退到 Shot） ----

@router.post("/projects/{pid}/generate", status_code=202)
async def generate_batch(pid: str, req: GenerateShotsRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready"}, "生成视频")
    if not req.generate_video:
        _err(400, "invalid_param", "generate_image 单独生成本版未实现（video-only）；请设 generate_video=true")
    segments = project.storyboard.get("segments", [])
    if segments:
        valid_segment_ids = {segment["segment_id"] for segment in segments}
        selected = list(dict.fromkeys(req.segments))
        if not selected and req.shots:
            # 兼容旧前端：选择 Shot 等价于选择其所属的完整 Segment。
            selected = list(dict.fromkeys(
                segment_planner.segment_for_shot(project.storyboard, shot_id)["segment_id"]
                for shot_id in req.shots
                if segment_planner.segment_for_shot(project.storyboard, shot_id)
            ))
        if not selected:
            selected = [segment["segment_id"] for segment in segments]
        unknown = [segment_id for segment_id in selected if segment_id not in valid_segment_ids]
        if unknown:
            _err(400, "invalid_param", f"segments 不存在: {unknown}，可用 {sorted(valid_segment_ids)}")
        _guard_segments_available(project, selected)
        ungrounded = [shot_id for segment_id in selected
                      for shot_id in _find_segment(project, segment_id).get("shot_ids", [])
                      if not _find_shot(project, shot_id).get("reference_asset_ids")]
        if project.visual_profile.get("reference_asset_ids") and ungrounded:
            _err(409, "invalid_state", f"以下 Shot 尚未绑定实景参考图: {sorted(set(ungrounded))}")

        tid = _new_id("st")
        snapshot = req.model_dump()
        snapshot.update({
            "segments": selected,
            "plan_version": project.plan_version,
            "storyboard_version": project.storyboard.get("storyboard_version", 2),
            "audio_version": project.audio.get("version"),
            "master_audio_sha256": project.audio.get("master_sha256"),
            "reference_version": project.reference_version,
        })
        task = P.SegmentTask(tid, pid, "batch", snapshot)
        task.init_segments([_find_segment(project, segment_id) for segment_id in selected])
        P.SEGMENT_TASKS[tid] = task
        project.segment_tasks.append(tid)
        project.status, project.progress, project.message = "generating", 45, "Segment 视频生成中"
        task.dump(), project.dump()
        asyncio.create_task(_run_segment_task(project, task, selected))
        return {"task_id": tid, "project_id": pid, "status": "generating", "progress": 0,
                "segments": task.segments}

    valid_ids = {sh["shot_id"] for sc in project.storyboard["scenes"] for sh in sc["shot_list"]}
    unknown = [s for s in req.shots if s not in valid_ids]
    if unknown:
        _err(400, "invalid_param", f"shots 不存在: {unknown}，可用镜头 {sorted(valid_ids)}")
    _guard_shots_available(project, list(req.shots))
    ungrounded = [shot_id for shot_id in req.shots
                  if not _find_shot(project, shot_id).get("reference_asset_ids")]
    if project.visual_profile.get("reference_asset_ids") and ungrounded:
        _err(409, "invalid_state", f"以下 Shot 尚未绑定实景参考图: {ungrounded}")

    tid = _new_id("vt")
    snapshot = req.model_dump()
    snapshot["reference_version"] = project.reference_version
    vt = P.VideoTask(tid, pid, "batch", snapshot)
    P.VIDEO_TASKS[tid] = vt
    project.video_tasks.append(tid)
    project.status, project.progress, project.message = "generating", 40, "视频生成中"
    project.dump()
    asyncio.create_task(_run_video_task(project, vt, list(req.shots)))
    return {"task_id": tid, "project_id": pid, "status": "generating", "progress": 0,
            "shots": [{"shot_id": s, "status": "pending"} for s in req.shots]}


# ---- 接口6：查询生成任务 ----

@router.get("/tasks/{task_id}")
async def get_video_task(task_id: str, user: str = Depends(get_current_user)):
    task = _get_task(task_id)
    _owned_project(task.project_id, user)   # 任务归属项目，沿用项目归属校验
    return task.to_dict()


# ---- §十五：Shot 级重新生成 ----

@router.post("/projects/{pid}/shots/{shot_id}/regenerate", status_code=202)
async def regenerate_shot(pid: str, shot_id: int, req: RegenerateShotRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready", "completed"}, "重新生成")
    shot = _find_shot(project, shot_id)
    segment = segment_planner.segment_for_shot(project.storyboard, shot_id)
    if segment:
        _guard_segments_available(project, [segment["segment_id"]])
    else:
        _guard_shots_available(project, [shot_id])
    if req.prompt and req.prompt.strip() and req.prompt.strip() != shot.get("prompt"):
        shot["prompt"] = req.prompt.strip()   # prompt 变化先写回分镜，新任务自然覆盖旧结果
        if segment:
            segment["status"] = "stale"
        project.dump()
    if segment:
        segment_id = segment["segment_id"]
        segment["status"] = "stale"
        _invalidate_render(project)
        tid = _new_id("st")
        snapshot = {"segments": [segment_id], "regenerate": req.model_dump(),
                    "audio_version": project.audio.get("version"),
                    "master_audio_sha256": project.audio.get("master_sha256"),
                    "reference_version": project.reference_version}
        task = P.SegmentTask(tid, pid, "single", snapshot)
        task.init_segments([segment])
        P.SEGMENT_TASKS[tid] = task
        project.segment_tasks.append(tid)
        project.status, project.progress = "generating", 45
        project.message = f"重新生成 {segment_id}（包含 Shot {segment.get('shot_ids', [])}）"
        task.dump(), project.dump()
        asyncio.create_task(_run_segment_task(project, task, [segment_id]))
        return {"task_id": tid, "shot_id": shot_id, "segment_id": segment_id,
                "status": "generating", "regeneration_unit": "segment"}
    tid = _new_id("vt")
    snapshot = {"shot_ids": [shot_id], "generate_image": False, "generate_video": True,
                "regenerate": req.model_dump(), "reference_version": project.reference_version}
    vt = P.VideoTask(tid, pid, "single", snapshot)
    P.VIDEO_TASKS[tid] = vt
    project.video_tasks.append(tid)
    project.status, project.progress = "generating", 40
    project.message = f"重新生成 Shot {shot_id}"
    project.dump()
    asyncio.create_task(_run_video_task(project, vt, [shot_id]))
    return {"task_id": tid, "shot_id": shot_id, "status": "generating"}


@router.post("/projects/{pid}/segments/{segment_id}/regenerate", status_code=202)
async def regenerate_segment(pid: str, segment_id: str, req: RegenerateSegmentRequest,
                             user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready", "completed"}, "重新生成")
    segment = _find_segment(project, segment_id)
    _guard_segments_available(project, [segment_id])
    if req.transition_note is not None:
        note = req.transition_note.strip()
        if len(note) > 500:
            _err(400, "invalid_param", "transition_note 最多 500 字")
        segment["transition_note"] = note
    segment["status"] = "stale"
    _invalidate_render(project)
    tid = _new_id("st")
    snapshot = {"segments": [segment_id], "regenerate": req.model_dump(),
                "audio_version": project.audio.get("version"),
                "master_audio_sha256": project.audio.get("master_sha256"),
                "reference_version": project.reference_version}
    task = P.SegmentTask(tid, pid, "single", snapshot)
    task.init_segments([segment])
    P.SEGMENT_TASKS[tid] = task
    project.segment_tasks.append(tid)
    project.status, project.progress, project.message = "generating", 45, f"重新生成 {segment_id}"
    task.dump(), project.dump()
    asyncio.create_task(_run_segment_task(project, task, [segment_id]))
    return {"task_id": tid, "project_id": pid, "segment_id": segment_id, "status": "generating"}


# ---- 接口7/8/9：母带、最终合成、成片查询 ----

@router.post("/projects/{pid}/audio", status_code=202)
async def create_audio(pid: str, req: AudioRequest | None = None,
                       user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _state_guard(project, {"plan_confirmed", "audio_ready", "failed"}, "生成 Master Audio")
    if any((task := P.load_audio_task(task_id)) is not None and task.status == "generating"
           for task_id in project.audio_tasks):
        _err(409, "audio_generating", "Master Audio 正在生成，请勿重复提交")
    request = (req or AudioRequest()).model_dump()
    tid = _new_id("at")
    task = P.AudioTask(tid, pid, request)
    P.AUDIO_TASKS[tid] = task
    project.audio_tasks.append(tid)
    # 母带改变后所有时间轴与视频都要重建。
    project.storyboard = {}
    project.segment_tasks = []
    project.render_tasks = []
    project.render = {"status": "none", "version": (project.render or {}).get("version", 0)}
    project.final_video = {"status": "none", "url": "", "preview_url": "", "duration_s": 0,
                           "resolution": project.request.get("resolution", "1080p"),
                           "aspect_ratio": project.request.get("aspect_ratio", "9:16")}
    project.status, project.progress, project.message = "audio_generating", 15, "正在生成完整旁白与背景音乐"
    task.dump(), project.dump()
    asyncio.create_task(_run_audio_task(project, task))
    return {"task_id": tid, "project_id": pid, "status": "generating", "progress": 0}


@router.post("/projects/{pid}/render", status_code=202)
async def create_render(pid: str, req: RenderRequest | None = None,
                        user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _state_guard(project, {"video_ready", "completed"}, "合成最终视频")
    if any((task := P.load_render_task(task_id)) is not None and task.status == "rendering"
           for task_id in project.render_tasks):
        _err(409, "rendering", "最终视频正在合成，请勿重复提交")
    all_ids = [segment["segment_id"] for segment in project.storyboard.get("segments", [])]
    requested = list(dict.fromkeys((req or RenderRequest()).segment_ids))
    if requested and requested != all_ids:
        _err(400, "invalid_param", "最终成片必须按时间轴包含全部 Segment")
    results = P.merge_segment_results(project)
    missing = [segment_id for segment_id in all_ids
               if results.get(segment_id, {}).get("status") != "completed"]
    if missing:
        _err(409, "invalid_state", f"以下 Segment 尚未生成或已失效: {missing}")
    request = (req or RenderRequest()).model_dump()
    request["segment_ids"] = all_ids
    request["audio_version"] = project.audio.get("version")
    request["master_audio_sha256"] = project.audio.get("master_sha256")
    tid = _new_id("rt")
    task = P.RenderTask(tid, pid, request)
    P.RENDER_TASKS[tid] = task
    project.render_tasks.append(tid)
    project.render = {"status": "rendering", "version": (project.render or {}).get("version", 0),
                      "task_id": tid}
    project.status, project.progress, project.message = "composing", 90, "正在拼接画面并回铺 Master Audio"
    task.dump(), project.dump()
    asyncio.create_task(_run_render_task(project, task))
    return {"task_id": tid, "project_id": pid, "status": "rendering", "progress": 0}


@router.get("/projects/{pid}/render/status")
async def render_status(pid: str, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    task = P.load_render_task(project.render_tasks[-1]) if project.render_tasks else None
    return {"task_id": task.task_id if task else None,
            "status": task.status if task else project.render.get("status", "none"),
            "progress": task.progress if task else 0,
            "message": task.message if task else "",
            "video": project.final_video}


# ---- 补充端点：项目列表（历史记录 / 我的创作，仅返回当前用户的） ----

@router.get("/projects")
async def list_projects(user: str = Depends(get_current_user)):
    items = []
    for p in P.list_projects():
        if p.username != user:
            continue
        segment_clips = P.merge_segment_results(p)
        clips = P.merge_video_results(p)
        cover = next((c["video_url"] for c in segment_clips.values()
                      if c.get("status") == "completed" and c.get("video_url")), None)
        if not cover:
            cover = next((c["video_url"] for c in clips.values()
                          if c.get("status") == "completed" and c.get("video_url")), None)
        if not cover:
            assets = ((p.visual_assets or {}).get("ref_images") or
                      (p.visual_assets or {}).get("kb_images") or [])
            cover = assets[0].get("url") if assets else None
        items.append({
            "project_id": p.project_id,
            "theme": p.request.get("theme", ""),
            "scene_type": p.request.get("scene_type", ""),
            "status": p.status,
            "progress": p.progress,
            "duration_s": p.request.get("duration_s", 0),
            "shot_count": sum(len(segment.get("shot_ids", []))
                              for segment in p.storyboard.get("segments", [])) or len(clips),
            "segment_count": len(p.storyboard.get("segments", [])),
            "cover_url": cover,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })
    return {"projects": items}


# ---- 补充端点：查询项目全量（分阶段轮询入口，V1 文档未列但流程必需） ----

@router.get("/projects/{pid}")
async def get_project(pid: str, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
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
