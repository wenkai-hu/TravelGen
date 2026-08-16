# -*- coding: utf-8 -*-
"""从 Unsplash 拉取知识库条目的视觉锚点图（Unsplash License：免费商用，无需署名）。

用法:
  python fetch_unsplash_images.py <UNSPLASH_ACCESS_KEY> [景点名...]
  # 不传景点名则处理全部无图条目；可指定只拉某几个

行为:
  - 搜索词优先取条目 images_search 字段（kb_extend.py 生成），缺失则用名称拼音兜底
  - 下载 landscape 方向 w=1280 版本到 images/<id>_<n>.jpg
  - 把图片路径/许可/来源写入 zhejiang_tourism_kb.json 的 images 字段
  - 免费档限速 50 次/小时，403 自动等待后重试
"""
import json, os, sys, time, urllib.request, urllib.parse

# 优先从环境变量取 key（推荐，避免 key 出现在命令行历史）；否则取 argv[1]
if os.environ.get("UNSPLASH_ACCESS_KEY"):
    KEY = os.environ["UNSPLASH_ACCESS_KEY"]
    TARGETS = sys.argv[1:] or None   # 位置参数全部是景点名
else:
    KEY = sys.argv[1] if len(sys.argv) > 1 else ""
    TARGETS = sys.argv[2:] or None   # 位置参数 = key + 景点名
if not KEY:
    sys.exit("用法: UNSPLASH_ACCESS_KEY=xxx python fetch_unsplash_images.py [景点名...]")

BASE = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE, "zhejiang_tourism_kb.json")


def search(query, per_page=3):
    url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&per_page={per_page}&orientation=landscape"
    req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {KEY}",
                                               "User-Agent": "Mozilla/5.0 (TravelGen-KB)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ascii_url(u):
    """Unsplash 个别图片 URL 含非 ASCII 字符，urllib 需百分号编码后才能请求。"""
    return urllib.parse.quote(u, safe=":/?&=%+-_,.;[]@!$'()*")


kb = json.load(open(KB_PATH, encoding="utf-8"))
os.makedirs(os.path.join(BASE, "images"), exist_ok=True)

for entry in kb["entries"]:
    if TARGETS and entry["name"] not in TARGETS:
        continue
    if entry.get("images"):
        print(f"跳过 {entry['name']}（已有 {len(entry['images'])} 张图）")
        continue

    queries = entry.get("images_search") or [entry["name"], f"{entry['city']} {entry['name']}"]
    imgs = []
    for q in queries:
        try:
            data = search(q)
            photos = data.get("results", [])
            if not photos:
                print(f"  ⚠️ {entry['name']}: 关键词 '{q}' 无搜索结果")
            for p in photos[:3]:
                u = ascii_url(p["urls"]["raw"] + "&w=1280&q=80")
                fname = os.path.join(BASE, "images", f"{entry['id']}_{len(imgs)+1}.jpg")
                try:
                    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        open(fname, "wb").write(resp.read())
                    imgs.append({"path": os.path.relpath(fname, BASE), "url": p["links"]["html"],
                                 "license": "Unsplash License", "alt": p.get("alt_description", "")})
                    print(f"  ✅ {entry['name']}: {os.path.basename(fname)} ({q})")
                except Exception as e:
                    print(f"  ⚠️ {entry['name']}: 下载失败 {type(e).__name__}")
            break
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("  ⚠️ 限速(403)，等待 70s..."); time.sleep(70)
            else:
                print(f"  ❌ {entry['name']}: HTTP {e.code}")
        except Exception as e:
            import traceback
            print(f"  ❌ {entry['name']}: {type(e).__name__}")
            traceback.print_exc(limit=3)
    entry["images"] = imgs
    time.sleep(1.2)

json.dump(kb, open(KB_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
n = sum(len(e["images"]) for e in kb["entries"])
print(f"\n完成：知识库现有 {n} 张视觉锚点图")
