# -*- coding: utf-8 -*-
"""OpenAI 兼容模型调用 + 配置加载（从 experiments/run_llm_benchmark.py 迁移，去实验专用逻辑）。

读 experiments/config.json（含各家 API Key，gitignore 不入库）；
文件不存在或环境变量 TRAVELGEN_MOCK=1 时返回 None，上层走 demo 模式（回放 Phase 3 成果）。
"""
import json, os, time, urllib.request, urllib.error

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CONFIG_PATH = os.path.join(REPO, "experiments", "config.json")


def _read_env_value(relative_path, key):
    """从仓库内 .env 读取单个值；只用于本地开发配置，不修改进程环境。"""
    if not relative_path or not key:
        return ""
    path = relative_path if os.path.isabs(relative_path) else os.path.join(REPO, relative_path)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    return ""


def _resolve_provider(config, provider, seen=None):
    """解析 credential_provider / api_key_env，返回不会修改原配置的 provider 副本。"""
    resolved = dict(provider)
    seen = set(seen or ())
    name = resolved.get("name", "")
    if name in seen:
        raise ValueError(f"provider 凭证引用成环: {name}")
    seen.add(name)

    source_name = resolved.get("credential_provider")
    if source_name and not resolved.get("api_key"):
        source = next((p for p in config.get("providers", []) if p.get("name") == source_name), None)
        if source:
            resolved["api_key"] = _resolve_provider(config, source, seen).get("api_key", "")

    env_name = resolved.get("api_key_env")
    if env_name and not resolved.get("api_key"):
        resolved["api_key"] = os.environ.get(env_name, "") or _read_env_value(
            resolved.get("env_file"), env_name)
    return resolved


def load_provider(name):
    """从统一配置取 provider，并解析共享凭证与环境变量；不可用返回 None。"""
    if os.environ.get("TRAVELGEN_MOCK") == "1":
        return None
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    for p in cfg.get("providers", []):
        if p.get("name") == name:
            return _resolve_provider(cfg, p)
    return None


def load_config():
    """返回 kimi provider 配置（管线文案/分镜首选模型）；不可用返回 None。"""
    return load_provider("kimi")


def load_seedance_config():
    """返回火山方舟 Seedance provider（视频生成）；不可用返回 None。"""
    return load_provider("seedance")


def load_vlm_config():
    """返回景点参考图视觉理解 provider；不可用返回 None。"""
    return load_provider("vlm")


def load_image_search_config():
    """返回百度千帆图片搜索 provider；不可用返回 None。"""
    return load_provider("qianfan_image_search")


def call_model(provider, messages, temperature=None):
    """统一 OpenAI 兼容端点调用，返回回复文本；429/网络错误重试 4 次，最终失败返回 None。"""
    temp = temperature if temperature is not None else float(provider.get("temperature", 0.7))
    url = provider["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}"}
    body = json.dumps({"model": provider["model"], "messages": messages,
                       "temperature": temp}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < 3:
                time.sleep(10)
                continue
            return None
