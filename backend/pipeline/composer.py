# -*- coding: utf-8 -*-
"""把 Segment 静音画面拼成时间轴并一次性回铺 master audio。"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RENDER_ROOT = REPO / "assets" / "renders"


def _ffmpeg_exe() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def _run(args: list[str], timeout: int = 1200) -> None:
    result = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(f"FFmpeg 合成失败: {result.stderr[-3000:]}")


def media_duration(path: str | Path) -> float | None:
    result = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _dimensions(resolution: str, ratio: str) -> tuple[int, int]:
    short = 1080 if resolution == "1080p" else 720
    if ratio == "16:9":
        return (round(short * 16 / 9 / 2) * 2, short)
    if ratio == "1:1":
        return (short, short)
    return (short, round(short * 16 / 9 / 2) * 2)


def _asset_url(path: Path) -> str:
    relative = path.resolve().relative_to((REPO / "assets").resolve()).as_posix()
    return f"/assets/{relative}"


def compose_project(project, segment_results: dict[str, dict], version: int) -> dict:
    segments = list(project.storyboard.get("segments", []))
    if not segments:
        raise ValueError("Storyboard 没有 Segment")
    master_path = Path((project.audio or {}).get("master_path", ""))
    if not master_path.is_file():
        raise FileNotFoundError("master_audio.wav 不存在")
    width, height = _dimensions(
        project.request.get("resolution", "720p"),
        project.request.get("aspect_ratio", "9:16"),
    )
    folder = RENDER_ROOT / project.project_id / f"v{version}"
    folder.mkdir(parents=True, exist_ok=True)
    normalized = []
    for index, segment in enumerate(segments, 1):
        segment_id = segment["segment_id"]
        result = segment_results.get(segment_id)
        if not result or result.get("status") != "completed":
            raise ValueError(f"{segment_id} 没有可用的当前视频结果")
        if result.get("audio_slice_sha256") != segment.get("audio_slice_sha256"):
            raise ValueError(f"{segment_id} 使用的音频切片已过期，请重新生成")
        source = Path(result.get("visual_path") or result.get("local_path") or "")
        if not source.is_file():
            raise FileNotFoundError(f"{segment_id} 静音画面不存在: {source}")
        duration = segment["duration_ms"] / 1000
        target = folder / f"{index:02d}_{segment_id}.mp4"
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,"
            f"tpad=stop_mode=clone:stop_duration=2,trim=duration={duration},setpts=PTS-STARTPTS"
        )
        _run(["-i", str(source), "-an", "-vf", vf,
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
              "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)])
        measured = media_duration(target)
        if measured is None or abs(measured - duration) > 0.08:
            raise RuntimeError(f"{segment_id} 归一化后时长 {measured} 与目标 {duration} 不一致")
        normalized.append(target)

    input_args = []
    for path in normalized:
        input_args += ["-i", str(path)]
    streams = "".join(f"[{index}:v:0]" for index in range(len(normalized)))
    visual_path = folder / "visual_track.mp4"
    _run([*input_args, "-filter_complex",
          f"{streams}concat=n={len(normalized)}:v=1:a=0[v]", "-map", "[v]",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(visual_path)])

    final_path = folder / "final.mp4"
    temp_path = folder / "final.tmp.mp4"
    _run(["-i", str(visual_path), "-i", str(master_path),
          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
          "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
          str(temp_path)])
    os.replace(temp_path, final_path)
    expected = (project.audio or {}).get("duration_ms", 0) / 1000
    actual = media_duration(final_path)
    if actual is None or abs(actual - expected) > 0.12:
        raise RuntimeError(f"成片时长 {actual} 与母带 {expected} 不一致")
    return {
        "status": "completed",
        "url": _asset_url(final_path),
        "preview_url": _asset_url(final_path),
        "local_path": str(final_path),
        "visual_track_path": str(visual_path),
        "duration_s": actual,
        "resolution": project.request.get("resolution", "720p"),
        "aspect_ratio": project.request.get("aspect_ratio", "9:16"),
        "version": version,
    }
