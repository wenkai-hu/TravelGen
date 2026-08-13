# API 契约 MVP — v0.1（A↔B 联调基线）

**版本**：v0.1｜**日期**：2026-08-13｜**作者**：成员A
**依据**：成员B 输入/输出契约（2026-08-13）+ [分镜 Schema v1](Storyboard_Schema_v1.md) + [Phase 4 管线设计](Phase4_Design_AI_Pipeline.md)
**Apifox 导入文件**：[docs/api/openapi.yaml](api/openapi.yaml)（OpenAPI 3.0）

---

## 1. 总体流程（异步任务）

```
POST /api/v1/generate            → 202 {task_id, status:"planning"}
GET  /api/v1/tasks/{task_id}     → 轮询（前端建议 2s 间隔），status 推进
```

状态机（与 B 契约一致）：`planning → copywriting → storyboard → generating → audio* → composing → done`，任意阶段失败 → `failed`（`message` 附失败阶段与原因）。

- `audio` 为预留阶段：配音接入后启用，MVP 跳过
- `progress` 权重：planning 10 → copywriting 20 → storyboard 20 → generating 40 → composing 10（done=100）

## 2. 输入 GenerateRequest

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| city | string | ✅ | — | 传播城市（杭州） |
| location | string | ✅ | — | 具体地点（西湖） |
| scene_type | enum | ✅ | — | 城市形象宣传 / 景区推荐 / 节庆活动推广 / 非遗文化传播 / 打卡视频 / 其他 |
| theme | string | ✅ | — | 传播主题（春日西湖旅游宣传） |
| audience | string | ❌ | 18-35岁年轻游客 | 目标人群 |
| style | string | ❌ | 大气唯美 | 视频风格 |
| duration_s | int | ❌ | 60 | 15–120s |
| aspect_ratio | enum | ❌ | 9:16 | 9:16 / 16:9 / 1:1 |
| resolution | enum | ❌ | 1080p | 720p / 1080p |
| video_model | enum | ❌ | seedance-2.0-pro | seedance-2.0 / seedance-2.0-pro（A 新增，见 §6） |
| description | string | ❌ | — | 补充要求说明 |
| assets | Asset[] | ❌ | [] | 参考素材（MVP 仅 image，见 §6） |

**A 侧决策**：temperature 不进输入 —— 后端固定 kimi-k2.6 temp=1（推理模型硬约束，Phase 3 实测），与 B 意见一致。

## 3. 输出 GenerateTask

阶段字段**始终存在**（未产生时为空对象/空数组），B 前端无需判空处理：

| 字段 | 说明 | MVP 内容 |
|---|---|---|
| task_id / status / progress | 见 §1 | ✅ |
| planning | 内容策划大纲（3-5 段：引入/展开/高潮/收尾） | 非空 |
| copywriting | 宣传文案：2 标题 + 4 段（含秒数）+ 3 标签 | 非空 |
| script | 配音稿/字幕稿（逐行 + 起止秒） | 非空（可作字幕） |
| storyboard | 分镜 JSON（**严格 Schema v1**：7 场景/8 镜头/≈60s） | 非空 |
| visual_assets | 视觉素材：知识库锚点图 + 用户参考图 | 非空 |
| voice | 配音结果 | 占位 `{enabled:false}` |
| music | BGM 建议 | 占位 `{status:"reserved"}` |
| video_clips | 逐镜头视频片段（8 条） | 非空 |
| safety | 内容安全/版权合规检查 | 非空 |
| final_video | 成片（B 合成后回填） | 空 → B 回填 |

各阶段完整字段结构见 [openapi.yaml](api/openapi.yaml) `components/schemas`（与前端类型定义同源，导入 Apifox 后自动生成 TS 类型可参考）。

### 关键嵌套结构（摘要）

```jsonc
copywriting: { "titles": ["...", "..."],
  "paragraphs": [{ "idx": 1, "text": "...", "duration_s": 15 }],   // 4 段
  "hashtags": ["#...", "#...", "#..."] }
script:      { "lines": [{ "line_id": 1, "text": "...", "start_s": 0, "end_s": 12 }] }
storyboard:  /* 分镜 Schema v1：theme + scenes[].shot_list[]（6-8 镜头）*/
video_clips: [{ "shot_id": 1, "task_id": "cpt-xxx", "status": "succeeded",
                "prompt": "...", "video_url": "https://...", "duration_s": 8, "cost_yuan": 1.0 }]
final_video: { "status": "ready", "url": "...", "preview_url": "...",
               "duration_s": 60, "resolution": "1080p", "aspect_ratio": "9:16" }
```

## 4. 错误规范

| HTTP | code | 场景 |
|---|---|---|
| 400 | invalid_param | 参数缺失 / 枚举越界 / 时长超界 |
| 404 | task_not_found | task_id 不存在 |
| 429 | rate_limited | 模型额度 / 限速 |
| 500 | internal | 管线内部异常 |

统一 body：`{"code": "...", "message": "...", "detail": "..."}`

## 5. 样例（完整流程）

```jsonc
POST /api/v1/generate
{ "city": "杭州", "location": "西湖", "scene_type": "景区推荐",
  "theme": "春日西湖旅游宣传", "audience": "18-35岁年轻游客",
  "style": "大气唯美", "duration_s": 60, "aspect_ratio": "9:16",
  "resolution": "1080p", "description": "突出春日西湖风景、年轻人打卡体验",
  "assets": [] }
→ 202 { "task_id": "t_20260813_a1b2c3", "status": "planning" }

GET /api/v1/tasks/t_20260813_a1b2c3        // 轮询① ~2s
→ 200 { "task_id": "...", "status": "copywriting", "progress": 20,
        "planning": { "outline": [...] }, "copywriting": {}, ... }

GET /api/v1/tasks/t_20260813_a1b2c3        // 轮询② ~20s
→ 200 { "task_id": "...", "status": "generating", "progress": 70,
        "planning": {...}, "copywriting": {...}, "script": {...},
        "storyboard": { "theme": "...", "scenes": [...] },   // 8 镜头
        "video_clips": [ { "shot_id": 1, "status": "succeeded", ... }, ... ], ... }

GET /api/v1/tasks/t_20260813_a1b2c3        // 轮询③ 最终
→ 200 { "task_id": "...", "status": "done", "progress": 100,
        "video_clips": [ /* 8 条 succeeded */ ],
        "safety": { "passed": true, "checks": [...] },
        "final_video": { "status": "ready", "url": "https://..." }, ... }
```

## 6. 对 B 契约的评审结论（A 的 4 个决定）

1. **status 枚举 / 异步模型：一致**，直接采用。`audio` 阶段保留但 MVP 跳过；`failed` 附 `message`（失败阶段 + 原因）
2. **新增可选字段 `video_model`**（默认 `seedance-2.0-pro`）：2.0 与 2.0 Pro 质量、单价不同（Pro ≈1 元/条 5s），字段预留便于 A/B 对比与答辩演示；前端不做下拉也可，后端固定默认值，字段无副作用。模型 ID（如 `doubao-seedance-2-0-260128`）映射在服务端配置，契约只暴露抽象名
3. **`script` 与 `storyboard` 分工**：B 契约里两者并存易歧义。定义：`script` = 配音稿/字幕稿（文案→逐行文本+起止秒），`storyboard` = 分镜 JSON（Schema v1）。两者均由 A 产出，B 无需猜
4. **`voice` / `music` / `assets[type=video|audio]`：MVP 预留**。字段始终存在但为空占位（避免前端 undefined）；参考音频/视频（即梦模式）成本与难度大，同意 B 的判断，Phase 5 再议

## 7. Apifox 协作流程

**准备（约 10 分钟，建议 B 操作）**：
1. apifox.com 建团队项目 **TravelGen**，邀请对方进团队（免费版即可）
2. 导入 `docs/api/openapi.yaml`（Apifox：项目 → 导入数据 → OpenAPI/Swagger）→ 自动生成接口文档、参数校验、Mock
3. 管理环境：`本地开发`（http://127.0.0.1:8000，A 用）与 `Apifox Mock`（B 前端先行用）

**开发期（并行）**：
- **B**：前端按接口文档开发，请求指向 Mock 环境 → 不依赖 A 的后端进度
- **A**：实现管线服务（FastAPI），在 Apifox「运行」里填参调试真实接口（example 已预填）
- 约定：接口变更改 openapi.yaml 重新导入（Apifox 增量更新）并口头知会；大改动升版本号 v0.1→v0.2

**运行方式**：仓库推送到 GitHub 后，B 克隆到本地直接跑服务（`pip install -r backend/requirements.txt && python backend/app.py`）——无需访问 A 的机器；无 API key 时自动 demo 模式，有 key 时（`experiments/config.json`）走真实生成，详见 [backend/README.md](../backend/README.md)。

**收尾**：Apifox 调试记录/用例可导出，答辩可截图「接口文档 + Mock + 联调」作为工程协作证据。

## 8. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-08-13 | 基线（对齐 B 契约 2026-08-13） |
