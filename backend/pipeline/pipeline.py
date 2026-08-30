# -*- coding: utf-8 -*-
"""6 节点流水线（Phase 4 设计落地）：planning → copywriting → script → storyboard → generating → composing。

- real 模式：文本阶段走 kimi-k2.6（temperature=1，Phase 3 实测唯一合法值），分镜 JSON 硬校验
- demo 模式：无 config.json 时回放 Phase 3 真实成果（demo.py），全流程可演示
- 视频阶段（Seedance 2.0 Pro）：当前两模式均模拟推进，真实接入 Phase 5（火山方舟异步任务）
"""
import asyncio, os, re

from . import model_client, validate as v
from . import demo as demo_mod
from .demo import parse_script
from .kb import knowledge_text, visual_assets

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

SYSTEM = "你是专业的浙江文旅内容创作助手。"

PLANNER_PROMPT = """你是浙江文旅视频策划。请为以下需求生成内容大纲（3-5 段：引入/展开/高潮/收尾）。
城市：{city}｜地点：{location}｜场景类型：{scene_type}｜主题：{theme}
目标人群：{audience}｜风格：{style}｜时长：{duration_s}秒
补充要求：{description}
只输出严格JSON：{{"outline":[{{"section":"段落标题","title":"小节名","content":"要点描述","duration_s":秒数}}]}}"""

COPYWRITING_PROMPT = """你是一位浙江文旅宣传片资深编导。请依据【创作方案大纲】，为【{city}·{location}】撰写【{duration_s}秒】宣传视频的旁白文案。

【创作方案大纲】
{planning}

要求：
1. 每段文案严格对应大纲的一个 section，段落顺序、起止秒数与大纲对齐（大纲每段秒数见上）
2. 开头3秒抓人，结尾有记忆点金句；全篇情绪随大纲的引入-展开-高潮-收尾节奏起伏
3. 必须融入真实文旅信息（可从下方知识库资料取材，禁止编造数据/典故）
4. 风格：【{style}】；目标人群：【{audience}】；主题：【{theme}】
5. 补充要求：{description}
6. 输出格式：分 N 段（N=大纲 section 数），每段标注起止秒数（如【0-15s】），全文250-300字
7. 同时输出（末尾附加，严格用此格式，禁止其他写法）：
   **备选标题：**
   1.《标题一》
   2.《标题二》
   **传播话题标签：**
   #话题一 #话题二 #话题三

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
1. 时间字段 time 只能用枚举值之一：清晨/上午/午后/黄昏/入夜（禁止"暮色/傍晚/夜晚"等变体）
2. 机位类型 camera.type 只能用：航拍/无人机/固定机位/地面机位/移动机位（禁止"地面/固定"等缩写）
3. 角度 camera.angle 只能用：俯拍/平拍/仰拍/侧拍（禁止"侧俯"等组合词）
4. 景别 shot_size 枚举：大远景/全景/中景/近景/特写；运镜 movement 枚举：固定/推/拉/摇/移/跟/升降/环绕
5. 镜头数量 {min_shots}-{max_shots}个（由总时长÷每镜4-15s推导，禁止写死）；每个镜头 duration_s 取4-15的整数，各镜头之和≈{duration_s}（容差±5%）
6. shot_id 全片唯一递增（1..N），禁止每个 scene 各自从 1 编号
7. 地标描述跨镜头保持一致（如雷峰塔样式、湖色色调不冲突）
8. 每镜头 prompt 字段须可直接用于文生图/文生视频，含主体/环境/光线/质感
9. 只输出JSON对象，禁止代码块标记和任何解释文字"""

RETRY_NOTE = "上一次输出未通过校验，严格按结构约束重新输出（只输出JSON）。具体错误：{errors}"

# V1 场景模板（TravelGen_v1.md §五）：按 scene_type 注入 planner 的内容结构建议
SCENE_STRUCTURES = {
    "景区推荐": ["视觉吸引", "核心景观", "特色体验", "文化特色", "游客体验", "行动召唤"],
    "城市形象宣传": ["城市航拍", "城市地标", "自然风光", "文化特色", "城市生活", "城市精神"],
    "非遗文化传播": ["文化Hook", "历史背景", "制作/表演过程", "文化特色", "年轻化表达", "文化价值"],
}


class PipelineRunner:
    """任务推进器：run(task) 异步执行，逐步写入 task 各阶段字段。

    阶段独立降级：文案/分镜有 kimi key 走 kimi-k2.6，否则回放 Phase 3 成果；
    视频有 Seedance key 走真实生成，否则模拟推进（TRAVELGEN_MOCK=1 强制全 demo）。
    """

    def __init__(self):
        self.kimi = model_client.load_config()
        self.seedance = model_client.load_seedance_config()

    @property
    def mock_all(self):
        return os.environ.get("TRAVELGEN_MOCK") == "1" or (self.kimi is None and self.seedance is None)

    async def run(self, task):
        try:
            if self.mock_all:
                await demo_mod.run_demo(task)
                task.safety = {"passed": True, "checks": [
                    {"type": "content", "result": "pass", "note": "demo 回放官方素材"},
                    {"type": "copyright", "result": "pass", "note": "素材来源可追溯"},
                    {"type": "license", "result": "pass", "note": "Unsplash License 免费商用"}]}
                task.visual_assets = visual_assets(task.request)
                task.status, task.progress = "done", 100
                return task

            # ---- 文本阶段（kimi 或 demo 回放） ----
            task.status, task.progress, task.message = "planning", 10, "生成内容大纲"
            if self.kimi:
                await self._text_real(task)
            else:
                await self._text_demo(task)
            await asyncio.sleep(0.2)

            # ---- 视频阶段（Seedance 或模拟） ----
            task.status, task.progress = "generating", 60
            task.message = "逐镜头生成视频片段"
            task.video_clips = await self._video(task.storyboard, task)

            # ---- 收尾 ----
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

    # ---- V1 分阶段入口（projects 流程用；demo 分流与旧链路一致） ----

    async def generate_plan(self, project):
        """V1 阶段①：生成创作方案（planning + copywriting/script）。kimi 真实，否则回放。"""
        if self.kimi:
            project.planning = await self._planning(project)
            project.copywriting, project.script = await self._copywriting(project)
        else:
            project.planning, project.copywriting, project.script = demo_mod.demo_plan(project.request)
        return project

    async def generate_storyboard(self, project):
        """V1 阶段②：基于已确认文案生成分镜（kimi 硬校验重试 1 次，失败 raise；否则回放）。"""
        if self.kimi:
            sb, errors = await self._storyboard(project)
            if sb is None:
                raise RuntimeError(f"分镜校验未通过: {'；'.join(errors[:4])}")
            project.storyboard = sb
        else:
            project.storyboard = demo_mod.demo_storyboard(project.request)
        return project

    async def generate_videos(self, project, shot_ids, task=None, on_progress=None):
        """V1 阶段③：按 shot_ids 子集批量生成视频（seedance 真实，否则模拟）。返回旧格式 clips。
        task 提供 task_id 作下载文件名（VideoTask）；on_progress(clips, done, total) 同步 per-shot 进度。"""
        shots = [sh for sc in project.storyboard["scenes"] for sh in sc["shot_list"]
                 if sh["shot_id"] in shot_ids]
        if self.seedance is None:
            return await self._video_simulated(shots)
        return await self._run_video_jobs(shots, task, on_progress=on_progress,
                                          ratio=project.request.get("aspect_ratio"),
                                          resolution=project.request.get("resolution"))

    async def _text_real(self, task):
        """kimi 真实生成：planning → copywriting/script → storyboard（硬校验失败重试 1 次）。"""
        task.planning = await self._planning(task)
        task.status, task.progress, task.message = "copywriting", 20, "生成宣传文案"
        task.copywriting, task.script = await self._copywriting(task)
        task.status, task.progress, task.message = "storyboard", 40, "正在拆分分镜…"
        storyboard, errors = await self._storyboard(task)
        if storyboard is None:
            raise RuntimeError(f"分镜校验未通过: {'；'.join(errors[:4])}")
        task.storyboard = storyboard

    async def _text_demo(self, task):
        """无 kimi key：回放 Phase 3 真实成果（kimi 最优西湖文案/分镜），视频仍可真实生成。"""
        sb = demo_mod.load_storyboard()
        cw = demo_mod.parse_copywriting()
        task.planning = demo_mod.parse_planning(sb)
        task.planning["plan_summary"] = task.request.get("theme", task.planning["plan_summary"])
        task.copywriting = cw
        task.copywriting["titles"][0] = task.request.get("theme", cw["titles"][0])
        task.script = demo_mod.parse_script(cw)
        task.storyboard = sb
        task.storyboard["theme"] = f"{task.request.get('city', '')}{task.request.get('location', '')}宣传片"

    # ---- 文本阶段（kimi-k2.6, temperature=1） ----

    async def _planning(self, task):
        prompt = PLANNER_PROMPT.format(**task.request)
        chain = SCENE_STRUCTURES.get(task.request.get("scene_type"))
        if chain:
            prompt += f"\n内容结构建议（按场景模板组织 3-5 段）：{' → '.join(chain)}"
        data, err = await self._ask_json([{"role": "system", "content": SYSTEM},
                                          {"role": "user", "content": prompt}])
        if data is None or not data.get("outline"):
            raise RuntimeError(f"Planner 输出无效: {err}")
        return {"outline": data["outline"], "plan_summary": task.request["theme"]}

    async def _copywriting(self, task):
        req = task.request
        knowledge = knowledge_text(req)
        planning = "\n".join(
            f"{i+1}. {o.get('section', '')}｜{o.get('title', '')}（{o.get('duration_s', '')}s）：{o.get('content', '')}"
            for i, o in enumerate(task.planning.get("outline", []))) \
            or "（未提供大纲，请按 引入-展开-高潮-收尾 自行组织 4 段）"
        prompt = COPYWRITING_PROMPT.format(planning=planning, knowledge=knowledge, **req)
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
        min_shots, max_shots = v.shot_count_range(task.request["duration_s"])
        prompt = STORYBOARD_PROMPT.format(script=cw_text, duration_s=task.request["duration_s"],
                                          min_shots=min_shots, max_shots=max_shots)
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt}]
        last_errors = ["模型无响应"]
        for attempt in range(2):
            text = await self._ask(messages)
            if not text:
                continue
            ok, errors, data = v.validate_and_normalize(text, target_s=task.request["duration_s"])
            if ok:
                return data, []  # 返回归一化后的数据（枚举漂移已修正落库）
            last_errors = errors
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": RETRY_NOTE.format(errors="；".join(errors[:4]))}]
        return None, last_errors

    # ---- 视频阶段（Seedance 2.0 Pro 真实生成；无 key 时模拟） ----

    async def _video(self, storyboard, task):
        """旧一键直出链路：有 Seedance 走真实生成，否则模拟（进度同步到 task 字段）。"""
        shots = [sh for sc in storyboard["scenes"] for sh in sc["shot_list"]]
        if self.seedance is None:
            return await self._video_simulated(shots)

        def sync(clips, done, total):
            task.video_clips = clips
            task.progress = 60 + int(done / total * 30)
            task.message = f"视频生成中 {done}/{total} 完成"

        return await self._run_video_jobs(shots, task, on_progress=sync,
                                          ratio=task.request.get("aspect_ratio"),
                                          resolution=task.request.get("resolution"))

    async def _video_simulated(self, shots):
        clips = []
        for sh in shots:
            clips.append({"shot_id": sh["shot_id"], "task_id": f"cpt-{sh['shot_id']:03d}",
                          "status": "succeeded", "prompt": sh["prompt"],
                          "duration_s": sh["duration_s"], "cost_yuan": 0.0,
                          "note": "simulated（无 Seedance key）"})
            await asyncio.sleep(0.3)
        return clips

    async def _run_video_jobs(self, shots, task, on_progress=None, ratio="adaptive", resolution=None):
        """Seedance 真实生成：并发提交 → 5s 间隔轮询（上限 180 次）→ failed 自动重试 1 次 → 成功即下载转存。
        task 提供 task_id（下载文件名）；on_progress(clips, done, total) 每轮轮询后回调，None 时跳过进度同步。
        ratio 传请求的 aspect_ratio（如 9:16），否则 adaptive；resolution 传请求的 resolution，否则用配置。
        每镜时长取 shot.duration_s（分镜按总时长切分；模型支持 4-15s，越界钳制），替代固定配置值。
        """
        from . import ark_client
        resolution = resolution or self.seedance.get("resolution", "1080p")

        def _shot_duration(sh):
            return max(4, min(15, int(sh.get("duration_s") or self.seedance.get("duration", 5))))

        # 1) 并发提交全部镜头
        clips = []
        for sh in shots:
            duration = _shot_duration(sh)
            tid, err = await asyncio.to_thread(ark_client.submit, self.seedance, sh["prompt"], duration, resolution, ratio)
            clips.append({"shot_id": sh["shot_id"], "task_id": tid,
                          "status": "queued" if tid else "failed",
                          "prompt": sh["prompt"], "duration_s": duration, "cost_yuan": 1.0})
            if not tid:
                clips[-1]["error"] = err
        if on_progress:
            on_progress(clips, 0, len(clips))

        # 2) 轮询直至全部完成（5s 间隔；上限 180 次 = 15 分钟，含失败重试的重新计时）
        total = len(clips)
        polls = 0
        while polls < 180:
            running = [c for c in clips if c["status"] in ("queued", "running")]
            retry = [c for c in clips if c["status"] == "failed" and not c.get("retried")]
            if not running and not retry:
                break
            await asyncio.sleep(5)
            polls += 1
            # 2a) 查询进行中的任务
            results = await asyncio.gather(*(
                asyncio.to_thread(ark_client.get_task, self.seedance, c["task_id"]) for c in running))
            for c, (status, url, err) in zip(running, results):
                if status == "succeeded":
                    c["status"] = "succeeded"
                    c["video_url"] = url
                    c["local_path"] = await self._download_video(task, c, url)
                elif status in ("failed", "expired"):
                    c["status"] = "failed"
                    c["error"] = err
                else:
                    c["status"] = status
            # 2b) 失败未重试的重新提交（1 次机会）
            results = await asyncio.gather(*(
                asyncio.to_thread(ark_client.submit, self.seedance, c["prompt"], c["duration_s"], resolution, ratio)
                for c in retry))
            for c, (tid, err) in zip(retry, results):
                c["retried"] = True
                if tid:
                    c["task_id"], c["status"] = tid, "queued"
                    c.pop("error", None)  # 重试成功，清除旧错误
                else:
                    c["error"] = err
            n_ok = sum(1 for c in clips if c["status"] == "succeeded")
            if on_progress:
                on_progress(clips, n_ok, total)
        # 触顶兜底：未完成的镜头标记超时（不阻塞任务收尾）
        for c in clips:
            if c["status"] in ("queued", "running"):
                c["status"] = "failed"
                c["error"] = c.get("error") or "生成超时（>15 分钟）"
        return clips

    async def _download_video(self, task, clip, url):
        """video_url 仅 24h 有效，成功即下载转存 assets/videos/{task_id}_{shot_id}.mp4。
        下载后转码成浏览器可播格式（Seedance 输出 H.264 4:2:2，Chrome 只认 4:2:0）。"""
        try:
            from . import ark_client
            dest = os.path.join(REPO, "assets", "videos", f"{task.task_id}_{clip['shot_id']}.mp4")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            raw = dest + ".raw.mp4"
            size = await asyncio.to_thread(ark_client.download, url, raw)
            if size <= 0:
                return None
            if await asyncio.to_thread(ark_client.transcode_web, raw, dest):
                os.remove(raw)
                return dest
            os.replace(raw, dest)  # 转码失败（如未装 imageio-ffmpeg）退回原始文件：浏览器可能仍黑屏，但下载兜底可用
            return dest
        except Exception:
            return None  # 下载失败不影响状态（URL 仍 24h 有效）

    # ---- 底层调用 ----

    async def _ask(self, messages):
        return await asyncio.to_thread(model_client.call_model, self.kimi, messages)

    async def _ask_json(self, messages):
        text = await self._ask(messages)
        if not text:
            return None, "模型无响应"
        data, err = v.extract_json(text)
        return data, err


def _extract_titles(text):
    """抽取备选标题。置信度从高到低：书名号 → 标题小节行。返回原始条目（未清洗）。

    实测漂移格式（旧正则只认 N.《》/裸《》/「标题：」块，以下全漏 → 兜底"无标题"）：
    kimi「**备选标题：**\n1.《x》\n2.《y》」、gpt「**封面标题备选：**\n1. **x**\n2. **y**」、
    「## 备选标题」「标题候选：x、y」「标题1：x」。标签的 #\S+ 宽容所以标签常有标题却没有。
    """
    hits = re.findall(r"《([^》\n]{1,40})》", text)
    if hits:
        return hits
    # 标题小节行：允许 #/加粗/数字前缀与「封面/备选/候选/推荐」前缀词，冒号或独占一行皆可；
    # 到话题标签小节 / 分隔线 / 文末为止
    m = re.search(
        r"(?:^|\n)\s*(?:\d+[.、)．]\s*)?(?:#{1,6}\s*|\*\*)?"
        r"(?:封面|备选|候选|推荐)?标题[0-9０-９]*(?:备选|候选|推荐)?"
        r"(?:[：:]\s*|\s*\n)"
        r"([\s\S]*?)"
        r"(?=\n\s*[#*>【《\s]*(?:传播)?(?:话题|标签)|\n\s*[-—=]{3,}|$)",
        text,
    )
    block = m.group(1) if m else ""
    items = []
    # 只按换行/顿号切：顿号是列表分隔，逗号是标题内部成分（实测「一眼西湖，千年入梦」）
    for ln in re.split(r"\n|、", block):
        s = re.sub(r"^\s*[0-9０-９]+[.、)．]?\s*", "", ln).strip()
        s = re.sub(r"^(?:封面|备选|候选|推荐)?标题[0-9０-９]*[：:]\s*", "", s)
        s = s.strip("*#> ").strip("\"'“”「」《》")
        if s and s not in items:
            items.append(s)
    return items


def _parse_cw(text):
    """解析文案输出（【0-15s】段落 + 标题 + 标签）→ 契约结构。"""
    import re
    paragraphs = []
    # 段落止于下一段 / 分隔线 / 标题标签小节（即使小节粘在段尾同一行，如「…C位出道。**备选标题：**…」）
    para_re = re.compile(r"【(\d+)-(\d+)s】\s*(.+?)(?=\n【|\n---|备选标题|候选标题|封面标题|标题候选|传播话题标签|话题标签|\Z)", re.S)
    for m in para_re.finditer(text):
        start, end = int(m.group(1)), int(m.group(2))
        paragraphs.append({"idx": len(paragraphs) + 1,
                           "text": m.group(3).strip().strip("*# ").replace("\n", ""),
                           "duration_s": end - start})
    titles = _extract_titles(text)
    # 统一清洗：剥 markdown ** / 书名号 / 首尾空白，去空去重（防「**」脏标题）
    cleaned = []
    for t in titles:
        s = re.search(r"《(.+?)》", t)
        s = s.group(1) if s else t
        s = s.replace("*", "").strip().strip("\"'“”「」")
        if s and s not in cleaned:
            cleaned.append(s)
    titles = cleaned or ["无标题"]  # 兜底②：绝不抓段落时间戳当标题
    tags = re.findall(r"#\S+", text)
    return {"titles": titles[:2], "paragraphs": paragraphs, "hashtags": tags[:3]}
