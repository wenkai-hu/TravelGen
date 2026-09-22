# -*- coding: utf-8 -*-
"""把连续 Shot 动态装入最长 15 秒的 Seedance Segment，不拆 Shot、不补时长。"""
from __future__ import annotations

from functools import lru_cache


SEGMENT_MIN_MS = 4_000
SEGMENT_MAX_MS = 15_000
MAX_REFERENCES_PER_SEGMENT = 9


def flatten_shots(storyboard: dict) -> list[dict]:
    return [shot for scene in storyboard.get("scenes", [])
            for shot in scene.get("shot_list", [])]


def find_segment(storyboard: dict, segment_id: str) -> dict | None:
    return next((segment for segment in storyboard.get("segments", [])
                 if segment.get("segment_id") == segment_id), None)


def segment_for_shot(storyboard: dict, shot_id: int) -> dict | None:
    shot = next((item for item in flatten_shots(storyboard)
                 if item.get("shot_id") == shot_id), None)
    return find_segment(storyboard, shot.get("segment_id")) if shot else None


def _shot_ms(shot: dict) -> int:
    value = shot.get("duration_s")
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Shot {shot.get('shot_id')} 的 duration_s 非法")
    duration = int(round(float(value) * 1000))
    if duration > SEGMENT_MAX_MS:
        raise ValueError(f"Shot {shot.get('shot_id')} 为 {duration / 1000:g}s，超过 Seedance 15 秒上限")
    return duration


def partition_shots(shots: list[dict]) -> list[list[dict]]:
    """连续分组 DP：最少调用次数；同调用数时优先让前段更满，但绝不拆 Shot。"""
    durations = [_shot_ms(shot) for shot in shots]
    n = len(shots)

    @lru_cache(maxsize=None)
    def solve(start: int):
        if start == n:
            return (0, (), ())
        total = 0
        candidates = []
        for end in range(start + 1, n + 1):
            total += durations[end - 1]
            if total > SEGMENT_MAX_MS:
                break
            if total < SEGMENT_MIN_MS:
                continue
            tail = solve(end)
            if tail is None:
                continue
            candidates.append((1 + tail[0], (end,) + tail[1], (total,) + tail[2]))
        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0], tuple(-duration for duration in item[2])))

    solution = solve(0)
    if solution is None:
        detail = "+".join(f"{value / 1000:g}" for value in durations)
        raise ValueError(
            f"Shot 时长序列 {detail}s 无法在不拆 Shot 的条件下组成 4–15 秒 Segment；请重新规划 Shot 时长"
        )
    groups, cursor = [], 0
    for end in solution[1]:
        groups.append(shots[cursor:end])
        cursor = end
    return groups


def _unique(values, limit=None):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
        if limit is not None and len(result) >= limit:
            break
    return result


def _assign_missing_narration(shots: list[dict], copywriting: dict | None) -> None:
    """按 Shot 时长切分已确认原文，确保模型不会增删或改写正式旁白。"""
    text = "".join(item.get("text", "").strip() for item in (copywriting or {}).get("paragraphs", []))
    if not text:
        for shot in shots:
            shot["narration"] = str(shot.get("narration", "")).strip()
        return
    # KIMI 若已经把确认原文完整、无改写地分配给 Shot，保留它的语义边界。
    existing = "".join(str(shot.get("narration", "")).strip() for shot in shots)
    if existing == text:
        return
    total_weight = sum(_shot_ms(shot) for shot in shots)
    cursor = 0
    consumed = 0
    for index, shot in enumerate(shots):
        if index == len(shots) - 1:
            end = len(text)
        else:
            consumed += _shot_ms(shot)
            target = round(len(text) * consumed / total_weight)
            candidates = [pos + 1 for pos in range(max(cursor + 1, target - 4), min(len(text), target + 8))
                          if text[pos] in "。！？；!?;"]
            end = min(candidates, key=lambda pos: abs(pos - target)) if candidates else target
        shot["narration"] = text[cursor:end].strip()
        cursor = end


def attach_segment_plan(storyboard: dict, copywriting: dict | None = None) -> dict:
    """由已规划的 Shot 时长动态组成 Segment；Segment 时长就是成员 Shot 时长之和。"""
    shots = flatten_shots(storyboard)
    if not shots:
        raise ValueError("Storyboard 没有 Shot")
    _assign_missing_narration(shots, copywriting)
    groups = partition_shots(shots)
    segments = []
    global_cursor = 0
    for index, group in enumerate(groups, 1):
        segment_id = f"seg_{index:02d}"
        local_cursor = 0
        for shot in group:
            duration = _shot_ms(shot)
            shot["segment_id"] = segment_id
            shot["segment_local_start_ms"] = local_cursor
            shot["segment_local_end_ms"] = local_cursor + duration
            shot["timeline_start_ms"] = global_cursor + local_cursor
            shot["timeline_end_ms"] = global_cursor + local_cursor + duration
            local_cursor += duration
        references = _unique(
            (asset_id for shot in group for asset_id in shot.get("reference_asset_ids", [])),
            MAX_REFERENCES_PER_SEGMENT + 1,
        )
        if len(references) > MAX_REFERENCES_PER_SEGMENT:
            raise ValueError(f"{segment_id} 去重后有 {len(references)} 张参考图，超过 9 张上限")
        segments.append({
            "segment_id": segment_id,
            "timeline_start_ms": global_cursor,
            "timeline_end_ms": global_cursor + local_cursor,
            "duration_ms": local_cursor,
            "shot_ids": [shot["shot_id"] for shot in group],
            "narration_text": "".join(shot.get("narration", "").strip() for shot in group),
            "reference_asset_ids": references,
            "transition_note": "保持段内地点、光线和色调连贯，镜头沿运动方向或相似构图自然转场",
            "status": "pending",
        })
        global_cursor += local_cursor
    storyboard["storyboard_version"] = 3
    storyboard["duration_ms"] = global_cursor
    storyboard["segments"] = segments
    return storyboard


def refresh_segment(storyboard: dict, segment_id: str) -> dict:
    """刷新不改变 Shot 时长/顺序的字段；时长变化必须重新运行全局装箱。"""
    segment = find_segment(storyboard, segment_id)
    if segment is None:
        raise ValueError(f"Segment {segment_id} 不存在")
    by_id = {shot.get("shot_id"): shot for shot in flatten_shots(storyboard)}
    shots = [by_id[shot_id] for shot_id in segment.get("shot_ids", []) if shot_id in by_id]
    references = _unique(
        (asset_id for shot in shots for asset_id in shot.get("reference_asset_ids", [])),
        MAX_REFERENCES_PER_SEGMENT + 1,
    )
    if len(references) > MAX_REFERENCES_PER_SEGMENT:
        raise ValueError(f"{segment_id} 去重后有 {len(references)} 张参考图，超过 9 张上限")
    segment["reference_asset_ids"] = references
    segment["narration_text"] = "".join(shot.get("narration", "").strip() for shot in shots)
    return segment


def validate_segment_plan(storyboard: dict, expected_duration_ms: int | None = None) -> list[str]:
    errors = []
    shots_list = flatten_shots(storyboard)
    shots = {shot.get("shot_id"): shot for shot in shots_list}
    segments = storyboard.get("segments", [])
    cursor = 0
    assigned = []
    expected_order = [shot.get("shot_id") for shot in shots_list]
    for segment in segments:
        sid = segment.get("segment_id")
        start, end = segment.get("timeline_start_ms"), segment.get("timeline_end_ms")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            errors.append(f"{sid}: 时间窗非法")
            continue
        if start != cursor:
            errors.append(f"{sid}: 应从 {cursor}ms 开始，实际 {start}ms")
        duration = end - start
        if not SEGMENT_MIN_MS <= duration <= SEGMENT_MAX_MS:
            errors.append(f"{sid}: 时长 {duration}ms 不在 4–15 秒")
        shot_ids = segment.get("shot_ids", [])
        member_duration = 0
        for shot_id in shot_ids:
            shot = shots.get(shot_id)
            if not shot:
                errors.append(f"{sid}: Shot {shot_id} 不存在")
                continue
            member_duration += _shot_ms(shot)
            if shot.get("segment_id") != sid:
                errors.append(f"Shot {shot_id}: segment_id 与 {sid} 不一致")
        if member_duration != duration:
            errors.append(f"{sid}: Segment 时长 {duration}ms 不等于 Shot 合计 {member_duration}ms")
        assigned.extend(shot_ids)
        if len(segment.get("reference_asset_ids", [])) > MAX_REFERENCES_PER_SEGMENT:
            errors.append(f"{sid}: 参考图超过 {MAX_REFERENCES_PER_SEGMENT} 张")
        cursor = end
    if assigned != expected_order:
        errors.append("Shot 必须按原顺序连续且仅分配一次")
    target = expected_duration_ms if expected_duration_ms is not None else storyboard.get("duration_ms")
    if target is not None and cursor != int(target):
        errors.append(f"Segment 总时长 {cursor}ms 与目标 {target}ms 不一致")
    return errors
