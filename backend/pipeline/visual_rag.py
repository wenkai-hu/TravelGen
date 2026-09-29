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
        raise RuntimeError("图片内容为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"图片超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB 限制")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            fmt = (image.format or "JPEG").upper()
            width, height = image.size
    except Exception as exc:
        raise RuntimeError("不是可解析的图片格式（支持 JPG / PNG / WEBP）") from exc
    extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt, ".jpg")
    return extension, width, height


def _download_image(url: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 TravelGen/1.0",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*",
    })
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_IMAGE_BYTES:
                raise RuntimeError(f"图片超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB 限制")
            return response.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"参考图下载失败: {exc.reason}") from exc


def _stored_image(project_id: str, data: bytes, candidate: dict, city: str, location: str) -> dict:
    """校验并落盘为不可变 ReferenceAsset。内容寻址，同一张图重复落盘是幂等的。"""
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
        "original_url": candidate.get("image_url", ""),
        "source_page_url": candidate.get("source_page_url", ""),
        "title": candidate.get("title", ""),
        "provider": candidate.get("provider", ""),
        "cached_url": uploaded_url(project_id, asset_id, extension),
        "local_path": local_path,
        "sha256": content_hash,
        "width": width,
        "height": height,
        "user_verified": True,
        "rights_status": "unknown",
        "analysis_status": "pending",
    }


UPLOAD_URL_PREFIX = "/assets/references/"


def uploaded_url(project_id: str, asset_id: str, extension: str) -> str:
    """上传图落盘后对外暴露的 URL。app.py 把 /assets 静态挂到仓库 assets/ 目录，直接可访问。"""
    return f"{UPLOAD_URL_PREFIX}{project_id}/{asset_id}{extension}"


def store_upload(project_id: str, data: bytes, city: str, location: str,
                 filename: str = "") -> dict:
    """把用户上传的字节存成不可变 ReferenceAsset（校验与落盘复用下载那条路径）。"""
    candidate = {"image_url": "", "candidate_id": None, "title": filename or "用户上传的参考图",
                 "provider": "user", "source_page_url": ""}
    return _stored_image(project_id, data, candidate, city, location)


def _local_upload_path(project_id: str, url: str) -> str | None:
    """上传的图在收件那一步就已落盘，image_url 形如 /assets/references/{pid}/ref_xxx.ext。
    文件名就是内容哈希，所以能从 URL 直接反推本地文件，确认阶段不必再下一遍。"""
    prefix = f"{UPLOAD_URL_PREFIX}{project_id}/"
    if not url.startswith(prefix):
        return None
    name = os.path.basename(url)
    if not name.startswith("ref_"):
        return None
    path = os.path.join(REFERENCE_ROOT, project_id, name)
    return path if os.path.isfile(path) else None


def cache_candidate(project_id: str, candidate: dict, city: str, location: str) -> dict:
    """把用户确认的候选图变成不可变 ReferenceAsset：本地已上传的读盘，远端 URL 的下载。"""
    url = str(candidate.get("image_url", ""))
    local = _local_upload_path(project_id, url)
    if local:
        with open(local, "rb") as f:
            data = f.read(MAX_IMAGE_BYTES + 1)
    elif url.startswith(("http://", "https://")):
        data = _download_image(url)
    elif url.startswith("/"):
        raise RuntimeError(f"上传的参考图已丢失或被清理，请重新上传: {url}")
    else:
        raise RuntimeError("参考图只支持 http/https URL 或本地上传")
    return _stored_image(project_id, data, candidate, city, location)


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


def _best_unused(shot: dict, profile: dict, catalog: list[dict], used_ids: set) -> str | None:
    """按内容相关性挑一张还没用过的图（auto_order 模式的兜底）。

    同分时按目录里的先后取 —— 结果可复现，同样的输入不会每次跑出不同的绑定。
    """
    ranked = {entry.get("asset_id"): i
              for i, entry in enumerate(profile.get("view_catalog", []))}
    best_id, best_key = None, None
    for entry in catalog:
        asset_id = entry.get("asset_id")
        if not asset_id or asset_id in used_ids:
            continue
        key = (_catalog_score(shot, entry), -ranked.get(asset_id, 0))
        if best_key is None or key > best_key:
            best_id, best_key = asset_id, key
    return best_id


def bind_storyboard_references(storyboard: dict, profile: dict,
                               auto_order: bool = False) -> dict:
    """为每个 Shot 绑定唯一实景图；参考图全片只使用一次。

    auto_order=True 表示用户没排顺序、交给模型自己配：模型在分镜里挑好的照单全收，
    它漏掉的按内容相关性补，而不是按位置顺序补。
    """
    valid_ids = set(profile.get("reference_asset_ids", []))
    catalog = [entry for entry in profile.get("view_catalog", []) if entry.get("asset_id") in valid_ids]
    catalog_ids = {entry["asset_id"] for entry in catalog}  # VLM 分析失败的图不在目录里
    used_ids = set()
    for scene in storyboard.get("scenes", []):
        scene.setdefault("place_id", profile.get("place_id"))
        for shot in scene.get("shot_list", []):
            requested = shot.get("reference_asset_ids")
            if isinstance(requested, list) and len(requested) > 1:
                raise ValueError(f"Shot {shot.get('shot_id')} 只能引用一张参考图")
            selected = requested[0] if isinstance(requested, list) and requested and requested[0] in valid_ids else None
            if selected in used_ids:
                raise ValueError(f"参考图 {selected} 被多个 Shot 重复使用")
            if selected is None and auto_order:
                selected = _best_unused(shot, profile, catalog, used_ids)
            if selected is None:
                # 按用户排定的顺序取目录里第一张还没被用掉的图。这里不打分：
                # 一旦按语义相关性挑，用户排好的第 N 张就会跑到别的镜头去，排序就白排了。
                # （原来还要求分数 > 0，分数不达标就报"参考图不足"，是个假失败。）
                selected = next(
                    (aid for aid in profile.get("reference_asset_ids", [])
                     if aid not in used_ids and aid in catalog_ids), None)
            if selected is None:
                raise ValueError("可用参考图不足：每个 Shot 必须独占一张图，请减少 Shot 数量")
            used_ids.add(selected)
            selected = [selected]
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
            shot["must_keep"] = _unique(selected_must_keep or _strings(shot.get("must_keep")), 12)
            shot["allowed_changes"] = _unique(selected_allowed or _strings(shot.get("allowed_changes")), 10)
            shot["unsupported_or_risky_shots"] = _unique(selected_risks, 10)
    return storyboard


def _local_data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _assets_by_id(project) -> dict:
    return {asset.get("asset_id"): asset for asset in getattr(project, "reference_assets", [])}


def segment_shots(project, segment: dict) -> list[dict]:
    """Segment 的 Shot 列表（按 shot_ids 顺序，找不到的跳过）。"""
    shots_by_id = {
        shot.get("shot_id"): shot
        for scene in getattr(project, "storyboard", {}).get("scenes", [])
        for shot in scene.get("shot_list", [])
    }
    return [shots_by_id[shot_id] for shot_id in segment.get("shot_ids", []) if shot_id in shots_by_id]


def ordered_asset_ids(project, shots: list[dict]) -> list[str]:
    """Shot 列表 → 有本地文件、去重、顺序稳定的参考图 asset_id。

    compile_*_input 的图片顺序就是这里的顺序（提示词里的"图片1/图片2"= 下标 +1），
    所以平台只回 content[k] 的审核类报错可以靠它反查是哪张图。
    """
    assets = _assets_by_id(project)
    ordered: list[str] = []
    for shot in shots:
        for asset_id in shot.get("reference_asset_ids", []):
            if asset_id in assets and assets[asset_id].get("local_path") and asset_id not in ordered:
                ordered.append(asset_id)
    return ordered


def compile_shot_input(project, shot: dict) -> tuple[str, list[str]]:
    """Shot 的引用 ID → 顺序稳定的原始图片附件与显式约束 Prompt。"""
    assets = _assets_by_id(project)
    selected = [assets[aid] for aid in ordered_asset_ids(project, [shot])[:MAX_REFERENCES_PER_SHOT]]
    images = [_local_data_uri(asset["local_path"]) for asset in selected]
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
    """把统一音色参考、段内新旁白、多 Shot 与图片绑定编译为一次 Seedance 输入。"""
    shots = segment_shots(project, segment)
    if not shots:
        raise ValueError(f"{segment.get('segment_id')} 没有可编译的 Shot")
    if getattr(project, "storyboard", {}).get("storyboard_version", 0) >= 4 and len(shots) != 1:
        raise ValueError("新分镜的一次生成请求只能包含一个 Shot")
    assets = _assets_by_id(project)
    ordered_ids = ordered_asset_ids(project, shots)
    if len(ordered_ids) > MAX_REFERENCES_PER_SEGMENT:
        raise ValueError(
            f"{segment.get('segment_id')} 去重后有 {len(ordered_ids)} 张参考图，超过 {MAX_REFERENCES_PER_SEGMENT} 张"
        )
    continuation = (getattr(project, "storyboard", {}).get("storyboard_version", 0) >= 4
                    and segment.get("continuation_index", 1) > 1)
    images = [] if continuation else [_local_data_uri(assets[asset_id]["local_path"]) for asset_id in ordered_ids]
    label = {asset_id: ("视频1" if continuation else f"图片{index}")
             for index, asset_id in enumerate(ordered_ids, 1)}
    duration_s = int(segment.get("duration_ms", 0)) / 1000
    narration = str(segment.get("narration_text", "")).strip()
    if not narration:
        narration = "".join(str(shot.get("narration", "")).strip() for shot in shots)
    request = getattr(project, "request", {})
    lines = [
        f"生成一条完整的{duration_s:g}秒、{request.get('aspect_ratio', '9:16')}、"
        f"{request.get('style', '写实电影感')}风格的文旅短片。",
        "",
        "【声音身份参考】",
        "@音频1只用于参考唯一画外旁白说话人的声音身份。保持其稳定的音色、年龄感、"
        "音高范围、共鸣位置、咬字习惯和普通话口音，确保与其他Segment听起来是同一个人。",
        "只参考说话人的身份特征，不要复述、改写、续写或引用@音频1中的测试台词。",
        "本段语气和情绪以当前内容为准，不要机械复制测试句的情绪。",
        "",
        "【本段表达要求】",
        f"整体风格为“{request.get('style', '自然真实')}”，自然口语化、不过度播音。"
        "本段开头先保持约0.3秒静默再开口，不要从第0秒就开始说话；"
        "旁白在距本段结束约0.3秒前完整说完，结尾保留自然静默，不要截断尾音。",
        "",
        "【本段旁白】",
    ]
    if narration:
        lines.extend([
            "只允许上述同一名画外旁白，准确完整地朗读：",
            f"“{narration}”",
            "不得增字、删字、换词、重复句子或增加其他对白。",
        ])
    else:
        lines.append("本段不生成任何人声、旁白或对白，只保留画面对应的自然环境声和必要拟音。")
    lines.extend([
        "",
        "【声音规则——固定最高优先级】",
        "只允许生成上述画外旁白、与当前画面对应的自然环境声，以及必要且克制的真实拟音。",
        "绝对禁止生成任何背景音乐、配乐、旋律、节奏铺底、鼓点、乐器声、吟唱、歌曲、"
        "哼唱或音乐化音效。整段从开始到结束都不得出现BGM。",
        "",
        "【实景参考】",
    ])
    if continuation:
        lines.append("沿用视频1中已建立的真实地点、构图和镜头运动，继续同一条镜头。")
    else:
        for asset_id in ordered_ids:
            used_by = [str(shot["shot_id"]) for shot in shots
                       if asset_id in shot.get("reference_asset_ids", [])]
            lines.append(f"{label[asset_id]}：作为 Shot {'/'.join(used_by)} 的真实地点依据。")
    lines.extend(["", "【画面与声音时间线】"])
    for order, shot in enumerate(shots, 1):
        if getattr(project, "storyboard", {}).get("storyboard_version", 0) >= 4:
            local_start = 0
            local_end = duration_s
        else:
            local_start = int(shot.get("segment_local_start_ms", 0)) / 1000
            local_end = int(shot.get("segment_local_end_ms", 0)) / 1000
        refs = "、".join(label[asset_id] for asset_id in shot.get("reference_asset_ids", [])
                        if asset_id in label) or "本 Shot 无单独参考图"
        must_keep = "；".join(_strings(shot.get("must_keep"))) or "真实地点的主体结构和空间关系"
        allowed = "；".join(_strings(shot.get("allowed_changes"))) or "自然光线和少量动态元素"
        shot_narration = (narration if len(shots) == 1 else str(shot.get("narration", "")).strip()) \
            or "本镜头无新增旁白，延续自然环境声"
        lines.append(
            f"Shot {order}（{local_start:g}–{local_end:g}秒，使用{refs}）："
            f"{shot.get('prompt', '')}。旁白安排：{shot_narration}。"
            "环境声只生成与该画面直接对应的自然声音，不得生成音乐。"
            f"必须保持：{must_keep}。允许改变：{allowed}。"
        )
    if getattr(project, "storyboard", {}).get("storyboard_version", 0) >= 4:
        lines.append("本片段是一条连续镜头，保持同一机位和稳定景别，不要突然切镜、跳变远近或重新取景。"
                     "不得增加参考图中不存在的标志性建筑，不得改变主要道路、建筑、山水的相对位置。")
    else:
        lines.append(
            f"段内统一要求：{segment.get('transition_note') or '保持地点、光线和色调连贯，镜头自然转场'}。"
            "不得增加参考图中不存在的标志性建筑，不得改变主要道路、建筑、山水的相对位置。"
        )
    lines.append(
        "画面中可以出现游客或当地居民，但任何人物都不得对口型说话；旁白始终来自画外。"
        "不要生成字幕、文字、标题、标志或水印。"
    )
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
