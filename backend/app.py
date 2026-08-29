# -*- coding: utf-8 -*-
"""TravelGen 生成管线 MVP 服务（契约 v0.2，docs/API_Contract_MVP.md）。

启动：
  pip install -r requirements.txt
  cd backend && python app.py          # http://127.0.0.1:8000（reload 自动重载：改后端代码即生效）
  TRAVELGEN_MOCK=1 python app.py       # 强制 demo 模式（回放 Phase 3 成果）

行为：
  - 旧契约（/api/v1/*）：一键直出，POST generate + 轮询 tasks
  - V1 分阶段（/api/*，TravelGen_v1.md）：创建项目 → 方案确认 → 分镜 → Shot 修改 → 批量生成（v1_router.py）
  - 有 experiments/config.json（kimi key）→ 真实模式（kimi-k2.6）
  - 无 config.json 或 TRAVELGEN_MOCK=1 → demo 模式，无需任何 key
  - 交互文档：http://127.0.0.1:8000/docs（可导出 OpenAPI）
"""
import asyncio, json, os, uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from constants import SCENE_TYPES, ASPECT_RATIOS, RESOLUTIONS, VIDEO_MODELS
from schemas import GenerateRequest
from pipeline import kb
from pipeline.pipeline import PipelineRunner
from v1_router import router as v1_router

app = FastAPI(title="TravelGen 生成管线 API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(v1_router)


class Task:
    """内存任务对象（重启即失，原型阶段够用）。"""

    def __init__(self, task_id: str, req: GenerateRequest):
        self.task_id = task_id
        self.request = req.model_dump()
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

    def dump(self):
        """任务产物落盘：experiments/results/05_pipeline/{task_id}.json（可复现，服务重启不丢）。"""
        out_dir = os.path.join(REPO_ROOT, "experiments", "results", "05_pipeline")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{self.task_id}.json"), "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


TASKS: dict[str, Task] = {}
runner = PipelineRunner()
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# 视频转存 assets/videos/ 静态挂载：真实模式 local_path 可直接被浏览器访问（/assets/videos/xxx.mp4）
_assets_dir = os.path.join(REPO_ROOT, "assets")
os.makedirs(_assets_dir, exist_ok=True)
app.mount("/assets", StaticFiles(directory=_assets_dir, check_dir=False), name="assets")


async def _run_and_dump(task: Task):
    """执行管线并落盘产物（done/failed 都写）。"""
    try:
        await runner.run(task)
    finally:
        task.dump()


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
    asyncio.create_task(_run_and_dump(task))
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
    print(f"TravelGen 管线服务 | 文案/分镜: {'kimi-k2.6' if runner.kimi else 'demo回放'} "
          f"| 视频: {'Seedance 2.0 Pro' if runner.seedance else '模拟'}")
    # reload 需传导入字符串（不能传 app 对象）；改后端 .py 自动重启，需在 backend/ 目录下运行
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
