# TravelGen 生成管线服务

当前主管线：输入城市/地点/主题 → 实景检索与 VLM → 文案确认 → Shot 分镜 → 动态 Segment → 选择统一参考音色与后期 BGM → Seedance 原生音视频 → 双版本成片。

详细设计：[Seedance 原生音视频管线](../docs/Seedance_Native_Audio_Pipeline.md)

## 启动

```bash
pip install -r backend/requirements.txt
cd backend
python app.py
```

- Swagger：http://127.0.0.1:8000/docs
- 默认开发模式自动 reload。
- `TRAVELGEN_MOCK=1` 可强制使用本地演示模式。

## 主流程接口

1. `POST /api/projects` 创建项目并搜索实景参考图。
2. `POST /api/projects/{id}/references/confirm` 确认参考图，启动 VLM 与文案方案。
3. `PUT /api/projects/{id}/plan` 确认或修改旁白文案。
4. `POST /api/projects/{id}/storyboard` 生成 Shot，并动态组成 Segment。
5. `GET /api/voice-presets` 获取 8 条预设参考音色；或 `POST /api/projects/{id}/voice-candidates` 生成自定义试听音色。
6. `PUT /api/projects/{id}/voice` 确认一个统一参考音色。
7. `GET /api/bgm` 获取按场景类型匹配的曲库；用户需要其他选曲方向时可调用 `POST /api/projects/{id}/bgm/recommendations`，KIMI 基于方案、旁白和分镜给出独立于曲库的类型及节奏建议；`PUT /api/projects/{id}/bgm` 确认 BGM 或明确选择无 BGM。
8. `POST /api/projects/{id}/generate` 按 Segment 调用 Seedance。
9. `GET /api/tasks/{task_id}` 轮询音色、Segment 或渲染任务。
10. `POST /api/projects/{id}/render` 拼接原生音视频并生成最终版本。

旧 `/api/v1/*` 一键接口仅为兼容已有调用方，不参与新的 Project 工作流。

## Segment 规则

- Segment 是 Seedance 最长 15 秒限制下的调用容器，不是新的内容单元。
- 只组合时间线上连续的完整 Shot，绝不为了填满 15 秒拆分 Shot，也不补齐到 15 秒。
- 后端使用全局动态规划，在每段 4–15 秒可行的前提下优先减少调用次数。
- 例如 `3 + 4 + 5 + 6` 秒会组成 `12` 秒和 `6` 秒两个 Segment。
- 修改 Shot 时长后会重新计算全部 Segment；修改画面、旁白或转场要求只使所属 Segment 失效。

## 声音与合成

- 每个 Segment 都注入同一条用户确认的参考音色。参考音频只定义说话人身份，不提供本段正式旁白。
- 本段旁白、Shot 时间窗、环境声要求和固定的“禁止任何 BGM”约束通过动态 Prompt 交给 Seedance。
- Seedance 返回的旁白、自然环境声和真实拟音均被保留；不会剥离原生音轨，也不会再回铺 TTS 母带。
- 最终先拼接所有 Segment 的原生音视频生成 `clean.mp4`，再在完整时间线上循环、裁剪、淡入淡出并归一化所选 BGM，生成独立声轨和 `with_bgm.mp4`。成片后可试听调整视频原声与 BGM 音量，`POST /api/projects/{id}/render/mix` 只重新混音。
- 如果用户明确选择无 BGM，只产出 clean 版本。

## 模式与落盘

| 阶段 | REAL | 无对应模型时 |
|---|---|---|
| 图片搜索与视觉理解 | 百度千帆 + 豆包 VLM | 搜图/VLM 缺失时停止并说明错误 |
| 文案与分镜 | KIMI | 回放内置演示素材并按目标时长调整 |
| 自定义音色 | Seedance 生成视频后 FFmpeg 抽取 WAV | 复制一条真实预设 WAV 作为可试听候选 |
| Segment | Seedance：统一音色参考 + 多 Shot + 原生音轨 | 生成带静音音轨的可合成占位视频 |
| 合成 | FFmpeg 原生音视频拼接与可选 BGM 混音 | 相同 |

- 项目和任务：`experiments/results/05_pipeline/{projects,voice_tasks,segment_tasks,render_tasks}/`
- 预设音色：`assets/media/voices/`
- BGM：`assets/media/bgm/`
- Seedance Segment：`assets/videos/{project_id}/{segment_id}/`
- 最终成片：`assets/renders/{project_id}/v{version}/`

模型 Key 配置：

```bash
cp experiments/config.example.json experiments/config.json
# 编辑 experiments/config.json：kimi / seedance / vlm / qianfan_image_search
```

## 已知边界

- “不得生成 BGM”依靠固定高优先级 Prompt，并保留原生音轨供人工试听；当前没有可靠的自动音乐分类器，`audio_qa.music_detection` 会明确返回 `not_available`。
- 最终拼接使用精确时长硬切，段内自然转场由 Seedance 在一次 Segment 生成中完成。
- 图片来源会保留并标记授权状态，正式发布前仍需人工复核。
