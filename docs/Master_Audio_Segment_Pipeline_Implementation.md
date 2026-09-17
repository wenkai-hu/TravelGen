# TravelGen Master Audio + Segment 管线改造方案

更新时间：2026-09-16。

## 已确认的架构决定

正式成片采用 PoC 的 B 方案：先生成并冻结完整 `master_audio.wav`，Seedance 使用对应的音频切片生成每个 Segment；下载后删除 Seedance 输出音轨，拼接全部静音画面，再把原始 `master_audio.wav` 一次性 mux 到最终画面轨。

生成单位改为 **Segment**，编辑单位继续保留 **Shot**：

- Segment 是一次 Seedance 请求，时长 4–15 秒，包含一个或多个 Shot。
- Shot 是 Segment 内的画面意图、时间窗和参考图绑定，不再独立调用 Seedance。
- Scene 仍表示地点、时段或叙事章节，不能拿 Scene 代替 Segment。
- 修改一个 Shot 会让其所属 Segment 失效；重新生成的是整个 Segment。

当前 PoC 同时向 Seedance 提供了音频和明确的 Shot 时间窗，因此只能证明这组正式候选输入整体有效，不能证明音频单独就能稳定决定切镜。Shot prompt 仍是必要输入。

## 新的执行顺序

```text
参考图确认 / VLM
→ Plan + Copywriting
→ 用户确认旁白文本
→ 按句生成 TTS，取得真实时长
→ 根据 Plan 的情绪段落生成/选择 BGM，混成完整 master_audio.wav
→ Storyboard 根据真实口播时间和音乐 cue 安排 Shot
→ Segment Planner 在完整句子和 Shot 边界处分组
→ 按 Segment 全局时间切 audio_seg_xx.wav
→ 每个 Segment：audio slice + 多 Shot prompt + 去重图片池 → Seedance
→ 保存 Seedance raw，另生成 visual_only.mp4
→ 所有 visual_only 按时间线拼接
→ 一次性回铺 master_audio.wav
→ 字幕/封面/元数据 → final.mp4
```

音频先行不要求先知道 Segment：TTS 按完整句子测时，BGM 根据已经存在的 Plan 情绪段落铺到全片时间轴，先得到完整母带；Storyboard 随后读取旁白时间窗和音乐 cue 元数据，Segment Planner 最后只选择从母带哪里切片。这样既符合“先有 master audio、再切 Segment”，也避免拿尚未生成的 Shot 反过来决定旁白时长。完整母带必须在第一次 Seedance 视频请求前冻结。

## 数据结构

保留现有 `storyboard.scenes[].shot_list[]`，增加稳定的口播和 Segment 关系。建议后端归一化后的结构如下：

```json
{
  "storyboard_version": 2,
  "theme": "西湖文旅短片",
  "scenes": [
    {
      "scene_id": 1,
      "location": "柳浪闻莺",
      "time": "黄昏",
      "shot_list": [
        {
          "shot_id": 1,
          "segment_id": "seg_01",
          "timeline_start_ms": 0,
          "timeline_end_ms": 5000,
          "narration_unit_ids": ["n_01"],
          "prompt": "暮色中的湖岸垂柳近景，缓慢向前推进",
          "reference_asset_ids": ["ref_a"]
        }
      ]
    }
  ],
  "segments": [
    {
      "segment_id": "seg_01",
      "timeline_start_ms": 0,
      "timeline_end_ms": 15000,
      "duration_ms": 15000,
      "shot_ids": [1, 2, 3],
      "narration_unit_ids": ["n_01", "n_02"],
      "reference_asset_ids": ["ref_a", "ref_b"],
      "transition_note": "同一暮色湖岸，沿镜头运动方向自然转场",
      "audio_slice_path": ".../audio_seg_01.wav",
      "audio_slice_sha256": "..."
    }
  ]
}
```

Shot 的时间使用全局时间，编译 Seedance prompt 时减去 Segment 起点得到局部时间。`duration_s` 可以为兼容前端继续返回，但权威字段改为毫秒起止时间。段内 Shot 可短于 4 秒；4–15 秒限制只检查 Segment。

音频建议新增一个权威对象，而不是继续让 `voice`、`music` 三个占位字段彼此分散：

```json
{
  "audio": {
    "status": "ready",
    "version": 1,
    "voice_profile": {"engine": "edge-tts", "voice": "zh-CN-XiaoxiaoNeural", "rate": "-20%"},
    "narration_units": [
      {"unit_id": "n_01", "text": "...", "start_ms": 350, "end_ms": 4210, "asset_path": "..."}
    ],
    "music_cues": [
      {"cue_id": "m_01", "start_ms": 0, "end_ms": 45000, "asset_path": "...", "gain_db": -20}
    ],
    "voice_track_path": ".../voice.wav",
    "master_path": ".../master_audio.wav",
    "master_sha256": "...",
    "duration_ms": 45000
  }
}
```

第一版把旁白按完整句子分别 TTS，再放进全局时间轴。这样不依赖供应商是否返回可靠的逐字时间戳，也能保证 Segment 分界不会切断一句话。

## Shot prompt 是否继续允许修改

需要，而且应继续作为主要人工控制点。音频告诉模型“正在讲什么”和整体节奏，不能可靠指定下面这些内容：

- 使用哪张实景图表现哪一句旁白；
- 主体、景别、机位、运镜和光线；
- 某个主体应在 0–5 秒还是 5–10 秒出现；
- 多 Shot 之间用遮挡、相似构图还是运动方向完成转场；
- 不得增加哪些虚构建筑和不受参考图支持的视角。

变化的是 prompt 的消费方式：

```text
旧：Shot prompt → 一次 Seedance 请求
新：多个 Shot prompt + Segment 过渡约束 + 图片编号 + audio slice
    → compile_segment_input()
    → 一次 Seedance 请求
```

前端继续显示和编辑每个 Shot 的 prompt。用户保存后，后端查到所属 `segment_id`，把该 Segment 标记为 `stale`，并提示“重新生成此 Segment（包含 Shot 4/5/6）”。当前“单镜试生成”和“重新生成此 Shot”按钮应改成“试生成此 Segment”和“重新生成此 Segment”。第一版不把单 Shot 临时生成结果混入正式成片。

同时增加一个较短的 Segment 级字段 `transition_note`，只负责段内统一色调、地点和镜头衔接。不要让用户直接编辑完整的编译后 prompt，否则图片编号、时间窗和后端约束容易失配。

## Segment Prompt 编译

在 `visual_rag.py` 增加 `compile_segment_input(project, segment, audio_slice)`：

1. 按 Shot 顺序收集参考图并按 asset ID 去重，总数不得超过 9。
2. 建立稳定编号，例如图片1只支持 Shot 1，图片2支持 Shot 2/3。
3. 把全局 Shot 时间转换为 Segment 内局部时间。
4. 拼接全片视觉规范、地点 must_keep、Segment transition_note 和逐 Shot prompt。
5. 附加 `reference_audio`，明确要求根据音频语义和节奏切换画面。

建议编译结果：

```text
生成完整 15 秒写实文旅短片。@音频1 是最终旁白与 BGM 的母带切片，
严格跟随其语义、时间和节奏安排画面，不改写旁白，不生成文字。

图片1：Shot 1 的垂柳与湖岸实景依据。
图片2：Shot 2/3 的湖面与长椅实景依据。

0–5 秒 Shot 1：……
5–10 秒 Shot 2：……
10–15 秒 Shot 3：……

段内保持同一黄昏色调，沿运动方向自然转场，不新增参考图中不存在的地标。
```

## 当前代码的修改点

### `backend/pipeline/pipeline.py`

- `COPYWRITING_PROMPT` 删除固定“250–300 字”，改成与目标时长和已校准语速相关的字数预算。
- 确认文案后先执行 TTS 测时闭环；超时则缩文案并重新合成，不能到视频阶段才把时长钳制。
- `STORYBOARD_PROMPT` 输入真实 `narration_units` 时间，要求 Shot 绑定 `narration_unit_ids`，并提出 `segment_id`。
- 新增 `generate_segments()` / `_run_segment_jobs()`；现有 `_run_video_jobs()` 暂留给旧 `/api/v1/*` 接口，避免一次改坏两套流程。
- 失败重试必须复用同一 audio slice、图片池、prompt hash 和版本快照。

### `backend/pipeline/validate.py`

- 移除“每个 Shot 必须 4–15 秒”和用该范围推导 Shot 数的逻辑。
- 新增 Segment 校验：4–15 秒、Shot 不跨段、段内时间连续、句子不跨段、图片去重后不超过 9、总时间等于母带时长。
- 禁止像当前 `_shot_duration()` 一样在调用前悄悄钳制时长；非法计划必须在生成前报错或重新规划。

### `backend/pipeline/visual_rag.py`

- 保留 `compile_shot_input()` 供旧接口使用。
- 新增 `compile_segment_input()`，处理跨 Shot 图片去重、图片编号、逐 Shot 绑定和 Segment Prompt。
- `MAX_REFERENCES_PER_SHOT=3` 可以继续用于单 Shot 质量控制，再增加 `MAX_REFERENCES_PER_SEGMENT=9`。

### `backend/pipeline/ark_client.py`

- `submit()` 增加 `audio` 和 `generate_audio` 参数，把音频写成 `audio_url/reference_audio` content item。
- 把目前会 `-an` 且覆盖目标文件的 `transcode_web()` 拆成明确函数：
  - `normalize_visual_only(raw, visual_path)`；
  - `mux_preview(visual_path, audio_slice, preview_path)`。
- 原始 Seedance MP4 不再在转码成功后删除。保留 `raw_path` 便于音轨、时长和模型行为审计。

### `backend/pipeline/audio_client.py`（新增）

- 第一版接入 Edge-TTS，固定 voice/rate/volume。
- 按句生成 PCM/WAV 并记录实际时长。
- TTS provider 做接口抽象，后续切换豆包语音时不影响 Storyboard 和 Composer。

### `backend/pipeline/audio_timeline.py`（新增）

- 生成 `narration_units`、`voice_track.wav`、BGM cue 和 `master_audio.wav`。
- 做旁白压低 BGM、淡入淡出、响度和峰值控制。
- 根据最终 Segment 时间切片并记录 SHA-256。

### `backend/pipeline/composer.py`（新增）

合成步骤固定为：

1. 校验每个 Segment 的成功结果与当前 audio/storyboard/reference 版本一致。
2. 读取 `visual_only.mp4`；统一尺寸、fps、SAR、像素格式和编码。
3. 把每段画面精确归一到 Segment 目标时长：小于容差可 trim 或末帧补齐，明显短缺直接失败。
4. 第一版使用自然边界硬切并 concat，避免叠化改变总时长和音画同步。
5. 把完整 `master_audio.wav` 一次性编码为 AAC 并 mux。
6. 可选烧录或挂载由 `narration_units` 生成的字幕。
7. 临时文件成功后原子替换为最终 MP4。

跨 Segment 叠化以后再做；`xfade` 会重叠画面并缩短总时长，必须先有明确的时间轴补偿，不能直接加在 concat 上。

### `backend/projects.py`

不要把新语义硬塞进当前按 Shot 设计的 `VideoTask.shots`。建议新增：

- `AudioTask`：TTS、BGM 和母带生成状态；
- `SegmentTask`：一次或一批 Segment 生成状态；
- `RenderTask`：最终合成状态；
- `Project.audio`、`Project.segment_tasks`、`Project.render_tasks`。

`merge_segment_results()` 按 `segment_id` 取最新终态任务，作用等同现在的 `merge_video_results()`。Segment 结果保存 `raw_path`、`visual_path`、`preview_path`、实测时长、Shot IDs、audio slice hash 和各版本号。

旧项目 JSON 通过 `from_dict()` 默认空字段继续可读；新项目写 `schema_version=2`。

### `backend/v1_router.py` 与 `schemas.py`

- 把 `/audio` 从 reserved 改为真实异步任务。
- `/storyboard` 只允许在 `audio_ready` 后调用。
- `/generate` 请求从 `shots` 改成 `segments`；迁移期可接受旧字段，但必须把整组 Shot 解析成完整 Segment，拒绝只生成 Segment 的一部分。
- 增加 `PUT /segments/{segment_id}` 和 `POST /segments/{segment_id}/regenerate`。
- `PUT /shots/{shot_id}` 保留；成功后只把所属 Segment 标记为 stale。
- `/render` 启动真实 RenderTask，`/render/status` 返回最终文件和错误。

新的主状态机：

```text
planning → waiting_confirm → audio_generating → audio_ready
→ storyboarding → waiting_storyboard_confirm
→ generating → video_ready → composing → completed
```

### 前端

`PlanConfirmView.vue` 确认文案后先显示音频生成/试听状态，再进入 Storyboard。`StoryboardView.vue` 改成 Segment 卡片包 Shot 子卡片：

- Segment 顶部显示 0–15s、音频试听、参考图总数和生成状态；
- Shot 内继续编辑 prompt 和查看绑定图片；
- 修改 Shot 后 Segment 显示“内容已修改，需要重新生成”；
- 生成、预览、失败重试都以 Segment 为单位；
- 全部 Segment ready 后出现“合成最终视频”，并轮询 render 状态。

## 失效规则

| 修改内容 | 必须失效的产物 |
|---|---|
| 旁白文字、音色或语速 | TTS、母带、Storyboard、全部 Segment、最终视频 |
| BGM 曲目、节拍或 cue 时间 | 母带切片、全部 Segment、最终视频 |
| 只调整最终输出音量且不改变时序 | 母带与最终视频；可复用 Segment 画面 |
| Shot prompt 或参考图 | 所属 Segment、最终视频 |
| Shot 时间、顺序或 Segment 分组 | 受影响 Segment；若全局时间后移则后续 Segment 与最终视频 |
| Segment transition_note | 该 Segment、最终视频 |
| 重新生成一个 Segment | 最终视频 |

所有任务记录 `plan_version`、`audio_version`、`storyboard_version`、`reference_version`、`prompt_hash` 和 `audio_slice_sha256`。Composer 不接受版本不一致的“completed”结果。

## 推荐实施顺序

1. **音频闭环**：Edge-TTS adapter、按句测时、母带生成和 `/audio` 状态。
2. **Schema/校验**：Storyboard v2、Segment Planner、真实时间窗和失效规则。
3. **Seedance Seg 调度**：`compile_segment_input`、音频附件、SegmentTask、保留 raw/生成 visual-only。
4. **Composer**：精确时长归一、concat、整条母带 mux、最终文件状态。
5. **前端迁移**：Segment 卡片、Shot 子编辑、音频试听、Segment 重生成和最终成片页。
6. **最后再做增强**：跨 Segment 叠化、关键帧延续、BGM 多 cue 编辑和自动音画 QA。

这个顺序能先打通一条完整但简单的正式链路；视觉增强不会阻塞音频和最终成片闭环。
