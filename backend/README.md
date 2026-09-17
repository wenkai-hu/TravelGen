# TravelGen 生成管线服务（MVP，成员A）

AI 生成管线：输入城市/地点/主题 → 知识检索 → 文案 → Master Audio → Segment 视频 → 母带回铺成片。
实现说明：[Master Audio + Segment Pipeline](../docs/Master_Audio_Segment_Pipeline_Implementation.md) ｜ 运行时 OpenAPI：http://127.0.0.1:8000/openapi.json

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
    `POST /api/projects/{id}/audio` 生成完整旁白/BGM → `POST /api/projects/{id}/storyboard` 按音频时间轴生成分镜 →
    `PUT /api/projects/{id}/shots/{shot_id}` 修改 Shot → `POST /api/projects/{id}/generate` 批量生成 Segment →
    `GET /api/tasks/{task_id}` 轮询 → `POST /api/projects/{id}/render` 拼接静音画面并回铺 Master Audio
  - 旧契约（/api/v1/*，保留兜底）：`POST /api/v1/generate` + `GET /api/v1/tasks/{task_id}`（一键直出）
  - `GET /api/kb/search`（及 `/api/v1/kb/search`）知识库检索

## 两种模式（阶段独立降级）

| 阶段 | REAL（有对应 key） | 降级（无 key） |
|---|---|---|
| 图片搜索 | 百度千帆搜索返回候选，用户确认后才进入管线 | 无候选时停止并返回明确错误 |
| 视觉 RAG | 豆包视觉模型逐图分析，形成 PlaceVisualProfile | VLM 不可用时停止在选图阶段 |
| 文案/分镜 | kimi-k2.6 + 用户确认的视觉档案 | 回放 Phase 3 真实成果（kimi 最优西湖文案/分镜） |
| 音频 | Edge-TTS 固定音色 + 连续环境 BGM | 离线提示音 + 同一 BGM，仍生成真实 WAV |
| 视频 | Seedance 2.0 Pro：音频切片 + 多 Shot prompt + 最多 9 张参考图 | 生成可合成的真实占位 MP4 |
| 合成 | FFmpeg 静音画面归一化、拼接、一次性回铺母带 | 与 REAL 相同 |

`TRAVELGEN_MOCK=1` 强制全 demo。例如：只有 kimi key → 文案真实 + 视频模拟；都有 → 全真实。

key 配置（把模板复制为真配置再填 key，**config.json 已被 gitignore，不会误提交**）：

```bash
cp experiments/config.example.json experiments/config.json
# 编辑 experiments/config.json，配置 kimi/seedance/vlm/qianfan_image_search
```

## 视频生成（Seedance 2.0 Pro，已实测 ✅）

- 提交：`POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`，Bearer 鉴权
- 模型：`doubao-seedance-2-0-260128`，每个 Segment `duration=4..15`，显式传项目画幅
- 流程：按完整旁白的自然句尾规划最少数量的 Segment；一个请求携带该段所有 Shot 指令、图片映射和母带切片
- Seedance 原始音视频保留为审计产物；另存无声音轨和回铺母带切片的预览版
- ⚠️ 远程 `video_url` 仅 24h 有效，成功后立即转存到 `assets/videos/{project_id}/{segment_id}/`
- 失败自动重试 1 次；Shot 编辑只让所属 Segment 失效，重新生成单位仍是完整 Segment

## V1 分阶段流程（关键语义）

```
POST /api/projects ──► searching_references ──► waiting_reference_confirm
POST /references/confirm ──► analyzing_references ──► planning ──► waiting_confirm
PUT /plan（可编辑文案）──► plan_confirmed
POST /audio ──► audio_generating ──► audio_ready
POST /storyboard ──► waiting_storyboard_confirm（生成 Segment + 嵌套 Shot）
PUT /shots/{id}（修改画面指令，所属 Segment 变 stale）
POST /generate（segments:[...]）──► generating ──► video_ready
POST /segments/{id}/regenerate（整段重生成）
POST /render ──► composing ──► completed
```

- 项目与任务自动落盘 `experiments/results/05_pipeline/{projects,audio_tasks,segment_tasks,render_tasks}/`，**服务重启不丢**（GET 懒加载恢复）
- 选中图片缓存到 `assets/references/{project_id}/`；每个 Shot 保存 `reference_asset_ids`，生成和重试都发送同一组原图
- `vlm` provider 通过 `credential_provider=seedance` 复用方舟 Key；百度 Key 优先读取 `QIANFAN_API_KEY`
- `GET /api/projects/{id}` 返回 `audio`、`storyboard.segments`、`segment_results`、`final_video`
- 补充端点 `GET /api/projects/{id}` 是分阶段轮询入口（TravelGen_v1.md 未列但流程必需）

## 当前边界（Phase 5 待办）

- **分镜图生成**：`generate_image` 参数接受但 video-only（无图像生成 API，`image_url` 恒 null）
- **转场策略**：当前最终拼接使用精确时长硬切，避免交叉淡化改变总时长；段内转场交给 Seedance 一次生成
- **BGM 来源**：当前内置连续环境音乐床，接口已保留 music preset；后续可换成版权明确的音乐服务
- **任务存储**：文件落盘实现（轻量），大流量上线换 Redis/DB
- **文字知识检索**：仍是关键词子串评分；本次新增的是独立视觉 RAG，图片不能替代历史事实来源
- **图片版权**：搜索结果只保留来源并标记 `rights_status=unknown`，正式发布前仍需人工确认授权

