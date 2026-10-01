# -*- coding: utf-8 -*-
"""百度千帆景点图片搜索：用户选图前只产生候选，不直接信任为真实地点。"""

import hashlib
import json
import time
import urllib.error
import urllib.request
from typing import Any


def _extract_images(payload: Any, query: str = "") -> list[dict]:
    """从千帆 references 中提取真实图片 URL，避免把来源网页 URL 当图片。"""
    references = payload.get("references") if isinstance(payload, dict) else []
    if not isinstance(references, list):
        references = []
    found = []

    for reference in references:
        if not isinstance(reference, dict) or reference.get("type") != "image":
            continue
        image = reference.get("image")
        image_url = image.get("url") if isinstance(image, dict) else None
        if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
            found.append((image_url, reference))

    # 部分结果把相关图片放在网页结果的 web_extensions.images 中。
    if not found:
        for reference in references:
            if not isinstance(reference, dict):
                continue
            extensions = reference.get("web_extensions")
            images = extensions.get("images", []) if isinstance(extensions, dict) else []
            for image in images if isinstance(images, list) else []:
                image_url = image.get("url") if isinstance(image, dict) else None
                if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
                    found.append((image_url, reference))

    unique, seen = [], set()
    for image_url, reference in found:
        if image_url in seen:
            continue
        seen.add(image_url)
        digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:16]
        unique.append({
            "candidate_id": f"ref_{digest}",
            "query": query,
            "image_url": image_url,
            "title": str(reference.get("title") or reference.get("web_anchor") or "景点图片"),
            "source_page_url": str(reference.get("url") or reference.get("website") or ""),
            "provider": "qianfan_image_search",
        })
    return unique


def search_images(provider: dict, city: str, location: str, top_k: int | None = None) -> list[dict]:
    """搜索“城市 + 景点 + 实景”，返回带稳定 candidate_id 的候选图片。"""
    if not provider or not provider.get("api_key"):
        raise RuntimeError("百度千帆图片搜索未配置 API Key")
    city, location = (city or "").strip(), (location or "").strip()
    query = " ".join(part for part in (city, location, "实景 风景") if part)
    if not query:
        raise RuntimeError("城市和景点不能为空")
    limit = max(1, min(30, int(top_k or provider.get("top_k", 30))))
    body = {
        "messages": [{"content": query, "role": "user"}],
        "search_source": provider.get("search_source", "baidu_search_v2"),
        "resource_type_filter": [{"type": "image", "top_k": limit}],
    }
    url = provider["base_url"].rstrip("/") + provider.get("endpoint", "/web_search")
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # 千帆边缘偶发 TLS 被重置（UNEXPECTED_EOF_WHILE_READING），单次失败不代表 Key 失效，重试即可。
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"百度千帆图片搜索失败 HTTP {exc.code}: {detail}") from exc
        except OSError as exc:  # URLError / SSLError / ConnectionResetError 都属于这一类瞬时故障
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"连接百度千帆图片搜索失败: {getattr(exc, 'reason', exc)}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("百度千帆图片搜索返回格式异常")
    if payload.get("code") and payload.get("message"):
        raise RuntimeError(f"百度千帆图片搜索错误 {payload['code']}: {payload['message']}")
    return _extract_images(payload, query=query)[:limit]
