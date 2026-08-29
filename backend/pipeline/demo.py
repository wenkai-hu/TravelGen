# -*- coding: utf-8 -*-
"""Demo 模式：无 API key 时回放 Phase 3 真实成果（kimi-k2.6 最优文案/分镜，experiments/results/）。

用途：B 克隆仓库后无需 key 即可全流程演示；答辩现场 API 不稳时兜底。
注意：demo 固定回放西湖样例，标题/主题用请求的 theme 覆盖以贴近输入。
"""
import asyncio, json, os, re

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
COPYWRITING_PATH = os.path.join(REPO, "experiments", "results", "best_copywriting.txt")
STORYBOARD_PATH = os.path.join(REPO, "experiments", "results", "best_storyboard.json")


def parse_copywriting(path=COPYWRITING_PATH):
    """解析实验文案（【0-15s】段落 + 备选标题 + 话题标签）→ 契约 copywriting 结构。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    paragraphs = []
    for m in re.finditer(r"【(\d+)-(\d+)s】\s*(.+?)(?=\n【|\n---|\Z)", text, re.S):
        start, end = int(m.group(1)), int(m.group(2))
        paragraphs.append({"idx": len(paragraphs) + 1,
                           "text": m.group(3).strip().replace("\n", ""),
                           "duration_s": end - start})
    titles = re.findall(r"\d+\.\s*《(.+?)》", text)
    if not titles:
        titles = re.findall(r"【(.*?)】", text)[:2]
    tags = re.findall(r"#\S+", text)
    return {"titles": titles[:2], "paragraphs": paragraphs, "hashtags": tags[:3]}


def parse_script(copywriting):
    """文案段落 → 配音稿/字幕稿（契约 script：逐行 + 起止秒）。"""
    lines, t = [], 0
    for p in copywriting["paragraphs"]:
        lines.append({"line_id": len(lines) + 1, "text": p["text"],
                      "start_s": t, "end_s": t + p["duration_s"]})
        t += p["duration_s"]
    return {"lines": lines}


def parse_planning(storyboard):
    """分镜场景 → 内容大纲（契约 planning：3-5 段引入/展开/高潮/收尾）。"""
    return {"outline": [{"section": s["location"], "title": s["shot_list"][0]["subject"],
                         "content": s["shot_list"][0]["prompt"][:40] + "…",
                         "duration_s": sum(sh["duration_s"] for sh in s["shot_list"])}
                        for s in storyboard["scenes"]],
            "plan_summary": storyboard["theme"]}


def load_storyboard(path=STORYBOARD_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def demo_plan(req):
    """回放 Phase 3 成果的 planning/copywriting/script 三件套（标题用请求 theme 覆盖）。"""
    storyboard = load_storyboard()
    copywriting = parse_copywriting()
    planning = parse_planning(storyboard)
    planning["plan_summary"] = req.get("theme", planning["plan_summary"])
    copywriting["titles"][0] = req.get("theme", copywriting["titles"][0])
    return planning, copywriting, parse_script(copywriting)


def demo_storyboard(req, storyboard=None):
    """回放分镜（theme 覆盖为 城市+地点宣传片）。"""
    sb = storyboard if storyboard is not None else load_storyboard()
    sb["theme"] = f"{req.get('city', '')}{req.get('location', '')}宣传片"
    return sb


def demo_clips(storyboard, shot_ids=None):
    """模拟逐镜头视频任务推进（shot_ids 为 None 表示全部镜头，V1 批量/单 shot 生成复用）。"""
    return [{"shot_id": sh["shot_id"], "task_id": f"demo-{sh['shot_id']:02d}",
             "status": "succeeded", "prompt": sh["prompt"],
             "duration_s": sh["duration_s"], "cost_yuan": 0.0}
            for sc in storyboard["scenes"] for sh in sc["shot_list"]
            if shot_ids is None or sh["shot_id"] in shot_ids]


async def run_demo(task):
    """demo 模式全流程：与 real 模式相同状态机，各阶段短延迟让前端可见进度。"""
    task.status, task.progress, task.message = "planning", 10, "生成内容大纲"
    task.planning, task.copywriting, task.script = demo_plan(task.request)
    await asyncio.sleep(0.6)

    task.status, task.progress, task.message = "copywriting", 20, "生成宣传文案"
    await asyncio.sleep(0.6)

    task.status, task.progress, task.message = "storyboard", 40, "正在拆分分镜…"
    task.storyboard = demo_storyboard(task.request)
    await asyncio.sleep(0.6)

    task.status, task.progress, task.message = "generating", 60, "逐镜头生成视频片段"
    task.video_clips = demo_clips(task.storyboard)
    for c in task.video_clips:
        await asyncio.sleep(0.4)

    task.status, task.progress, task.message = "composing", 90, "合成编排（交 B 的 Composer）"
    await asyncio.sleep(0.3)
    return task
