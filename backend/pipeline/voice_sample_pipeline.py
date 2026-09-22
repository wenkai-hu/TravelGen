# -*- coding: utf-8 -*-
"""用 Seedance 生成自定义参考音色候选，并抽取干净人声 WAV。"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from . import ark_client, media_catalog, media_qc


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "assets" / "media" / "voices" / "custom"
TEST_NARRATION = "西湖的清晨，风把柳枝吹成了一句诗。"


def build_prompt(description: str) -> str:
    return "\n".join([
        "生成一条用于确认中文解说音色的5秒短视频，声音质量是唯一重点。",
        f"旁白音色：{description.strip()}",
        "只由一名说话者用普通话自然朗读；保持同一个说话人，不唱歌，不添加其他对白。",
        "必须准确完整地朗读下面这句话，不增字、不删字、不换词：",
        f"“{TEST_NARRATION}”",
        "只生成干净旁白人声。绝对不要背景音乐、配乐、旋律、节奏铺底、环境声、拟音、"
        "乐器声、唱歌或哼唱。",
        "画面保持最低复杂度：中性纯色背景前的一名旁白，固定近景，动作极少，"
        "无转场、无字幕、无文字、无标志、无水印。",
    ])


def paths(project_id: str, task_id: str) -> tuple[Path, Path]:
    folder = ROOT / project_id / task_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "seedance_raw.mp4", folder / "reference_voice.wav"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_url(path: Path) -> str:
    return "/assets/" + path.resolve().relative_to((REPO / "assets").resolve()).as_posix()


def finalize(project_id: str, task_id: str, raw_path: str | Path) -> dict:
    raw, wav = paths(project_id, task_id)
    raw_path = Path(raw_path)
    if raw_path.resolve() != raw.resolve():
        shutil.copy2(raw_path, raw)
    if not ark_client.extract_audio(str(raw), str(wav)):
        raise RuntimeError("Seedance 自定义音色视频没有可用音轨")
    analysis = media_qc.inspect_wav(wav, 5)
    return {
        "status": "candidate_ready",
        "voice_id": f"custom_{task_id}",
        "name": "自定义音色",
        "description": "由用户描述生成，确认后作为所有 Segment 的统一声音身份参考",
        "source": "custom",
        "reference_path": str(wav),
        "preview_url": _asset_url(wav),
        "reference_sha256": _sha256(wav),
        "raw_video_path": str(raw),
        "analysis": analysis,
    }


def mock_candidate(project_id: str, task_id: str, description: str) -> dict:
    """demo 模式复用首条正式预设，仍返回可试听的真实 WAV。"""
    presets = media_catalog.voice_presets()
    if not presets:
        raise RuntimeError("正式预设音色目录为空")
    _, wav = paths(project_id, task_id)
    shutil.copy2(presets[0]["local_path"], wav)
    return {
        "status": "candidate_ready",
        "voice_id": f"custom_{task_id}",
        "name": "自定义音色（演示）",
        "description": description,
        "source": "custom",
        "reference_path": str(wav),
        "preview_url": _asset_url(wav),
        "reference_sha256": _sha256(wav),
        "analysis": media_qc.inspect_wav(wav, 5.088),
    }
