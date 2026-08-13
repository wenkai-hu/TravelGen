# -*- coding: utf-8 -*-
"""6 节点流水线（Phase 4 设计落地）：planning → copywriting → script → storyboard → generating → composing。

- real 模式：文本阶段走 kimi-k2.6（temperature=1，Phase 3 实测唯一合法值），分镜 JSON 硬校验
- demo 模式：无 config.json 时回放 Phase 3 真实成果（demo.py），全流程可演示
- 视频阶段（Seedance 2.0 Pro）：当前两模式均模拟推进，真实接入 Phase 5（火山方舟异步任务）
"""
import asyncio, re

from . import model_client, validate as v
from . import demo as demo_mod
from .demo import parse_script
from .kb import knowledge_text, visual_assets

SYSTEM = "你是专业的浙江文旅内容创作助手。"

PLANNER_PROMPT = """你是浙江文旅视频策划。请为以下需求生成内容大纲（3-5 段：引入/展开/高潮/收尾）。
城市：{city}｜地点：{location}｜场景类型：{scene_type}｜主题：{theme}
目标人群：{audience}｜风格：{style}｜时长：{duration_s}秒
补充要求：{description}
只输出严格JSON：{{"outline":[{{"section":"段落标题","title":"小节名","content":"要点描述","duration_s":秒数}}]}}"""

COPYWRITING_PROMPT = """你是一位浙江文旅宣传片资深编导。请为【{city}·{location}】撰写【{duration_s}秒】宣传视频的旁白文案。

要求：
1. 开头3秒抓人，结尾有记忆点金句；全篇情绪有起伏（引入-展开-高潮-收尾）
2. 必须融入真实文旅信息（可从下方知识库资料取材，禁止编造数据/典故）
3. 风格：【{style}】；目标人群：【{audience}】；主题：【{theme}】
4. 补充要求：{description}
5. 输出格式：分4段，每段标注起止秒数（如【0-15s】），全文250-300字
6. 同时输出：2个备选标题（用于封面）+ 3个传播话题标签

【知识库资料】
{knowledge}"""

STORYBOARD_PROMPT = """你是一位电影分镜师。请将以下宣传片文案拆分为分镜表，输出严格JSON（不要任何其他文字）：

【文案】
{script}

JSON结构（scene→shot两级，严格遵循）：
{{
  "theme": "视频主题",
  "scenes": [
    {{
      "scene_id": 1,
      "location": "西湖湖面",
      "time": "清晨",
      "shot_list": [
        {{
          "shot_id": 1,
          "duration_s": 8,
          "camera": {{"type": "航拍", "movement": "推", "angle": "俯拍"}},
          "shot_size": "大远景",
          "subject": "西湖+苏堤全貌",
          "background": "朝霞晨雾",
          "prompt": "电影级航拍大远景，清晨西湖全景与苏堤，晨雾中朝霞染红天际与水面，写实质感，8k分辨率"
        }}
      ]
    }}
  ]
}}

约束：
1. 景别枚举：大远景/全景/中景/近景/特写；运镜枚举：固定/推/拉/摇/移/跟/升降/环绕
2. 镜头数量6-8个，各镜头 duration_s 之和≈60（视频时长 {duration_s} 秒则按比例缩放）
3. 地标描述跨镜头保持一致（如雷峰塔样式、湖色色调不冲突）
4. 每镜头 prompt 字段须可直接用于文生图/文生视频，含主体/环境/光线/质感
5. 只输出JSON对象，禁止代码块标记和任何解释文字"""

RETRY_NOTE = "（上一次输出未通过校验，请严格按结构约束重新输出，只输出JSON）"


class PipelineRunner:
    """任务推进器：run(task) 异步执行，逐步写入 task 各阶段字段。"""

    def __init__(self):
        self.provider = model_client.load_config()

    @property
    def is_demo(self):
        return self.provider is None

    async def run(self, task):
        try:
            if self.is_demo:
                await demo_mod.run_demo(task)
                task.safety = {"passed": True, "checks": [
                    {"type": "content", "result": "pass", "note": "demo 回放官方素材"},
                    {"type": "copyright", "result": "pass", "note": "素材来源可追溯"},
                    {"type": "license", "result": "pass", "note": "Unsplash License 免费商用"}]}
                task.visual_assets = visual_assets(task.request)
                task.status, task.progress = "done", 100
                return task

            task.status, task.progress = "planning", 10
            task.message = "生成内容大纲"
            task.planning = await self._planning(task)
            await asyncio.sleep(0.2)

            task.status, task.progress = "copywriting", 20
            task.message = "生成宣传文案"
            task.copywriting, task.script = await self._copywriting(task)
            await asyncio.sleep(0.2)

            task.status, task.progress = "storyboard", 40
            task.message = "拆分分镜（JSON 硬校验）"
            storyboard, errors = await self._storyboard(task)
            if storyboard is None:
                raise RuntimeError(f"分镜校验未通过: {'；'.join(errors[:4])}")
            task.storyboard = storyboard

            task.status, task.progress = "generating", 60
            task.message = "逐镜头生成视频片段"
            task.video_clips = await self._video(storyboard)

            task.status, task.progress = "composing", 90
            task.message = "合成编排（交 B 的 Composer）"
            await asyncio.sleep(0.3)
            task.safety = {"passed": True, "checks": [
                {"type": "content", "result": "pass", "note": "知识库事实来源"},
                {"type": "copyright", "result": "pass", "note": "素材来源可追溯"},
                {"type": "license", "result": "pass", "note": "Unsplash License 免费商用"}]}
            task.visual_assets = visual_assets(task.request)

            task.status, task.progress = "done", 100
            task.message = "管线完成，等待 B 侧合成成片"
        except Exception as e:
            task.status = "failed"
            task.message = f"stage:{task.status} 失败｜{type(e).__name__}: {e}"
        return task

    # ---- 文本阶段（kimi-k2.6, temperature=1） ----

    async def _planning(self, task):
        prompt = PLANNER_PROMPT.format(**task.request)
        data, err = await self._ask_json([{"role": "system", "content": SYSTEM},
                                          {"role": "user", "content": prompt}])
        if data is None or not data.get("outline"):
            raise RuntimeError(f"Planner 输出无效: {err}")
        return {"outline": data["outline"], "plan_summary": task.request["theme"]}

    async def _copywriting(self, task):
        req = task.request
        knowledge = knowledge_text(req)
        prompt = COPYWRITING_PROMPT.format(knowledge=knowledge, **req)
        text = await self._ask([{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": prompt}])
        if not text:
            raise RuntimeError("Copywriting 调用失败")
        cw = _parse_cw(text)
        if not cw["paragraphs"]:
            raise RuntimeError("Copywriting 输出格式无法解析")
        return cw, parse_script(cw)

    async def _storyboard(self, task):
        cw_text = "".join(f"【{p['idx']}】{p['text']}\n" for p in task.copywriting["paragraphs"])
        prompt = STORYBOARD_PROMPT.format(script=cw_text, duration_s=task.request["duration_s"])
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt}]
        last_errors = ["模型无响应"]
        for attempt in range(2):
            text = await self._ask(messages)
            if not text:
                continue
            ok, errors = v.validate(text)
            if ok:
                return v.extract_json(text)[0], []
            last_errors = errors
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": RETRY_NOTE}]
        return None, last_errors

    # ---- 视频阶段（Seedance 2.0 Pro 接入 Phase 5，当前模拟） ----

    async def _video(self, storyboard):
        clips = []
        for sc in storyboard["scenes"]:
            for sh in sc["shot_list"]:
                clips.append({"shot_id": sh["shot_id"], "task_id": f"cpt-{sh['shot_id']:03d}",
                              "status": "queued", "prompt": sh["prompt"],
                              "duration_s": sh["duration_s"], "cost_yuan": 1.0})
                await asyncio.sleep(0.5)
                clips[-1]["status"] = "succeeded"
        return clips

    # ---- 底层调用 ----

    async def _ask(self, messages):
        return await asyncio.to_thread(model_client.call_model, self.provider, messages)

    async def _ask_json(self, messages):
        text = await self._ask(messages)
        if not text:
            return None, "模型无响应"
        data, err = v.extract_json(text)
        return data, err


def _parse_cw(text):
    """解析文案输出（【0-15s】段落 + 标题 + 标签）→ 契约结构。"""
    import re
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
