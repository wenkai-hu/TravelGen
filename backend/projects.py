# -*- coding: utf-8 -*-
"""Project 流程的模型与追加式任务存储。

- Project：一次创作任务的主实体（方案 → 母带 → 分镜 → Segment → 最终合成），
  落盘 experiments/results/05_pipeline/projects/{project_id}.json
- AudioTask/SegmentTask/RenderTask：新管线的三个可轮询任务；VideoTask 保留旧数据兼容。
- Project 与各类任务 GET 时从对应目录懒加载；聚合结果不单独落盘，始终由追加式任务重算，最新任务胜出。
"""
import json, os
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RESULTS_DIR = os.path.join(REPO, "experiments", "results", "05_pipeline")
PROJECTS_DIR = os.path.join(RESULTS_DIR, "projects")
VIDEO_TASKS_DIR = os.path.join(RESULTS_DIR, "video_tasks")
AUDIO_TASKS_DIR = os.path.join(RESULTS_DIR, "audio_tasks")
SEGMENT_TASKS_DIR = os.path.join(RESULTS_DIR, "segment_tasks")
RENDER_TASKS_DIR = os.path.join(RESULTS_DIR, "render_tasks")

PROJECTS: dict[str, "Project"] = {}
VIDEO_TASKS: dict[str, "VideoTask"] = {}
AUDIO_TASKS: dict[str, "AudioTask"] = {}
SEGMENT_TASKS: dict[str, "SegmentTask"] = {}
RENDER_TASKS: dict[str, "RenderTask"] = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


class Project:
    """一次创作任务。status 状态机见 docs/API_Contract_MVP.md V1 章节。"""

    def __init__(self, project_id: str, request: dict, username: str = ""):
        self.schema_version = 2
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
        self.voice = {"status": "reserved", "engine": None}
        self.music = {"suggestions": [], "status": "reserved"}
        self.audio = {"status": "none", "version": 0}
        self.audio_tasks: list[str] = []
        self.video_tasks: list[str] = []   # task_id 追加式列表（merge 时最新胜出）
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

    def to_dict(self) -> dict:
        self.touch()
        d = {k: getattr(self, k) for k in (
            "schema_version", "project_id", "username", "status", "progress", "message", "request", "planning",
            "copywriting", "script", "storyboard", "plan_id", "plan_version",
            "reference_candidates", "reference_assets", "visual_profile", "reference_version",
            "visual_assets", "voice", "music", "audio", "audio_tasks", "video_tasks", "segment_tasks",
            "render_tasks", "render",
            "final_video", "safety", "created_at", "updated_at")}
        d["copywriting_text"] = self.copywriting_text
        d["video_clips"] = merge_video_results(self)  # 权威来自任务重算
        d["segment_results"] = merge_segment_results(self)
        d["active_segment_ids"] = sorted(active_segment_ids(self))
        return d

    def dump(self):
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        with open(os.path.join(PROJECTS_DIR, f"{self.project_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d) -> "Project":
        p = cls(d["project_id"], d["request"])
        for k in ("schema_version", "username", "status", "progress", "message", "planning", "copywriting", "script",
                  "storyboard", "plan_id", "plan_version", "reference_candidates",
                  "reference_assets", "visual_profile", "reference_version", "visual_assets", "voice",
                  "music", "audio", "audio_tasks", "video_tasks", "segment_tasks", "render_tasks",
                  "render", "final_video", "safety",
                  "created_at", "updated_at"):
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


def _web_url(local_path):
    """本地转存绝对路径 → 浏览器可访问 URL（/assets/videos/xxx.mp4，app.py 已挂载 /assets）。"""
    if not local_path:
        return None
    return _asset_url(local_path)


class VideoTask:
    """一次视频生成子任务（kind=batch 批量 | single 单 shot 重生成）。"""

    def __init__(self, task_id: str, project_id: str, kind: str, request_snapshot: dict):
        self.task_id = task_id
        self.project_id = project_id
        self.kind = kind
        self.status = "generating"
        self.progress = 0
        self.message = ""
        self.request = request_snapshot   # {shot_ids, generate_image, generate_video, regenerate}
        self.shots: list[dict] = []
        self.created_at = _now()
        self.updated_at = self.created_at

    def init_shots(self, shot_ids: list[int]):
        self.shots = [{"shot_id": sid, "status": "pending", "image_url": None,
                       "video_url": None, "local_path": None, "error": None,
                       "reference_asset_ids": []}
                      for sid in shot_ids]

    def sync_from_clips(self, clips: list[dict]):
        """旧格式 clips（pipeline 产出）→ V1 shots 行。clips 原地更新，轮询中每 5s 同步一次。"""
        for c in clips:
            row = next((s for s in self.shots if s["shot_id"] == c["shot_id"]), None)
            if row is None:
                continue
            row["reference_asset_ids"] = list(c.get("reference_asset_ids", []))
            if c["status"] in ("queued", "running"):
                row["status"] = "generating"
            elif c["status"] == "succeeded":
                row["status"] = "completed"
                row["local_path"] = c.get("local_path")
                # 前端播放用可访问 URL：本地转存 → /assets/videos/{文件名}（app.py 已挂载 /assets）
                row["video_url"] = _web_url(c.get("local_path")) or c.get("video_url")
            else:
                row["status"] = "failed"
                row["error"] = c.get("error")
        n_ok = sum(1 for s in self.shots if s["status"] == "completed")
        n_done = sum(1 for s in self.shots if s["status"] in ("completed", "failed"))
        self.progress = int(n_done / len(self.shots) * 100) if self.shots else 0
        self.message = f"视频生成中 {n_ok}/{len(self.shots)} 完成"

    def to_dict(self) -> dict:
        self.updated_at = _now()
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "shots", "created_at", "updated_at")}

    def dump(self):
        os.makedirs(VIDEO_TASKS_DIR, exist_ok=True)
        with open(os.path.join(VIDEO_TASKS_DIR, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d) -> "VideoTask":
        t = cls(d["task_id"], d["project_id"], d["kind"], d["request"])
        for k in ("status", "progress", "message", "shots", "created_at", "updated_at"):
            if k in d:
                setattr(t, k, d[k])
        return t


class AudioTask:
    def __init__(self, task_id: str, project_id: str, request_snapshot: dict):
        self.task_id = task_id
        self.project_id = project_id
        self.kind = "audio"
        self.status = "generating"
        self.progress = 0
        self.message = ""
        self.request = request_snapshot
        self.result = {}
        self.error = None
        self.created_at = _now()
        self.updated_at = self.created_at

    def to_dict(self):
        self.updated_at = _now()
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "result", "error", "created_at", "updated_at")}

    def dump(self):
        os.makedirs(AUDIO_TASKS_DIR, exist_ok=True)
        with open(os.path.join(AUDIO_TASKS_DIR, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
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
            "raw_path": None,
            "visual_path": None,
            "preview_path": None,
            "error": None,
            "audio_slice_sha256": segment.get("audio_slice_sha256", ""),
            "reference_asset_ids": list(segment.get("reference_asset_ids", [])),
        } for segment in segments]

    def sync_from_clips(self, clips: list[dict]):
        for clip in clips:
            row = next((item for item in self.segments
                        if item["segment_id"] == clip["segment_id"]), None)
            if row is None:
                continue
            row["shot_ids"] = list(clip.get("shot_ids", row.get("shot_ids", [])))
            row["reference_asset_ids"] = list(clip.get("reference_asset_ids", []))
            row["audio_slice_sha256"] = clip.get("audio_slice_sha256", "")
            status = clip.get("status")
            if status in ("queued", "running"):
                row["status"] = "generating"
            elif status == "succeeded":
                row["status"] = "completed"
                for key in ("raw_path", "visual_path", "preview_path"):
                    row[key] = clip.get(key)
                row["video_url"] = _asset_url(clip.get("preview_path")) or clip.get("video_url")
                row["error"] = None
            else:
                row["status"] = "failed"
                row["error"] = clip.get("error")
        done = sum(1 for item in self.segments if item["status"] in ("completed", "failed"))
        ok = sum(1 for item in self.segments if item["status"] == "completed")
        self.progress = int(done / len(self.segments) * 100) if self.segments else 0
        self.message = f"Segment 生成中 {ok}/{len(self.segments)} 完成"

    def to_dict(self):
        self.updated_at = _now()
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "segments", "error", "created_at", "updated_at")}

    def dump(self):
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
        self.updated_at = _now()
        return {k: getattr(self, k) for k in (
            "task_id", "project_id", "kind", "status", "progress", "message",
            "request", "result", "error", "created_at", "updated_at")}

    def dump(self):
        os.makedirs(RENDER_TASKS_DIR, exist_ok=True)
        with open(os.path.join(RENDER_TASKS_DIR, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d):
        task = cls(d["task_id"], d["project_id"], d.get("request", {}))
        for key in ("status", "progress", "message", "result", "error", "created_at", "updated_at"):
            if key in d:
                setattr(task, key, d[key])
        return task


def load_project(project_id: str) -> Project | None:
    """内存 → 磁盘懒加载（重启恢复）。"""
    p = PROJECTS.get(project_id)
    if p is not None:
        return p
    path = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        p = Project.from_dict(json.load(f))
    PROJECTS[project_id] = p
    return p


def load_video_task(task_id: str) -> VideoTask | None:
    t = VIDEO_TASKS.get(task_id)
    if t is not None:
        return t
    path = os.path.join(VIDEO_TASKS_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        t = VideoTask.from_dict(json.load(f))
    VIDEO_TASKS[task_id] = t
    return t


def _load_task(cache, folder, task_id, cls):
    task = cache.get(task_id)
    if task is not None:
        return task
    path = os.path.join(folder, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as source:
        task = cls.from_dict(json.load(source))
    cache[task_id] = task
    return task


def load_audio_task(task_id: str) -> AudioTask | None:
    return _load_task(AUDIO_TASKS, AUDIO_TASKS_DIR, task_id, AudioTask)


def load_segment_task(task_id: str) -> SegmentTask | None:
    return _load_task(SEGMENT_TASKS, SEGMENT_TASKS_DIR, task_id, SegmentTask)


def load_render_task(task_id: str) -> RenderTask | None:
    return _load_task(RENDER_TASKS, RENDER_TASKS_DIR, task_id, RenderTask)


def load_any_task(task_id: str):
    for loader in (load_audio_task, load_segment_task, load_render_task, load_video_task):
        task = loader(task_id)
        if task is not None:
            return task
    return None


def active_video_shot_ids(project: Project) -> set[int]:
    """返回仍在生成的 Shot ID；不同 Shot 可并发，同一 Shot 避免重复扣费。"""
    active: set[int] = set()
    for tid in project.video_tasks:
        task = load_video_task(tid)
        if task is None or task.status != "generating":
            continue
        if task.shots:
            active.update(
                row["shot_id"] for row in task.shots
                if row.get("status") in ("pending", "generating")
            )
            continue
        # create_task 尚未获得调度时 task.shots 还是空的，从请求快照兜住竞态窗口。
        requested = task.request.get("shots") or task.request.get("shot_ids") or []
        active.update(int(shot_id) for shot_id in requested)
    return active


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


def list_projects() -> list[Project]:
    """磁盘扫描全部项目（懒加载），按文件名倒序（p_时间戳_hex，天然时间倒序）。
    跳过非 p_ 前缀 / 损坏的 json：一个坏文件不应拖垮整个列表接口。"""
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


def merge_video_results(project: Project) -> dict[int, dict]:
    """遍历 project.video_tasks，按 shot_id 合并已终止结果（最新 task 胜出）。幂等。"""
    merged: dict[int, dict] = {}
    for tid in project.video_tasks:
        vt = load_video_task(tid)
        if vt is None:
            continue
        for s in vt.shots:
            if s["status"] in ("completed", "failed"):
                merged[s["shot_id"]] = {"shot_id": s["shot_id"], "task_id": vt.task_id,
                                        "status": s["status"], "video_url": s.get("video_url"),
                                        "local_path": s.get("local_path"),
                                        "reference_asset_ids": s.get("reference_asset_ids", []),
                                        "error": s.get("error")}
    return merged


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
    return merged


def recompute_project_status(project: Project):
    """从当前有效 Segment/旧 Shot 任务重算项目状态，不把旧成片误当作新结果。"""
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
            project.status, project.progress, project.message = "video_ready", 85, "全部 Segment 已生成，可合成成片"
        elif results:
            project.status = "waiting_storyboard_confirm"
            project.progress = 45
            project.message = ("存在生成失败的 Segment，可重新生成" if failed
                               else "部分 Segment 已生成，可继续生成或修改")
        return
    active = any(load_video_task(tid) is not None and load_video_task(tid).status == "generating"
                 for tid in project.video_tasks)
    if active:
        project.status = "generating"
        return
    results = merge_video_results(project)
    total = sum(len(sc.get("shot_list", [])) for sc in project.storyboard.get("scenes", []))
    done = len(results)
    if total and done >= total:
        if any(r["status"] == "failed" for r in results.values()):
            project.status = "failed"
        else:
            project.status, project.progress, project.message = "completed", 100, "全部镜头生成完成"
    elif done:
        # 部分镜头已生成（单镜测试/部分失败）：回到分镜编辑态，允许继续生成剩余镜头
        project.status, project.progress, project.message = "waiting_storyboard_confirm", 40, "分镜待确认（部分镜头已生成）"
