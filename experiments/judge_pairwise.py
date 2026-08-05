# -*- coding: utf-8 -*-
"""TravelGen Phase 3 成对比较评分脚本（A负责）。

用法:
  python judge_pairwise.py --results results/01_copywriting --scores results/scores_copywriting.csv --out results/pairwise_copywriting.csv --votes 1

行为:
  - 从 scores CSV 取每家模型平均分最高的文件作为代表（失败输出自动跳过）
  - 每对调用 Judge 2 次（AB 与 BA 位置交换，消除顺序偏差），--votes 控制每位置重复次数
  - 裁判对双方分别打 1-5 分（MT-Bench 法）：同一篇在两轮中的得分合计，总分高者胜，相等则平
  - 输出 CSV：pair | winner | 分差 | reason_A先 | reason_B先
  - 汇总胜/平/负与胜率，打印并写入 pairwise_summary_<任务>.csv

设计依据：MT-Bench / Prometheus 成对评测方法论——直接让裁判选边会有强位置偏差（裁判倾向选先出现的一方），
给双方分别打分再交换位置合计，可平均掉偏差，区分度更高。
"""
import argparse, csv, itertools, json, os, re, sys
from run_llm_benchmark import load_config, call_openai_compatible, PROMPTS_DIR
from judge_llm import extract_content


def load_best_per_model(scores_csv, results_dir):
    """从 scores CSV 取每模型最高分文件，返回 {model: content}。"""
    best = {}
    with open(scores_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            m, fn, avg = row["model"], row["file"], float(row["平均分"])
            if m not in best or avg > best[m][0]:
                best[m] = (avg, fn)
    contents = {}
    for m, (avg, fn) in sorted(best.items()):
        path = os.path.join(results_dir, fn)
        # 分镜任务：JSON 非法的代表文件不参与成对对决（结构化程度硬校验）
        with open(path, encoding="utf-8") as f:
            head = f.read(400)
        if "json_valid=false" in head or '"json_valid=false"' in head:
            print(f"[skip] {m} 代表文件 {fn} JSON非法，跳过")
            continue
        c = extract_content(path).strip()
        if c.startswith("[ERROR"):
            print(f"[skip] {m} 代表文件输出失败，跳过")
            continue
        contents[m] = c
    return contents


def call_judge(judge, prompt_tpl, text_a, text_b):
    """一次位置固定的比较；返回 (scoreA, scoreB, reasonA, reasonB)，解析失败返回 None。"""
    user = prompt_tpl.replace("{OUTPUT_A}", text_a).replace("{OUTPUT_B}", text_b)
    resp = call_openai_compatible(judge, [{"role": "user", "content": user}], temperature=0)
    m = re.search(r"\{.*\}", resp, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        sa, sb = float(data["score_A"]), float(data["score_B"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if sa < 0 or sa > 5 or sb < 0 or sb > 5:
        return None
    return sa, sb, str(data.get("reason_A", ""))[:150], str(data.get("reason_B", ""))[:150]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="结果目录，如 results/01_copywriting")
    ap.add_argument("--scores", required=True, help="judge_llm.py 产出的 scores CSV")
    ap.add_argument("--out", required=True, help="输出 CSV 路径")
    ap.add_argument("--votes", type=int, default=1, help="每位置重复次数（默认1，即每对2次调用）")
    args = ap.parse_args()

    cfg = load_config()
    judge = cfg["judge"]
    contents = load_best_per_model(args.scores, args.results)
    if len(contents) < 2:
        sys.exit("[错误] 可用模型不足2家，无法成对比较")

    # 优先用任务专属成对评审提示词（judge_pairwise_<实验目录>.txt），否则用通用 judge_pairwise.txt
    task_name = os.path.basename(os.path.normpath(args.results))
    prompt_file = os.path.join(PROMPTS_DIR, f"judge_pairwise_{task_name}.txt")
    if not os.path.exists(prompt_file):
        prompt_file = os.path.join(PROMPTS_DIR, "judge_pairwise.txt")
    with open(prompt_file, encoding="utf-8") as f:
        prompt_tpl = f.read()

    models = sorted(contents)
    rows = []
    for a, b in itertools.combinations(models, 2):
        ta = tb = None
        for _ in range(args.votes):
            c1 = call_judge(judge, prompt_tpl, contents[a], contents[b])  # A=文本a
            c2 = call_judge(judge, prompt_tpl, contents[b], contents[a])  # A=文本b
            if c1 and c2:
                # 文本a的总分 = 位置1的score_A + 位置2的score_B；文本b相反
                total_a = c1[0] + c2[1]
                total_b = c1[1] + c2[0]
                if ta is None:
                    ta, tb = total_a, total_b
                    ra_first, rb_first = c1[3], c2[2]
                else:
                    ta, tb = ta + total_a, tb + total_b
        if ta is None:
            print(f"[warn] {a} vs {b} 判决解析失败，按平局计")
            winner, diff = "tie", 0.0
            ra_first = rb_first = "（解析失败）"
        elif abs(ta - tb) < 1e-9:
            winner, diff = "tie", 0.0
        else:
            winner, diff = (a if ta > tb else b), abs(ta - tb)
        rows.append({"pair": f"{a} vs {b}", "winner": winner, "分差": f"{diff:.1f}",
                     "reason_A先": ra_first or "", "reason_B先": rb_first or ""})
        print(f"[ok] {a} vs {b} -> 胜者: {winner} (分差 {diff:.1f})")

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pair", "winner", "分差", "reason_A先", "reason_B先"])
        w.writeheader()
        w.writerows(rows)

    # 汇总：胜/平/负 + 胜率（平局不计入胜率分母）
    stats = {m: {"wins": 0, "losses": 0, "ties": 0} for m in models}
    for r in rows:
        p = r["pair"].split(" vs ")
        w, l = (p[0], p[1]) if r["winner"] == p[0] else (p[1], p[0]) if r["winner"] == p[1] else (None, None)
        if w:
            stats[w]["wins"] += 1
            stats[l]["losses"] += 1
        else:
            stats[p[0]]["ties"] += 1
            stats[p[1]]["ties"] += 1
    summary = [{"model": m, **s, "胜率": round(s["wins"] / (s["wins"] + s["losses"]), 2)
                if (s["wins"] + s["losses"]) else 0.0}
               for m, s in stats.items()]
    summary.sort(key=lambda x: (-x["胜率"], -x["wins"]))
    print("\n=== 成对比较排名（胜率，平局不计）===")
    for s in summary:
        print(f"  {s['model']:>8}  胜{s['wins']} 负{s['losses']} 平{s['ties']}  胜率{s['胜率']:.2f}")

    sum_path = os.path.join(os.path.dirname(args.out) or ".",
                            f"pairwise_summary_{os.path.basename(os.path.normpath(args.results)).split('_')[1]}.csv")
    with open(sum_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "wins", "losses", "ties", "胜率"])
        w.writeheader()
        w.writerows(summary)
    print(f"\n详情 -> {args.out}\n汇总 -> {sum_path}")


if __name__ == "__main__":
    main()
