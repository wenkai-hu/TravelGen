# Seedance 原生音视频管线

## 目标

正式管线不再预生成 Edge-TTS 旁白，也不再用旁白母带驱动画面。用户先确认一个参考音色；每个 Segment 都使用这条参考音色，由 Seedance 同时生成准确旁白、自然环境声、克制拟音和画面。BGM 始终由系统在最终拼接后单独加入。

## 数据流

```text
创作需求
  → 实景图片检索与 VLM 档案
  → 文案确认
  → Shot 分镜
  → 动态 Segment 分组
  → 用户确认统一参考音色
  → 按场景类型突出曲库；需要时由 KIMI 给出独立选曲方向；用户确认 BGM 或无 BGM
  → 每个 Segment 调用 Seedance（原生画面 + 旁白 + 环境声，禁止 BGM）
  → 拼接 Segment 原生音视频，得到 clean.mp4
  → 可选：完整时间线混入 BGM，得到 with_bgm.mp4
```

## 动态 Segment

- Seedance 单次允许 4–15 秒。
- Segment 只用于高效装入连续 Shot，不承担独立叙事含义。
- Shot 是不可拆分的原子单元；不会为了凑满 15 秒拆 Shot，也不会补空白时间。
- 使用动态规划减少调用次数，并处理末段不足 4 秒的问题。
- 示例：`3 + 4 + 5 + 6` → `12 + 6`，而不是把第四个 Shot 拆出 3 秒填满前段。

## 统一参考音色

两种来源：

1. `assets/media/voices/` 中的 8 条正式预设 WAV。
2. 用户描述希望的声音，Seedance 生成 5 秒试听视频；FFmpeg 抽取 PCM WAV，用户试听确认。

确认后项目保存参考文件、SHA-256 和版本号。每个 Segment 任务都记录同一份音色哈希；更换音色会让已有 Segment 失效，避免新旧音色混用。

## Segment Prompt

固定模板负责不可变规则，项目和 Segment 数据负责动态内容：

- 动态：实际时长、画幅、风格、本段旁白、Shot 局部时间窗、画面 Prompt、参考图映射、转场要求。
- 固定：参考音频只定义说话人身份；旁白不得增删改；只允许旁白、对应环境声和必要拟音；禁止背景音乐、旋律、节奏铺底、鼓点、乐器、吟唱、歌曲、哼唱和音乐化音效；禁止对口型人物、字幕、文字、标志和水印。

所有 Segment 都将同一条参考 WAV 作为 `reference_audio`，并显式请求 `generate_audio=true`。

## BGM

- 正式目录为 `assets/media/bgm/catalog.csv` 及对应 MP3。
- 曲库按项目场景类型突出匹配的歌曲。KIMI 仅在用户主动请求时读取方案、文案和 Shot 信息，提供类型、节奏、音色、情绪及检索词，不参与本地曲库排序。
- 用户可以选择一首，也可以明确选择无 BGM。
- 最终合成保留纯净版、带 BGM 版及对齐的 BGM 声轨。用户可在成片页边听边分别调整视频原声和 BGM（静音到 `0 dB`），确认后调用 `POST /api/projects/{pid}/render/mix` 仅重新混音，不重新生成 Shot 或 Segment。
- 选择 BGM 不影响 Segment 生成；只会使旧的最终 Render 失效。
- 最终混音会循环并裁剪 BGM、做淡入淡出，并将不同来源的音乐统一归一化到背景音乐目标响度后混入。原生音轨同时包含旁白和环境声，不能直接用整轨做侧链 key，否则环境声会持续把 BGM 压到不可闻。

## 输出与 QA

- 每个 Segment 保留原始下载文件、归一化 AV 文件和抽取出的原生 WAV。
- 轻量 QA 检查音轨是否存在、时长是否匹配和尾部活动；不会把能量启发式冒充音乐识别。
- “无 BGM”仍需通过 Prompt 强约束和人工试听确认；接口明确返回 `music_detection: not_available`。
- 最终始终生成纯净版；选择 BGM 时额外生成带 BGM 展示版。

## 失效规则

- 修改 Shot 画面 Prompt、旁白或参考图：所属 Segment 失效。
- 修改 Shot 时长：重新动态规划全部 Segment，全部旧 Segment 失效。
- 修改转场要求：所属 Segment 失效。
- 更换参考音色：全部已有 Segment 失效。
- 更换 BGM 或切换为无 BGM：只使最终 Render 失效，Segment 不重生成。
