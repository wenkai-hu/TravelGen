# Experiment Report — Phase 3 Benchmark

**项目**：TravelGen——基于多智能体协同与知识增强的浙江文旅AIGC城市短视频自动生成平台
**赛题**：中国移动杯·第二届浙江省大学生人工智能竞赛 JBGS-2026-01
**编写**：成员A｜**日期**：2026-08-05｜**版本**：v1.0（定稿）

---

## 1. 实验目的与统一 Prompt

**目的**：用统一 Prompt 对比文案/分镜环节的候选 LLM，为平台确定最终模型选型（评分 × 成本矩阵）。

**统一 Prompt**：`请生成一段杭州西湖一分钟宣传视频。`
- 文案 Prompt：`prompts/copywriting.txt`（v1，含知识库注入）
- 分镜 Prompt：`prompts/storyboard.txt`（v1，scene→shot 两级严格 JSON）

## 2. 实验设计

### 2.1 分组与参数

| 项目 | 设置 |
|---|---|
| 候选模型 | GPT / Claude / Qwen / Gemini / DeepSeek / Kimi（6 家） |
| 模型版本 | deepseek-v4-flash / qwen-plus / kimi-k2.6 / gemini-3.5-flash / claude-sonnet-5 / gpt-5.4-mini |
| 每模型生成次数 | 3 次（多轮取代表） |
| 温度 | 0.7（kimi-k2.6 为推理模型仅接受 temperature=1，单独覆盖） |
| Judge | deepseek-v4-flash，temperature=0，每文件 3 票取中位数 |
| 数据源 | 官方 API（DeepSeek/Kimi）+ 聚合通道（v3.cm，其余四家） |

### 2.2 评分方法（对齐赛事评分标准）

赛事评分标准第（2）条「AIGC生成效果（30%）」细化为两套机制：

1. **绝对评分**（LLM-Judge，1-5 分）：文案维度 = 内容质量与主题契合 / 传播感染力 / 风格一致性 / 信息真实性 / 格式规范与可执行性；分镜维度 = 镜头质量 / 镜头逻辑 / 画面一致性 / 结构化程度 / 可执行性。含硬性罚分规则（编造史实判 1 分、格式违规扣分、JSON 非法结构化 1 分等）。
2. **成对比较**（MT-Bench 双打分法）：每家取最高分文件为代表，两两对决，裁判对双方分别打 1-5 分，位置交换两次合计总分，高者胜——消除位置偏差，区分度显著优于绝对分。

### 2.3 已知局限

- LLM-Judge 绝对分存在天花板效应（文案环节集中在 5.0），因此**排名以成对比较为准**，绝对分作为及格线文档参考。
- 聚合通道与官方通道存在延迟差异，不影响内容质量对比。

## 3. 实验结果

### 3.1 文案对比（实验1）

| 排名 | 模型 | 三局绝对分 | 平均 | 成对胜率 | 胜/负/平 |
|---|---|---|---|---|---|
| 1 | **kimi** | 5.0/5.0/5.0 | 5.00 | **1.00** | 3-0-2 |
| 2 | deepseek | 5.0/5.0/5.0 | 5.00 | 0.75 | 3-1-1 |
| 3 | gemini | 5.0/5.0/5.0 | 5.00 | 0.67 | 2-1-2 |
| 4 | gpt | 5.0/5.0/5.0 | 5.00 | 0.25 | 1-3-1 |
| 5 | claude | 5.0/4.8/5.0 | 4.93 | 0.00 | 0-3-2 |
| 6 | qwen | 4.8/5.0/5.0 | 4.93 | 0.00 | 0-1-4 |

**代表性输出摘录**（kimi_01，冠军）：
> 三面云山一面城，6.38平方公里的湖面，盛着一座城最温柔的野心。2011年，西湖文化景观列入世界遗产——这里不是封存的过往，是流动着的千年美学。……（完整输出见 `experiments/results/01_copywriting/kimi_01.md`）

### 3.2 分镜对比（实验2）

| 排名 | 模型 | 三局绝对分 | 平均 | 成对胜率 | 胜/负/平 | 备注 |
|---|---|---|---|---|---|---|
| 1 | **kimi** | 5.0/5.0/5.0 | 5.00 | **1.00** | 4-0-1 | 双榜第一 |
| 2 | qwen | 2.6/3.6/2.8 | 3.00 | 1.00 | 4-0-1 | 单条最强但波动大 |
| 3 | claude | 3.8/3.0/3.6 | 3.47 | 0.50 | 2-2-1 | |
| 4 | gemini | 5.0/2.8/5.0 | 4.27 | 0.33 | 1-2-2 | 质量不稳定 |
| 5 | deepseek | 3.0/4.8/4.2 | 4.00 | 0.25 | 1-3-1 | |
| 6 | gpt | 2.8/4.0/3.4 | 3.40 | 0.00 | 0-5-0 | |

**说明**：18/18 输出均为合法 JSON；kimi 绝对分与成对比较双第一；qwen 成对全胜系取单条最强（qwen_02）之故，实际三局波动大，不作首选。

**最优分镜 JSON 样例**（kimi_01，7 场景 / 8 镜头 / 60s）：
```json
{
  "theme": "杭州西湖宣传片",
  "scenes": [
    {
      "scene_id": 1, "location": "西湖湖面", "time": "清晨",
      "shot_list": [
        {"shot_id": 1, "duration_s": 8,
         "camera": {"type": "航拍", "movement": "推", "angle": "俯拍"},
         "shot_size": "大远景", "subject": "西湖与苏堤全貌", "background": "朝霞晨雾",
         "prompt": "电影级航拍大远景，清晨西湖全景与苏堤横贯湖面……"}
      ]
    }
  ]
}
```
时间线清晨→入夜推进，苏堤/三潭印月/雷峰塔/断桥白堤/曲院风荷等地标跨镜头描述一致。完整输出见 `experiments/results/best_storyboard.json`。

### 3.3 视频对比（实验3）

**选型决策已定：Seedance 2.0 Pro**（依据 Phase 1/2 调研：中文最优 API 档，约 1 元/条）。
- 输入已就绪：`results/03_video/shot_prompts.txt`（8 镜头 prompt + 统一后缀）
- 样片验证与成本/耗时数据由成员 B 补录至 `results/video_record.csv`（本报告 3.3 节待回填）

### 3.4 配音对比（实验4）

本次跳过（可选实验）。Phase 5 若需配音，候选 CosyVoice2（开源本地）/ GPT-SoVITS（开源本地）/ EdgeTTS（免费）。

## 4. 分析与选型结论

| 环节 | 入选模型 | 备选 | 理由 |
|---|---|---|---|
| 文案 | **kimi-k2.6** | deepseek-v4-flash | 成对比较无败绩，风格契合"大气唯美+年轻化"；DeepSeek 为低成本备选 |
| 分镜 | **kimi-k2.6** | qwen-plus（单条强） | 绝对分 + 成对双第一，输出严格符合 Schema 契约 |
| 视频 | **Seedance 2.0 Pro** | 可灵 3.0 / Wan2.2 本地 | 中文最优 API 档（约 1 元/条）；本地 Wan2.2 作成本兜底 |
| 配音 | 暂不选型 | — | — |

**成本说明**：实验 1/2 主要消耗各家新人免费额度（DeepSeek 赠送 500 万 token、Kimi 赠送 15 元等），实际现金成本 ≈ 0。

## 5. 对 Phase 4 系统设计的输入

1. **分镜 JSON Schema 契约**（定稿版）：`docs/Storyboard_Schema_v1.md` —— Phase 5 Storyboard Agent 输出 / Video Composer 消费的唯一接口
2. **Prompt 模板**：`experiments/prompts/copywriting.txt` / `storyboard.txt` / `video_suffix.txt`（v1 定稿）
3. **模型接入清单**：
   - kimi-k2.6：`https://api.moonshot.cn/v1`，OpenAI 兼容，temperature 须为 1（推理模型）
   - Seedance 2.0 Pro：火山方舟异步任务接口（见 `experiments/03_video/README.md`）
   - 评测数据：`experiments/results/Benchmark_汇总.xlsx`（Sheet1 总览 / 2 文案 / 3 分镜 / 4 视频 / 5 配音）

## 附录 A：过程中发现与修复的问题

| 问题 | 修复 |
|---|---|
| kimi-k2.6 仅接受 temperature=1，0.7 导致 400 | run_llm_benchmark.py 支持每模型独立 temperature（config.json 内配置） |
| judge_llm.py 未跳过 `[ERROR` 失败文件、文案任务误加"结构化程度"维度导致 CSV 崩溃 | 修复跳过判断（strip 后检查）+ 结构化程度兜底仅限分镜任务 |
| 成对比较裁判误用文案标准评分镜（位置偏差致 11/15 平局） | 分镜专属成对提示词 + MT-Bench 双打分法（裁判对双方分别打分、交换位置合计） |
| `.gitignore` 行内注释导致 `experiments/config.json`（含 API Key）忽略规则失效 | 移除行内注释，修复后验证生效 |

## 附录 B：复现方法

```bash
cd experiments
python run_llm_benchmark.py --task copywriting --script results/best_copywriting.txt   # 实验1（--only <模型> 可单独重跑）
python judge_llm.py --results results/01_copywriting --out results/scores_copywriting.csv --judge-count 3
python judge_pairwise.py --results results/01_copywriting --scores results/scores_copywriting.csv --out results/pairwise_copywriting.csv
# 实验2 同理换 --task storyboard / 02_storyboard
```
