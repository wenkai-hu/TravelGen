# -*- coding: utf-8 -*-
"""Project 流程的模型与追加式任务存储。

- Project：一次创作任务的主实体（方案 → 分镜 → 音色/BGM选择 → Segment → 双版本成片），
  应用启动后写入 MySQL；独立管线测试保留 JSON 文件存储。
- VoiceTask/SegmentTask/RenderTask：新管线的三个可轮询任务。
- Project 与各类任务 GET 时从对应目录懒加载；聚合结果不单独落盘，始终由追加式任务重算，最新任务胜出。
"""
import json, os
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RESULTS_DIR = os.path.join(REPO, "experiments", "results", "05_pipeline")
PROJECTS_DIR = os.path.join(RESULTS_DIR, "projects")
VOICE_TASKS_DIR = os.path.join(RESULTS_DIR, "voice_tasks")
SEGMENT_TASKS_DIR = os.path.join(RESULTS_DIR, "segment_tasks")
RENDER_TASKS_DIR = os.path.join(RESULTS_DIR, "render_tasks")

PROJECTS: dict[str, "Project"] = {}
VOICE_TASKS: dict[str, "VoiceTask"] = {}
SEGMENT_TASKS: dict[str, "SegmentTask"] = {}
RENDER_TASKS: dict[str, "RenderTask"] = {}
STORAGE = None  # Set at app startup; standalone pipeline tests retain file storage.


def configure_storage(storage):
    global STORAGE
    STORAGE = storage
    for cache in (PROJECTS, VOICE_TASKS, SEGMENT_TASKS, RENDER_TASKS):
        cache.clear()


def _now():
    return datetime.now(timezone.utc).isoformat()


class Project:
    """一次创作任务。status 状态机见 docs/API_Contract_MVP.md V1 章节。"""

    def __init__(self, project_id: str, request: dict, username: str = ""):
        self.schema_version = 3
        self.project_id = project_id
        self.request = request          # 创建入参（scene_type 已归一化为中文枚举）
        self.username = username        # 归属用户（创建时从登录 token 解析；旧数据为 "" 即视为不可见垃圾数据）
        self.status = "created"
        self.progress = 0
        self.message = ""
        self.planning = {}
        self.copywriting = {}
        self.script = {}
        self.storyboard = {}
        self.plan_id = None
        self.plan_version = 0
        self.reference_candidates: list[dict] = []
        self.reference_assets: list[dict] = []
        self.visual_profile = {}
        self.reference_version = 0
        self.visual_assets = {}
        self.voice = {"status": "none", "version": 0}
        self.music = {"status": "none", "version": 0,
                      "recommendation_status": "none", "recommendation": None}
        self.voice_tasks: list[str] = []
        self.segment_tasks: list[str] = []
        self.render_tasks: list[str] = []
        self.render = {"status": "none", "version": 0}
        self.final_video = {"status": "none", "url": "", "preview_url": "",
                            "duration_s": 0,
                            "resolution": request.get("resolution", "1080p"),
                            "aspect_ratio": request.get("aspect_ratio", "9:16")}
        self.safety = {}
        self.created_at = _now()
        self.updated_at = self.created_at
        self.name = request.get("theme") or "未命名项目"
        self.draft = {}
        self.deleted_at = None
        self.interrupted_stage = None

    @property
    def copywriting_text(self) -> str:
        """B 文档展示格式：文案段落拼接字符串（【0-15s】…）。"""
        parts, t = [], 0
        for p in self.copywriting.get("paragraphs", []):
            t2 = t + p.get("duration_s", 0)
            parts.append(f"【{t}-{t2}s】{p.get('text', '')}")
            t = t2
        return "\n".join(parts)

    def touch(self):
        self.updated_at = _now()

    def to_dict(self, include_private: bool = False) -> dict:
        d = {k: getattr(self, k) for k in (
            "schema_version", "project_id", "username", "status", "progress", "message", "request", "planning",
            "copywriting", "script", "storyboard", "plan_id", "plan_version",
            "reference_candidates", "reference_assets", "visual_profile", "reference_version",
            "visual_assets", "voice", "music", "voice_tasks", "segment_tasks",
            "render_tasks", "render",
            "final_video", "safety", "created_at", "updated_at", "name", "draft",
            "deleted_at", "interrupted_stage")}
        d["copywriting_text"] = self.copywriting_text
        if not include_private:
            # 任务和媒体文件的本机绝对路径只供后端处理；浏览器只拿静态预览 URL。
            d["voice"] = {key: value for key, value in (self.voice or {}).items()
                          if key not in {"reference_path", "local_path", "raw_video_path"}}
            d["music"] = dict(self.music or {})
            if d["music"].get("selected"):
                d["music"]["selected"] = {
                    key: value for key, value in d["music"]["selected"].items()
                    if key != "local_path"
                }
            d["voice_candidates"] = []
            for task_id in self.voice_tasks:
                task = load_voice_task(task_id)
                if task is None:
                    continue
                item = task.to_dict()
                item["result"] = {key: value for key, value in item.get("result", {}).items()
                                  if key not in {"reference_path", "local_path", "raw_video_path"}}
                d["voice_candidates"].append(item)
            d["final_video"] = dict(self.final_video or {})
            for variant in ("clean", "with_bgm", "bgm_bed"):
                if d["final_video"].get(variant):
                    d["final_video"][variant] = {
                        key: value for key, value in d["final_video"][variant].items()
                        if key != "local_path"
                    }
        segment_results = merge_segment_results(self)
        if not include_private:
            private_fields = {"raw_path", "normalized_av_path", "native_audio_path", "source_video_url"}
            segment_results = {
                segment_id: {key: value for key, value in result.items()
                             if key not in private_fields}
                for segment_id, result in segment_results.items()
            }
        d["segment_results"] = segment_results
        d["active_segment_ids"] = sorted(active_segment_ids(self))
        return d

    def dump(self):
        self.touch()
        if STORAGE is not None:
            STORAGE.save_project(self.to_dict(include_private=True))
            return
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        with open(os.path.join(PROJECTS_DIR, f"{self.project_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(include_private=True), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d) -> "Project":
        p = cls(d["project_id"], d["request"])
        for k in ("schema_version", "username", "status", "progress", "message", "planning", "copywriting", "script",
                  "storyboard", "plan_id", "plan_version", "reference_candidates",
                  "reference_assets", "visual_profile", "reference_version", "visual_assets", "voice",
                  "music", "voice_tasks", "segment_tasks", "render_tasks",
                  "render", "final_video", "safety",
                  "created_at", "updated_at", "name", "draft", "deleted_at", "interrupted_stage"):
            if k in d:
                setattr(p, k, d[k])
        return p


def _asset_url(local_path):
    """assets 下本地路径 → 静态 URL。"""
    if not local_path:
        return None
    normalized = os.path.abspath(local_path)
    assets_root = os.path.join(REPO, "assets")
    try:
        relative = os.path.relpath(normalized, assets_root)
    except ValueError:
        return None
    if relative.startswith(".."):
        return None
    return "/assets/" + relative.replace("\\", "/")


class VoiceTask:
    def __init__(self, task_id: str, project_id: str, request_snapshot: dict):
        self.task_id = task_id
        self.project_id = project_id
        self.kind = "voice_candidate"
        self.status = "generating"
        self.progress = 0
        self.message = ""
        self.request = request_snapshot
        self.result = {}
        self.error = None
        self.created_at = _now()
        self.updated_at = self.created_at

    def to_dict(self):
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "result", "error", "created_at", "updated_at")}

    def dump(self):
        self.updated_at = _now()
        if STORAGE is not None:
            STORAGE.save_task(self.to_dict(), "voice")
            return
        os.makedirs(VOICE_TASKS_DIR, exist_ok=True)
        with open(os.path.join(VOICE_TASKS_DIR, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d):
        task = cls(d["task_id"], d["project_id"], d.get("request", {}))
        for key in ("status", "progress", "message", "result", "error", "created_at", "updated_at"):
            if key in d:
                setattr(task, key, d[key])
        return task


class SegmentTask:
    """一次或一批 Seedance Segment 生成；Shot 只是每段内部指令。"""
    def __init__(self, task_id: str, project_id: str, kind: str, request_snapshot: dict):
        self.task_id = task_id
        self.project_id = project_id
        self.kind = kind
        self.status = "generating"
        self.progress = 0
        self.message = ""
        self.request = request_snapshot
        self.segments: list[dict] = []
        self.error = None
        self.created_at = _now()
        self.updated_at = self.created_at

    def init_segments(self, segments: list[dict]):
        self.segments = [{
            "segment_id": segment["segment_id"],
            "shot_ids": list(segment.get("shot_ids", [])),
            "status": "pending",
            "video_url": None,
            "source_video_url": None,
            "raw_path": None,
            "normalized_av_path": None,
            "native_audio_path": None,
            "audio_qa": {},
            "error": None,
            "voice_reference_sha256": self.request.get("voice_reference_sha256", ""),
            "voice_version": self.request.get("voice_version", 0),
            "narration_hash": None,
            "prompt_hash": None,
            "reference_asset_ids": list(segment.get("reference_asset_ids", [])),
        } for segment in segments]

    def sync_from_clips(self, clips: list[dict]):
        for clip in clips:
            row = next((item for item in self.segments
                        if item["segment_id"] == clip["segment_id"]), None)
            if row is None:
                continue
            row["shot_ids"] = list(clip.get("shot_ids", row.get("shot_ids", [])))
            row["external_task_id"] = clip.get("task_id")
            row["reference_asset_ids"] = list(clip.get("reference_asset_ids", []))
            for key in ("voice_reference_sha256", "voice_version", "narration_hash", "prompt_hash"):
                if key in clip:
                    row[key] = clip.get(key)
            status = clip.get("status")
            if status in ("queued", "running"):
                row["status"] = "generating"
            elif status == "succeeded":
                row["status"] = "completed"
                for key in ("raw_path", "normalized_av_path", "native_audio_path", "audio_qa"):
                    row[key] = clip.get(key)
                row["source_video_url"] = clip.get("video_url")
                row["video_url"] = _asset_url(clip.get("normalized_av_path")) or clip.get("video_url")
                row["error"] = None
            else:
                row["status"] = "failed"
                row["error"] = clip.get("error")
        done = sum(1 for item in self.segments if item["status"] in ("completed", "failed"))
        ok = sum(1 for item in self.segments if item["status"] == "completed")
        self.progress = int(done / len(self.segments) * 100) if self.segments else 0
        self.message = f"镜头生成中 {ok}/{len(self.segments)} 完成"

    def to_dict(self):
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "segments", "error", "created_at", "updated_at")}

    def dump(self):
        self.updated_at = _now()
        if STORAGE is not None:
            STORAGE.save_task(self.to_dict(), "segment")
            return
        os.makedirs(SEGMENT_TASKS_DIR, exist_ok=True)
        with open(os.path.join(SEGMENT_TASKS_DIR, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d):
        task = cls(d["task_id"], d["project_id"], d.get("kind", "batch"), d.get("request", {}))
        for key in ("status", "progress", "message", "segments", "error", "created_at", "updated_at"):
            if key in d:
                setattr(task, key, d[key])
        return task


class RenderTask:
    def __init__(self, task_id: str, project_id: str, request_snapshot: dict):
        self.task_id = task_id
        self.project_id = project_id
        self.kind = "render"
        self.status = "rendering"
        self.progress = 0
        self.message = ""
        self.request = request_snapshot
        self.result = {}
        self.error = None
        self.created_at = _now()
        self.updated_at = self.created_at

    def to_dict(self):
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "result", "error", "created_at", "updated_at")}

    def dump(self):
        self.updated_at = _now()
        if STORAGE is not None:
            STORAGE.save_task(self.to_dict(), "render")
            return
        os.makedirs(RENDER_TASKS_DIR, exist_ok=True)
        with open(os.path.join(RENDER_TASKS_DIR, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d):
        task = cls(d["task_id"], d["project_id"], d.get("request", {}))
        for key in ("kind", "status", "progress", "message", "result", "error", "created_at", "updated_at"):
            if key in d:
                setattr(task, key, d[key])
        return task


def load_project(project_id: str) -> Project | None:
    """内存 → 数据库存档懒加载；独立测试使用文件存档。"""
    p = PROJECTS.get(project_id)
    if p is not None:
        return None if p.deleted_at else p
    if STORAGE is not None:
        data = STORAGE.get_project(project_id)
        if data is None:
            return None
        p = Project.from_dict(data)
        PROJECTS[project_id] = p
        return p
    path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        p = Project.from_dict(json.load(f))
    PROJECTS[project_id] = p
    return p


def _load_task(cache, folder, task_id, cls):
    task = cache.get(task_id)
    if task is not None:
        return task
    if STORAGE is not None:
        kind = {VoiceTask: "voice", SegmentTask: "segment", RenderTask: "render"}[cls]
        data = STORAGE.get_task(task_id, kind)
        if data is None:
            return None
        task = cls.from_dict(data)
        cache[task_id] = task
        return task
    path = os.path.join(folder, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as source:
        task = cls.from_dict(json.load(source))
    cache[task_id] = task
    return task


def load_voice_task(task_id: str) -> VoiceTask | None:
    return _load_task(VOICE_TASKS, VOICE_TASKS_DIR, task_id, VoiceTask)


def load_segment_task(task_id: str) -> SegmentTask | None:
    return _load_task(SEGMENT_TASKS, SEGMENT_TASKS_DIR, task_id, SegmentTask)


def load_render_task(task_id: str) -> RenderTask | None:
    return _load_task(RENDER_TASKS, RENDER_TASKS_DIR, task_id, RenderTask)


def load_any_task(task_id: str):
    for loader in (load_voice_task, load_segment_task, load_render_task):
        task = loader(task_id)
        if task is not None:
            return task
    return None


def active_segment_ids(project: Project) -> set[str]:
    active = set()
    for task_id in project.segment_tasks:
        task = load_segment_task(task_id)
        if task is None or task.status != "generating":
            continue
        if task.segments:
            active.update(item["segment_id"] for item in task.segments
                          if item.get("status") in ("pending", "generating"))
        else:
            active.update(task.request.get("segments", []))
    return active


def list_projects(username=None) -> list[Project]:
    """磁盘扫描全部项目（懒加载），按文件名倒序（p_时间戳_hex，天然时间倒序）。
    跳过非 p_ 前缀 / 损坏的 json：一个坏文件不应拖垮整个列表接口。"""
    if STORAGE is not None:
        return [project for data in STORAGE.projects(username)
                if (project := load_project(data["project_id"])) is not None]
    if not os.path.isdir(PROJECTS_DIR):
        return []
    names = sorted((f[:-5] for f in os.listdir(PROJECTS_DIR)
                    if f.endswith(".json") and f.startswith("p_")), reverse=True)
    projects = []
    for n in names:
        try:
            p = load_project(n)
        except Exception:
            continue  # 损坏/半写的项目文件跳过（dump 非原子，服务中断可能留下）
        if p is not None:
            projects.append(p)
    return projects


def merge_segment_results(project: Project) -> dict[str, dict]:
    """按 segment_id 合并最新终态任务；stale Segment 不作为当前可渲染结果。"""
    merged: dict[str, dict] = {}
    stale = {segment.get("segment_id") for segment in project.storyboard.get("segments", [])
             if segment.get("status") == "stale"}
    for task_id in project.segment_tasks:
        task = load_segment_task(task_id)
        if task is None:
            continue
        for item in task.segments:
            segment_id = item.get("segment_id")
            if item.get("status") in ("completed", "failed"):
                merged[segment_id] = {
                    **item,
                    "task_id": task.task_id,
                    "status": item["status"],
                }
    for segment_id in stale:
        if segment_id in merged:
            merged[segment_id] = {**merged[segment_id], "status": "stale"}
    current_voice_hash = (project.voice or {}).get("reference_sha256")
    current_voice_version = (project.voice or {}).get("version")
    for segment_id, result in list(merged.items()):
        if result.get("status") == "completed" and (
            result.get("voice_reference_sha256") != current_voice_hash
            or result.get("voice_version") != current_voice_version
        ):
            merged[segment_id] = {**result, "status": "stale"}
    return merged


def recompute_project_status(project: Project):
    """从当前有效 Segment 任务重算项目状态，不把旧成片误当作新结果。"""
    if project.final_video.get("status") == "completed" and project.render.get("status") == "completed":
        project.status, project.progress, project.message = "completed", 100, "最终视频已生成"
        return
    segment_active = any(load_segment_task(tid) is not None and load_segment_task(tid).status == "generating"
                         for tid in project.segment_tasks)
    if segment_active:
        project.status = "generating"
        return
    if project.storyboard.get("segments"):
        results = merge_segment_results(project)
        total = len(project.storyboard["segments"])
        completed = sum(1 for result in results.values() if result.get("status") == "completed")
        failed = any(result.get("status") == "failed" for result in results.values())
        if total and completed == total:
            project.status, project.progress, project.message = "video_ready", 85, "全部镜头已生成，可合成成片"
        elif results:
            project.status = "waiting_storyboard_confirm"
            project.progress = 45
            project.message = ("存在生成失败的镜头，可重新生成" if failed
                               else "部分镜头已生成，可继续生成或修改")
        return
