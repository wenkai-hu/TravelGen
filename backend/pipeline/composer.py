# -*- coding: utf-8 -*-
"""拼接 Seedance 原生音视频，并在完整时间轴上一次性混入用户选择的 BGM。"""
from __future__ import annotations

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RENDER_ROOT = REPO / "assets" / "renders"
BGM_TARGET_LUFS = -23.0


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
    import re
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def mean_audio_level_dbfs(path: str | Path) -> float | None:
    """Return the decoded audio mean level, primarily for mix regression checks."""
    result = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-i", str(path), "-map", "0:a:0",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    import re
    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?|-inf)\s*dB", result.stderr)
    if not match:
        return None
    return float("-inf") if match.group(1) == "-inf" else float(match.group(1))


def _dimensions(resolution: str, ratio: str) -> tuple[int, int]:
    short = 1080 if resolution == "1080p" else 720
    if ratio == "16:9":
        return round(short * 16 / 9 / 2) * 2, short
    if ratio == "1:1":
        return short, short
    return short, round(short * 16 / 9 / 2) * 2


def _asset_url(path: Path) -> str:
    return "/assets/" + path.resolve().relative_to((REPO / "assets").resolve()).as_posix()


def _mix_tracks(clean_path: Path, bed_path: Path, target: Path,
                video_gain_db: float, bgm_gain_db: float, expected: float) -> None:
    video_gain = "0" if video_gain_db <= -60 else f"{video_gain_db}dB"
    music_gain = "0" if bgm_gain_db <= -60 else f"{bgm_gain_db}dB"
    audio_filter = (
        f"[0:a]volume={video_gain}[video];"
        f"[1:a]volume={music_gain}[music];"
        "[video][music]amix=inputs=2:duration=first:normalize=0:dropout_transition=0,"
        "alimiter=limit=0.95[a]"
    )
    _run(["-i", str(clean_path), "-i", str(bed_path), "-filter_complex", audio_filter,
          "-map", "0:v:0", "-map", "[a]", "-c:v", "copy",
          "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
          str(target)])
    measured = media_duration(target)
    if measured is None or abs(measured - expected) > 0.15:
        raise RuntimeError(f"带 BGM 成片时长 {measured} 与目标 {expected} 不一致")


def remix_render(final_video: dict, video_gain_db: float, bgm_gain_db: float,
                 mix_version: int) -> dict:
    """只重混已经拼接好的音轨；不会重新编码视频或生成 Segment。"""
    clean_path = Path(final_video["clean"]["local_path"])
    bed_path = Path(final_video["bgm_bed"]["local_path"])
    if not clean_path.is_file() or not bed_path.is_file():
        raise FileNotFoundError("成片声轨不存在，请重新合成最终视频")
    target = clean_path.parent / f"with_bgm_mix_{mix_version}.mp4"
    _mix_tracks(clean_path, bed_path, target, video_gain_db, bgm_gain_db,
                float(final_video["duration_s"]))
    result = dict(final_video)
    result["with_bgm"] = {"url": _asset_url(target), "local_path": str(target)}
    result["url"] = result["preview_url"] = _asset_url(target)
    result["mix_version"] = mix_version
    result["bgm_mix"] = {**(result.get("bgm_mix") or {}),
                         "video_gain_db": video_gain_db, "bgm_gain_db": bgm_gain_db,
                         "gain_db": bgm_gain_db}
    return result


def compose_project(project, segment_results: dict[str, dict], version: int, output_id: str | None = None) -> dict:
    segments = list(project.storyboard.get("segments", []))
    if not segments:
        raise ValueError("Storyboard 没有 Segment")
    width, height = _dimensions(
        project.request.get("resolution", "720p"),
        project.request.get("aspect_ratio", "9:16"),
    )
    folder = RENDER_ROOT / project.project_id / f"v{version}"
    if output_id:
        folder = folder / output_id
    folder.mkdir(parents=True, exist_ok=True)
    normalized = []
    voice = project.voice or {}
    for index, segment in enumerate(segments, 1):
        segment_id = segment["segment_id"]
        result = segment_results.get(segment_id)
        if not result or result.get("status") != "completed":
            raise ValueError(f"{segment_id} 没有可用的当前视频结果")
        if result.get("voice_reference_sha256") != voice.get("reference_sha256"):
            raise ValueError(f"{segment_id} 使用的参考音色已过期，请重新生成")
        source = Path(result.get("normalized_av_path") or result.get("raw_path") or "")
        if not source.is_file():
            raise FileNotFoundError(f"{segment_id} 原生音视频不存在: {source}")
        duration = segment["duration_ms"] / 1000
        target = folder / f"{index:02d}_{segment_id}.mp4"
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,"
            f"tpad=stop_mode=clone:stop_duration=1,trim=duration={duration},setpts=PTS-STARTPTS"
        )
        audio_filter = f"aresample=48000,apad=pad_dur=1,atrim=duration={duration},asetpts=PTS-STARTPTS"
        _run(["-i", str(source), "-filter_complex",
              f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
              "-map", "[v]", "-map", "[a]",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
              "-movflags", "+faststart", str(target)])
        measured = media_duration(target)
        if measured is None or abs(measured - duration) > 0.12:
            raise RuntimeError(f"{segment_id} 归一化后时长 {measured} 与目标 {duration} 不一致")
        normalized.append(target)

    input_args = []
    for path in normalized:
        input_args += ["-i", str(path)]
    streams = "".join(f"[{index}:v:0][{index}:a:0]" for index in range(len(normalized)))
    clean_path = folder / "clean.mp4"
    _run([*input_args, "-filter_complex",
          f"{streams}concat=n={len(normalized)}:v=1:a=1[v][a]",
          "-map", "[v]", "-map", "[a]",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(clean_path)])

    expected = sum(int(segment["duration_ms"]) for segment in segments) / 1000
    clean_duration = media_duration(clean_path)
    if clean_duration is None or abs(clean_duration - expected) > 0.15:
        raise RuntimeError(f"无 BGM 成片时长 {clean_duration} 与 Segment 合计 {expected} 不一致")

    music = project.music or {}
    selected = music.get("selected") if music.get("status") == "selected" else None
    with_bgm_path = None
    bed_path = None
    bgm_mix = None
    if selected:
        bgm = Path(selected.get("local_path", ""))
        if not bgm.is_file():
            raise FileNotFoundError(f"所选 BGM 文件不存在: {bgm}")
        with_bgm_path = folder / "with_bgm.mp4"
        bed_path = folder / "bgm_bed.m4a"
        fade_out = max(0.0, expected - 1.2)
        audio_filter = (
            f"[0:a]aresample=48000,loudnorm=I={BGM_TARGET_LUFS}:TP=-3:LRA=11,"
            f"atrim=duration={expected},afade=t=in:st=0:d=0.8,"
            f"afade=t=out:st={fade_out}:d=1.2[a]"
        )
        _run(["-stream_loop", "-1", "-i", str(bgm),
              "-filter_complex", audio_filter,
              "-map", "[a]", "-c:a", "aac", "-b:a", "192k", str(bed_path)])
        _mix_tracks(clean_path, bed_path, with_bgm_path, 0, 0, expected)
        bgm_mix = {
            "bgm_id": selected.get("bgm_id"),
            "title": selected.get("title"),
            "target_lufs": BGM_TARGET_LUFS,
            "video_gain_db": 0,
            "bgm_gain_db": 0,
            "gain_db": 0,
            "strategy": "loudness_normalized_mix",
        }

    default_path = with_bgm_path or clean_path
    return {
        "status": "completed",
        "url": _asset_url(default_path),
        "preview_url": _asset_url(default_path),
        "default_variant": "with_bgm" if with_bgm_path else "clean",
        "clean": {"url": _asset_url(clean_path), "local_path": str(clean_path)},
        "with_bgm": ({"url": _asset_url(with_bgm_path), "local_path": str(with_bgm_path)}
                     if with_bgm_path else None),
        "bgm_bed": ({"url": _asset_url(bed_path), "local_path": str(bed_path)}
                    if bed_path else None),
        "bgm_mix": bgm_mix,
        "duration_s": clean_duration,
        "resolution": project.request.get("resolution", "720p"),
        "aspect_ratio": project.request.get("aspect_ratio", "9:16"),
        "version": version,
        "voice_version": voice.get("version"),
        "music_version": music.get("version"),
    }
