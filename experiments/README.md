# TravelGen Phase 3 Benchmark 实验操作指南

**目标**：用统一Prompt比较文案/分镜/视频模型，确定最终选型（输出 Experiment Report + Benchmark.xlsx）
**负责人**：A（文案/分镜/评测）＋ B（视频接入/成本）
**统一Prompt**：`请生成一段杭州西湖一分钟宣传视频。`

---

## 0. 实验总览

| # | 实验 | 输入 | 候选模型 | 输出 | 负责人 | 时间 |
|---|---|---|---|---|---|---|
| 1 | 文案对比 | 统一文案Prompt | GPT/Claude/Qwen/Gemini/DeepSeek/Kimi（各3次） | results/01_copywriting/ + 评分表 | A | D3-4 |
| 2 | 分镜对比 | 实验1最优文案+分镜Prompt | 同上6家（各3次） | results/02_storyboard/ + JSON | A | D3-4 |
| 3 | 视频对比 | 实验2最优分镜的镜头prompt | Seedance 2.0/可灵/混元/Runway/Veo/MiniMax/即梦 | results/03_video/ + 样片 | B接入，A评测 | D5-6 |
| 4 | 配音对比（可选） | 实验1最优旁白 | CosyVoice2/GPT-SoVITS/EdgeTTS | results/04_voice/ | A/B | D6 |

## 1. 实验前准备（D1-2）

### 1.1 目录结构（本目录已建好）
```
experiments/
├── README.md              # 本指南
├── prompts/               # 统一Prompt（定稿后加版本号，勿再手改）
│   ├── copywriting.txt    # 实验1 文案Prompt（含{KNOWLEDGE}占位）
│   ├── storyboard.txt     # 实验2 分镜Prompt（含{SCRIPT}占位）
│   ├── video_suffix.txt   # 实验3 镜头prompt统一后缀
│   └── judge.txt          # LLM-Judge 评分Prompt
├── config.json            # API配置（各家 base_url/api_key/model）——勿提交git
├── run_llm_benchmark.py   # 实验1/2 统一执行脚本（A）
├── judge_llm.py           # LLM-Judge 评分脚本（A）
└── results/
    ├── 01_copywriting/ 02_storyboard/ 03_video/ 04_voice/
    ├── scores_copywriting.csv   scores_storyboard.csv
    └── video_record.csv         # 视频实验记录（B填）
```

### 1.2 API Key 配置
编辑 `config.json`：
```json
{
  "providers": [
    {"name": "deepseek", "base_url": "https://api.deepseek.com/v1", "api_key": "sk-xxx", "model": "deepseek-chat"},
    {"name": "qwen",     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "sk-xxx", "model": "qwen-plus"},
    {"name": "kimi",     "base_url": "https://api.moonshot.cn/v1", "api_key": "sk-xxx", "model": "moonshot-v1-128k"},
    {"name": "gemini",   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key": "AIza-xxx", "model": "gemini-2.5-pro"},
    {"name": "claude",   "base_url": "https://api.anthropic.com/v1", "api_key": "sk-ant-xxx", "model": "claude-sonnet-5"},
    {"name": "gpt",      "base_url": "https://api.openai.com/v1", "api_key": "sk-xxx", "model": "gpt-5-mini"}
  ],
  "judge": {"name": "judge", "base_url": "https://api.deepseek.com/v1", "api_key": "sk-xxx", "model": "deepseek-chat", "temperature": 0},
  "temperature": 0.7,
  "n_runs": 3
}
```
> 模型ID按2026年各家实际版本填写；所有兼容端点统一走 OpenAI 格式（本项目脚本用 requests 直连，无SDK依赖）。**Claude 端点需加 `x-api-key` 与 `anthropic-version` 头**（脚本已处理）。

### 1.3 B 侧准备（视频实验前提）
- 开通/确认：Seedance 2.0（火山方舟）、可灵（klingai）、腾讯混元、MiniMax、即梦、Runway、Veo 的 API Key 与额度
- 填预算单：每通道单条成本预估（参考 survey/GithubSurvey.xlsx 价格列）
- 确认本地 GPU：`nvidia-smi` 显存≥24G 则 Wan2.2-TI2V-5B 可本地跑（备选通道）

## 2. 实验1：文案对比（A，D3）

```bash
# 1) 跑6家LLM × 3次（prompts/copywriting.txt 中 {KNOWLEDGE} 默认注入西湖知识资料）
python run_llm_benchmark.py --task copywriting --knowledge "西湖十景：苏堤春晓、断桥残雪...（D1人工整理版）"

# 2) 评分：LLM-Judge 3票 + 输出 scores_copywriting.csv
python judge_llm.py --results results/01_copywriting --out results/scores_copywriting.csv --judge-count 3

# 3) 人工复核：抽最高/最低各1家，修正明显误判；填写最终结论
```
- 记录：每模型输出存 `results/01_copywriting/<model>_<run>.md`（脚本自动含版本/时间头）
- 结论产出：最优文案 → 复制为 `results/best_copywriting.txt`（实验2输入）

## 3. 实验2：分镜对比（A，D4）

```bash
# 用实验1最优文案注入 {SCRIPT}，跑6家 × 3次
python run_llm_benchmark.py --task storyboard --script results/best_copywriting.txt

# JSON 合法性自动校验（脚本内置），非法输出记0分不参与内容评分
python judge_llm.py --results results/02_storyboard --out results/scores_storyboard.csv --judge-count 3
```
- 评分维度：镜头质量/镜头逻辑/画面一致性/结构化程度/可执行性
- 结论产出：最优分镜JSON → `results/best_storyboard.json`（实验3输入，也是 Phase 5 分镜Schema的基线）

## 4. 实验3：视频对比（B主导接入，A评测，D5-6）

### 4.1 操作流程
1. 从 `results/best_storyboard.json` 提取每镜头的 `prompt` 字段 + 拼接 `prompts/video_suffix.txt` 统一后缀 → `results/03_video/shot_prompts.txt`
2. 每个视频通道生成同一组镜头（建议先每通道跑1条样片，确认质量与计费后批量）
3. 每通道记录：耗时（提交→完成）、实际扣费 → 填 `results/video_record.csv`
4. D6 下午：AB 一起过样片，A 按维度打分（画质/一致性/中文适配），B 提供成本/速度

### 4.2 各通道调用要点（详细见 03_video/README.md）
| 通道 | 要点 |
|---|---|
| Seedance 2.0 | POST ark.cn-beijing.volces.com/api/v3 /v1/contents/generations/tasks → task_id → 轮询（5-15s间隔+退避），video_url 仅24h需及时下载 |
| 可灵 3.0 | api-beijing.klingai.com，API Key鉴权，资源包预购制，支持按任务ID批量查询 |
| 腾讯混元 | 异步任务+积分制，生成失败不扣费 |
| Runway/Veo/MiniMax/即梦 | 官方API异步提交；Veo国内不可直连（需代理或仅作海外参照） |
| Wan2.2（本地兜底） | ComfyUI-WanVideoWrapper 或官方仓库脚本；4090约9分钟/5s 720P |

### 4.3 评测记录表（video_record.csv）
```csv
channel,shot_id,prompt_md5,耗时秒,成本元,画质分,一致性分,中文适配分,样片链接,备注
seedance2,1,abc123,95,4.3,5,5,5,https://...,首帧稳定
```

## 5. 实验4：配音对比（可选，D6）

- 同一旁白（best_copywriting.txt）分别用 CosyVoice2 / GPT-SoVITS / EdgeTTS 生成
- 评分：中文自然度/音色质感/合成速度（人工听评，10秒级盲测）

## 6. 评测方法论（防坑）

1. **版本记录**：脚本自动在输出头记录 model/日期/Prompt版本/温度——LLM与视频模型迭代快，无版本=不可复现
2. **多轮取代表**：每模型3次；LLM-Judge 3票取中位数，人工抽检20%（最高/最低各1家）
3. **评分锚点**（统一各维度1-5含义）：1=不可用 2=明显缺陷 3=及格可用 4=良好 5=优秀可直接商用
4. **JSON校验**：分镜输出必须严格JSON，解析失败的按0分处理（实测不少模型会夹带文字）
5. **成本红线**：视频通道先样片后批量；总预算超支前 AB 确认

## 7. 汇总输出（D7）

1. 汇总 `scores_*.csv` → `results/Benchmark_汇总.xlsx`（Sheet1总览/2文案/3分镜/4视频/5配音）
2. 撰写 `docs/Experiment_Report_Phase3.md`（结构见 docs/Phase3_Handoff_Plan.md 4.1节）
3. 选型结论（评分×成本矩阵）→ 输出给 Phase 4 系统设计
