# 实验3：视频生成对比 —— 操作手册（B主导接入，A评测）

**输入**：results/best_storyboard.json 中每个镜头的 `prompt` 字段 + prompts/video_suffix.txt 统一后缀
**候选通道**：Seedance 2.0 / 可灵 3.0 / 腾讯混元 / MiniMax / 即梦 / Runway / Veo / Wan2.2（本地兜底）

---

## 0. 前置（D5 前完成，B负责）

- [ ] 各通道 API Key / 积分 / 资源包到位（未开通的先申请，注意可灵资源包预购、Veo 需海外访问）
- [ ] 预算单确认：单条成本 = 时长×单价（参考 survey/GithubSurvey.xlsx 价格列）
- [ ] 本地 GPU 确认：`nvidia-smi` 显存≥24G → Wan2.2-TI2V-5B 本地可用

## 1. 生成步骤

### 1.1 准备镜头 Prompt（A提供）
从 `results/best_storyboard.json` 提取每个镜头：
```
shot_prompts.txt 每行一个镜头：<shot_id>\t<prompt字段> + 统一后缀
示例：
1	航拍镜头缓缓推进，西湖苏堤在晨雾中，朝霞映红水面，写实电影质感，自然光影，8K细节，稳定构图，无文字水印
```

### 1.2 各通道调用要点

**Seedance 2.0（火山方舟）** ⭐主通道
```python
import requests, time
# 1) 提交（异步）
r = requests.post("https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
                  headers={"Authorization": "Bearer <ARK_KEY>"},
                  json={"model": "doubao-seedance-2-0-260128",
                        "content": [{"type": "text", "text": "<镜头prompt>"}],
                        "duration": 5, "resolution": "1080p"})
task_id = r.json()["id"]
# 2) 轮询：5-15s间隔+指数退避，状态机 queued→running→succeeded/failed/expired
for _ in range(60):
    st = requests.get(f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}",
                      headers={"Authorization": "Bearer <ARK_KEY>"}).json()
    if st["status"] == "succeeded":
        video_url = st["content"]["video_url"]   # ⚠️ 仅24h有效，立即下载
        break
    time.sleep(10)
```

**可灵 3.0（快手）**
- 域名 `https://api-beijing.klingai.com`，API Key 鉴权，资源包预购制（Turbo 0.8-1.0 积分/s）
- 支持按任务 ID/Cursor 批量查询；`mode: "pro"`，`aspect_ratio: "16:9"`，`duration: "5"`

**腾讯混元生视频**
- 异步任务 + 积分制（1元/积分，生成失败不扣费）；文生 1080p 5s = 3积分；图生 720p = 5积分
- 人像驱动（数字人播报）1-2 元/s —— 文旅"虚拟导游"候选

**MiniMax / 即梦**
- 官方 API 异步提交；MiniMax 支持 S2V 首尾帧；即梦与 Seedance 同生态可少测

**Runway / Veo**
- Runway Gen-4 API（海外）；Veo 走 Gemini API（$0.4/s，国内不可直连）——**仅作海外质量参照**，不进入最终选型对比

**Wan2.2-TI2V-5B（本地兜底）**
- 官方仓库 Wan-Video/Wan2.2 推理脚本，或 ComfyUI + ComfyUI-WanVideoWrapper（kijai）
- RTX 4090 上 5s/720P 约 9 分钟；输入 = 分镜图（图生视频）或纯 prompt（文生视频）

### 1.3 记录（B填 video_record.csv）
每通道每镜头一行：耗时（提交→完成）、实际成本、样片下载链接、异常备注

## 2. 评测流程（D6 下午，AB 共同）

1. A 提前把样片按 通道×镜头 编号整理（建议同镜头多通道并排播放对比）
2. A 按三维度打分：**画质**（分辨率/细节/色彩）、**一致性**（主体/地标/场景）、**中文适配**（prompt理解/视频内中文文字）
3. B 提供：**速度**（分钟/条）、**成本**（元/条）
4. 记入 video_record.csv → 汇总到 Benchmark_汇总.xlsx

## 3. 判定规则（评分×成本矩阵）

- 画质分接近（差≤0.5）→ 选成本低者
- 本地通道（Wan2.2）若画质≥4.0 → 优先入选（可持续批量、无限流）
- Seedance 2.0 与可灵 3.0 分不出高下 → 保留双通道，A/B 成本测试后定

## 4. 产出

- `results/03_video/video_record.csv`（全部原始记录）
- `results/03_video/样片链接清单.md`（评委回看用）
- 结论 → 写入 `docs/Experiment_Report_Phase3.md` 第3.3节
