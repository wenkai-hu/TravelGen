# -*- coding: utf-8 -*-
"""从 Unsplash 拉取核心地标视觉锚点图（Unsplash License：免费商用，无需署名）。

用法:
  python fetch_unsplash_images.py <UNSPLASH_ACCESS_KEY>
  （限速 50 次/小时 免费档，13 地标 × 每地标最多3张 = 13 次搜索请求，足够）

行为:
  - 对每个地标按中英文关键词搜索（英文质量更佳，失败自动回退）
  - 下载 landscape 方向 w=1280 版本到 images/<id>_<n>.jpg
  - 把图片 URL/许可/来源写入 zhejiang_tourism_kb.json 的 images 字段
"""
import json, os, sys, time, urllib.request, urllib.parse

KEY = sys.argv[1]
BASE = "https://api.unsplash.com/search/photos"
KB_PATH = "zhejiang_tourism_kb.json"

# 地标 → 搜索词（英文优先，备选回退）
QUERIES = {
    "西湖": ["West Lake Hangzhou", "Hangzhou West Lake"],
    "灵隐寺": ["Lingyin Temple", "Lingyin Temple Hangzhou"],
    "西溪湿地": ["Xixi Wetland", "Hangzhou wetland"],
    "雷峰塔": ["Leifeng Pagoda", "Leifeng Pagoda Hangzhou"],
    "三潭印月": ["Three Pools Mirroring the Moon", "West Lake Hangzhou"],
    "断桥残雪": ["Broken Bridge West Lake", "West Lake bridge"],
    "苏堤春晓": ["Su Causeway West Lake", "West Lake causeway"],
    "岳王庙": ["Yue Fei Temple Hangzhou", "Hangzhou temple"],
    "乌镇": ["Wuzhen", "Wuzhen water town"],
    "普陀山": ["Mount Putuo", "Putuoshan"],
    "嘉兴南湖": ["Nanhu Lake Jiaxing", "Jiaxing lake"],
    "千岛湖": ["Qiandao Lake", "Thousand Island Lake"],
    "横店影视城": ["Hengdian", "Hengdian film studio"],
}

def search(query, per_page=3):
    url = f"{BASE}?query={urllib.parse.quote(query)}&per_page={per_page}&orientation=landscape"
    req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

kb = json.load(open(KB_PATH, encoding="utf-8"))
os.makedirs("images", exist_ok=True)

for entry in kb["entries"]:
    imgs = []
    for q in QUERIES[entry["name"]]:
        try:
            data = search(q)
            photos = data.get("results", [])
            if photos:
                for p in photos[:3]:
                    u = p["urls"]["raw"] + "&w=1280&q=80"
                    fname = f"images/{entry['id']}_{len(imgs)+1}.jpg"
                    try:
                        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=60) as resp:
                            open(fname, "wb").write(resp.read())
                        imgs.append({"path": fname, "url": p["links"]["html"],
                                     "license": "Unsplash License", "alt": p.get("alt_description", "")})
                        print(f"  ✅ {entry['name']}: {fname} ({q})")
                    except Exception as e:
                        print(f"  ⚠️ {entry['name']}: 下载失败 {type(e).__name__}")
                break
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("  ⚠️ 限速(403)，等待 70s..."); time.sleep(70)
            else:
                print(f"  ❌ {entry['name']}: HTTP {e.code}")
    entry["images"] = imgs
    time.sleep(1.2)  # 免费档限速保护

json.dump(kb, open(KB_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
n = sum(len(e["images"]) for e in kb["entries"])
print(f"\n完成：共下载 {n} 张视觉锚点图")
