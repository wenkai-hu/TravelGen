# -*- coding: utf-8 -*-
"""Project 化分阶段接口：Storyboard → 音色/BGM → Seedance Segment → 双版本 Render。

- 新旧共存：本 router 提供 /api/ 前缀的 V1 接口，旧 /api/v1/* 在 app.py 原样保留
- 分阶段：创建项目 → 搜图 → 方案确认 → 分镜/动态分段 → 音色/BGM → Segment → 双版本成片
- Shot 是 Segment 内可编辑的画面指令；实际生成和重生成的最小单位始终是 Segment
"""
import asyncio, copy, uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from pipeline import (ark_client, composer, kb, media_catalog, model_client, reference_search,
                      segment_planner, visual_rag, vlm_client, voice_sample_pipeline)
from pipeline import validate as v
from pipeline.demo import parse_script
from pipeline.pipeline import PipelineRunner, _parse_cw
from schemas import (ConfirmPlanRequest, ConfirmReferencesRequest,
                     GenerateRequest, GenerateSegmentsRequest, RegenerateSegmentRequest,
                     RegenerateShotRequest, RenderRequest, SegmentPatch, ShotPatch, StoryboardRequest,
                     VoiceCandidateRequest, VoiceSelectionRequest, MusicSelectionRequest,
                     RenderMixRequest)
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


async def _run_voice_task(project: P.Project, task: P.VoiceTask):
    try:
        task.progress, task.message = 5, "正在生成自定义音色试听样本"
        task.dump()
        description = task.request["description"]
        if runner.seedance is None:
            result = await asyncio.to_thread(
                voice_sample_pipeline.mock_candidate, project.project_id, task.task_id, description)
        else:
            prompt = voice_sample_pipeline.build_prompt(description)
            seedance_id, error = await asyncio.to_thread(
                ark_client.submit, runner.seedance, prompt, 5, "480p", "9:16",
                images=None, audio=None, generate_audio=True,
            )
            if not seedance_id:
                raise RuntimeError(error or "Seedance 自定义音色提交失败")
            task.result = {"seedance_task_id": seedance_id}
            task.progress, task.message = 15, "Seedance 正在生成音色样本"
            task.dump()
            video_url = None
            for _ in range(240):
                status, url, poll_error = await asyncio.to_thread(
                    ark_client.get_task, runner.seedance, seedance_id)
                if status == "succeeded":
                    video_url = url
                    break
                if status in {"failed", "expired", "cancelled"}:
                    raise RuntimeError(poll_error or f"Seedance 音色任务 {status}")
                await asyncio.sleep(5)
            if not video_url:
                raise TimeoutError("Seedance 音色任务等待超过20分钟")
            raw_path, _ = voice_sample_pipeline.paths(project.project_id, task.task_id)
            await asyncio.to_thread(ark_client.download, video_url, str(raw_path))
            result = await asyncio.to_thread(
                voice_sample_pipeline.finalize, project.project_id, task.task_id, raw_path)
        task.result = result
        task.status, task.progress, task.message = "completed", 100, "自定义音色候选已生成，请试听确认"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = "自定义音色生成失败"
    finally:
        task.dump()


async def _run_storyboard(project: P.Project):
    try:
        await runner.generate_storyboard(project)
        errors = segment_planner.validate_segment_plan(
            project.storyboard, int(project.request.get("duration_s", 0)) * 1000)
        if errors:
            raise ValueError("Segment 规划校验失败：" + "；".join(errors[:6]))
        project.visual_assets = visual_rag.public_visual_assets(project, kb.visual_assets(project.request))
        music_status = ((project.music or {}).get("status")
                        if (project.music or {}).get("status") in {"selected", "explicit_none"}
                        else "waiting_select")
        project.music = {**(project.music or {}), "status": music_status,
                         "recommendation_status": "none", "recommendation": None}
        project.status, project.progress, project.message = "waiting_storyboard_confirm", 40, "分镜待确认（可修改 Shot）"
        project.dump()
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
        completed_ids = {
            clip["segment_id"] for clip in clips
            if clip["status"] == "succeeded"
            and clip.get("voice_reference_sha256") == project.voice.get("reference_sha256")
            and clip.get("voice_version") == project.voice.get("version")
        }
        for segment in project.storyboard.get("segments", []):
            if segment["segment_id"] in completed_ids:
                segment["status"] = "ready"
            elif segment["segment_id"] in segment_ids and segment.get("status") == "ready":
                segment["status"] = "stale"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = f"Segment 生成失败｜{task.error}"
    finally:
        task.dump()
        P.recompute_project_status(project)
        project.dump()


async def _run_render_task(project: P.Project, task: P.RenderTask):
    try:
        project.status, project.progress, project.message = "composing", 90, "正在拼接原生音视频并生成双版本成片"
        task.progress, task.message = 15, "校验 Segment 与音色版本"
        task.dump(), project.dump()
        if (task.request.get("voice_version") != project.voice.get("version")
                or task.request.get("voice_reference_sha256") != project.voice.get("reference_sha256")
                or task.request.get("music_version") != project.music.get("version")):
            raise RuntimeError("合成所用的音色或 BGM 已变化，本次任务已失效")
        version = int((project.render or {}).get("version", 0)) + 1
        result = await asyncio.to_thread(
            composer.compose_project, project, P.merge_segment_results(project), version)
        if (task.request.get("voice_version") != project.voice.get("version")
                or task.request.get("voice_reference_sha256") != project.voice.get("reference_sha256")
                or task.request.get("music_version") != project.music.get("version")):
            raise RuntimeError("合成过程中音色或 BGM 已变化，请重新合成")
        task.result = result
        task.status, task.progress, task.message = "completed", 100, "最终视频已生成"
        project.render = {"status": "completed", "version": version, "task_id": task.task_id}
        project.final_video = result
        project.status, project.progress, project.message = "completed", 100, "最终视频已生成"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = "最终合成失败"
        project.render = {**(project.render or {}), "status": "failed", "error": task.error}
        project.final_video = {**(project.final_video or {}), "status": "none"}
        P.recompute_project_status(project)
        project.message = f"合成失败，可重试｜{task.error}"
    finally:
        task.dump(), project.dump()


async def _run_mix_task(project: P.Project, task: P.RenderTask):
    try:
        snapshot = task.request
        result = await asyncio.to_thread(
            composer.remix_render, copy.deepcopy(project.final_video),
            snapshot["video_gain_db"], snapshot["bgm_gain_db"], snapshot["mix_version"])
        if (project.final_video.get("version") != snapshot["render_version"]
                or project.music.get("version") != snapshot["music_version"]
                or project.render.get("status") != "completed"):
            raise RuntimeError("成片或 BGM 已变化，本次混音已失效")
        project.final_video = result
        task.result = result
        task.status, task.progress, task.message = "completed", 100, "混音已更新"
    except Exception as exc:
        task.status, task.error = "failed", f"{type(exc).__name__}: {exc}"
        task.message = "混音失败，原成片仍可使用"
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
            # 逐图原因必须带出来，否则只剩一句"都失败了"，无从排查
            detail = "；".join(
                f"{f['candidate_id']}: {f['error']}" for f in failures[:3])
            raise RuntimeError(f"所有参考图均下载或分析失败（{detail}）")

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
    if project.status != "waiting_confirm":
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
    project.segment_tasks = []
    project.music = {"status": "none", "version": (project.music or {}).get("version", 0),
                     "recommendation_status": "none", "recommendation": None}
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


# ---- 接口3：生成视频脚本 + Shot，并按时长动态装入 Segment ----

@router.post("/projects/{pid}/storyboard", status_code=202)
async def create_storyboard(pid: str, req: StoryboardRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    recoverable_storyboard_failure = project.status == "failed" and bool(project.copywriting)
    if project.status != "plan_confirmed" and not recoverable_storyboard_failure:
        _state_guard(project, {"plan_confirmed"}, "生成分镜")
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
    if segment is None:
        _err(409, "invalid_state", "该 Shot 不属于动态 Segment，请重新生成分镜")
    if patch.duration_s is not None and P.active_segment_ids(project):
        _err(409, "segment_generating", "修改 Shot 时长前请等待当前 Segment 生成完成")
    if patch.duration_s is None:
        _guard_segments_available(project, [segment["segment_id"]])
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
    invalidated_ids = []
    if "duration_s" in norm:
        candidate = copy.deepcopy(project.storyboard)
        candidate_shot = next(item for item in segment_planner.flatten_shots(candidate)
                              if item.get("shot_id") == shot_id)
        candidate_shot.update(norm)
        if "reference_asset_ids" in norm:
            candidate_shot["reference_roles"] = [
                {"asset_id": aid, "role": "identity_and_composition" if i == 0 else "detail"}
                for i, aid in enumerate(norm["reference_asset_ids"])
            ]
            candidate_shot["grounding_strength"] = "strong" if norm["reference_asset_ids"] else "none"
        total_duration = sum(int(item.get("duration_s", 0))
                             for item in segment_planner.flatten_shots(candidate))
        if not 15 <= total_duration <= 120:
            _err(400, "invalid_param", "修改后全片总时长需保持在 15–120 秒")
        try:
            project.storyboard = segment_planner.attach_segment_plan(candidate)
        except ValueError as exc:
            _err(400, "invalid_param", str(exc))
        project.request["duration_s"] = total_duration
        shot = _find_shot(project, shot_id)
        for item in project.storyboard.get("segments", []):
            item["status"] = "stale" if project.segment_tasks else "pending"
            invalidated_ids.append(item["segment_id"])
        _invalidate_render(project)
        project.status, project.progress = "waiting_storyboard_confirm", 40
        project.message = "Shot 时长已修改，全部 Segment 已重新动态分组"
        segment = segment_planner.segment_for_shot(project.storyboard, shot_id)
    else:
        shot.update(norm)
        if "reference_asset_ids" in norm:
            shot["reference_roles"] = [
                {"asset_id": aid, "role": "identity_and_composition" if i == 0 else "detail"}
                for i, aid in enumerate(norm["reference_asset_ids"])
            ]
            shot["grounding_strength"] = "strong" if norm["reference_asset_ids"] else "none"
        segment = segment_planner.refresh_segment(project.storyboard, segment["segment_id"])
        segment["status"] = "stale"
        invalidated_ids = [segment["segment_id"]]
        _invalidate_render(project)
        project.status, project.progress = "waiting_storyboard_confirm", 40
        project.message = f"{segment['segment_id']} 已修改，需要重新生成"
    project.dump()
    return {"project_id": pid, "shot_id": shot_id, "status": "updated", "shot": shot,
            "invalidated_segment_id": segment.get("segment_id") if segment else None,
            "invalidated_segment_ids": invalidated_ids}


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


# ---- 接口5：批量生成 Segment ----

@router.post("/projects/{pid}/generate", status_code=202)
async def generate_batch(pid: str, req: GenerateSegmentsRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready"}, "生成视频")
    if not req.generate_video:
        _err(400, "invalid_param", "generate_image 单独生成本版未实现（video-only）；请设 generate_video=true")
    if (project.voice or {}).get("status") != "selected":
        _err(409, "voice_required", "请先选择并确认参考音色")
    if (project.music or {}).get("status") not in {"selected", "explicit_none"}:
        _err(409, "music_required", "请先选择 BGM，或明确选择无 BGM")
    segments = project.storyboard.get("segments", [])
    if not segments:
        _err(409, "invalid_state", "Storyboard 尚未生成动态 Segment，请重新生成分镜")
    valid_segment_ids = {segment["segment_id"] for segment in segments}
    selected = list(dict.fromkeys(req.segments)) or [segment["segment_id"] for segment in segments]
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
        "storyboard_version": project.storyboard.get("storyboard_version", 3),
        "voice_version": project.voice.get("version"),
        "voice_reference_sha256": project.voice.get("reference_sha256"),
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


# ---- 接口6：查询生成任务 ----

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, user: str = Depends(get_current_user)):
    task = _get_task(task_id)
    _owned_project(task.project_id, user)   # 任务归属项目，沿用项目归属校验
    data = task.to_dict()
    if data.get("kind") == "voice_candidate":
        data["result"] = {
            key: value for key, value in data.get("result", {}).items()
            if key not in {"reference_path", "local_path", "raw_video_path"}
        }
    if "segments" in data:
        private_fields = {"raw_path", "normalized_av_path", "native_audio_path"}
        data["segments"] = [
            {key: value for key, value in segment.items() if key not in private_fields}
            for segment in data["segments"]
        ]
    if data.get("kind") in {"render", "mix"}:
        data["result"] = dict(data.get("result") or {})
        for variant in ("clean", "with_bgm", "bgm_bed"):
            if data.get("result", {}).get(variant):
                data["result"][variant] = {
                    key: value for key, value in data["result"][variant].items()
                    if key != "local_path"
                }
    return data


# ---- §十五：Shot 级重新生成 ----

@router.post("/projects/{pid}/shots/{shot_id}/regenerate", status_code=202)
async def regenerate_shot(pid: str, shot_id: int, req: RegenerateShotRequest, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready", "completed"}, "重新生成")
    if (project.voice or {}).get("status") != "selected":
        _err(409, "voice_required", "请先选择并确认参考音色")
    shot = _find_shot(project, shot_id)
    segment = segment_planner.segment_for_shot(project.storyboard, shot_id)
    if segment is None:
        _err(409, "invalid_state", "该 Shot 不属于动态 Segment，请重新生成分镜")
    _guard_segments_available(project, [segment["segment_id"]])
    if req.prompt and req.prompt.strip() and req.prompt.strip() != shot.get("prompt"):
        shot["prompt"] = req.prompt.strip()   # prompt 变化先写回分镜，新任务自然覆盖旧结果
        segment["status"] = "stale"
        project.dump()
    segment_id = segment["segment_id"]
    segment["status"] = "stale"
    _invalidate_render(project)
    tid = _new_id("st")
    snapshot = {"segments": [segment_id], "regenerate": req.model_dump(),
                "voice_version": project.voice.get("version"),
                "voice_reference_sha256": project.voice.get("reference_sha256"),
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


@router.post("/projects/{pid}/segments/{segment_id}/regenerate", status_code=202)
async def regenerate_segment(pid: str, segment_id: str, req: RegenerateSegmentRequest,
                             user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    _state_guard(project, {"waiting_storyboard_confirm", "generating", "video_ready", "completed"}, "重新生成")
    if (project.voice or {}).get("status") != "selected":
        _err(409, "voice_required", "请先选择并确认参考音色")
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
                "voice_version": project.voice.get("version"),
                "voice_reference_sha256": project.voice.get("reference_sha256"),
                "reference_version": project.reference_version}
    task = P.SegmentTask(tid, pid, "single", snapshot)
    task.init_segments([segment])
    P.SEGMENT_TASKS[tid] = task
    project.segment_tasks.append(tid)
    project.status, project.progress, project.message = "generating", 45, f"重新生成 {segment_id}"
    task.dump(), project.dump()
    asyncio.create_task(_run_segment_task(project, task, [segment_id]))
    return {"task_id": tid, "project_id": pid, "segment_id": segment_id, "status": "generating"}


# ---- 音色与 BGM 素材、候选生成和项目选择 ----

@router.get("/voice-presets")
async def get_voice_presets(user: str = Depends(get_current_user)):
    return {"voices": [{key: value for key, value in item.items() if key != "local_path"}
                       for item in media_catalog.voice_presets()]}


@router.get("/bgm")
async def get_bgm_catalog(user: str = Depends(get_current_user)):
    return {"tracks": [{key: value for key, value in item.items() if key != "local_path"}
                       for item in media_catalog.bgm_catalog()]}


@router.post("/projects/{pid}/voice-candidates", status_code=202)
async def create_voice_candidate(pid: str, req: VoiceCandidateRequest,
                                 user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    if any((task := P.load_voice_task(task_id)) is not None and task.status == "generating"
           for task_id in project.voice_tasks):
        _err(409, "voice_generating", "已有自定义音色正在生成，请先等待完成")
    tid = _new_id("voice")
    task = P.VoiceTask(tid, pid, req.model_dump())
    P.VOICE_TASKS[tid] = task
    project.voice_tasks.append(tid)
    task.dump(), project.dump()
    asyncio.create_task(_run_voice_task(project, task))
    return {"task_id": tid, "project_id": pid, "status": "generating", "progress": 0}


@router.put("/projects/{pid}/voice")
async def select_voice(pid: str, req: VoiceSelectionRequest,
                       user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    if bool(req.voice_id) == bool(req.candidate_task_id):
        _err(400, "invalid_param", "voice_id 与 candidate_task_id 必须且只能提供一个")
    if req.voice_id:
        selected = media_catalog.find_voice(req.voice_id)
        if not selected:
            _err(404, "voice_not_found", f"预设音色 {req.voice_id} 不存在")
        voice = {
            "source": "preset", "voice_id": selected["voice_id"], "name": selected["name"],
            "description": selected["description"], "reference_path": selected["local_path"],
            "preview_url": selected["preview_url"], "reference_sha256": selected["sha256"],
        }
    else:
        task = P.load_voice_task(req.candidate_task_id)
        if task is None or task.project_id != pid:
            _err(404, "voice_not_found", "自定义音色候选不存在")
        if task.status != "completed" or task.result.get("status") != "candidate_ready":
            _err(409, "voice_not_ready", "自定义音色候选尚未生成完成")
        voice = dict(task.result)
        voice.pop("status", None)
    version = int((project.voice or {}).get("version", 0)) + 1
    project.voice = {"status": "selected", "version": version, **voice}
    for segment in project.storyboard.get("segments", []):
        if project.segment_tasks:
            segment["status"] = "stale"
    _invalidate_render(project)
    if project.storyboard.get("segments"):
        project.status, project.progress, project.message = (
            "waiting_storyboard_confirm", 40, "参考音色已确认，可生成或重新生成 Segment")
    project.dump()
    return {"project_id": pid, "voice": {
        key: value for key, value in project.voice.items()
        if key not in {"reference_path", "local_path", "raw_video_path"}
    }}


async def _run_bgm_recommendations(project: P.Project, plan_version: int,
                                   storyboard_version: int | None):
    try:
        recommendation = await asyncio.to_thread(media_catalog.recommend_bgm, project, runner.kimi)
        if (project.plan_version != plan_version
                or project.storyboard.get("storyboard_version") != storyboard_version):
            return
        selection_status = ((project.music or {}).get("status")
                            if (project.music or {}).get("status") in {"selected", "explicit_none"}
                            else "waiting_select")
        project.music = {**(project.music or {}), "status": selection_status,
                         "recommendation_status": "ready", "recommendation": recommendation,
                         "warning": None}
    except Exception as exc:
        if (project.plan_version != plan_version
                or project.storyboard.get("storyboard_version") != storyboard_version):
            return
        selection_status = ((project.music or {}).get("status")
                            if (project.music or {}).get("status") in {"selected", "explicit_none"}
                            else "waiting_select")
        project.music = {**(project.music or {}), "status": selection_status,
                         "recommendation_status": "failed", "recommendation": None,
                         "warning": f"KIMI 选曲建议不可用：{exc}"}
    finally:
        project.dump()


@router.post("/projects/{pid}/bgm/recommendations", status_code=202)
async def refresh_bgm_recommendations(pid: str, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _require_storyboard(project)
    project.music = {**(project.music or {}), "recommendation_status": "recommending",
                     "recommendation": None, "warning": None}
    project.dump()
    asyncio.create_task(_run_bgm_recommendations(
        project, project.plan_version, project.storyboard.get("storyboard_version")))
    return {"project_id": pid, "status": "recommending"}


@router.put("/projects/{pid}/bgm")
async def select_bgm(pid: str, req: MusicSelectionRequest,
                     user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    if req.explicit_none and req.bgm_id:
        _err(400, "invalid_param", "选择无 BGM 时不能同时提供 bgm_id")
    if not req.explicit_none and not req.bgm_id:
        _err(400, "invalid_param", "请选择 bgm_id，或明确设置 explicit_none=true")
    version = int((project.music or {}).get("version", 0)) + 1
    recommendation = (project.music or {}).get("recommendation")
    recommendation_status = (project.music or {}).get("recommendation_status", "none")
    recommendation_warning = (project.music or {}).get("warning")
    if req.explicit_none:
        project.music = {"status": "explicit_none", "version": version,
                         "recommendation_status": recommendation_status,
                         "recommendation": recommendation,
                         "warning": recommendation_warning,
                         "selected": None}
    else:
        selected = media_catalog.find_bgm(req.bgm_id)
        if not selected:
            _err(404, "bgm_not_found", f"BGM {req.bgm_id} 不存在")
        project.music = {"status": "selected", "version": version,
                         "recommendation_status": recommendation_status,
                         "recommendation": recommendation,
                         "warning": recommendation_warning,
                         "selected": selected}
    _invalidate_render(project)
    P.recompute_project_status(project)
    project.dump()
    public_music = dict(project.music)
    if public_music.get("selected"):
        public_music["selected"] = {key: value for key, value in public_music["selected"].items()
                                      if key != "local_path"}
    return {"project_id": pid, "music": public_music}


# ---- 最终合成与成片查询 ----


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
    if (project.voice or {}).get("status") != "selected":
        _err(409, "voice_required", "参考音色未确认")
    if (project.music or {}).get("status") not in {"selected", "explicit_none"}:
        _err(409, "music_required", "请先选择 BGM，或明确选择无 BGM")
    request = (req or RenderRequest()).model_dump()
    request["segment_ids"] = all_ids
    request["voice_version"] = project.voice.get("version")
    request["voice_reference_sha256"] = project.voice.get("reference_sha256")
    request["music_version"] = project.music.get("version")
    tid = _new_id("rt")
    task = P.RenderTask(tid, pid, request)
    P.RENDER_TASKS[tid] = task
    project.render_tasks.append(tid)
    project.render = {"status": "rendering", "version": (project.render or {}).get("version", 0),
                      "task_id": tid}
    project.status, project.progress, project.message = "composing", 90, "正在拼接 Seedance 原生音视频并混合所选 BGM"
    task.dump(), project.dump()
    asyncio.create_task(_run_render_task(project, task))
    return {"task_id": tid, "project_id": pid, "status": "rendering", "progress": 0}


@router.post("/projects/{pid}/render/mix", status_code=202)
async def mix_render(pid: str, req: RenderMixRequest,
                     user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    _state_guard(project, {"completed"}, "调整成片音量")
    if not project.final_video.get("bgm_bed") or not project.final_video.get("clean"):
        _err(409, "mix_tracks_unavailable", "当前成片没有独立 BGM 声轨，请重新合成最终视频")
    if any((task := P.load_render_task(task_id)) is not None and task.status == "rendering"
           for task_id in project.render_tasks):
        _err(409, "rendering", "已有混音任务正在进行")
    tid = _new_id("rt")
    task = P.RenderTask(tid, pid, {
        **req.model_dump(), "mix_version": int(project.final_video.get("mix_version", 0)) + 1,
        "render_version": project.final_video.get("version"),
        "music_version": project.music.get("version"),
    })
    task.kind = "mix"
    P.RENDER_TASKS[tid] = task
    project.render_tasks.append(tid)
    task.dump(), project.dump()
    asyncio.create_task(_run_mix_task(project, task))
    return {"task_id": tid, "project_id": pid, "status": "rendering"}


@router.get("/projects/{pid}/render/status")
async def render_status(pid: str, user: str = Depends(get_current_user)):
    project = _owned_project(pid, user)
    task = P.load_render_task(project.render_tasks[-1]) if project.render_tasks else None
    return {"task_id": task.task_id if task else None,
            "status": task.status if task else project.render.get("status", "none"),
            "progress": task.progress if task else 0,
            "message": task.message if task else "",
            "video": project.to_dict().get("final_video", {})}


# ---- 补充端点：项目列表（历史记录 / 我的创作，仅返回当前用户的） ----

@router.get("/projects")
async def list_projects(user: str = Depends(get_current_user)):
    items = []
    for p in P.list_projects():
        if p.username != user:
            continue
        segment_clips = P.merge_segment_results(p)
        cover = next((c["video_url"] for c in segment_clips.values()
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
                              for segment in p.storyboard.get("segments", [])),
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
