# -*- coding: utf-8 -*-
"""视觉 RAG 编排工具：参考图缓存、VLM 结果汇总、分镜绑定和 Seedance 输入编译。"""

import base64
import hashlib
import io
import json
import mimetypes
import os
import urllib.error
import urllib.request

from PIL import Image


REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
REFERENCE_ROOT = os.path.join(REPO, "assets", "references")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_REFERENCES_PER_SHOT = 3
MAX_REFERENCES_PER_SEGMENT = 9


def place_id(city: str, location: str) -> str:
    raw = f"{(city or '').strip()}|{(location or '').strip()}"
    return "place_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def candidate_from_user_asset(asset: dict, city: str, location: str) -> dict:
    """把创建项目时已有的 assets URL 也登记成服务端候选。"""
    url = str(asset.get("url", "")).strip()
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return {
        "candidate_id": f"ref_{digest}",
        "query": f"{city} {location}".strip(),
        "image_url": url,
        "title": "用户提供的参考图",
        "source_page_url": "",
        "provider": "user",
    }


def _validated_image(data: bytes) -> tuple[str, int, int]:
    if not data:
        raise RuntimeError("下载到的图片为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"图片超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB 限制")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            fmt = (image.format or "JPEG").upper()
            width, height = image.size
    except Exception as exc:
        raise RuntimeError("下载内容不是可解析图片") from exc
    extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt, ".jpg")
    return extension, width, height


def cache_candidate(project_id: str, candidate: dict, city: str, location: str) -> dict:
    """下载用户确认的候选图，校验后保存为不可变 ReferenceAsset。"""
    url = str(candidate.get("image_url", ""))
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("参考图只支持 http/https URL")
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 TravelGen/1.0",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*",
    })
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_IMAGE_BYTES:
                raise RuntimeError(f"图片超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB 限制")
            data = response.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"参考图下载失败: {exc.reason}") from exc
    extension, width, height = _validated_image(data)
    content_hash = hashlib.sha256(data).hexdigest()
    asset_id = f"ref_{content_hash[:16]}"
    folder = os.path.join(REFERENCE_ROOT, project_id)
    os.makedirs(folder, exist_ok=True)
    local_path = os.path.join(folder, f"{asset_id}{extension}")
    with open(local_path, "wb") as f:
        f.write(data)
    return {
        "asset_id": asset_id,
        "candidate_id": candidate.get("candidate_id"),
        "place_id": place_id(city, location),
        "place_name": location,
        "city": city,
        "original_url": url,
        "source_page_url": candidate.get("source_page_url", ""),
        "title": candidate.get("title", ""),
        "provider": candidate.get("provider", ""),
        "cached_url": f"/assets/references/{project_id}/{asset_id}{extension}",
        "local_path": local_path,
        "sha256": content_hash,
        "width": width,
        "height": height,
        "user_verified": True,
        "rights_status": "unknown",
        "analysis_status": "pending",
    }


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(items, limit=30) -> list[str]:
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def build_visual_profile(city: str, location: str, assets: list[dict]) -> dict:
    """把逐图 VLM observation 汇总成 LLM 可消费、仍保留证据来源的景点视觉档案。"""
    successful = [asset for asset in assets if asset.get("analysis_status") == "completed"]
    stable_features, view_catalog = [], []
    allowed, uncertain, visible, risk_lists = [], [], [], []
    for asset in successful:
        analysis = (asset.get("observation") or {}).get("analysis") or {}
        aid = asset["asset_id"]
        for text in _strings(analysis.get("must_keep_candidates")):
            stable_features.append({
                "text": text,
                "evidence_asset_ids": [aid],
                "strength": "image_observed",
            })
        visible.extend(_strings(analysis.get("visible_elements")))
        allowed.extend(_strings(analysis.get("allowed_changes")))
        risks = _strings(analysis.get("unsupported_or_risky_shots"))
        risk_lists.append(risks)
        uncertain.extend(_strings(analysis.get("uncertain")))
        view_catalog.append({
            "asset_id": aid,
            "summary": str(analysis.get("summary", "")),
            "visible_elements": _strings(analysis.get("visible_elements")),
            "spatial_layout": _strings(analysis.get("spatial_layout")),
            "architecture_and_materials": _strings(analysis.get("architecture_and_materials")),
            "viewpoint": analysis.get("viewpoint") if isinstance(analysis.get("viewpoint"), dict) else {},
            "lighting_weather_season": analysis.get("lighting_weather_season")
            if isinstance(analysis.get("lighting_weather_season"), dict) else {},
            "must_keep_candidates": _strings(analysis.get("must_keep_candidates")),
            "allowed_changes": _strings(analysis.get("allowed_changes")),
            "suitable_shots": _strings(analysis.get("suitable_shots")),
            "unsupported_or_risky_shots": risks,
        })
    # 只有所有已选视角都明确不支持的镜头才成为地点级禁区；单图局限保留在 view_catalog。
    unsupported = ([risk for risk in risk_lists[0]
                    if all(risk in other for other in risk_lists[1:])]
                   if risk_lists else [])
    return {
        "profile_version": "place_visual_profile_v1",
        "place_id": place_id(city, location),
        "place_name": location,
        "city": city,
        "reference_asset_ids": [asset["asset_id"] for asset in successful],
        "user_verified_place_identity": bool(successful),
        "visible_elements": _unique(visible),
        "stable_features": stable_features[:30],
        "must_keep": _unique([item["text"] for item in stable_features], 20),
        "allowed_changes": _unique(allowed, 15),
        "unsupported_shots": _unique(unsupported, 15),
        "uncertain": _unique(uncertain, 15),
        "view_catalog": view_catalog,
    }


def grounding_for_prompt(profile: dict, include_catalog: bool = False) -> str:
    """生成提示词注入块；仅保留视觉事实，不包含调用耗时、token 等运维字段。"""
    if not profile or not profile.get("reference_asset_ids"):
        return "（用户尚未确认可用的实景参考图；不得编造特定地标外观或不受支持的机位。）"
    fields = (
        "place_id", "place_name", "city", "visible_elements", "stable_features",
        "must_keep", "allowed_changes", "unsupported_shots", "uncertain",
    )
    compact = {field: profile.get(field) for field in fields}
    if include_catalog:
        compact["view_catalog"] = profile.get("view_catalog", [])
    return json.dumps(compact, ensure_ascii=False, indent=2)


def _shot_text(shot: dict) -> str:
    camera = shot.get("camera") if isinstance(shot.get("camera"), dict) else {}
    return " ".join(str(shot.get(key, "")) for key in ("subject", "background", "shot_size", "prompt")) + \
        " " + " ".join(str(camera.get(key, "")) for key in ("type", "movement", "angle"))


def _catalog_score(shot: dict, entry: dict) -> int:
    text = _shot_text(shot)
    score = 0
    viewpoint = entry.get("viewpoint") if isinstance(entry.get("viewpoint"), dict) else {}
    for value in (viewpoint.get("angle"), viewpoint.get("shot_size")):
        if value and str(value) in text:
            score += 3
    terms = entry.get("visible_elements", []) + entry.get("suitable_shots", [])
    for term in terms:
        for token in str(term).replace("，", "、").split("、"):
            token = token.strip()
            if len(token) >= 2 and token in text:
                score += 1
    return score


def bind_storyboard_references(storyboard: dict, profile: dict) -> dict:
    """校正 LLM 给出的引用 ID；缺失或非法时按视角/主体目录自动补齐。"""
    valid_ids = set(profile.get("reference_asset_ids", []))
    catalog = [entry for entry in profile.get("view_catalog", []) if entry.get("asset_id") in valid_ids]
    for scene in storyboard.get("scenes", []):
        scene.setdefault("place_id", profile.get("place_id"))
        for shot in scene.get("shot_list", []):
            requested = shot.get("reference_asset_ids")
            selected = [aid for aid in requested if aid in valid_ids] if isinstance(requested, list) else []
            if not selected and catalog:
                ranked = sorted(catalog, key=lambda entry: _catalog_score(shot, entry), reverse=True)
                selected = [entry["asset_id"] for entry in ranked[:1]]
            selected = selected[:MAX_REFERENCES_PER_SHOT]
            shot["place_id"] = profile.get("place_id")
            shot["reference_asset_ids"] = selected
            shot["reference_roles"] = [
                {"asset_id": aid, "role": "identity_and_composition" if i == 0 else "detail"}
                for i, aid in enumerate(selected)
            ]
            selected_entries = [entry for entry in catalog if entry.get("asset_id") in selected]
            best_score = max((_catalog_score(shot, entry) for entry in selected_entries), default=0)
            shot["grounding_strength"] = (
                "strong" if best_score >= 3 else "medium" if best_score >= 1
                else "weak" if selected else "none")
            selected_must_keep = [text for entry in selected_entries
                                  for text in entry.get("must_keep_candidates", [])]
            selected_allowed = [text for entry in selected_entries
                                for text in entry.get("allowed_changes", [])]
            selected_risks = [text for entry in selected_entries
                              for text in entry.get("unsupported_or_risky_shots", [])]
            shot["must_keep"] = _unique(
                _strings(shot.get("must_keep")) + selected_must_keep, 12)
            shot["allowed_changes"] = _unique(
                _strings(shot.get("allowed_changes")) + selected_allowed, 10)
            shot["unsupported_or_risky_shots"] = _unique(selected_risks, 10)
    return storyboard


def _local_data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def compile_shot_input(project, shot: dict) -> tuple[str, list[str]]:
    """Shot 的引用 ID → 顺序稳定的原始图片附件与显式约束 Prompt。"""
    assets = {asset.get("asset_id"): asset for asset in getattr(project, "reference_assets", [])}
    selected = [assets[aid] for aid in shot.get("reference_asset_ids", [])
                if aid in assets and assets[aid].get("local_path")]
    images = [_local_data_uri(asset["local_path"]) for asset in selected[:MAX_REFERENCES_PER_SHOT]]
    if not images:
        return shot["prompt"], []

    refs = "、".join(f"图片{i}" for i in range(1, len(images) + 1))
    must_keep = "；".join(_strings(shot.get("must_keep"))) or "参考图中的真实主体和空间结构"
    allowed = "；".join(_strings(shot.get("allowed_changes"))) or "自然光线和少量动态元素"
    unsupported = "；".join(_strings(shot.get("unsupported_or_risky_shots")))
    suffix = (
        f"\n\n【实景参考约束】{refs}均为用户确认的该景点实景。"
        f"必须保持：{must_keep}。允许改变：{allowed}。"
        "不得凭空增加新的标志性建筑，不得改变主要道路、建筑、山水的相对位置。"
    )
    if unsupported:
        suffix += f"参考图不支持的内容：{unsupported}；不要生成这些视角或结构。"
    return shot["prompt"].rstrip() + suffix, images


def compile_segment_input(project, segment: dict) -> tuple[str, list[str]]:
    """把段内多个 Shot、图片绑定和音频语义编译为一次 Seedance 输入。"""
    shots_by_id = {
        shot.get("shot_id"): shot
        for scene in getattr(project, "storyboard", {}).get("scenes", [])
        for shot in scene.get("shot_list", [])
    }
    shots = [shots_by_id[shot_id] for shot_id in segment.get("shot_ids", [])
             if shot_id in shots_by_id]
    if not shots:
        raise ValueError(f"{segment.get('segment_id')} 没有可编译的 Shot")
    assets = {asset.get("asset_id"): asset for asset in getattr(project, "reference_assets", [])}
    ordered_ids = []
    for shot in shots:
        for asset_id in shot.get("reference_asset_ids", []):
            if asset_id in assets and assets[asset_id].get("local_path") and asset_id not in ordered_ids:
                ordered_ids.append(asset_id)
    if len(ordered_ids) > MAX_REFERENCES_PER_SEGMENT:
        raise ValueError(
            f"{segment.get('segment_id')} 去重后有 {len(ordered_ids)} 张参考图，超过 {MAX_REFERENCES_PER_SEGMENT} 张"
        )
    images = [_local_data_uri(assets[asset_id]["local_path"]) for asset_id in ordered_ids]
    label = {asset_id: f"图片{index}" for index, asset_id in enumerate(ordered_ids, 1)}
    start_ms = int(segment.get("timeline_start_ms", 0))
    duration_s = int(segment.get("duration_ms", 0)) / 1000
    lines = [
        f"生成一条完整的{duration_s:g}秒写实电影感文旅短片。",
        "@音频1是最终旁白与背景音乐母带切片；严格跟随其语义、时间和节奏安排画面切换，"
        "不改写旁白，不增加新对白，不生成文字、字幕、标志或水印。",
    ]
    for asset_id in ordered_ids:
        used_by = [str(shot["shot_id"]) for shot in shots
                   if asset_id in shot.get("reference_asset_ids", [])]
        lines.append(f"{label[asset_id]}：作为 Shot {'/'.join(used_by)} 的真实地点依据。")
    for order, shot in enumerate(shots, 1):
        local_start = (int(shot.get("timeline_start_ms", start_ms)) - start_ms) / 1000
        local_end = (int(shot.get("timeline_end_ms", start_ms)) - start_ms) / 1000
        refs = "、".join(label[asset_id] for asset_id in shot.get("reference_asset_ids", [])
                        if asset_id in label) or "本 Shot 无单独参考图"
        must_keep = "；".join(_strings(shot.get("must_keep"))) or "真实地点的主体结构和空间关系"
        allowed = "；".join(_strings(shot.get("allowed_changes"))) or "自然光线和少量动态元素"
        lines.append(
            f"Shot {order}（{local_start:g}–{local_end:g}秒，使用{refs}）："
            f"{shot.get('prompt', '')}。必须保持：{must_keep}。允许改变：{allowed}。"
        )
    lines.append(
        f"段内统一要求：{segment.get('transition_note') or '保持地点、光线和色调连贯，镜头自然转场'}。"
        "不得增加参考图中不存在的标志性建筑，不得改变主要道路、建筑、山水的相对位置。"
    )
    units = {unit.get("unit_id"): unit for unit in getattr(project, "audio", {}).get("narration_units", [])}
    narration = "".join(units[unit_id].get("text", "")
                         for unit_id in segment.get("narration_unit_ids", []) if unit_id in units)
    if narration:
        lines.append(f"旁白原文仅用于校验语义：{narration}")
    return "\n".join(lines), images


def public_visual_assets(project, kb_assets: dict | None = None) -> dict:
    """兼容原 visual_assets 契约，同时暴露已确认的 RAG 参考图。"""
    result = dict(kb_assets or {})
    refs = []
    for asset in getattr(project, "reference_assets", []):
        if asset.get("analysis_status") == "completed":
            refs.append({
                "asset_id": asset.get("asset_id"),
                "name": asset.get("place_name"),
                "url": asset.get("cached_url"),
                "source_page_url": asset.get("source_page_url"),
                "user_verified": asset.get("user_verified", False),
                "rights_status": asset.get("rights_status", "unknown"),
            })
    result["ref_images"] = refs
    return result
