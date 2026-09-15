# -*- coding: utf-8 -*-
"""豆包 VLM 客户端：逐张图片提取可追溯的视觉事实，不判断地点真伪。"""

import base64
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request


VISUAL_OBSERVATION_PROMPT = """你是文旅视频项目的实景参考图分析器。只记录图片中直接可见的内容。

约束：
1. 不要根据文件名、用户暗示或常识断言具体地点；无法从画面确认的地名放入 uncertain。
2. 不要编造建筑年代、历史事件、精确地理位置或不可见区域。
3. 输出一个严格 JSON 对象，不要 Markdown 代码块或额外说明。

输出结构：
{
  "summary": "整体画面概述",
  "visible_elements": ["直接可见主体、建筑、道路、山水和植被"],
  "spatial_layout": ["画面中稳定的相对位置关系"],
  "architecture_and_materials": ["可见建筑形态、材质和色彩"],
  "viewpoint": {
    "camera_position": "地面/高位/无法判断",
    "angle": "平视/俯视/仰视/无法判断",
    "shot_size": "远景/全景/中景/近景/特写",
    "orientation_clues": ["只能基于画面描述的朝向线索"]
  },
  "lighting_weather_season": {
    "time_of_day": "可见判断或无法判断",
    "weather": "可见判断或无法判断",
    "season": "可见判断或无法判断"
  },
  "must_keep_candidates": ["视频生成中值得保持的结构和辨识特征"],
  "allowed_changes": ["不破坏地点结构时可以变化的动态元素"],
  "suitable_shots": ["图片能够支持的镜头设计"],
  "unsupported_or_risky_shots": ["图片无法可靠支持的视角或运动"],
  "visible_text": ["能明确读出的文字；没有则为空数组"],
  "uncertain": ["无法确认或可能误判的内容"]
}"""


def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise RuntimeError("VLM 没有返回 JSON 对象")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"VLM JSON 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("VLM 返回值不是 JSON 对象")
    return data


def analyze_image(provider: dict, image_path: str) -> dict:
    """分析一张本地图片，返回 analysis + 模型与用量元数据。"""
    if not provider or not provider.get("api_key"):
        raise RuntimeError("VLM provider 未配置 API Key")
    body = {
        "model": provider["model"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": VISUAL_OBSERVATION_PROMPT},
                {"type": "image_url", "image_url": {
                    "url": _data_uri(image_path),
                    "detail": provider.get("detail", "high"),
                }},
            ],
        }],
        "thinking": {"type": provider.get("thinking", "disabled")},
        "temperature": 0.1,
        "max_completion_tokens": int(provider.get("max_completion_tokens", 1600)),
    }
    request_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    url = provider["base_url"].rstrip("/") + "/chat/completions"
    started = time.perf_counter()
    last_error = None
    for attempt in range(3):
        request = urllib.request.Request(
            url,
            data=request_data,
            headers={
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.loads(response.read().decode("utf-8"))
            choices = payload.get("choices") or []
            content = ((choices[0].get("message") or {}).get("content") if choices else "") or ""
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("VLM 返回正文为空；请确认 thinking=disabled 或提高输出上限")
            return {
                "model": provider["model"],
                "prompt_version": "visual_observation_v1",
                "elapsed_s": round(time.perf_counter() - started, 3),
                "usage": payload.get("usage", {}),
                "analysis": _extract_json(content),
            }
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            last_error = RuntimeError(f"VLM 调用失败 HTTP {exc.code}: {detail}")
            if exc.code != 429 or attempt == 2:
                raise last_error from exc
            time.sleep(2 * (attempt + 1))
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"连接 VLM 失败: {exc.reason}")
            if attempt == 2:
                raise last_error from exc
            time.sleep(2 * (attempt + 1))
    raise last_error or RuntimeError("VLM 调用失败")
