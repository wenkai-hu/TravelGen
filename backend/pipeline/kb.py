# -*- coding: utf-8 -*-
"""浙江文旅 RAG 知识库检索（MVP 简化版：关键词子串评分；Phase 5 换向量检索/LightRAG）。

数据：models/knowledge_base/zhejiang_tourism_kb.json（16 条地标，46 张视觉锚点图）
"""
import json, os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KB_PATH = os.path.join(REPO, "models", "knowledge_base", "zhejiang_tourism_kb.json")


def _load():
    with open(KB_PATH, encoding="utf-8") as f:
        return json.load(f)["entries"]


def search(query, top_k=5, entries=None):
    """按 名称/城市/标签 子串匹配打分，返回 top_k 条。"""
    entries = entries or _load()
    q = (query or "").strip()
    if not q:
        return []
    scored = []
    for e in entries:
        text = " ".join([e.get("name", ""), e.get("city", ""), e.get("category", ""),
                         " ".join(e.get("search_tags", []))])
        score = 0
        if q in text:
            score += 2
        # 词级匹配（如 "西湖" 命中 "西湖十景" 标签）
        for kw in q.split():
            if kw in text:
                score += 1
        if q in " ".join(e.get("facts", [])):
            score += 1
        if score:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:top_k]]


def knowledge_text(req):
    """按请求（地点/城市/主题）检索，拼成注入文案 prompt 的知识块。"""
    hits, seen = [], set()
    for kw in [req.get("location"), req.get("city"), req.get("theme")]:
        for e in search(kw, 3):
            if e["id"] not in seen:
                seen.add(e["id"])
                hits.append(e)
    if not hits:
        return "（暂无知识库资料，请使用常识，禁止编造具体数据/典故）"
    lines = []
    for e in hits[:5]:
        lines.append(f"【{e['name']}】（{e.get('city', '')}/{e.get('category', '')}）")
        lines += [f"- {f}" for f in e.get("facts", [])]
        for img in e.get("images", [])[:2]:
            lines.append(f"- 视觉锚点: {img.get('path', '')}")
    return "\n".join(lines)


def visual_assets(req):
    """视觉素材：知识库锚点图 + 用户参考图（契约 visual_assets 字段）。"""
    imgs, seen = [], set()
    for kw in [req.get("location"), req.get("city")]:
        for e in search(kw, 3):
            for img in e.get("images", []):
                if img.get("path") not in seen:
                    seen.add(img.get("path"))
                    imgs.append({"name": e["name"], **img})
    return {"kb_images": imgs[:6], "ref_images": [a["url"] for a in req.get("assets", [])]}
