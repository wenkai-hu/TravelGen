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

## 两种模式

| 模式 | 触发条件 | 行为 |
|---|---|---|
| **REAL** | 存在 `experiments/config.json`（含 kimi key） | 文案/分镜走 kimi-k2.6 真实生成（温度固定 1） |
| **DEMO** | 无 config.json，或 `TRAVELGEN_MOCK=1` | 回放 Phase 3 真实成果（kimi 最优西湖文案/分镜），无需 key，全流程可演示 |

有 key 时配置（把模板复制为真配置再填 key，**config.json 已被 gitignore，不会误提交**）：

```bash
cp experiments/config.example.json experiments/config.json
# 编辑 experiments/config.json，填入 api_key
```

## 当前边界（Phase 5 待办）

- **视频生成**：`video_clips` 为模拟推进（Seedance 2.0 Pro 火山方舟异步任务接入 Phase 5）
- **成片合成**：`final_video` 由 B 的 Composer 合成后回填（本服务只产出合成所需元数据）
- **配音/BGM**：`voice`/`music` 为占位字段（Phase 5 接入）
- **任务存储**：内存实现，服务重启任务丢失（上线换 Redis/DB）
- **知识检索**：关键词子串评分（Phase 5 换向量检索）
