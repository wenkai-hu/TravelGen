# -*- coding: utf-8 -*-
"""正式音色/BGM 素材目录，以及独立于曲库的选曲方向建议。"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from . import model_client


REPO = Path(__file__).resolve().parents[2]
VOICE_ROOT = REPO / "assets" / "media" / "voices"
BGM_ROOT = REPO / "assets" / "media" / "bgm"

VOICE_PRESETS = [
    ("voice_01_female_fresh", "清新探索女声", "01_清新探索_女声.wav",
     "年轻清亮女高音、音质纤细通透", ["城市漫游", "小众景点", "轻旅行"]),
    ("voice_02_female_healing", "温柔治愈女声", "02_温柔治愈_女声.wav",
     "成熟温暖女中低音、圆润厚实", ["山水慢游", "疗愈风景", "民宿"]),
    ("voice_03_female_intellectual", "知性人文女声", "03_知性人文_女声.wav",
     "沉静女中低音、略带细微沙感", ["古镇", "博物馆", "非遗故事"]),
    ("voice_04_female_guide", "热情向导女声", "04_热情向导_女声.wav",
     "爽朗厚亮女声、声音有穿透力", ["景区介绍", "路线推荐", "地方体验"]),
    ("voice_05_male_documentary", "沉稳纪录男声", "05_沉稳纪录_男声.wav",
     "低沉厚重男声、略带粗粝颗粒", ["山河大片", "城市历史", "纪录短片"]),
    ("voice_06_male_warm", "温暖故事男声", "06_温暖故事_男声.wav",
     "温暖柔和男中音、亲切细腻", ["人物故事", "地方记忆", "慢旅行"]),
    ("voice_07_male_travel", "轻松漫游男声", "07_轻松漫游_男声.wav",
     "自然松弛的男声、亲切口语感", ["美食探访", "街区漫游", "旅行见闻"]),
    ("voice_08_male_cultured", "儒雅文化男声", "08_儒雅文化_男声.wav",
     "清瘦温雅男中音、略带岁月沙感", ["古建", "古城", "文化遗产"]),
]

BGM_DESCRIPTIONS = {
    "Driving Ambition": "大气、向上、电影配乐感；适合城市天际线、产业、交通和航拍开篇",
    "Hazy After Hours": "都市、时尚、电子氛围；适合夜景、商圈、科技与现代生活",
    "Hip Hop 02": "松弛、积极、节奏稳定；适合城市漫游、街区和人文生活",
    "Serene View": "舒缓、开阔、氛围感；适合湖泊、水乡、山林和慢镜头",
    "Classical vibes 4": "钢琴与弦乐、温暖抒情；适合古镇、园林、晨昏和历史建筑",
    "Love is Eternal": "柔和、带笛声和世界音乐气质；适合竹林、茶园与江南水乡",
    "What About Action?": "明快、现代、律动强；适合市集、音乐节、巡游和活动预告",
    "Feel Alive": "热情、有趣、铜管感；适合开幕、互动、群众笑脸和快切",
    "Holiday Fun": "轻松、友好、节日感适中；适合亲子节庆、文创市集和美食活动",
    "A Decade in Beijing": "东方气质、轻快但不喧闹；适合传统工艺、古建、服饰和民俗",
    "Romantic 03": "世界音乐、木质与原声感；适合手作流程、匠人和器物细节",
    "Relaxation 05": "长笛、竖琴、冥想氛围；适合茶文化、丝绸、青瓷和展陈",
    "Reaching Out": "青春、坚定、独立流行；适合校园建筑、社团和毕业季",
    "Rising Sun": "电子、明亮、有冲劲；适合卡点转场、地标打卡和快节奏混剪",
    "Traveling Along": "轻松、积极、旅行感；适合 Citywalk、骑行和校园日常",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_url(path: Path) -> str:
    return "/assets/" + path.resolve().relative_to((REPO / "assets").resolve()).as_posix()


def voice_presets() -> list[dict]:
    result = []
    for voice_id, name, filename, description, scenes in VOICE_PRESETS:
        path = VOICE_ROOT / filename
        if not path.is_file():
            continue
        digest = _sha256(path)
        result.append({
            "voice_id": voice_id,
            "name": name,
            "description": description,
            "recommended_scenes": scenes,
            "preview_url": f"{_asset_url(path)}?v={digest[:12]}",
            "local_path": str(path),
            "sha256": digest,
            "source": "preset",
        })
    return result


def find_voice(voice_id: str) -> dict | None:
    return next((item for item in voice_presets() if item["voice_id"] == voice_id), None)


def bgm_catalog() -> list[dict]:
    catalog_path = BGM_ROOT / "catalog.csv"
    if not catalog_path.is_file():
        return []
    items = []
    with catalog_path.open(encoding="utf-8-sig", newline="") as source:
        for index, row in enumerate(csv.DictReader(source), 1):
            path = BGM_ROOT / row["file"]
            if not path.is_file():
                continue
            items.append({
                "bgm_id": f"bgm_{index:02d}",
                "scene": row["scene"],
                "scene_type": "打卡视频" if row["scene"] == "校园/城市打卡" else row["scene"],
                "title": row["title"],
                "artist": row["artist"],
                "duration": row["duration"],
                "description": BGM_DESCRIPTIONS.get(row["title"], "文旅短片背景音乐"),
                "preview_url": _asset_url(path),
                "local_path": str(path),
                "source_page": row.get("source_page", ""),
                "license": "Mixkit Stock Music Free License",
            })
    return items


def find_bgm(bgm_id: str) -> dict | None:
    return next((item for item in bgm_catalog() if item["bgm_id"] == bgm_id), None)


def recommend_bgm(project, provider=None) -> dict:
    """给出可在任意曲库中使用的风格方向，不读取本地 BGM 目录。"""
    if provider is None:
        provider = model_client.load_config()
    if not provider:
        raise RuntimeError("KIMI 未配置")
    shots = [{
        "shot_id": shot.get("shot_id"), "duration_s": shot.get("duration_s"),
        "narration": shot.get("narration", ""), "subject": shot.get("subject", ""),
        "prompt": shot.get("prompt", ""),
    } for scene in project.storyboard.get("scenes", []) for shot in scene.get("shot_list", [])]
    brief = {key: project.request.get(key) for key in (
        "scene_type", "theme", "city", "location", "audience", "style", "duration_s", "description")
        if project.request.get(key) is not None}
    prompt = f"""你是文旅短视频音乐编辑。用户对现有曲库可能不满意，请提供在其他曲库搜索音乐的具体方向。
不要挑选、排序或引用本系统已有歌曲，也不要编造可直接下载的曲目。建议应呼应视频节奏和旁白，为人声留空间。
项目需求：{json.dumps(brief, ensure_ascii=False)}
方案：{json.dumps(project.planning, ensure_ascii=False)}
旁白：{project.copywriting_text}
分镜：{json.dumps(shots, ensure_ascii=False)}
只输出 JSON：{{"style":"音乐类型/风格","tempo":"速度范围或节奏特点","instruments":"主要乐器/音色","mood":"情绪走向","reason":"结合方案、旁白和画面的理由","search_keywords":["可用于曲库检索的词"],"example_tracks":["可选的具体参考曲目名称；不确定时留空"]}}
"""
    text = model_client.call_model(provider, [
        {"role": "system", "content": "你是专业的文旅短视频音乐编辑。"},
        {"role": "user", "content": prompt},
    ], temperature=0.3)
    try:
        match = re.search(r"\{.*\}", text or "", re.S)
        data = json.loads(match.group(0)) if match else {}
        fields = ("style", "tempo", "instruments", "mood", "reason")
        result = {key: str(data.get(key, "")).strip() for key in fields}
        if not all(result.values()):
            raise ValueError("KIMI 建议缺少必要字段")
        for key in ("search_keywords", "example_tracks"):
            values = data.get(key, [])
            result[key] = [str(value).strip() for value in values[:5] if str(value).strip()] if isinstance(values, list) else []
        return result
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError("KIMI 返回的选曲建议格式无效") from exc
