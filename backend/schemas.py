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
    narration: str | None = None
    subject: str | None = None
    background: str | None = None
    shot_size: str | None = None
    camera: dict | None = None
    reference_asset_ids: list[str] | None = None


class GenerateSegmentsRequest(BaseModel):
    """按一个或多个完整 Segment 生成；空列表表示生成全部待选 Segment。"""
    segments: list[str] = Field(default_factory=list)
    generate_video: bool = True


class RegenerateShotRequest(BaseModel):
    """接口（§十五）：单 Shot 重新生成。
    reason/keep_style 仅作审计落库，不影响生成（每次调用隔离，只认 prompt）。"""
    reason: str = ""
    prompt: str | None = None
    keep_style: bool = True


class VoiceCandidateRequest(BaseModel):
    """用 Seedance 生成一条可试听、可确认的自定义参考音色。"""
    description: str = Field(..., min_length=2, max_length=300)


class VoiceSelectionRequest(BaseModel):
    """确认预设音色，或确认已经完成的自定义音色任务。"""
    voice_id: str | None = None
    candidate_task_id: str | None = None


class MusicSelectionRequest(BaseModel):
    """确认一首预设 BGM；explicit_none=true 表示明确不要 BGM。"""
    bgm_id: str | None = None
    explicit_none: bool = False


class RenderMixRequest(BaseModel):
    """成片试听后调整原视频声轨与配乐声轨的音量。"""
    video_gain_db: float = Field(0, ge=-60, le=0)
    bgm_gain_db: float = Field(0, ge=-60, le=0)


class RenderRequest(BaseModel):
    """拼接 Seedance 原生音视频，并按选择生成 clean/with-BGM 双版本。"""
    segment_ids: list[str] = Field(default_factory=list)


class SegmentPatch(BaseModel):
    transition_note: str | None = None


class RegenerateSegmentRequest(BaseModel):
    reason: str = ""
    transition_note: str | None = None
