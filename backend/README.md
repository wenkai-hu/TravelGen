# TravelGen 生成管线服务（MVP，成员A）

AI 生成管线原型：输入城市/地点/主题 → 知识检索 → 文案 → 分镜 → 视频任务 → 任务状态轮询。
API 契约：[docs/API_Contract_MVP.md](../docs/API_Contract_MVP.md) ｜ OpenAPI：[docs/api/openapi.yaml](../docs/api/openapi.yaml)（Apifox 导入）

## 启动（B 侧：克隆仓库后）

```bash
pip install -r backend/requirements.txt
cd backend
python app.py
```

> 默认 `reload=True`：改后端任意 `.py` 即自动重启，无需手动重启服务（依赖 watchfiles）。

- 交互文档：http://127.0.0.1:8000/docs（Swagger UI，可直接调试/导出）
- 接口清单（两套并存）：
  - **V1 分阶段（/api/*，推荐，对应 TravelGen_v1.md）**：
    `POST /api/projects` 创建并搜索图片 → `GET /api/projects/{id}/references` 查询候选 →
    `POST /api/projects/{id}/references/confirm` 确认实景图并启动 VLM/Plan → `PUT /api/projects/{id}/plan` 确认方案 →
    `POST /api/projects/{id}/storyboard` 生成分镜 → `PUT /api/projects/{id}/shots/{shot_id}` 修改 Shot →
    `POST /api/projects/{id}/generate` 批量生成视频 → `GET /api/tasks/{task_id}` 轮询 per-shot 状态 →
    `POST /api/projects/{id}/shots/{shot_id}/regenerate` 单 Shot 重生成
  - 旧契约（/api/v1/*，保留兜底）：`POST /api/v1/generate` + `GET /api/v1/tasks/{task_id}`（一键直出）
  - `GET /api/kb/search`（及 `/api/v1/kb/search`）知识库检索

## 两种模式（阶段独立降级）

| 阶段 | REAL（有对应 key） | 降级（无 key） |
|---|---|---|
| 图片搜索 | 百度千帆搜索返回候选，用户确认后才进入管线 | 无候选时停止并返回明确错误 |
| 视觉 RAG | 豆包视觉模型逐图分析，形成 PlaceVisualProfile | VLM 不可用时停止在选图阶段 |
| 文案/分镜 | kimi-k2.6 + 用户确认的视觉档案 | 回放 Phase 3 真实成果（kimi 最优西湖文案/分镜） |
| 视频 | Seedance 2.0 Pro 真实生成（火山方舟异步任务） | 模拟推进（clips 标记 `note: simulated`） |

`TRAVELGEN_MOCK=1` 强制全 demo。例如：只有 kimi key → 文案真实 + 视频模拟；都有 → 全真实。

key 配置（把模板复制为真配置再填 key，**config.json 已被 gitignore，不会误提交**）：

```bash
cp experiments/config.example.json experiments/config.json
# 编辑 experiments/config.json，配置 kimi/seedance/vlm/qianfan_image_search
```

## 视频生成（Seedance 2.0 Pro，已实测 ✅）

- 提交：`POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`，Bearer 鉴权
- 模型：`doubao-seedance-2-0-260128`，`duration=5`，`resolution=1080p`
- 流程：并发提交全部镜头 → 5s 间隔轮询（状态机 queued→running→succeeded）→ **失败自动重试 1 次** → 成功即下载转存
- ⚠️ `video_url` 仅 24h 有效，已转存到 `assets/videos/{task_id}_{shot_id}.mp4`（gitignore，不入库）
- 成本：≈1 元/条 5s 视频；单条生成 ≈3-4 分钟，8 镜头并发总耗时 ≈4-5 分钟
- `video_clips[]` 附带 `local_path`（本地转存路径），B 合成时直接读取

## V1 分阶段流程（关键语义）

```
POST /api/projects ──► searching_references ──► waiting_reference_confirm
POST /references/confirm ──► analyzing_references ──► planning ──► waiting_confirm
PUT /plan（可编辑文案）──► plan_confirmed
POST /storyboard ──► waiting_storyboard_confirm
PUT /shots/{id}（可修改任一 Shot）→ POST /generate（即确认分镜）──► generating
GET /api/tasks/{task_id}（per-shot 进度）→ completed
POST /shots/{id}/regenerate（单 Shot 局部重生成，系统必须保留功能）
```

- 项目与视频任务自动落盘 `experiments/results/05_pipeline/{projects,video_tasks}/`，**服务重启不丢**（GET 懒加载恢复）
- 选中图片缓存到 `assets/references/{project_id}/`；每个 Shot 保存 `reference_asset_ids`，生成和重试都发送同一组原图
- `vlm` provider 通过 `credential_provider=seedance` 复用方舟 Key；百度 Key 优先读取 `QIANFAN_API_KEY`
- 接口 7/8/9（audio/render/成片查询）返回 `reserved` 占位，本版未实现
- 补充端点 `GET /api/projects/{id}` 是分阶段轮询入口（TravelGen_v1.md 未列但流程必需）

## 当前边界（Phase 5 待办）

- **分镜图生成**：`generate_image` 参数接受但 video-only（无图像生成 API，`image_url` 恒 null）
- **成片合成**：`final_video` 由 B 的 Composer 合成后回填（本服务只产出合成所需元数据）
- **配音/BGM**：`voice`/`music` 为占位字段（V1 接口 7 返回 reserved）
- **任务存储**：文件落盘实现（轻量），大流量上线换 Redis/DB
- **文字知识检索**：仍是关键词子串评分；本次新增的是独立视觉 RAG，图片不能替代历史事实来源
- **图片版权**：搜索结果只保留来源并标记 `rights_status=unknown`，正式发布前仍需人工确认授权

