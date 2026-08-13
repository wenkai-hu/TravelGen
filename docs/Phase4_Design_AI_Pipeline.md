# Phase 4 设计（A侧）—— 智能体编排工作流与模型接入

**项目**：TravelGen｜**编写**：成员A｜**日期**：2026-08-07｜**版本**：v0.1（评审稿，契约对齐会后定稿）
**依据**：Phase 1 调研（编排 LangGraph / 知识库 LightRAG）+ Phase 3 Benchmark 选型结论

---

## 1. 端到端生成管线（总览）

```
用户输入 ──► [Input Normalizer] ──► [Planner] ──► [Script Agent] ──► [Storyboard Agent] ──► [T2V Dispatcher] ──► [Composer Hook]
(城市/主题/          规范化参数        生成内容大纲     宣传文案(4段+标题+标签)  分镜JSON(Schema v1)    逐镜头提交视频任务      拼接成片(留给B)
 人群/风格/时长)            │                 │                  │                    │                    │
                          ▼                 ▼                  ▼                    ▼                    ▼
                     任务上下文        RAG知识检索 ─────► 注入{KNOWLEDGE}         JSON硬校验              结果收集/下载
```

**分工边界**：本管线覆盖 文案→分镜→视频任务下发；前端交互、任务队列、异步回调、文件存储、视频合成（MoviePy/FFmpeg）属 B 侧，管线与其通过"任务契约"对接（见 §5）。

## 2. 智能体编排设计（LangGraph）

| 节点 | 输入 | 输出 | 模型 | 温度 | 说明 |
|---|---|---|---|---|---|
| Input Normalizer | 用户自由输入 | 结构化参数 `{city, theme, audience, style, duration_s, extra}` | 规则+LLM | 0 | 兜底默认：杭州西湖/文旅宣传/18-35/大气唯美/60s |
| Planner | 结构化参数 | 内容大纲（3-5 段：引入/展开/高潮/收尾） | kimi-k2.6 | 1 | 输出大纲文本，供 Script 参考与用户预览 |
| Script Agent | 大纲 + RAG 知识 | 文案（4 段含秒数 + 2 标题 + 3 标签） | kimi-k2.6 | 1 | 复用 `prompts/copywriting.txt`（v1），`{KNOWLEDGE}` 注入 RAG 检索结果 |
| Storyboard Agent | 文案 | 分镜 JSON（Schema v1） | kimi-k2.6 | 1 | 复用 `prompts/storyboard.txt`（v1）；**必须通过 JSON 硬校验**（复用 `run_llm_benchmark.validate_storyboard_json`），失败自动重试 1 次后仍失败则回退 deepseek-v4-flash |
| T2V Dispatcher | 分镜 JSON | 每镜头一个视频任务（异步） | —（纯逻辑） | — | 按 Schema 拆解 shot_list，逐镜头拼接 `video_suffix.txt`（v1）生成完整 prompt，提交 Seedance 2.0 Pro，轮询收集结果 |
| Composer Hook | 镜头视频 + 时长表 | 合成任务元数据 | — | — | 按 `duration_s` 顺序拼接 + 文案旁白（配音待 Phase 5 接入），交给 B 的 Video Composer |

**状态机（每节点）**：`queued → running → succeeded | failed | retrying`；失败重试策略：LLM 节点重试 1 次（换温度无效则换备选模型）；T2V 任务失败重试 1 次后跳过该镜头并在结果中标记。

**关键设计决策（来自 Phase 3 实测）**：
1. kimi-k2.6 为推理模型，**temperature 只能取 1**（Phase 3 实验1/2 均以此配置跑通）——文案质量稳定，但代价是输出偏"探索性"，重试兜底必要
2. 分镜 JSON 校验是硬门槛：Phase 3 实测部分模型会夹带文字/结构错，**校验失败直接不进 T2V 阶段**，防止脏数据污染视频任务
3. 知识注入点只在 Script 节点（`{KNOWLEDGE}` 占位）——信息真实性是赛事评分项（编造史实判 1 分），RAG 检索结果作为唯一事实来源

## 3. 模型接入清单（实测参数，Phase 3 验证）

| 环节 | 首选 | 备选 | 接入要点 |
|---|---|---|---|
| 文案/分镜 | **kimi-k2.6** | deepseek-v4-flash | base_url `https://api.moonshot.cn/v1`；OpenAI 兼容；**temperature=1**；免费额度 15 元（够 MVP） |
| 视频 | **Seedance 2.0 Pro**（火山方舟） | Wan2.2-TI2V-5B 本地 | 见下方 Seedance 调用规范；本地兜底需 GPU ≥24G |
| 配音 | 预留接口（暂不选型） | — | Phase 5 候选：CosyVoice2（本地）/ EdgeTTS（免费） |

**Seedance 2.0 Pro 调用规范（来自 `experiments/results/03_video/03_video/README.md`，B 已跑通样片）**：
- 提交：`POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`，Bearer 鉴权，`model=doubao-seedance-2-0-260128`，`content=[{"type":"text","text":"<镜头prompt>"}]`，`duration=5`，`resolution="1080p"`
- 轮询：5-15s 间隔 + 指数退避，状态机 `queued→running→succeeded/failed/expired`，最多 60 次
- ⚠️ `video_url` 仅 24h 有效，成功即下载，存 `assets/videos/`（不入库，网盘备份）
- 成本：约 1 元/条（5s 1080p），每片 8 镜头 ≈ 8 元

## 4. RAG 知识库设计（LightRAG，Phase 1 选型）

- **数据**：浙江城市/景区条目（西湖十景、地标典故、节庆非遗），每条含 `名称/类别/真实信息/来源`，初始 50-100 条人工整理（实验1 的 KNOWLEDGE 字符串就是雏形）
- **注入点**：仅 Script Agent（`{KNOWLEDGE}`），按主题检索 top-5
- **校验**：文案生成后抽检"地名/年份/典故"是否在知识库内（防编造，对应赛事真实性要求）——Phase 5 实现为独立校验节点

## 5. 对 B 的接口需求（契约对齐会主题）

| 接口 | 方向 | 内容 | 状态 |
|---|---|---|---|
| 输入/输出全契约 | A↔B | `docs/API_Contract_MVP.md` + `docs/api/openapi.yaml`（Apifox 导入文件） | ✅ 2026-08-13 对齐 |
| 分镜 JSON Schema | A→B | `docs/Storyboard_Schema_v1.md`（字段/枚举/约束） | ✅ 已定稿 |
| 镜头 prompt 格式 | A→B | shot 级 prompt = `prompt字段 + video_suffix`，示例见 `results/03_video/shot_prompts.txt` | ✅ 已产出 |
| 视频任务提交契约 | B→A | 已并入 API 契约：`POST /api/v1/generate` + `GET /api/v1/tasks/{id}`（B 前端轮询） | ✅ 2026-08-13 对齐 |
| 成片合成元数据 | A→B | `final_video` / `video_clips` 字段：镜头顺序 + duration_s + 旁白文本（配音接口预留） | ✅ 2026-08-13 对齐 |

**建议契约对齐会**：A 用 15 分钟讲 Schema v1 字段与硬约束，B 确认 Video Composer 能按 shot_list 拆解成 8 个视频任务并回拼，当场敲定第 3/4 行接口签名。

## 6. 待定项 / 风险

1. **Seedance 2.0 Pro 模型 ID 与样片核对**：README 中为 `doubao-seedance-2-0-260128`，B 样片已出（hy-video-1.5/minimax），需确认 Seedance 官方模型名后锁定
2. **多镜头一致性**：T2V 逐镜头独立生成，跨镜头地标一致性依赖 prompt 约束（Schema 已要求地标描述一致），成片拼接后可能需要 1-2 个过渡镜头兜底
3. **成本**：单条视频 ≈1 元，MVP 演示按 3 城市 × 8 镜头估算 ≈ 24 元 + 重试余量，建议 B 侧设预算上限
4. **kimi 免费额度**：15 元赠送仅够 MVP 开发期，上线前需评估 kimi 官方充值或换 deepseek-v4-flash（¥1/百万输入）

## 7. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-08-07 | 评审稿（契约对齐会前） |
| v0.2 | 2026-08-13 | 对齐 B 输入/输出契约，新增 API_Contract_MVP.md + openapi.yaml（Apifox） |
