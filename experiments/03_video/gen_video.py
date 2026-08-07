# -*- coding: utf-8 -*-
"""统一视频生成入口——实验3 文生视频通道对比（B 负责接入）。

统一性设计（控制变量，保证可比）:
  - 所有通道吃同一份 shot_prompts.txt（<shot_id>\\t<prompt>），不按通道改文案
  - 统一参数 --duration/--resolution/--aspect（默认 5 / 1080p / 16:9），
    各通道适配器负责翻译成自家 API 字段名；实际档位写入记录备注
  - 统一记录 video_record.csv

用法:
  python gen_video.py --check --channel seedance
  python gen_video.py --channel seedance --prompt "航拍镜头缓缓推进，西湖苏堤在晨雾中"
  python gen_video.py --channel hy-video-1.5 --shots shot_prompts.txt --cost 1.8

当前通道: seedance（火山方舟）、hy-video-1.5（腾讯混元文生）、minimax（MiniMax-H3 文生）。
yt-video-2.0 为纯图生，不入文生对比（README 已记录）。
"""
import argparse, csv, hashlib, json, os, time, datetime, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "video_config.json")
OUT_DIR = os.path.join(ROOT, "results", "03_video")
RECORD_CSV = os.path.join(OUT_DIR, "video_record.csv")
COLUMNS = ["channel", "shot_id", "prompt_md5", "耗时秒", "成本元", "画质分", "一致性分", "中文适配分", "样片链接", "备注"]
POLL_INTERVAL = 5
POLL_MAX = 120


# ---------- 通用工具 ----------
def http_json(req, timeout=60, retries=0):
    """urlopen 封装：HTTPError（语义错误）立即失败；URLError（网络抖动）按 retries 重试。"""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise SystemExit(f"[FAIL http {e.code}] {e.read().decode('utf-8', 'ignore')[:300]}")
        except urllib.error.URLError:
            if attempt >= retries:
                raise
            time.sleep(2 * (attempt + 1))


def load_channel(name):
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    if name not in cfg["channels"]:
        raise SystemExit(f"[错误] video_config.json 里没有通道 {name}，现有 {list(cfg['channels'])}")
    return cfg["channels"][name]


def find_url(obj):
    """递归找第一个 http 视频/文件地址。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("video_url", "video", "url", "file_url", "video_link") and isinstance(v, str) and v.startswith("http"):
                return v
            r = find_url(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_url(v)
            if r:
                return r
    return None


def record(row):
    os.makedirs(OUT_DIR, exist_ok=True)
    new = not os.path.exists(RECORD_CSV)
    with open(RECORD_CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def read_items(prompt, shots):
    if shots:
        items = []
        for ln in open(shots, encoding="utf-8"):
            parts = ln.rstrip("\n").split("\t", 1)
            if len(parts) == 2 and parts[1].strip():
                items.append((parts[0].strip(), parts[1].strip()))
        if not items:
            raise SystemExit("[错误] shot_prompts.txt 为空或格式不对，应为 <shot_id>\\t<prompt>")
        return items
    if prompt:
        return [("test", prompt)]
    raise SystemExit("[错误] 需要 --prompt 或 --shots")


# ---------- 通道适配器 ----------
# 统一签名: submit(prompt, duration, resolution, aspect, cfg) -> task_id；poll(task_id, cfg) -> (elapsed, video_url)

def _seedance_submit(prompt, duration, resolution, aspect, cfg):
    url = cfg["base_url"].rstrip("/") + "/contents/generations/tasks"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    body = json.dumps({"model": cfg["model"], "content": [{"type": "text", "text": prompt}],
                       "duration": duration, "resolution": resolution}).encode("utf-8")
    return http_json(urllib.request.Request(url, data=body, headers=headers))["id"]


def _seedance_poll(task_id, cfg):
    url = cfg["base_url"].rstrip("/") + f"/contents/generations/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    t0 = time.time()
    for i in range(POLL_MAX):
        data = http_json(urllib.request.Request(url, headers=headers), retries=4)
        if data.get("status") == "succeeded":
            return time.time() - t0, data["content"]["video_url"]
        if data.get("status") in ("failed", "expired"):
            raise SystemExit(f"[FAIL 任务{data.get('status')}] {json.dumps(data, ensure_ascii=False)[:400]}")
        time.sleep(min(POLL_INTERVAL * (i // 4 + 1), 15))   # 5s 起步，指数退避，封顶 15s
    raise SystemExit("[FAIL 轮询超时] 约 30 分钟未完成")


def _tencent_submit(prompt, duration, resolution, aspect, cfg):
    if len(prompt) > 200:
        raise SystemExit(f"[错误] hy-video-1.5 的 prompt 限 200 字，当前 {len(prompt)} 字，请裁短镜头 prompt")
    url = cfg["base_url"].rstrip("/") + "/submit"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    body = {"model": cfg["model"], "prompt": prompt, "resolution": resolution, "logo_add": 0}
    # 官方：duration/aspect_ratio/negative_prompt/fps/seed 均不支持（模型自动决定），故忽略；
    # logo_add 默认 1（加水印），显式传 0 关掉（后缀已要求"无文字水印"）。
    data = http_json(urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers))
    tid = data.get("id") or (data.get("data") or {}).get("id")
    if not tid:
        raise SystemExit(f"[FAIL] 提交响应里没找到 id：{json.dumps(data, ensure_ascii=False)[:400]}")
    return tid


def _tencent_poll(task_id, cfg):
    url = cfg["base_url"].rstrip("/") + "/query"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    t0 = time.time()
    for i in range(POLL_MAX):
        body = json.dumps({"model": cfg["model"], "id": task_id}).encode("utf-8")
        data = http_json(urllib.request.Request(url, data=body, headers=headers), retries=4)
        video = find_url(data)
        if video:
            return time.time() - t0, video
        if str(data.get("status", "")).lower() in ("failed", "failure", "error", "expired"):
            raise SystemExit(f"[FAIL 任务{data.get('status')}] {json.dumps(data, ensure_ascii=False)[:400]}")
        time.sleep(POLL_INTERVAL)
    raise SystemExit(f"[FAIL 轮询超时] 约 {POLL_MAX * POLL_INTERVAL // 60} 分钟未完成")


def _minimax_submit(prompt, duration, resolution, aspect, cfg):
    url = cfg["base_url"].rstrip("/") + "/v2/video_generation"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    r = {"768p": "768P", "1080p": "2K"}.get(resolution.lower(), resolution)  # MiniMax 无 1080p 档，1080p→2K 高解析档
    body = json.dumps({"model": cfg["model"], "content": [{"type": "text", "text": prompt}],
                       "resolution": r, "duration": duration, "ratio": aspect}).encode("utf-8")
    data = http_json(urllib.request.Request(url, data=body, headers=headers))
    tid = data.get("task_id")
    if not tid:
        raise SystemExit(f"[FAIL] 提交响应里没找到 task_id：{json.dumps(data, ensure_ascii=False)[:400]}")
    return tid


def _minimax_poll(task_id, cfg):
    url = cfg["base_url"].rstrip("/") + f"/v2/query/video_generation/{task_id}"
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    t0 = time.time()
    for i in range(POLL_MAX):
        data = http_json(urllib.request.Request(url, headers=headers), retries=4)
        task = data.get("task") or {}
        status = str(task.get("status", "")).lower()
        if status == "succeeded":
            u = (task.get("content") or {}).get("url")
            if not u:
                raise SystemExit(f"[FAIL] succeeded 但没找到 task.content.url：{json.dumps(data, ensure_ascii=False)[:400]}")
            return time.time() - t0, u
        if status in ("failed", "cancelled"):
            raise SystemExit(f"[FAIL 任务{status}] {json.dumps(data, ensure_ascii=False)[:400]}")
        time.sleep(min(POLL_INTERVAL * (i // 4 + 1), 15))
    raise SystemExit("[FAIL 轮询超时] 约 30 分钟未完成")


CHANNELS = {
    "seedance": {"submit": _seedance_submit, "poll": _seedance_poll, "auto_params": False},
    "hy-video-1.5": {"submit": _tencent_submit, "poll": _tencent_poll, "auto_params": True},  # 时长/画幅模型自动
    "minimax": {"submit": _minimax_submit, "poll": _minimax_poll, "auto_params": False},
}


def check_auth(cfg):
    base = cfg["base_url"]
    if "tencentmaas" in base:   # 混元：query 无效 id（返回"任务不存在"即 key 有效）
        url = base.rstrip("/") + "/query"
        req = urllib.request.Request(url, data=json.dumps({"model": cfg["model"], "id": "__none__"}).encode("utf-8"),
                                     headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"})
    elif "minimax" in base:     # MiniMax：GET 任务列表（key 有效必然 200）
        url = base.rstrip("/") + "/v2/query/video_generation"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {cfg['api_key']}"})
    else:                       # 方舟：GET 任务列表
        url = base.rstrip("/") + "/contents/generations/tasks"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {cfg['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"[OK] 鉴权通过 HTTP {r.status}：{r.read().decode('utf-8', 'ignore')[:150]}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"[FAIL http {e.code}] 鉴权失败，检查 api_key")
        else:
            print(f"[OK 鉴权通过] HTTP {e.code}（key 有效，该码为接口正常返回）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="仅验证鉴权，不计费")
    ap.add_argument("--channel", required=True, choices=sorted(CHANNELS))
    ap.add_argument("--prompt", default="")
    ap.add_argument("--shots", default="", help="shot_prompts.txt，每行 <shot_id>\\t<prompt>")
    ap.add_argument("--shot", default="", help="单条/补下时用的 shot_id")
    ap.add_argument("--resume-task", default="", help="已有 task_id：只轮询下载不重新提交（配 --shot/--prompt）")
    ap.add_argument("--duration", type=int, default=5)
    ap.add_argument("--resolution", default="1080p")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--cost", default="", help="实际成本(元/条)，生成后补填")
    args = ap.parse_args()

    cfg = load_channel(args.channel)
    if args.check:
        check_auth(cfg)
        return

    adapters = CHANNELS[args.channel]
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.resume_task:   # 断点补下：任务已在服务端，只轮询拿链接，不重新生成
        elapsed, video_url = adapters["poll"](args.resume_task, cfg)
        out = os.path.join(OUT_DIR, f"{args.channel}_{args.shot or 'resume'}_{stamp}.mp4")
        urllib.request.urlretrieve(video_url, out)   # ⚠️ 链接仅 24h 有效，立即下载
        md5 = hashlib.md5(args.prompt.encode("utf-8")).hexdigest()[:8] if args.prompt else ""
        record({"channel": args.channel, "shot_id": args.shot or "resume", "prompt_md5": md5,
                "耗时秒": round(elapsed), "成本元": args.cost, "画质分": "", "一致性分": "",
                "中文适配分": "", "样片链接": out, "备注": f"resume task {args.resume_task}"})
        print(f"[ok] 补下 task {args.resume_task} -> {out}")
        return

    items = read_items(args.prompt, args.shots)
    for shot_id, prompt in items:
        print(f"[submit] {args.channel} shot={shot_id} {args.duration}s {args.resolution} {args.aspect} ...", flush=True)
        task_id = adapters["submit"](prompt, args.duration, args.resolution, args.aspect, cfg)
        print(f"[task] {task_id} 轮询中...", flush=True)
        elapsed, video_url = adapters["poll"](task_id, cfg)
        out = os.path.join(OUT_DIR, f"{args.channel}_{shot_id}_{stamp}.mp4")
        urllib.request.urlretrieve(video_url, out)   # ⚠️ 链接仅 24h 有效，立即下载
        md5 = hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8]
        note = (f"{cfg['model']} {args.resolution} 时长/画幅模型自动 logo=off"
                if adapters.get("auto_params")
                else f"{cfg['model']} {args.resolution} {args.aspect} {args.duration}s")
        record({"channel": args.channel, "shot_id": shot_id, "prompt_md5": md5,
                "耗时秒": round(elapsed), "成本元": args.cost, "画质分": "", "一致性分": "",
                "中文适配分": "", "样片链接": out, "备注": note})
        print(f"[ok] 完成 {elapsed:.0f}s -> {out}", flush=True)

    print(f"\n记录已追加 -> {RECORD_CSV}")


if __name__ == "__main__":
    main()
