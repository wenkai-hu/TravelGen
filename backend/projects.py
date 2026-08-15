# -*- coding: utf-8 -*-
"""V1 project 化流程的模型与存储（TravelGen_v1.md §六~§十八）。

- Project：一次创作任务的主实体（创建 → 方案确认 → 分镜 → Shot 修改 → 视频生成），
  落盘 experiments/results/05_pipeline/projects/{project_id}.json
- VideoTask：一次批量/单 shot 视频生成子任务（POST /generate 与 /regenerate 的产物），
  落盘 experiments/results/05_pipeline/video_tasks/{task_id}.json
- 两者 GET 时磁盘懒加载，服务重启不丢；project.video_clips 不落盘为权威，
  每次由 merge_video_results() 从 video_tasks 重算（天然一致，最新 task 胜出）。
"""
import json, os
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RESULTS_DIR = os.path.join(REPO, "experiments", "results", "05_pipeline")
PROJECTS_DIR = os.path.join(RESULTS_DIR, "projects")
VIDEO_TASKS_DIR = os.path.join(RESULTS_DIR, "video_tasks")

PROJECTS: dict[str, "Project"] = {}
VIDEO_TASKS: dict[str, "VideoTask"] = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


class Project:
    """一次创作任务。status 状态机见 docs/API_Contract_MVP.md V1 章节。"""

    def __init__(self, project_id: str, request: dict):
        self.project_id = project_id
        self.request = request          # 创建入参（scene_type 已归一化为中文枚举）
        self.status = "created"
        self.progress = 0
        self.message = ""
        self.planning = {}
        self.copywriting = {}
        self.script = {}
        self.storyboard = {}
        self.plan_id = None
        self.plan_version = 0
        self.visual_assets = {}
        self.voice = {"status": "reserved", "engine": None}
        self.music = {"suggestions": [], "status": "reserved"}
        self.video_tasks: list[str] = []   # task_id 追加式列表（merge 时最新胜出）
        self.render = {"status": "reserved"}
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
            "project_id", "status", "progress", "message", "request", "planning",
            "copywriting", "script", "storyboard", "plan_id", "plan_version",
            "visual_assets", "voice", "music", "video_tasks", "render",
            "final_video", "safety", "created_at", "updated_at")}
        d["copywriting_text"] = self.copywriting_text
        d["video_clips"] = merge_video_results(self)  # 权威来自任务重算
        return d

    def dump(self):
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        with open(os.path.join(PROJECTS_DIR, f"{self.project_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d) -> "Project":
        p = cls(d["project_id"], d["request"])
        for k in ("status", "progress", "message", "planning", "copywriting", "script",
                  "storyboard", "plan_id", "plan_version", "visual_assets", "voice",
                  "music", "video_tasks", "render", "final_video", "safety",
                  "created_at", "updated_at"):
            if k in d:
                setattr(p, k, d[k])
        return p


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
                       "video_url": None, "local_path": None, "error": None}
                      for sid in shot_ids]

    def sync_from_clips(self, clips: list[dict]):
        """旧格式 clips（pipeline 产出）→ V1 shots 行。clips 原地更新，轮询中每 5s 同步一次。"""
        for c in clips:
            row = next((s for s in self.shots if s["shot_id"] == c["shot_id"]), None)
            if row is None:
                continue
            if c["status"] in ("queued", "running"):
                row["status"] = "generating"
            elif c["status"] == "succeeded":
                row["status"] = "completed"
                row["video_url"] = c.get("local_path") or c.get("video_url")
                row["local_path"] = c.get("local_path")
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
                                        "local_path": s.get("local_path"), "error": s.get("error")}
    return merged


def recompute_project_status(project: Project):
    """有进行中的视频任务 → generating；全部终止且全成功 → completed；有失败 → failed；否则不变。"""
    active = any(load_video_task(tid) is not None and load_video_task(tid).status == "generating"
                 for tid in project.video_tasks)
    if active:
        project.status = "generating"
        return
    results = merge_video_results(project)
    if results:
        project.status = "failed" if any(r["status"] == "failed" for r in results.values()) else "completed"
