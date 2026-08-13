# -*- coding: utf-8 -*-
"""OpenAI 兼容模型调用 + 配置加载（从 experiments/run_llm_benchmark.py 迁移，去实验专用逻辑）。

读 experiments/config.json（含各家 API Key，gitignore 不入库）；
文件不存在或环境变量 TRAVELGEN_MOCK=1 时返回 None，上层走 demo 模式（回放 Phase 3 成果）。
"""
import json, os, time, urllib.request, urllib.error

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CONFIG_PATH = os.path.join(REPO, "experiments", "config.json")


def load_config():
    """返回 kimi provider 配置（管线文案/分镜首选模型）；不可用返回 None。"""
    if os.environ.get("TRAVELGEN_MOCK") == "1":
        return None
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    for p in cfg.get("providers", []):
        if p.get("name") == "kimi":
            return p
    return None


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
