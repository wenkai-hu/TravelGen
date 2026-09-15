# -*- coding: utf-8 -*-
"""共享 Pydantic 请求模型（app.py 旧契约 + v1_router V1 接口共用）。"""
from pydantic import BaseModel, Field


class Asset(BaseModel):
    type: str = "image"
    url: str


class GenerateRequest(BaseModel):
    """输入契约（docs/API_Contract_MVP.md §2 / TravelGen_v1.md §六）。"""
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


class ConfirmPlanRequest(BaseModel):
    """接口2：用户修改/确认后的旁白文案（TravelGen_v1.md §八）。"""
    copywriting: str


class ConfirmReferencesRequest(BaseModel):
    """用户从服务端搜索候选中确认真实景点图片；确认后才启动 VLM 与 Plan。"""
    reference_ids: list[str] = Field(..., min_length=1, max_length=8)


class StoryboardRequest(BaseModel):
    """接口3：生成脚本+分镜（plan_id 可选，用于并发安全校验）。"""
    plan_id: str | None = None


class ShotPatch(BaseModel):
    """接口4：修改单个 Shot 的部分字段（只更新出现的字段）。"""
    prompt: str | None = None
    duration_s: int | None = None
    subject: str | None = None
    background: str | None = None
    shot_size: str | None = None
    camera: dict | None = None
    reference_asset_ids: list[str] | None = None


class GenerateShotsRequest(BaseModel):
    """接口5：批量生成视频（shots 为 shot_id 列表；generate_image 本版预留 video-only）。"""
    shots: list[int] = Field(..., min_length=1)
    generate_image: bool = False
    generate_video: bool = True


class RegenerateShotRequest(BaseModel):
    """接口（§十五）：单 Shot 重新生成。
    reason/keep_style 仅作审计落库，不影响生成（每次调用隔离，只认 prompt）。"""
    reason: str = ""
    prompt: str | None = None
    keep_style: bool = True


class AudioRequest(BaseModel):
    """接口7：配音+音乐（本版占位）。"""
    voice: str = ""
    music: str = ""


class RenderRequest(BaseModel):
    """接口8：最终合成（本版占位，字段对齐 TravelGen_v1.md §十七）。"""
    shot_ids: list[str] = []
    voice_url: str = ""
    music_url: str = ""
    subtitle: bool = True
    resolution: str = "1080p"
    aspect_ratio: str = "9:16"
