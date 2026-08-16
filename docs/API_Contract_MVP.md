# API 契约 MVP — v0.2（A↔B 联调基线）

**版本**：v0.2｜**日期**：2026-08-15｜**作者**：成员A
**依据**：成员B 输入/输出契约（2026-08-13）+ [TravelGen_v1.md](../TravelGen_v1.md)（v1.0 分阶段接口设计）+ [分镜 Schema v1](Storyboard_Schema_v1.md) + [Phase 4 管线设计](Phase4_Design_AI_Pipeline.md)
**Apifox 导入文件**：[docs/api/openapi.yaml](api/openapi.yaml)（OpenAPI 3.0）

> 两套接口并存：**V1 分阶段（§7，推荐，对应 TravelGen_v1.md 9 接口）**与旧一键直出（§1-§6，保留兜底）。前端按 V1 开发。

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
video_clips: [{ "shot_id": 1, "task_id": "cgt-xxx", "status": "succeeded",
                "prompt": "...", "video_url": "https://...",   // 24h 有效
                "local_path": "assets/videos/t_xxx_1.mp4",     // 本地转存（B 合成直接读）
                "duration_s": 5, "cost_yuan": 1.0 }]
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

## 7. V1 分阶段接口（TravelGen_v1.md，推荐前端使用）

对应 [TravelGen_v1.md](../TravelGen_v1.md) §七~§十八 的 9 接口 + §十五 单 Shot 重生成。用户流程：**创建项目 → 方案确认 → 分镜 → Shot 修改 → 批量生成 → （音频/合成占位）**，两次人工干预点（方案、Shot）。

### 7.1 接口清单

| # | 接口 | 说明 | 状态 |
|---|---|---|---|
| 1 | POST /api/projects | 创建项目 + 异步生成创作方案（planning + copywriting） | ✅ |
| — | GET /api/projects/{id} | **补充端点**：查询项目全量（V1 文档未列但分阶段轮询必需，前端统一轮询它） | ✅ |
| 2 | PUT /api/projects/{id}/plan | 提交用户编辑后的文案 → plan_confirmed + plan_id | ✅ |
| 3 | POST /api/projects/{id}/storyboard | 基于已确认文案生成脚本+分镜（JSON 硬校验） | ✅ |
| 4 | PUT /api/projects/{id}/shots/{shot_id} | 修改单个 Shot（部分字段，枚举自动归一化） | ✅ |
| 5 | POST /api/projects/{id}/generate | 批量生成视频（`shots:[1,2,...]`）→ 返回 vt_ task_id | ✅ |
| 6 | GET /api/tasks/{task_id} | 轮询 per-shot 生成状态（pending/generating/completed/failed） | ✅ |
| — | POST /api/projects/{id}/shots/{shot_id}/regenerate | 单 Shot 重新生成（文档 §十五"必须保留"） | ✅ |
| 7 | POST /api/projects/{id}/audio | 配音+音乐 | ⏸ reserved 占位 |
| 8 | POST /api/projects/{id}/render | 最终合成 | ⏸ reserved 占位 |
| 9 | GET /api/projects/{id}/render/status | 成片状态 | ⏸ reserved 占位 |
| — | GET /api/kb/search | 知识库检索（V1 别名，同 /api/v1/kb/search） | ✅ |

### 7.2 项目状态机

```
created → planning → waiting_confirm → plan_confirmed → storyboarding → waiting_storyboard_confirm
                                                                        │ POST generate（即确认分镜）
                                                                        ▼
                                  generating ⇄（regenerate / 补批）→ completed
                                                                  ↘ failed（任意阶段，终态）
```

**关键语义**：
1. **POST generate 即视为"确认分镜"**（V1 文档无独立确认端点，前端"确认分镜"按钮直接调 generate）
2. **轮询用 GET /api/projects/{id}**（V1 文档未列此端点，本服务补充——方案/分镜异步生成期间轮询它，waiting_confirm / waiting_storyboard_confirm 即对应两次人工确认点）
3. 允许增量补批：generate 前置只要分镜已生成（waiting_storyboard_confirm/generating/completed/failed 均可）
4. failed 为终态：文本阶段失败需重建项目；视频阶段失败可 regenerate 单 Shot

### 7.3 字段约定（与 B 文档的差异处理）

| 项 | 约定 |
|---|---|
| copywriting 双形态 | 接口 1/2 输入输出按 B 文档**字符串**（`【0-15s】…`）；GET project 同时给结构化 `copywriting` 与拼接 `copywriting_text`（展示用）。PUT plan 提交的字符串丢失时间戳标记时，后端兜底整段为一个段落（不拒绝） |
| shot_id | 统一 **int**（文档示例 "shot_01" 是前端展示标签，即补零） |
| generate_image | 接受参数但本版 **video-only**（无图像生成 API），`image_url` 恒 null |
| video 产物 | 真实模式 `video_url` 为本地转存路径（assets/videos/，24h URL 已转存）；demo 模式恒 null |
| scene_type | 支持中文枚举或英文别名（scenic→景区推荐 等），落库统一中文 |

### 7.4 视频任务（VideoTask，GET /api/tasks/{id} 返回）

```jsonc
{ "task_id": "vt_xxx", "project_id": "p_xxx", "kind": "batch|single",
  "status": "generating|completed|failed", "progress": 65,
  "message": "视频生成中 3/5 完成",
  "shots": [ { "shot_id": 1, "status": "completed", "image_url": null,
               "video_url": "D:\\...\\vt_xxx_1.mp4", "local_path": "...", "error": null },
             { "shot_id": 2, "status": "generating", ... },
             { "shot_id": 3, "status": "pending", ... } ] }
```

### 7.5 错误码（V1 新增）

| HTTP | code | 场景 |
|---|---|---|
| 409 | invalid_state | 状态机前置不满足（分镜未生成就 generate、非 waiting_confirm 就确认方案、plan_id 不匹配） |
| 404 | project_not_found / shot_not_found | 项目 / 镜头不存在 |
| 400 | invalid_param | shots 含不存在的镜头、generate_video=false、PUT plan 文案为空等 |

### 7.6 持久化与 demo 模式

- 项目与视频任务自动落盘 `experiments/results/05_pipeline/{projects,video_tasks}/`，服务重启后 GET 懒加载恢复
- demo 模式（无 key / TRAVELGEN_MOCK=1）：各阶段回放 Phase 3 真实成果（西湖样例），视频为模拟成功——B 克隆仓库后无需任何 key 即可全流程联调

## 8. Apifox 协作流程

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

## 9. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-08-13 | 基线（对齐 B 契约 2026-08-13） |
| v0.2 | 2026-08-15 | 新增 V1 分阶段接口（TravelGen_v1.md 9 接口 + Shot 重生成 + 项目查询补充端点）；接口 7/8/9 占位 reserved；新旧接口共存 |
