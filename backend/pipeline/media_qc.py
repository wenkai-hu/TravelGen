# -*- coding: utf-8 -*-
"""Seedance 原生 PCM 音轨的轻量 QA；不把启发式底噪判断冒充音乐识别。"""
from __future__ import annotations

import array
import math
import sys
import wave
from pathlib import Path


WINDOW_MS = 20
DB_FLOOR = -120.0


def _db(value: float) -> float:
    return max(DB_FLOOR, 20.0 * math.log10(max(value, 1e-12)))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return DB_FLOOR
    ordered = sorted(values)
    at = (len(ordered) - 1) * q / 100
    lo, hi = math.floor(at), math.ceil(at)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - at) + ordered[hi] * (at - lo)


def inspect_wav(path: str | Path, expected_duration_s: float | None = None) -> dict:
    path = Path(path)
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        width = source.getsampwidth()
        frames = source.getnframes()
        raw = source.readframes(frames)
    if channels < 1 or width != 2:
        raise RuntimeError(f"只支持 PCM16 WAV：{path}")
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    mono = [sum(samples[index:index + channels]) / (channels * 32768.0)
            for index in range(0, len(samples), channels)]
    window = max(1, round(rate * WINDOW_MS / 1000))
    levels = []
    for start in range(0, max(0, len(mono) - window + 1), window):
        chunk = mono[start:start + window]
        levels.append(_db(math.sqrt(sum(value * value for value in chunk) / len(chunk))))
    levels = levels or [DB_FLOOR]
    speech_level = _percentile(levels, 90)
    gate = speech_level - 25
    signal_present = speech_level > -70
    active = ([index for index, level in enumerate(levels) if level >= gate]
              if signal_present else [])
    duration = frames / rate
    head_silence = min(duration, active[0] * WINDOW_MS / 1000) if active else 0.0
    offset = min(duration, (active[-1] + 1) * WINDOW_MS / 1000) if active else 0
    tail_silence = max(0.0, duration - offset)
    duration_ok = expected_duration_s is None or abs(duration - expected_duration_s) <= 0.2
    return {
        "status": "passed" if active and duration_ok else "warning",
        "has_audio": bool(active),
        "duration_seconds": round(duration, 4),
        "expected_duration_seconds": expected_duration_s,
        "duration_ok": duration_ok,
        "head_silence_seconds": round(head_silence, 3),
        "head_activity_warning": bool(active and head_silence < 0.15),
        "tail_silence_seconds": round(tail_silence, 3),
        "tail_activity_warning": bool(active and tail_silence < 0.12),
        "speech_level_p90_dbfs": round(speech_level, 2),
        "music_detection": "not_available",
        "bgm_policy": "forbidden_by_prompt_manual_review_supported",
    }
