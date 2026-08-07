# -*- coding: utf-8 -*-
"""TravelGen Phase 3 实验1/2 统一执行脚本（A负责）。

用法:
  python run_llm_benchmark.py --task copywriting --knowledge "西湖十景：苏堤春晓..."
  python run_llm_benchmark.py --task storyboard --script results/best_copywriting.txt

行为:
  - 读取 config.json 中所有 providers
  - 每个 provider 跑 n_runs 次（默认3），输出存 results/01_copywriting|02_storyboard/<model>_<run>.md
  - storyboard 任务做严格 JSON 校验，非法输出附加解析错误到文件头
  - 每个输出文件头部自动记录 模型版本/日期/Prompt版本/温度（可复现性）
"""
import argparse, json, os, re, sys, time, datetime, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(ROOT, "prompts")
CONFIG_PATH = os.path.join(ROOT, "config.json")
RESULTS_DIR = os.path.join(ROOT, "results")
TASKS = {"copywriting": ("01_copywriting", ["传播感染力", "信息准确性", "风格符合度", "长度控制", "脚本可执行性"]),
         "storyboard": ("02_storyboard", ["镜头质量", "镜头逻辑", "画面一致性", "结构化程度", "可执行性"])}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"[错误] 缺少 {CONFIG_PATH}，请按 README.md 1.2 节创建（含各家 API Key）")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def call_openai_compatible(cfg, messages, temperature):
    """统一走 OpenAI 兼容端点；Claude 特殊处理 x-api-key 头。返回回复文本。"""
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}"}
    if "anthropic" in cfg["base_url"]:
        headers["x-api-key"] = cfg["api_key"]
        headers["anthropic-version"] = "2023-06-01"
    body = json.dumps({"model": cfg["model"], "messages": messages,
                       "temperature": temperature}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1)); continue
            return f"[ERROR http {e.code}] {e.read().decode('utf-8', 'ignore')[:300]}"
        except Exception as e:
            if attempt < 3:
                time.sleep(10); continue
            return f"[ERROR {type(e).__name__}] {e}"


def build_messages(task, prompt_text, knowledge, script):
    if task == "copywriting":
        user = prompt_text.replace("{KNOWLEDGE}", knowledge or "（暂无知识库资料，请使用常识）")
    else:
        script_text = script if os.path.exists(script) else script
        user = prompt_text.replace("{SCRIPT}", script_text)
    return [{"role": "system", "content": "你是专业的文旅内容创作与评测助手。"},
            {"role": "user", "content": user}]


def validate_storyboard_json(text):
    """抽取首个 {...} 块尝试解析；返回 (ok, error_msg)。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return False, "未找到JSON对象"
    try:
        data = json.loads(m.group(0))
        if "scenes" not in data or not isinstance(data["scenes"], list):
            return False, "缺少scenes数组"
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"JSON解析失败: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=list(TASKS))
    ap.add_argument("--knowledge", default="")
    ap.add_argument("--script", default="")
    ap.add_argument("--providers", default="", help="逗号分隔的 provider 名，只跑这些（默认全部）")
    args = ap.parse_args()

    cfg = load_config()
    out_dir_name, dims = TASKS[args.task]
    out_dir = os.path.join(RESULTS_DIR, out_dir_name)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(PROMPTS_DIR, f"{args.task}.txt"), encoding="utf-8") as f:
        prompt_text = f.read()

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    n = int(cfg.get("n_runs", 3))
    only = set(x.strip() for x in args.providers.split(",")) if args.providers else None

    for p in cfg["providers"]:
        if only and p["name"] not in only:
            continue
        temp = float(p.get("temperature", cfg.get("temperature", 0.7)))  # 各模型温度约束不同，可单独覆盖
        for i in range(1, n + 1):
            msg = build_messages(args.task, prompt_text, args.knowledge, args.script)
            content = call_openai_compatible(p, msg, temp)
            fname = os.path.join(out_dir, f"{p['name']}_{i:02d}.md")
            header = (f"<!-- model={p['name']}:{p['model']} | date={stamp} | temp={temp} | run={i} -->\n")
            if args.task == "storyboard":
                ok, err = validate_storyboard_json(content)
                header += f"<!-- json_valid={ok} | {err} -->\n"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(header + "\n" + content)
            print(f"[ok] {p['name']} run{i}/{n} -> {fname}")

    print("\n完成。下一步：")
    print("  python judge_llm.py --results " + out_dir + " --out results/scores_" + out_dir_name.split("_")[1] + ".csv")


if __name__ == "__main__":
    main()
