# -*- coding: utf-8 -*-
"""TravelGen 生成管线 MVP 服务（契约 v0.1，docs/API_Contract_MVP.md）。

启动：
  pip install -r requirements.txt
  python app.py                        # http://127.0.0.1:8000
  TRAVELGEN_MOCK=1 python app.py       # 强制 demo 模式（回放 Phase 3 成果）

行为：
  - 有 experiments/config.json（kimi key）→ 真实模式（kimi-k2.6）
  - 无 config.json 或 TRAVELGEN_MOCK=1 → demo 模式，无需任何 key
  - 交互文档：http://127.0.0.1:8000/docs（可导出 OpenAPI）
"""
import asyncio, uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline import kb
from pipeline.pipeline import PipelineRunner

app = FastAPI(title="TravelGen 生成管线 API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCENE_TYPES = ["城市形象宣传", "景区推荐", "节庆活动推广", "非遗文化传播", "打卡视频", "其他"]
ASPECT_RATIOS = ["9:16", "16:9", "1:1"]
RESOLUTIONS = ["720p", "1080p"]
VIDEO_MODELS = ["seedance-2.0", "seedance-2.0-pro"]


class Asset(BaseModel):
    type: str = "image"
    url: str


class GenerateRequest(BaseModel):
    """输入契约（docs/API_Contract_MVP.md §2）。"""
    city: str
    location: str
    scene_type: str
    theme: str
    audience: str = "18-35岁年轻游客"
    style: str = "大气唯美"
    duration_s: int = Field(60, ge=15, le=120)
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    video_model: str = "seedance-2.0-pro"
    description: str = ""
    assets: list[Asset] = []


class Task:
    """内存任务对象（重启即失，原型阶段够用）。"""

    def __init__(self, task_id: str, req: GenerateRequest):
        self.task_id = task_id
        self.request = req.dict()
        self.status = "planning"
        self.progress = 0
        self.message = ""
        self.planning = {}
        self.copywriting = {}
        self.script = {}
        self.storyboard = {}
        self.visual_assets = {}
        self.voice = {"enabled": False, "status": "reserved", "engine": None}
        self.music = {"suggestions": [], "status": "reserved"}
        self.video_clips = []
        self.safety = {}
        self.final_video = {"status": "none", "url": "", "preview_url": "",
                            "duration_s": 0, "resolution": req.resolution,
                            "aspect_ratio": req.aspect_ratio}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def to_dict(self):
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return {"task_id": self.task_id, "status": self.status, "progress": self.progress,
                "message": self.message,
                "planning": self.planning, "copywriting": self.copywriting,
                "script": self.script, "storyboard": self.storyboard,
                "visual_assets": self.visual_assets, "voice": self.voice,
                "music": self.music, "video_clips": self.video_clips,
                "safety": self.safety, "final_video": self.final_video,
                "created_at": self.created_at, "updated_at": self.updated_at}


TASKS: dict[str, Task] = {}
runner = PipelineRunner()


@app.post("/api/v1/generate", status_code=202)
async def create_generate_task(req: GenerateRequest):
    """提交生成任务（异步，202 返回 task_id）。"""
    errs = []
    if req.scene_type not in SCENE_TYPES:
        errs.append(f"scene_type 需为 {SCENE_TYPES}")
    if req.aspect_ratio not in ASPECT_RATIOS:
        errs.append(f"aspect_ratio 需为 {ASPECT_RATIOS}")
    if req.resolution not in RESOLUTIONS:
        errs.append(f"resolution 需为 {RESOLUTIONS}")
    if req.video_model not in VIDEO_MODELS:
        errs.append(f"video_model 需为 {VIDEO_MODELS}")
    if errs:
        raise HTTPException(400, detail={"code": "invalid_param", "message": "；".join(errs), "detail": ""})

    task_id = f"t_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    task = Task(task_id, req)
    TASKS[task_id] = task
    asyncio.create_task(runner.run(task))
    return {"task_id": task_id, "status": task.status}


@app.get("/api/v1/tasks/{task_id}")
async def get_generate_task(task_id: str):
    """轮询任务状态与阶段输出（前端 2s 间隔）。"""
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, detail={"code": "task_not_found",
                                         "message": f"任务 {task_id} 不存在", "detail": ""})
    return task.to_dict()


@app.get("/api/v1/kb/search")
async def search_kb(q: str, top_k: int = 5):
    """知识库检索（可选，供前端知识点预览）。"""
    if not q.strip():
        raise HTTPException(400, detail={"code": "invalid_param", "message": "q 不能为空", "detail": ""})
    entries = kb.search(q, top_k)
    return {"results": [{"id": e["id"], "name": e["name"], "city": e.get("city", ""),
                         "category": e.get("category", ""), "facts": e.get("facts", [])[:3],
                         "source": e.get("source", ""), "verified": e.get("verified", False)}
                        for e in entries]}


if __name__ == "__main__":
    import uvicorn
    print(f"TravelGen 管线服务 | 模式: {'DEMO（无需 key，回放 Phase3 成果）' if runner.is_demo else 'REAL（kimi-k2.6）'}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
