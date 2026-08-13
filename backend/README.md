# TravelGen 生成管线服务（MVP，成员A）

AI 生成管线原型：输入城市/地点/主题 → 知识检索 → 文案 → 分镜 → 视频任务 → 任务状态轮询。
API 契约：[docs/API_Contract_MVP.md](../docs/API_Contract_MVP.md) ｜ OpenAPI：[docs/api/openapi.yaml](../docs/api/openapi.yaml)

## 启动（B 侧：克隆仓库后）

```bash
pip install -r backend/requirements.txt
cd backend
python app.py
```

- 交互文档：http://127.0.0.1:8000/docs（Swagger UI，可直接调试/导出）
- 接口清单：
  - `POST /api/v1/generate` 提交生成任务（输入契约 §2）
  - `GET  /api/v1/tasks/{task_id}` 轮询状态与阶段输出（2s 间隔）
  - `GET  /api/v1/kb/search?q=西湖` 知识库检索

## 两种模式（阶段独立降级）

| 阶段 | REAL（有对应 key） | 降级（无 key） |
|---|---|---|
| 文案/分镜 | kimi-k2.6 真实生成（温度固定 1） | 回放 Phase 3 真实成果（kimi 最优西湖文案/分镜） |
| 视频 | Seedance 2.0 Pro 真实生成（火山方舟异步任务） | 模拟推进（clips 标记 `note: simulated`） |

`TRAVELGEN_MOCK=1` 强制全 demo。例如：只有 kimi key → 文案真实 + 视频模拟；都有 → 全真实。

key 配置（把模板复制为真配置再填 key，**config.json 已被 gitignore，不会误提交**）：

```bash
cp experiments/config.example.json experiments/config.json
# 编辑 experiments/config.json，填入 kimi/seedance 的 api_key
```

## 视频生成（Seedance 2.0 Pro，已实测 ✅）

- 提交：`POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`，Bearer 鉴权
- 模型：`doubao-seedance-2-0-260128`，`duration=5`，`resolution=1080p`
- 流程：并发提交全部镜头 → 5s 间隔轮询（状态机 queued→running→succeeded）→ **失败自动重试 1 次** → 成功即下载转存
- ⚠️ `video_url` 仅 24h 有效，已转存到 `assets/videos/{task_id}_{shot_id}.mp4`（gitignore，不入库）
- 成本：≈1 元/条 5s 视频；单条生成 ≈3-4 分钟，8 镜头并发总耗时 ≈4-5 分钟
- `video_clips[]` 附带 `local_path`（本地转存路径），B 合成时直接读取

## 当前边界（Phase 5 待办）

- **成片合成**：`final_video` 由 B 的 Composer 合成后回填（本服务只产出合成所需元数据）
- **配音/BGM**：`voice`/`music` 为占位字段（Phase 5 接入）
- **任务存储**：内存实现，服务重启任务丢失（上线换 Redis/DB）
- **知识检索**：关键词子串评分（Phase 5 换向量检索）
