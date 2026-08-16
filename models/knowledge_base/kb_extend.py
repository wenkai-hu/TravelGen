# -*- coding: utf-8 -*-
"""知识库扩展脚本：一条命令给知识库加新景点。

用法:
  python kb_extend.py 绍兴鲁迅故里 温州雁荡山 宁波溪口
  python kb_extend.py --file 待添加景点列表.txt   # 每行一个景点名

行为:
  1. 读取现有 zhejiang_tourism_kb.json（跳过已存在条目）
  2. LLM（deepseek-v4-flash）生成条目初稿：facts/search_tags/landmarks/images_search
  3. 官方名录（raw/scenic_spot_names.txt）自动交叉验证 → verified 标记
  4. 追加入库 + 更新校验清单（kb_verification_checklist.csv）
  5. 提示下一步拉图命令（fetch_unsplash_images.py）

注意：LLM 初稿仅作草稿，入库后请按校验清单人工复核事实（赛事"信息真实性"评分要求）。
"""
import argparse, csv, json, os, re, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "../../experiments")))
from run_llm_benchmark import load_config, call_openai_compatible

KB_PATH = os.path.join(BASE, "zhejiang_tourism_kb.json")
LIST_PATH = os.path.join(BASE, "raw", "scenic_spot_names.txt")
CHECKLIST_PATH = os.path.join(BASE, "kb_verification_checklist.csv")

PROMPT_TEMPLATE = """你是浙江文旅知识库构建专家。请为以下浙江文旅地标生成结构化知识条目（用于文旅宣传文案与视频生成的RAG知识库）。

地标：%s

要求：
1. facts：3-5 条**真实可查证**的事实（位置/历史/数据/典故/文化价值），宁缺毋滥，不确定的信息绝不编造
2. search_tags：4-6 个检索关键词（含别名、关联景点）
3. landmarks：关联子景点数组（无则空数组）
4. images_search：2 个用于在英文图库搜索该地标照片的英文关键词（如 ["West Lake Hangzhou", "Hangzhou lake"]）
5. id：小写连字符格式，如 hz-luyang-temple
6. 只输出严格JSON，格式：{"entries": [{"id": "...", "name": "地标名", "city": "城市", "category": "景区/历史名胜/古镇/宗教/非遗", "facts": [...], "landmarks": [...], "search_tags": [...], "images_search": [...]}]}"""


def llm_generate(name):
    cfg = load_config()
    ds = next(p for p in cfg["providers"] if p["name"] == "deepseek")
    for attempt in range(3):
        resp = call_openai_compatible(ds, [{"role": "user", "content": PROMPT_TEMPLATE % name}], 0.7)
        m = re.search(r"\{.*\}", resp, re.S)
        try:
            data = json.loads(m.group(0))
            e = data["entries"][0]
            assert e["name"] == name and len(e["facts"]) >= 3
            return e
        except Exception:
            print(f"  ⚠️ {name} 第{attempt+1}次解析失败，重试...")
            time.sleep(2)
    return None


def verify_with_list(e, names):
    hits = [n for n in names if e["name"] in n]
    if hits:
        e["verified"] = True
        e["verified_note"] = f"名录匹配 {len(hits)} 处，如: {hits[0]}"
    else:
        e["verified"] = False
        e["verified_note"] = "名录未收录（子景点/历史名胜，需人工确认事实）"


def update_checklist(kb):
    with open(CHECKLIST_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "city", "verified", "来源"])
        for e in kb["entries"]:
            w.writerow([e["id"], e["name"], e["city"], "是" if e["verified"] else "否", e["verified_note"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="景点名（多个用空格分隔）")
    ap.add_argument("--file", default="", help="待添加景点列表文件（每行一个）")
    args = ap.parse_args()

    names = list(args.names)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            names += [l.strip() for l in f if l.strip()]
    names = list(dict.fromkeys(names))  # 去重保序
    if not names:
        sys.exit("用法: python kb_extend.py 景点名... 或 --file 列表文件")

    kb = json.load(open(KB_PATH, encoding="utf-8"))
    existing = {e["name"] for e in kb["entries"]}
    names = [n for n in names if n not in existing]
    if not names:
        print("所有景点已在知识库中，无需扩展")
        return
    print(f"待扩展 {len(names)} 个景点（跳过已存在）")

    with open(LIST_PATH, encoding="utf-8") as f:
        names_list = [l.strip() for l in f if l.strip()]

    for name in names:
        print(f"\n生成 {name} ...")
        e = llm_generate(name)
        if not e:
            print(f"  ❌ {name} 生成失败，跳过（可重试）")
            continue
        e["source"] = "LLM生成(deepseek-v4-flash) + 名录交叉验证（待人工复核）"
        e["images"] = []
        verify_with_list(e, names_list)
        kb["entries"].append(e)
        print(f"  ✅ 入库：{e['id']} | facts {len(e['facts'])}条 | {'名录确认' if e['verified'] else '待人工'}")

    kb["count"] = len(kb["entries"])
    json.dump(kb, open(KB_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    update_checklist(kb)
    print(f"\n完成：知识库现有 {kb['count']} 条。")
    print("下一步拉图：python fetch_unsplash_images.py <UNSPLASH_ACCESS_KEY>")
    print("⚠️ 新条目为 LLM 初稿，请按 kb_verification_checklist.csv 人工复核事实后再用于生产")


if __name__ == "__main__":
    main()
