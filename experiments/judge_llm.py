# -*- coding: utf-8 -*-
"""TravelGen Phase 3 LLM-Judge 评分脚本（A负责）。

用法:
  python judge_llm.py --results results/01_copywriting --out results/scores_copywriting.csv --judge-count 3

行为:
  - 读取 results 目录下所有 <model>_<run>.md（跳过 [ERROR 开头的失败输出）
  - 用 config.json 的 judge provider 按 prompts/judge.txt 逐维度打分（--judge-count 票）
  - 输出 CSV：model | run | 各维度分 | 平均分 | reason
  - storyboard 任务: 文件头 json_valid=false 的按 结构化程度=0 记
"""
import argparse, csv, json, os, re, sys
from run_llm_benchmark import load_config, call_openai_compatible, PROMPTS_DIR

DIMS = {"01_copywriting": ["传播感染力", "信息准确性", "风格符合度", "长度控制", "脚本可执行性"],
        "02_storyboard": ["镜头质量", "镜头逻辑", "画面一致性", "结构化程度", "可执行性"]}


def extract_content(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    return "\n".join(l for l in lines if not l.startswith("<!--"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--judge-count", type=int, default=3)
    args = ap.parse_args()

    cfg = load_config()
    judge = cfg["judge"]
    dir_name = os.path.basename(args.results.rstrip("/\\"))
    dims = DIMS.get(dir_name)
    if not dims:
        sys.exit(f"[错误] 未知实验目录 {dir_name}，应为 {list(DIMS)}")

    with open(os.path.join(PROMPTS_DIR, "judge.txt"), encoding="utf-8") as f:
        judge_prompt_tpl = f.read()

    files = sorted(os.listdir(args.results))
    rows = []
    for fn in files:
        if not fn.endswith(".md"):
            continue
        path = os.path.join(args.results, fn)
        model = fn.rsplit("_", 1)[0]
        content = extract_content(path)
        json_valid = True
        try:
            with open(path, encoding="utf-8") as f:
                head = f.read(400)
            json_valid = '"json_valid=True"' in head or "json_valid=True" in head
        except Exception:
            pass
        if content.startswith("[ERROR"):
            print(f"[skip] {fn} 输出失败，跳过")
            continue

        votes = []
        for v in range(args.judge_count):
            user = judge_prompt_tpl.replace("{DIMENSIONS}", "/".join(dims)).replace("{OUTPUT}", content[:3000])
            resp = call_openai_compatible(judge, [{"role": "user", "content": user}], temperature=0)
            try:
                m = re.search(r"\{.*\}", resp, re.S)
                votes.append(json.loads(m.group(0)))
            except Exception:
                votes.append({})  # 该票作废，记空
        # 汇总：各维度取中位数票
        scores = {}
        for d in dims:
            vals = [v["scores"][d] for v in votes if d in v.get("scores", {})]
            if not vals:
                vals = [0]
            vals.sort()
            scores[d] = vals[len(vals) // 2]
        if not json_valid:
            scores["结构化程度"] = 0
        avg = round(sum(scores.values()) / len(scores), 2)
        reason = votes[0].get("reason", "") if votes and isinstance(votes[0], dict) else ""
        rows.append({"model": model, "file": fn, **{f"score_{d}": s for d, s in scores.items()},
                     "平均分": avg, "reason": reason[:100]})
        print(f"[ok] {fn} 平均分={avg}")

    if not rows:
        sys.exit("[错误] 没有可评分的结果文件")

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["model", "file"] + [f"score_{d}" for d in dims] + ["平均分", "reason"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"\n评分完成 -> {args.out}")
    print("下一步：人工抽检最高/最低各1家，把最终结论记入 Benchmark_汇总.xlsx")


if __name__ == "__main__":
    main()
