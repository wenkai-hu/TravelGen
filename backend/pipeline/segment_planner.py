# -*- coding: utf-8 -*-
"""新分镜按 Shot 生成；Segment 仅保留为旧任务和渲染的内部片段记录。"""
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
    return duration


def split_shot_ms(duration: int) -> list[int]:
    """一个视觉 Shot 超过 15 秒时拆成可续写的 4–15 秒调用。"""
    if duration < SEGMENT_MIN_MS:
        raise ValueError("Shot 时长不能短于 4 秒")
    if duration % 1000:
        raise ValueError("Shot 时长必须为整秒")
    seconds = duration // 1000
    count = (seconds + 14) // 15
    parts = [15] * (count - 1) + [seconds - 15 * (count - 1)]
    if count > 1 and parts[-1] < 4:
        parts[-2] -= 4 - parts[-1]
        parts[-1] = 4
    parts = [part * 1000 for part in parts]
    if min(parts) < SEGMENT_MIN_MS:
        raise ValueError("Shot 无法拆成 4–15 秒的续写片段")
    return parts


def _split_narration(text: str, parts: list[int]) -> list[str]:
    """按片段时长分配同一 Shot 的旁白，保持连接后与原文完全一致。"""
    if len(parts) == 1:
        return [text]
    result, cursor, elapsed = [], 0, 0
    for duration in parts[:-1]:
        elapsed += duration
        target = round(len(text) * elapsed / sum(parts))
        candidates = [i + 1 for i in range(max(cursor, target - 6), min(len(text), target + 7))
                      if text[i] in "。！？；，、!?;,"]
        end = min(candidates, key=lambda i: abs(i - target)) if candidates else target
        result.append(text[cursor:end])
        cursor = end
    result.append(text[cursor:])
    return result


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
    """每个 Shot 独占一张图；一次调用只生成该 Shot，超时长部分依次续写。"""
    if storyboard.get("storyboard_version") == 3:
        return _attach_legacy_segment_plan(storyboard, copywriting)
    shots = flatten_shots(storyboard)
    if not shots:
        raise ValueError("Storyboard 没有 Shot")
    _assign_missing_narration(shots, copywriting)
    segments = []
    global_cursor = 0
    used_refs: set[str] = set()
    for shot in shots:
        refs = shot.get("reference_asset_ids", [])
        if len(refs) != 1:
            raise ValueError(f"Shot {shot.get('shot_id')} 必须且只能绑定一张参考图")
        if refs[0] in used_refs:
            raise ValueError(f"参考图 {refs[0]} 已被其他 Shot 使用；每张图全片只能使用一次")
        used_refs.add(refs[0])
        parts = split_shot_ms(_shot_ms(shot))
        narrations = _split_narration(str(shot.get("narration", "")), parts)
        shot["timeline_start_ms"] = global_cursor
        shot["timeline_end_ms"] = global_cursor + sum(parts)
        shot["segment_ids"] = []
        for part_index, (duration, narration) in enumerate(zip(parts, narrations), 1):
            segment_id = f"seg_{len(segments) + 1:02d}"
            previous_id = shot["segment_ids"][-1] if shot["segment_ids"] else None
            shot["segment_ids"].append(segment_id)
            segments.append({
                "segment_id": segment_id,
                "timeline_start_ms": global_cursor,
                "timeline_end_ms": global_cursor + duration,
                "duration_ms": duration,
                "shot_ids": [shot["shot_id"]],
                "narration_text": narration,
                "reference_asset_ids": refs[:],
                "continuation_index": part_index,
                "continuation_total": len(parts),
                "previous_segment_id": previous_id,
                "status": "pending",
            })
            global_cursor += duration
        shot["segment_id"] = shot["segment_ids"][0]
        shot["segment_local_start_ms"] = 0
        shot["segment_local_end_ms"] = parts[0]
    storyboard["storyboard_version"] = 4
    storyboard["duration_ms"] = global_cursor
    storyboard["segments"] = segments
    return storyboard


def _attach_legacy_segment_plan(storyboard: dict, copywriting: dict | None = None) -> dict:
    """已有 v3 项目重排时保留原有多 Shot Segment 语义。"""
    shots = flatten_shots(storyboard)
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
        refs = _unique(asset_id for shot in group for asset_id in shot.get("reference_asset_ids", []))
        if len(refs) > MAX_REFERENCES_PER_SEGMENT:
            raise ValueError(f"{segment_id} 去重后参考图超过上限")
        segments.append({
            "segment_id": segment_id,
            "timeline_start_ms": global_cursor,
            "timeline_end_ms": global_cursor + local_cursor,
            "duration_ms": local_cursor,
            "shot_ids": [shot["shot_id"] for shot in group],
            "narration_text": "".join(str(shot.get("narration", "")).strip() for shot in group),
            "reference_asset_ids": refs,
            "transition_note": "保持段内地点、光线和色调连贯，镜头自然转场",
            "status": "pending",
        })
        global_cursor += local_cursor
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
    if storyboard.get("storyboard_version", 0) >= 4:
        if len(shots) != 1:
            raise ValueError(f"{segment_id} 必须只包含一个 Shot")
        shot = shots[0]
        parts = [find_segment(storyboard, sid) for sid in shot.get("segment_ids", [])]
        narrations = _split_narration(str(shot.get("narration", "")),
                                      [part["duration_ms"] for part in parts])
        for part, narration in zip(parts, narrations):
            part["reference_asset_ids"] = list(shot.get("reference_asset_ids", []))
            part["narration_text"] = narration
        return segment
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
            if (sid not in shot.get("segment_ids", []) if storyboard.get("storyboard_version", 0) >= 4
                    else shot.get("segment_id") != sid):
                errors.append(f"Shot {shot_id}: segment_id 与 {sid} 不一致")
        if storyboard.get("storyboard_version", 0) >= 4:
            member_duration = duration if len(shot_ids) == 1 else member_duration
        if member_duration != duration:
            errors.append(f"{sid}: Segment 时长 {duration}ms 不等于 Shot 合计 {member_duration}ms")
        assigned.extend(shot_ids)
        if len(segment.get("reference_asset_ids", [])) > MAX_REFERENCES_PER_SEGMENT:
            errors.append(f"{sid}: 参考图超过 {MAX_REFERENCES_PER_SEGMENT} 张")
        cursor = end
    if storyboard.get("storyboard_version", 0) >= 4:
        assigned = list(dict.fromkeys(assigned))
    if assigned != expected_order:
        errors.append("Shot 必须按原顺序连续且仅分配一次")
    if storyboard.get("storyboard_version", 0) >= 4:
        refs = [shot.get("reference_asset_ids", []) for shot in shots_list]
        if any(len(item) != 1 for item in refs) or len({item[0] for item in refs if item}) != len(refs):
            errors.append("每个 Shot 必须独占一张参考图")
        by_segment = {segment.get("segment_id"): segment for segment in segments}
        for shot in shots_list:
            part_ids = shot.get("segment_ids", [])
            if not part_ids or any(sid not in by_segment for sid in part_ids):
                errors.append(f"Shot {shot.get('shot_id')}: 缺少生成片段")
                continue
            part_total = sum(by_segment[sid]["duration_ms"] for sid in part_ids)
            if part_total != _shot_ms(shot):
                errors.append(f"Shot {shot.get('shot_id')}: 生成片段总时长与 Shot 不一致")
    target = expected_duration_ms if expected_duration_ms is not None else storyboard.get("duration_ms")
    if target is not None and cursor != int(target):
        errors.append(f"Segment 总时长 {cursor}ms 与目标 {target}ms 不一致")
    return errors
