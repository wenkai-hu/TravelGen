# -*- coding: utf-8 -*-
"""把可编辑 Shot 归入 Seedance Segment，并写入精确时间窗。"""
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


def _partition_shots(shots: list[dict], target_ms: list[int]) -> list[list[dict]]:
    """按顺序把 N 个 Shot 分给 K 个 Segment，最小化各组原始时长与目标时长差。"""
    n, k = len(shots), len(target_ms)
    if n < k:
        raise ValueError(f"Shot 数量 {n} 少于 Segment 数量 {k}，无法保证每段至少一个 Shot")
    weights = [max(1, int(round(float(shot.get("duration_s", 1)) * 1000))) for shot in shots]
    prefix = [0]
    for value in weights:
        prefix.append(prefix[-1] + value)

    @lru_cache(maxsize=None)
    def solve(start: int, group: int):
        if group == k:
            return (0, ()) if start == n else (float("inf"), ())
        remaining_groups = k - group
        best_cost, best_cuts = float("inf"), ()
        max_end = n - (remaining_groups - 1)
        for end in range(start + 1, max_end + 1):
            group_sum = prefix[end] - prefix[start]
            tail_cost, tail_cuts = solve(end, group + 1)
            cost = (group_sum - target_ms[group]) ** 2 + tail_cost
            if cost < best_cost:
                best_cost, best_cuts = cost, (end,) + tail_cuts
        return best_cost, best_cuts

    _, cuts = solve(0, 0)
    groups, start = [], 0
    for end in cuts:
        groups.append(shots[start:end])
        start = end
    return groups


def _allocate_ranges(shots: list[dict], start_ms: int, end_ms: int) -> None:
    total_ms = end_ms - start_ms
    weights = [max(1, int(round(float(shot.get("duration_s", 1)) * 1000))) for shot in shots]
    weight_sum = sum(weights)
    cursor = start_ms
    remaining = total_ms
    for index, (shot, weight) in enumerate(zip(shots, weights)):
        if index == len(shots) - 1:
            duration = remaining
        else:
            duration = max(500, int(round(total_ms * weight / weight_sum)))
            minimum_for_rest = 500 * (len(shots) - index - 1)
            duration = min(duration, remaining - minimum_for_rest)
        shot["timeline_start_ms"] = cursor
        shot["timeline_end_ms"] = cursor + duration
        shot["duration_s"] = round(duration / 1000, 3)
        cursor += duration
        remaining -= duration


def _unique(values, limit=None):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
        if limit is not None and len(result) >= limit:
            break
    return result


def refresh_segment(storyboard: dict, segment_id: str) -> dict:
    """Shot 被编辑后重算该 Segment 的段内时间与参考图集合。"""
    segment = find_segment(storyboard, segment_id)
    if segment is None:
        raise ValueError(f"Segment {segment_id} 不存在")
    by_id = {shot.get("shot_id"): shot for shot in flatten_shots(storyboard)}
    shots = [by_id[shot_id] for shot_id in segment.get("shot_ids", []) if shot_id in by_id]
    if not shots:
        raise ValueError(f"Segment {segment_id} 没有 Shot")
    _allocate_ranges(shots, int(segment["timeline_start_ms"]), int(segment["timeline_end_ms"]))
    references = _unique(
        (asset_id for shot in shots for asset_id in shot.get("reference_asset_ids", [])),
        MAX_REFERENCES_PER_SEGMENT + 1,
    )
    if len(references) > MAX_REFERENCES_PER_SEGMENT:
        raise ValueError(f"{segment_id} 去重后有 {len(references)} 张参考图，超过 9 张上限")
    segment["reference_asset_ids"] = references
    return segment


def attach_segment_plan(storyboard: dict, audio: dict) -> dict:
    """以音频自然窗口为 Segment，按顺序分配 Shot，并补全图片池和本地时间。"""
    shots = flatten_shots(storyboard)
    units = list(audio.get("narration_units", []))
    if not shots:
        raise ValueError("Storyboard 没有 Shot")
    if not units:
        raise ValueError("音频没有 narration_units，不能规划 Segment")
    targets = [int(unit["end_ms"]) - int(unit["start_ms"]) for unit in units]
    for index, duration in enumerate(targets, 1):
        if not SEGMENT_MIN_MS <= duration <= SEGMENT_MAX_MS:
            raise ValueError(f"音频窗口 {index} 为 {duration}ms，Segment 必须为 4–15 秒")

    groups = _partition_shots(shots, targets)
    slices = {item.get("segment_id"): item for item in audio.get("slices", [])}
    segments = []
    for index, (unit, group) in enumerate(zip(units, groups), 1):
        segment_id = unit.get("segment_id") or f"seg_{index:02d}"
        start_ms, end_ms = int(unit["start_ms"]), int(unit["end_ms"])
        _allocate_ranges(group, start_ms, end_ms)
        for shot in group:
            shot["segment_id"] = segment_id
            shot["narration_unit_ids"] = [unit["unit_id"]]
        references = _unique(
            (asset_id for shot in group for asset_id in shot.get("reference_asset_ids", [])),
            MAX_REFERENCES_PER_SEGMENT + 1,
        )
        if len(references) > MAX_REFERENCES_PER_SEGMENT:
            raise ValueError(f"{segment_id} 去重后有 {len(references)} 张参考图，超过 9 张上限")
        audio_slice = slices.get(segment_id, {})
        segments.append({
            "segment_id": segment_id,
            "timeline_start_ms": start_ms,
            "timeline_end_ms": end_ms,
            "duration_ms": end_ms - start_ms,
            "shot_ids": [shot["shot_id"] for shot in group],
            "narration_unit_ids": [unit["unit_id"]],
            "reference_asset_ids": references,
            "transition_note": "保持段内地点、光线和色调连贯，镜头沿运动方向或相似构图自然转场",
            "audio_slice_path": audio_slice.get("local_path", ""),
            "audio_slice_url": audio_slice.get("url", ""),
            "audio_slice_sha256": audio_slice.get("sha256", ""),
            "status": "pending",
        })
    storyboard["storyboard_version"] = 2
    storyboard["segments"] = segments
    return storyboard


def validate_segment_plan(storyboard: dict, master_duration_ms: int) -> list[str]:
    errors = []
    shots = {shot.get("shot_id"): shot for shot in flatten_shots(storyboard)}
    segments = storyboard.get("segments", [])
    cursor = 0
    assigned = []
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
        if not shot_ids:
            errors.append(f"{sid}: 没有 Shot")
        for shot_id in shot_ids:
            shot = shots.get(shot_id)
            if not shot:
                errors.append(f"{sid}: Shot {shot_id} 不存在")
            elif shot.get("segment_id") != sid:
                errors.append(f"Shot {shot_id}: segment_id 与 {sid} 不一致")
        assigned.extend(shot_ids)
        if len(segment.get("reference_asset_ids", [])) > MAX_REFERENCES_PER_SEGMENT:
            errors.append(f"{sid}: 参考图超过 {MAX_REFERENCES_PER_SEGMENT} 张")
        cursor = end
    if cursor != master_duration_ms:
        errors.append(f"Segment 总时长 {cursor}ms 与母带 {master_duration_ms}ms 不一致")
    if sorted(assigned) != sorted(shots):
        errors.append("存在未分配或重复分配的 Shot")
    return errors
