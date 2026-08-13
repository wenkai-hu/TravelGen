# -*- coding: utf-8 -*-
"""分镜 JSON 硬校验（Storyboard Schema v1，docs/Storyboard_Schema_v1.md）。

比实验版严格：枚举逐项校验 + 镜头数 6-8 + 总时长 60±5。校验失败不进视频阶段。
"""
import json, re

TIME_ENUM = ["清晨", "上午", "午后", "黄昏", "入夜"]
CAMERA_TYPE_ENUM = ["航拍", "无人机", "固定机位", "地面机位", "移动机位"]
MOVEMENT_ENUM = ["固定", "推", "拉", "摇", "移", "跟", "升降", "环绕"]
ANGLE_ENUM = ["俯拍", "平拍", "仰拍", "侧拍"]
SHOT_SIZE_ENUM = ["大远景", "全景", "中景", "近景", "特写"]


def extract_json(text):
    """抽取首个 {...} 块解析；返回 (data, error)。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, "未找到 JSON 对象"
    try:
        return json.loads(m.group(0)), ""
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {e}"


def validate(text):
    """完整校验；返回 (ok, errors)。errors 为空列表表示通过。"""
    data, err = extract_json(text)
    if data is None:
        return False, [err]
    errors = []

    if not isinstance(data, dict) or not isinstance(data.get("theme"), str) or not data["theme"]:
        errors.append("缺少 theme")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return False, errors + ["缺少 scenes 数组"]

    shots = []
    for sc in scenes:
        sid = sc.get("scene_id")
        if not isinstance(sid, int):
            errors.append(f"scene 非整数编号: {sid}")
        if sc.get("time") not in TIME_ENUM:
            errors.append(f"scene {sid}: time 枚举越界: {sc.get('time')}")
        for sh in sc.get("shot_list", []):
            shots.append(sh)

    for sh in shots:
        sid = sh.get("shot_id")
        if not isinstance(sid, int):
            errors.append("shot 非整数编号")
        if not isinstance(sh.get("duration_s"), int) or not (1 <= sh["duration_s"] <= 15):
            errors.append(f"shot {sid}: duration_s 需为 1-15 的整数")
        cam = sh.get("camera", {})
        if cam.get("type") not in CAMERA_TYPE_ENUM:
            errors.append(f"shot {sid}: camera.type 枚举越界: {cam.get('type')}")
        if cam.get("movement") not in MOVEMENT_ENUM:
            errors.append(f"shot {sid}: camera.movement 枚举越界: {cam.get('movement')}")
        if cam.get("angle") not in ANGLE_ENUM:
            errors.append(f"shot {sid}: camera.angle 枚举越界: {cam.get('angle')}")
        if sh.get("shot_size") not in SHOT_SIZE_ENUM:
            errors.append(f"shot {sid}: shot_size 枚举越界: {sh.get('shot_size')}")
        for field in ("subject", "background", "prompt"):
            if not isinstance(sh.get(field), str) or not sh[field].strip():
                errors.append(f"shot {sid}: {field} 为空")

    if not 6 <= len(shots) <= 8:
        errors.append(f"镜头总数 {len(shots)} 超出 6-8")
    total = sum(sh.get("duration_s", 0) for sh in shots if isinstance(sh.get("duration_s"), int))
    if not 55 <= total <= 65:
        errors.append(f"总时长 {total}s 超出 60±5")

    return not errors, errors
