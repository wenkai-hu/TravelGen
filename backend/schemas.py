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
    """接口5：新项目按 Segment 生成；shots 仅保留给旧 Storyboard 兼容。"""
    segments: list[str] = Field(default_factory=list)
    shots: list[int] = Field(default_factory=list)
    generate_image: bool = False
    generate_video: bool = True


class RegenerateShotRequest(BaseModel):
    """接口（§十五）：单 Shot 重新生成。
    reason/keep_style 仅作审计落库，不影响生成（每次调用隔离，只认 prompt）。"""
    reason: str = ""
    prompt: str | None = None
    keep_style: bool = True


class AudioRequest(BaseModel):
    """接口7：先生成完整旁白与 BGM 母带。"""
    voice: str = "zh-CN-XiaoxiaoNeural"
    music: str = "ambient"


class RenderRequest(BaseModel):
    """接口8：拼接 Segment 静音画面并回铺项目 master audio。"""
    segment_ids: list[str] = Field(default_factory=list)
    shot_ids: list[str] = Field(default_factory=list)  # 旧客户端兼容，服务端不再作为权威输入
    voice_url: str = ""
    music_url: str = ""
    subtitle: bool = True
    resolution: str = "1080p"
    aspect_ratio: str = "9:16"


class SegmentPatch(BaseModel):
    transition_note: str | None = None


class RegenerateSegmentRequest(BaseModel):
    reason: str = ""
    transition_note: str | None = None
