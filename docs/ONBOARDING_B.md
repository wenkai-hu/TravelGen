# 成员B 交接手册（克隆 → 启动 → 联调全流程）

**日期**：2026-08-15｜**写给**：成员B｜**依据**：backend/README.md + docs/API_Contract_MVP.md v0.2

> 本手册按「从零到跑通」顺序编写。克隆仓库后照着做即可，全流程约 30 分钟（demo 模式）。

---

## 0. 本机需要装什么

| 工具 | 说明 |
|---|---|
| Git | Windows 官网 git-scm.com 安装，装完 `git --version` 验证 |
| Python 3.10+ | `python --version` 验证（项目只用标准库 + fastapi/uvicorn 等纯 Python 依赖） |
| Apifox（可选） | 导入 `docs/api/openapi.yaml` 自动生成全部接口文档 + Mock，前端开发期可先用 |

## 1. 克隆仓库

```bash
git clone https://github.com/Ryan-812/TravelGen.git
cd TravelGen
```

## 2. 安装依赖并启动

```bash
pip install -r backend/requirements.txt
cd backend
python app.py
```

启动日志会打印当前模式：

```
TravelGen 管线服务 | 文案/分镜: kimi-k2.6 | 视频: Seedance 2.0 Pro   ← 真实模式
TravelGen 管线服务 | 文案/分镜: demo回放 | 视频: 模拟                ← demo 模式
```

- **无任何 key → 自动 demo 模式**：全流程回放真实样例（西湖），视频为模拟成功。**不用花一分钱，优先用它联调**。
- **有 key 想走真实生成**：`cp experiments/config.example.json experiments/config.json`，填入 kimi/seedance 的 api_key 后重启（config.json 已被 gitignore，不会误提交；key 是你自己的，B 侧可不填）。
- 交互文档（可直接点按钮调试）：http://127.0.0.1:8000/docs

## 3. 完整联调流程（V1 分阶段接口，按顺序）

下面所有 `{pid}` 用第①步返回的 project_id 替换，`{tid}` 用第⑥步返回的 task_id。curl 或 Apifox 均可。

### ① 创建项目（异步生成创作方案）

```bash
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"city":"杭州","location":"西湖","scene_type":"景区推荐","theme":"春日西湖旅游宣传","audience":"18-35岁年轻游客","style":"大气唯美","duration_s":60,"aspect_ratio":"9:16","resolution":"1080p","video_model":"seedance-2.0-pro"}'
```

→ `202 {"project_id":"p_xxx", "status":"planning", ...}`

### ② 轮询方案生成

```bash
curl http://127.0.0.1:8000/api/projects/{pid}
```

`status` 变为 `waiting_confirm` 即方案就绪（demo ≈10s；真实 kimi ≈2-3 分钟）。取返回里的 `copywriting_text`（字符串，含【0-15s】时间戳）——**这就是你页面里给用户编辑的文案**。

### ③ 确认方案（第一次人工干预点）

```bash
curl -X PUT http://127.0.0.1:8000/api/projects/{pid}/plan \
  -H "Content-Type: application/json" \
  -d '{"copywriting":"<粘贴上一步的 copywriting_text，可先让用户编辑再提交>"}'
```

→ `200 {"status":"plan_confirmed", "plan_id":"plan_..."}`

### ④ 生成分镜

```bash
curl -X POST http://127.0.0.1:8000/api/projects/{pid}/storyboard \
  -H "Content-Type: application/json" -d '{}'
```

再轮询 `GET /api/projects/{pid}` 至 `waiting_storyboard_confirm`（demo ≈10s；真实 kimi ≈3-4 分钟）。此时 `storyboard` 里有 6-8 个镜头，每个含 prompt/duration_s/camera 等。

### ⑤ 修改单个 Shot（第二次人工干预点，可选）

```bash
curl -X PUT http://127.0.0.1:8000/api/projects/{pid}/shots/3 \
  -H "Content-Type: application/json" \
  -d '{"prompt":"...改后的镜头描述..."}'
```

支持字段：`prompt` / `duration_s` / `subject` / `background` / `shot_size` / `camera{angle,movement}`，只写想改的字段。

### ⑥ 确认声音设置后批量生成 Segment

先通过 `/api/voice-presets` + `PUT /api/projects/{pid}/voice` 确认统一参考音色，并通过 `/api/bgm` + `PUT /api/projects/{pid}/bgm` 选择 BGM（或传 `explicit_none:true`）。

```bash
curl -X POST http://127.0.0.1:8000/api/projects/{pid}/generate \
  -H "Content-Type: application/json" \
  -d '{"segments":["seg_01","seg_02"],"generate_video":true}'
```

→ `202 {"task_id":"st_xxx", "segments":[{segment_id,status:"pending"},...]}`。不传 `segments` 时生成全部 Segment。

### ⑦ 轮询 Segment 任务

```bash
curl http://127.0.0.1:8000/api/tasks/{tid}
```

per-segment 状态推进：`pending → generating → completed`。每个 Segment 内含一个或多个完整 Shot，真实 Seedance 调用不会拆 Shot，也不会为了凑满 15 秒补时长。全部完成后：

- 项目 `GET /api/projects/{pid}` → `status:"video_ready"`
- 每段原生音视频位于 `assets/videos/{project_id}/{segment_id}/`，浏览器读取 `segment_results.{segment_id}.video_url`
- demo 模式也会生成带静音音轨的真实占位 MP4，以验证 AV 拼接路径

### ⑧ 从 Shot 发起重生成（实际重生成所属 Segment）

```bash
curl -X POST http://127.0.0.1:8000/api/projects/{pid}/shots/3/regenerate \
  -H "Content-Type: application/json" \
  -d '{"reason":"画面不满意","prompt":"换成黄昏色调的断桥"}'
```

→ 新 `st_xxx` 任务，返回 `regeneration_unit:"segment"`；该 Shot 所属的完整 Segment 会重新生成。

### ⑨ 音色、BGM 与最终合成

- `GET /api/voice-presets` 获取预设试听；`POST /api/projects/{pid}/voice-candidates` 生成自定义候选；`PUT /api/projects/{pid}/voice` 确认统一音色。
- `GET /api/bgm` 获取目录；`POST /api/projects/{pid}/bgm/recommendations` 获取 KIMI 建议；`PUT /api/projects/{pid}/bgm` 确认 BGM 或无 BGM。
- `POST /api/projects/{pid}/render` 拼接 Seedance 原生音视频并可选混入 BGM；`GET /api/projects/{pid}/render/status` 返回 clean/with_bgm 双版本。

## 4. 状态机速查（调试 409 时对照）

```
created → planning → waiting_confirm ──PUT /plan──▶ plan_confirmed
        → storyboarding → waiting_storyboard_confirm ──POST /generate──▶ generating → completed/failed
```

- 两次人工干预点：`waiting_confirm`（③确认方案）、`waiting_storyboard_confirm`（⑤改 Shot 或直接⑥）
- 状态不对时返回 `409 {"code":"invalid_state", "message":"xxx 需项目处于 [...]，当前 xxx"}` —— 按 message 提示走流程即可

## 5. 关键约定（避免踩坑）

| 项 | 约定 |
|---|---|
| 轮询入口 | 方案/分镜阶段用 `GET /api/projects/{pid}`；视频阶段用 `GET /api/tasks/{tid}` |
| shot_id | int（前端展示可补零成 "shot_01"） |
| scene_type | 中文枚举（景区推荐/城市形象宣传/非遗文化传播/节庆活动推广/打卡视频/其他）或英文别名（scenic 等）均可 |
| 错误格式 | 统一 `{"code","message","detail"}`；400 参数错 / 404 不存在 / 409 状态错 / 500 内部 |
| 旧接口 | `POST /api/v1/generate` + `GET /api/v1/tasks/{id}` 一键直出仍可用（答辩兜底），但**前端按 V1 分阶段开发** |
| 重启 | 服务重启不丢数据——项目/任务落盘 `experiments/results/05_pipeline/`，GET 自动恢复 |

## 6. 常见问题

| 问题 | 解决 |
|---|---|
| 端口 8000 被占用 | `netstat -ano | findstr :8000` 找到 PID 后 `taskkill /PID <pid> /F` |
| 改了代码没生效 | 服务是常驻进程，改完必须重启（Ctrl+C 再 `python app.py`） |
| 想要真实视频但没有 key | 找 A 要 key 填进 `experiments/config.json`，或让 A 跑完任务后把 `assets/videos/` 发你 |
| 不确定接口字段 | 看 Swagger http://127.0.0.1:8000/docs，每个接口有示例 |

## 7. 文档索引

| 文件 | 用途 |
|---|---|
| [backend/README.md](../backend/README.md) | 启动说明、模式切换、接口清单 |
| [docs/API_Contract_MVP.md](API_Contract_MVP.md) | 契约 v0.2：全部字段结构、错误码、状态机 |
| [docs/api/openapi.yaml](api/openapi.yaml) | Apifox 导入（接口文档 + Mock + TS 类型参考） |
| [TravelGen_v1.md](../TravelGen_v1.md) | 你写的 V1 分阶段设计文档（本手册即它的落地实现） |

**Apifox 协作**（可选，见契约文档 §8）：导入 openapi.yaml → 前端指向 Apifox Mock 先开发 → 本地服务跑通后切换指向 http://127.0.0.1:8000。
