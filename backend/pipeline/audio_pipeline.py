# -*- coding: utf-8 -*-
"""Edge-TTS 旁白、连续 BGM、master audio 与 Segment 音频切片。"""
from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import wave
from array import array
from functools import lru_cache
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
AUDIO_ROOT = REPO / "assets" / "audio"
SAMPLE_RATE = 24_000
LEAD_SECONDS = 0.30
TAIL_SECONDS = 0.30


def _ffmpeg_exe() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe
    return get_ffmpeg_exe()


def _run_ffmpeg(args: list[str], timeout: int = 300) -> None:
    result = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(f"FFmpeg 失败: {result.stderr[-2000:]}")


def _asset_url(path: Path) -> str:
    relative = path.resolve().relative_to((REPO / "assets").resolve()).as_posix()
    return f"/assets/{relative}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_pcm(path: Path) -> array:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != SAMPLE_RATE:
            raise RuntimeError(f"音频不是 {SAMPLE_RATE}Hz mono PCM16: {path}")
        result = array("h")
        result.frombytes(source.readframes(source.getnframes()))
        return result


def _write_pcm(path: Path, samples: array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as dest:
        dest.setnchannels(1)
        dest.setsampwidth(2)
        dest.setframerate(SAMPLE_RATE)
        dest.writeframes(samples.tobytes())


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in re.findall(r"[^。！？!?；;]+[。！？!?；;]?", text or "")]
    return [part for part in parts if part]


def _split_text(text: str, count: int) -> list[str]:
    sentences = _sentences(text)
    if count <= 1:
        return [text.strip()]
    if len(sentences) < count:
        compact = text.strip()
        if len(compact) < count:
            raise ValueError(f"旁白过短，无法拆成 {count} 个非空 Segment")
        cut_points = [round(len(compact) * index / count) for index in range(count + 1)]
        return [compact[cut_points[index]:cut_points[index + 1]].strip()
                for index in range(count)]
    weights = [len(sentence) for sentence in sentences]
    prefix = [0]
    for weight in weights:
        prefix.append(prefix[-1] + weight)
    target = prefix[-1] / count

    @lru_cache(maxsize=None)
    def solve(start: int, group: int):
        if group == count:
            return (0, ()) if start == len(sentences) else (float("inf"), ())
        remaining_groups = count - group
        max_end = len(sentences) - (remaining_groups - 1)
        best_cost, best_cuts = float("inf"), ()
        for end in range(start + 1, max_end + 1):
            chars = prefix[end] - prefix[start]
            tail_cost, tail_cuts = solve(end, group + 1)
            cost = (chars - target) ** 2 + tail_cost
            if cost < best_cost:
                best_cost, best_cuts = cost, (end,) + tail_cuts
        return best_cost, best_cuts

    _, cuts = solve(0, 0)
    result, start = [], 0
    for end in cuts:
        result.append("".join(sentences[start:end]).strip())
        start = end
    return result


def build_audio_windows(copywriting: dict, target_seconds: int) -> list[dict]:
    """以最少的 4–15 秒容器拆分全文，并优先在完整句子后断开。"""
    paragraphs = list(copywriting.get("paragraphs", []))
    full_text = "".join(item.get("text", "").strip() for item in paragraphs)
    if not full_text:
        raise ValueError("旁白没有段落")
    count = max(1, math.ceil(target_seconds / 15))
    if target_seconds / count < 4:
        raise ValueError("无法把旁白安排为 4–15 秒的自然语义段，请调整目标时长")
    texts = _split_text(full_text, count)
    base, extra = divmod(target_seconds, count)
    pieces = [{"text": text, "duration_s": base + (1 if index < extra else 0)}
              for index, text in enumerate(texts)]

    cursor = 0
    windows = []
    for index, piece in enumerate(pieces, 1):
        duration_ms = piece["duration_s"] * 1000
        windows.append({
            "unit_id": f"n_{index:02d}",
            "segment_id": f"seg_{index:02d}",
            "text": piece["text"],
            "start_ms": cursor,
            "end_ms": cursor + duration_ms,
        })
        cursor += duration_ms
    if cursor != target_seconds * 1000:
        raise AssertionError("音频窗口总时长不等于项目目标时长")
    return windows


def _bgm(total_seconds: int) -> array:
    chords = [(196.00, 246.94, 293.66), (174.61, 220.00, 261.63),
              (146.83, 196.00, 246.94), (164.81, 220.00, 261.63)]
    total = total_seconds * SAMPLE_RATE
    output = array("h", [0]) * total
    for index in range(total):
        t = index / SAMPLE_RATE
        chord = chords[min(int(t // 15), len(chords) - 1) % len(chords)]
        fade = min(1.0, t / 1.2, (total_seconds - t) / 1.2)
        pulse = 0.78 + 0.22 * math.sin(2 * math.pi * 0.08 * t)
        tone = sum(math.sin(2 * math.pi * frequency * t) for frequency in chord) / len(chord)
        output[index] = int(32767 * 0.075 * fade * pulse * tone)
    return output


def _mock_voice(duration_seconds: float) -> array:
    count = max(1, int(duration_seconds * SAMPLE_RATE))
    # demo 模式用很低的提示音代替在线 TTS，保证整条媒体链路仍可运行。
    return array("h", [int(900 * math.sin(2 * math.pi * 220 * index / SAMPLE_RATE))
                       for index in range(count)])


def _rate_value(value: str) -> int:
    match = re.fullmatch(r"([+-]?)(\d+)%", (value or "").strip())
    if not match:
        return 0
    number = int(match.group(2))
    return -number if match.group(1) == "-" else number


async def _edge_voice(text: str, voice: str, requested_rate: str,
                      usable_seconds: float, folder: Path, unit_id: str) -> tuple[array, str]:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("缺少 edge-tts；请执行 pip install -r backend/requirements.txt") from exc
    candidates = []
    for value in (_rate_value(requested_rate), 5, 15, 25, 35):
        if value not in candidates:
            candidates.append(value)
    for value in candidates:
        rate = f"{value:+d}%"
        mp3 = folder / f"{unit_id}_{value:+d}.mp3"
        wav = folder / f"{unit_id}_tts.wav"
        await edge_tts.Communicate(text=text, voice=voice, rate=rate).save(str(mp3))
        _run_ffmpeg(["-i", str(mp3), "-ac", "1", "-ar", str(SAMPLE_RATE),
                     "-c:a", "pcm_s16le", str(wav)])
        samples = _read_pcm(wav)
        if len(samples) / SAMPLE_RATE <= usable_seconds:
            return samples, rate
    raise ValueError(
        f"旁白“{text[:24]}…”即使提高到 +35% 仍超过 {usable_seconds:.2f}s，请缩短文案"
    )


async def build_master_audio(project, voice: str, music: str = "ambient",
                             mock: bool = False) -> dict:
    target_seconds = int(project.request.get("duration_s", 60))
    version = int((getattr(project, "audio", {}) or {}).get("version", 0)) + 1
    folder = AUDIO_ROOT / project.project_id / f"v{version}"
    folder.mkdir(parents=True, exist_ok=True)
    windows = build_audio_windows(project.copywriting, target_seconds)
    master = _bgm(target_seconds)
    voice_track = array("h", [0]) * (target_seconds * SAMPLE_RATE)
    requested_rate = "-10%"

    for unit in windows:
        window_seconds = (unit["end_ms"] - unit["start_ms"]) / 1000
        usable_seconds = window_seconds - LEAD_SECONDS - TAIL_SECONDS
        if mock:
            estimated = min(usable_seconds, max(1.0, len(unit["text"]) / 4.2))
            samples, actual_rate = _mock_voice(estimated), "mock"
        else:
            samples, actual_rate = await _edge_voice(
                unit["text"], voice, requested_rate, usable_seconds, folder, unit["unit_id"]
            )
        local_start = int(LEAD_SECONDS * SAMPLE_RATE)
        global_start = int(unit["start_ms"] / 1000 * SAMPLE_RATE) + local_start
        for offset, sample in enumerate(samples):
            at = global_start + offset
            if at >= len(master):
                break
            voice_track[at] = sample
            mixed = master[at] + int(sample * 0.94)
            master[at] = max(-32768, min(32767, mixed))
        unit["speech_start_ms"] = unit["start_ms"] + round(LEAD_SECONDS * 1000)
        unit["speech_end_ms"] = unit["speech_start_ms"] + round(len(samples) / SAMPLE_RATE * 1000)
        unit["tts_duration_ms"] = round(len(samples) / SAMPLE_RATE * 1000)
        unit["rate"] = actual_rate

    voice_path = folder / "voice_track.wav"
    bgm_path = folder / "bgm_bed.wav"
    master_path = folder / "master_audio.wav"
    _write_pcm(voice_path, voice_track)
    _write_pcm(bgm_path, _bgm(target_seconds))
    _write_pcm(master_path, master)

    slices = []
    for unit in windows:
        start = int(unit["start_ms"] / 1000 * SAMPLE_RATE)
        end = int(unit["end_ms"] / 1000 * SAMPLE_RATE)
        path = folder / f"audio_{unit['segment_id']}.wav"
        _write_pcm(path, master[start:end])
        slices.append({
            "segment_id": unit["segment_id"],
            "local_path": str(path),
            "url": _asset_url(path),
            "sha256": _sha256(path),
            "duration_ms": unit["end_ms"] - unit["start_ms"],
        })

    return {
        "status": "ready",
        "version": version,
        "voice_profile": {"engine": "edge-tts" if not mock else "mock",
                          "voice": voice, "requested_rate": requested_rate},
        "narration_units": windows,
        "music_cues": [{"cue_id": "m_01", "preset": music or "ambient",
                         "start_ms": 0, "end_ms": target_seconds * 1000, "gain_db": -22}],
        "voice_track_path": str(voice_path),
        "voice_track_url": _asset_url(voice_path),
        "bgm_path": str(bgm_path),
        "master_path": str(master_path),
        "master_url": _asset_url(master_path),
        "master_sha256": _sha256(master_path),
        "duration_ms": target_seconds * 1000,
        "slices": slices,
    }
