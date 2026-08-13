# -*- coding: utf-8 -*-
"""分镜 JSON 硬校验（Storyboard Schema v1，docs/Storyboard_Schema_v1.md）+ 枚举归一化。

策略（三层防线）：
1. 校验：枚举逐项检查 + 镜头数 6-8 + 总时长 60±5
2. 归一化：LLM 常见枚举漂移（如 "暮色"→"黄昏"、"侧俯"→"侧拍"、"地面"→"地面机位"）自动修正后落库
3. 无法归一化的字段仍判失败 → 上游带错误重试
"""
import json, re

TIME_ENUM = ["清晨", "上午", "午后", "黄昏", "入夜"]
CAMERA_TYPE_ENUM = ["航拍", "无人机", "固定机位", "地面机位", "移动机位"]
MOVEMENT_ENUM = ["固定", "推", "拉", "摇", "移", "跟", "升降", "环绕"]
ANGLE_ENUM = ["俯拍", "平拍", "仰拍", "侧拍"]
SHOT_SIZE_ENUM = ["大远景", "全景", "中景", "近景", "特写"]

# 常见变体 → 标准枚举（LLM 漂移实测：暮色/侧俯/地面/推进 等）
TIME_ALIASES = {"暮色": "黄昏", "夕照": "黄昏", "傍晚": "黄昏", "夜晚": "入夜", "深夜": "入夜",
                "黎明": "清晨", "拂晓": "清晨", "日出": "清晨", "白天": "上午", "正午": "午后",
                "中午": "午后", "午后时光": "午后", "清晨日出": "清晨"}
CAMERA_ALIASES = {"地面": "地面机位", "固定": "固定机位", "移动": "移动机位", "航拍机": "航拍",
                  "无人机航拍": "无人机", "空中": "航拍"}
ANGLE_ALIASES = {"侧俯": "侧拍", "俯侧": "俯拍", "仰视": "仰拍", "鸟瞰": "俯拍", "平视": "平拍"}
SHOT_ALIASES = {"远景": "大远景", "大全景": "大远景", "全身": "全景", "半身": "中景", "面部": "特写"}
MOVEMENT_ALIASES = {"推进": "推", "拉近": "拉", "推近": "推", "平移": "移", "跟随": "跟",
                    "环绕飞行": "环绕", "上升": "升降", "下降": "升降", "摇移": "摇", "跟拍": "跟"}


def _normalize(value, enum, aliases):
    """枚举归一化：精确 → 别名 → 子串包含 → 组合词首字位置。返回 (归一化值, 是否成功)。"""
    if not isinstance(value, str):
        return value, False
    v = value.strip()
    if v in enum:
        return v, True
    if v in aliases and aliases[v] in enum:
        return aliases[v], True
    for e in enum:  # 子串包含（如 "地面" → "地面机位"、"推进" → "推"）
        if e in v or v in e:
            return e, True
    # 组合词：取位置最靠前的枚举首字（如 "侧俯" → "侧拍"）
    best = None
    for e in enum:
        idx = v.find(e[0])
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, e)
    if best:
        return best[1], True
    return v, False


def extract_json(text):
    """抽取首个 {...} 块解析；返回 (data, error)。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, "未找到 JSON 对象"
    try:
        return json.loads(m.group(0)), ""
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {e}"


def validate_and_normalize(text):
    """完整校验 + 归一化；返回 (ok, errors, data)。ok 时 data 为归一化后的分镜数据。"""
    data, err = extract_json(text)
    if data is None:
        return False, [err], None
    errors = []

    if not isinstance(data, dict) or not isinstance(data.get("theme"), str) or not data["theme"]:
        errors.append("缺少 theme")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return False, errors + ["缺少 scenes 数组"], None

    shots = []
    for sc in scenes:
        sid = sc.get("scene_id")
        if not isinstance(sid, int):
            errors.append(f"scene 非整数编号: {sid}")
        sc["time"], ok_t = _normalize(sc.get("time"), TIME_ENUM, TIME_ALIASES)
        if not ok_t:
            errors.append(f"scene {sid}: time 无法归一化: {sc.get('time')}")
        for sh in sc.get("shot_list", []):
            shots.append(sh)

    for sh in shots:
        sid = sh.get("shot_id")
        if not isinstance(sid, int):
            errors.append("shot 非整数编号")
        if not isinstance(sh.get("duration_s"), int) or not (1 <= sh["duration_s"] <= 15):
            errors.append(f"shot {sid}: duration_s 需为 1-15 的整数")
        cam = sh.setdefault("camera", {})
        cam["type"], ok1 = _normalize(cam.get("type"), CAMERA_TYPE_ENUM, CAMERA_ALIASES)
        cam["movement"], ok2 = _normalize(cam.get("movement"), MOVEMENT_ENUM, MOVEMENT_ALIASES)
        cam["angle"], ok3 = _normalize(cam.get("angle"), ANGLE_ENUM, ANGLE_ALIASES)
        if not ok1:
            errors.append(f"shot {sid}: camera.type 无法归一化: {cam.get('type')}")
        if not ok2:
            errors.append(f"shot {sid}: camera.movement 无法归一化: {cam.get('movement')}")
        if not ok3:
            errors.append(f"shot {sid}: camera.angle 无法归一化: {cam.get('angle')}")
        sh["shot_size"], ok4 = _normalize(sh.get("shot_size"), SHOT_SIZE_ENUM, SHOT_ALIASES)
        if not ok4:
            errors.append(f"shot {sid}: shot_size 无法归一化: {sh.get('shot_size')}")
        for field in ("subject", "background", "prompt"):
            if not isinstance(sh.get(field), str) or not sh[field].strip():
                errors.append(f"shot {sid}: {field} 为空")

    if not 6 <= len(shots) <= 8:
        errors.append(f"镜头总数 {len(shots)} 超出 6-8")
    total = sum(sh.get("duration_s", 0) for sh in shots if isinstance(sh.get("duration_s"), int))
    if not 55 <= total <= 65:
        errors.append(f"总时长 {total}s 超出 60±5")

    return not errors, errors, data


def validate(text):
    """兼容旧接口：只校验不归一化。"""
    ok, errors, _ = validate_and_normalize(text)
    return ok, errors
