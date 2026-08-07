# TravelGen 文献阅读笔记（Reading Notes）

**项目**：TravelGen——基于多智能体协同与知识增强的浙江文旅 AIGC 城市短视频自动生成平台
**阶段**：Phase 1 文献调研（Week1~Week2）｜**负责人**：成员A
**日期**：2026-08-02
**范围**：四大方向共 37 项（任务清单 27 项 + 新增 10 项，新增以 ⭐ 标注）

---

## 总览表

| # | 方向 | 论文/报告 | 团队 | 年份 | 对本项目的核心价值 |
|---|---|---|---|---|---|
| 1 | 视频 | Sora Technical Report | OpenAI | 2024 | 时空patch+DiT范式；prompt扩写提示工程 |
| 2 | 视频 | Seedance 1.0 | ByteDance | 2025 | 原生多镜头10s；中文指令；三奖励RLHF |
| 3 | 视频 | Wan2.2 | Alibaba | 2025 | MoE DiT；Apache2.0自部署骨干；中文视频内文字 |
| 4 | 视频 | HunyuanVideo | Tencent | 2024 | 13B开源；MLLM文本编码；9:16原生 |
| 5 | 视频 | CogVideoX | Zhipu AI | 2024 | 轻量预览稿引擎；免费flash API |
| 6 | 视频 | Open-Sora | HPC-AI Tech | 2024-25 | 全栈开源；20万美元低成本训练方法论 |
| 7 | 视频 | VideoPoet | Google | 2023 | 视频+音频统一token自回归；续帧转场思想 |
| 8 | 视频 | VideoCrafter2 | 腾讯AI Lab | 2024 | 运动-外观数据解耦训练配方 |
| 9 | 视频 | AnimateDiff | HKU/AI Lab | 2023 | MotionLoRA运镜模板；图片微动效 |
| 10 | 视频 | Emu Video | Meta | 2023 | 首帧→视频两阶段；首帧即关键帧 |
| 11 | 视频⭐ | HunyuanVideo 1.5 | Tencent | 2025 | 14GB可跑；视频内中文字渲染；Apache2.0 |
| 12 | 视频⭐ | LTX-2 | Lightricks | 2026 | 开源音画同步4K；竖屏直出 |
| 13 | 视频⭐ | Wan 2.6 | Alibaba | 2025 | 自动分镜+跨镜头一致+R2V；15s一条成片 |
| 14 | 分镜 | StoryGen (Intelligent Grimm) | SJTU/Meituan | 2024 | 参考帧锚定一致性；双路CFG |
| 15 | 分镜 | Visual Storytelling综述 | UIC | 2019 | 六维评测量表；视觉接地 |
| 16 | 分镜 | LLM Story Generation综述 | TAMU等 | 2025 | 层级大纲=叙事规划核心；批评家Agent |
| 17 | 分镜 | DirectorLLM | Meta GenAI | 2024 | 导演/渲染解耦；姿态token化 |
| 18 | 分镜 | Story2Board | HUJI等 | 2025 | 免训练一致性（LPA/RAVM）；两段式prompt |
| 19 | 分镜⭐ | FilmAgent | HIT(深圳) | 2024 | 剧组角色分工；272预置镜头；评审回路 |
| 20 | 分镜⭐ | VideoDirectorGPT | UNC | 2024 | 分镜JSON模板；实体一致性分组 |
| 21 | 分镜⭐ | StoryDiffusion | NKU/ByteDance | 2024 | 免训练一致性自注意力；图生视频桥接 |
| 22 | Agent | AutoGen | Microsoft | 2023 | Conversable Agent；UserProxy人工参与 |
| 23 | Agent | MetaGPT | DeepWisdom | 2024 | SOP+结构化文档契约；消息池黑板 |
| 24 | Agent | CAMEL | KAUST | 2023 | Task Specifier任务规格化；失效模式警示 |
| 25 | Agent | CrewAI | CrewAI Inc. | 2023- | 角色制四原语；Flows确定性工作流 |
| 26 | Agent | LangGraph | LangChain | 2024- | Graph+checkpoint+HITL，生产首选 |
| 27 | Agent | OpenManus | MetaGPT团队 | 2025 | 计划文件+任务分派；MVP快速验证 |
| 28 | Agent | AutoGen现状/AG2 | MS/AG2 | 2025-26 | 维护模式警示；Agent Framework继任 |
| 29 | Agent⭐ | OpenAI Agents SDK | OpenAI | 2025- | guardrails三层校验；内置tracing |
| 30 | Agent⭐ | Google ADK 2.0 | Google | 2026 | graph-first+HITL原生；内置eval |
| 31 | RAG | RAG (原始) | Meta AI | 2020 | 检索-生成范式；索引热替换 |
| 32 | RAG | Self-RAG | UW/AI2/IBM | 2024 | 反思token；按需检索；事实核查器 |
| 33 | RAG | GraphRAG | Microsoft | 2024 | 实体-关系-社区摘要；global/local搜索 |
| 34 | RAG | LightRAG | HKU | 2024 | 轻量图+增量更新；双级检索 |
| 35 | RAG | HippoRAG | OSU/Stanford | 2024 | PPR单步多跳；OpenIE无schema图 |
| 36 | RAG | RAPTOR | Stanford | 2024 | 递归摘要树；层级粒度检索 |
| 37 | RAG⭐ | RAG综述 (Gao et al.) | FDU/TJU | 2024 | Naive/Advanced/Modular分类；RAGAS评估 |
| 38 | RAG⭐ | CRAG | USTC/UCLA/Google | 2024 | 检索质量门控；防幻觉三道闸门之一 |
| 39 | RAG⭐ | RAG-Fusion & ColBERT | Infineon/Stanford | 2020-24 | 多查询+RRF召回；MaxSim重排 |

---

## 一、AIGC 视频生成方向

### 1. Sora Technical Report（OpenAI, 2024-02）
- **摘要**：OpenAI 世界模拟器技术报告，确立 Diffusion Transformer（DiT）+ 时空 patch 的视频生成范式。
- **核心要点**：视频压缩网络映射像素到 latent → 时空 patch 作为 transformer token 扩散去噪；训练不裁剪缩放，支持可变分辨率/时长/宽高比；文本用 GPT 扩写 + DALL·E 3 式重标注；演示最长 60s/1080p；涌现 3D 一致性、物体恒存。
- **对本项目**：① prompt 扩写/重标注提示工程 → 文案→镜头级导演提示词；② 按镜头粒度生成再拼接；③ 质量与物理一致性评测参照系。闭源，国内不可直连。
- **引用**：https://openai.com/index/video-generation-models-as-world-simulators/

### 2. Seedance 1.0（ByteDance, 2025-06）
- **摘要**：字节跳动旗舰视频生成模型，中文指令理解强、原生多镜头叙事。
- **核心要点**：解耦时空 MM-DiT（空间层跨模态交互、时间层窗口划分全局感受野）+ 3D 多模态 RoPE；时间因果 VAE (4,16,16)；微调 decoder-only LLM 文本编码；480p 基础模型+级联 refiner 至 1080p；**原生多镜头 10s（2-3镜头无缝切换）**；后训练含视频 RLHF 三奖励模型（VLM/运动/美学）。闭源，火山引擎 API 0.21-0.73 元/条。
- **对本项目**：① 原生多镜头直接承载"分镜→成片"；② RLHF 三奖励提示用投放数据做风格反馈迭代；③ 双语数据策展可复用到文旅知识库构建。

### 3. Wan2.2（Alibaba, 2025-07）⭐清单新增
- **摘要**：阿里首个 MoE 视频扩散大模型，开源生态最好、中文视频内文字能力首创。
- **核心要点**：flow-matching + 两专家 MoE DiT（总参 27B/激活 14B，按 SNR 切分高/低噪声专家）；UMT5-XXL 文本编码；3D 因果 VAE (4×16×16)；A14B 系列 + TI2V-5B 密集版；开源 480p/720p、5s、24fps；**Apache 2.0**；衍生 Flash（快12倍）/S2V/Animate。
- **对本项目**：① 自部署骨干首选，LoRA 做"浙江山水/古镇/茶园"风格微调；② TI2V-5B（24G显存）批量出片与高价 API 成本分层；③ 高/低噪声专家分工启发"构图-细节"两段式质检。

### 4. HunyuanVideo（Tencent, 2024-12）
- **摘要**：腾讯混元 13B 开源视频模型，MLLM 文本编码显著提升指令理解。
- **核心要点**：双流→单流混合 transformer（20双流+40单流块）；3D 因果 VAE；文本编码 = LLaVA-llama-3-8B MLLM + 双向 token refiner + CLIP；720p/24fps/约5s；多宽高比含 9:16；社区许可全球（除EU/UK/KR）商用免版税。
- **对本项目**：① 原生 9:16 适配抖音/视频号；② 视觉-语言联合编码提升中文指令理解的验证；③ 社区许可条款作为开源选型法律评估范本。

### 5. CogVideoX（Zhipu AI, 2024-08）
- **摘要**：智谱开源视频生成模型，2B/5B 参数弹性、轻量易部署。
- **核心要点**：3D 因果 VAE（压缩至约2%）+ 冻结 T5-XXL + DiT（3D RoPE）；初版 720×480/8fps/6s 仅英文；X1.5-5B 升级 768p/16fps/10s + I2V；2B 与 X1.5 为 Apache 2.0，5B 需登记商用；cogvideox-flash API 免费。
- **对本项目**：① 2B 模型作"低质快速预览稿"引擎（先看构图分镜再出正片）；② 免费 flash API 批量测试脚本/分镜可行性。

### 6. Open-Sora（HPC-AI Tech, 2024-03 / 2.0: 2025-03）
- **摘要**：Sora 路线全开源复刻，2.0 端到端训练成本约 20 万美元，VBench 与 Sora 差距缩至 0.69%。
- **核心要点**：STDiT → MMDiT；2.0 用 Video DC-AE（4×32×32，训练快5.2×/推理快10×）+ T5-XXL + CLIP-L；768×768、约5s；权重+训练+推理代码全开源（Apache 2.0）。
- **对本项目**：① 低成本训练方法论 → 开放数据+文旅数据小规模微调/蒸馏；② 全栈代码是自研视频骨干的最佳起点（可改造 conditioning 注入分镜/机位信息）。

### 7. VideoPoet（Google, 2023-12）
- **摘要**：视频+音频统一 token 的自回归生成范式，非扩散路线。
- **核心要点**：MAGVIT V2（视频）+ SoundStream（音频）tokenizer；T5 文本编码；多任务预训练；以"最后1秒为条件"自回归续写；单次最长 10s 可无限续写；T2V/I2V/风格化/编辑/视频转音频。未开源未商用。
- **对本项目**：① "续帧"思想 → 片段间过渡生成（以前镜结尾为条件生成转场）；② 视频+音频联合生成范式已被 Seedance/LTX 落地，配音环节可探索"生成即带声"。

### 8. VideoCrafter2（腾讯AI Lab, 2024-01, CVPR 2024）
- **摘要**：运动-外观数据解耦的训练配方，解决高质量视频数据稀缺问题。
- **核心要点**：低质视频（WebVid-10M）学运动、高质量合成图像学画质；全量预训练后仅微调空间模块；T2V 320×512/16fps 秒级；I2V 拆至 DynamiCrafter；Apache 2.0。
- **对本项目**：① 数据解耦配方复用于"文旅风格微调"（运动学实拍、画质学专业摄影图集）；② DynamiCrafter 作"分镜首帧→视频"降级备选。

### 9. AnimateDiff（2023-07, ICLR 2024 Spotlight）
- **摘要**：SD1.5 即插即用运动模块，给静态图加动画。
- **核心要点**：冻结 T2I U-Net 时间轴插入运动模块；MotionLoRA 提供 8 种镜头运动；SparseCtrl 涂鸦/RGB 控制；Apache 2.0；生态庞大（A1111/ComfyUI）。
- **对本项目**：① MotionLoRA 镜头运动库 → "西湖游船/古镇巷道"固定运镜模板；② 风格化图片→微动效低成本物料（海报级短视频）。

### 10. Emu Video（Meta, 2023-11, ECCV 2024）
- **摘要**：分解式两阶段（T2I 生成首帧 → 首帧+文本 I2V），解耦空间与时间学习。
- **核心要点**：去掉时间层做 T2I；冻结 2.7B 空间参数、训练 1.7B 时间参数；512×512/4s/16fps；zero terminal-SNR 噪声调度。未开源。
- **对本项目**：① 两阶段与平台"AI图片→AI视频"环节天然对应——先定关键帧（构图/机位）再动画化；② 首帧条件化保证镜头画面一致性。

### 11. ⭐ HunyuanVideo 1.5（Tencent, 2025-11 开源）
- **摘要**：腾讯轻量旗舰开源视频模型，14GB 显存可跑、视频内中文文字渲染。
- **核心要点**：8.3B DiT + SSTA 稀疏滑窗注意力（提速1.87×）；Qwen2.5-VL（7B）+ T5 双文本编码；字形感知文本编码支持视频内中英文字；480p/720p→1080p；5-10s；相机运动控制；**Apache 2.0**；4090 蒸馏版省时 75%。
- **对本项目**：① 自部署骨干首选——中文指令+视频内中文字幕（景点名/诗句直出，免合成字幕）；② 14GB 门槛适合团队 GPU 批量出片与 LoRA 微调；③ Qwen2.5-VL 可与中文 RAG 链路共用。

### 12. ⭐ LTX-2（Lightricks, 2026-01 开源）
- **摘要**：首个开源"视频+音频联合生成"4K 模型，音画一次成。
- **核心要点**：双流 DiT（视频14B+音频5B）经双向交叉注意力耦合；48kHz 音频、音素级口型；原生 4K/50fps/10-20s；12-24GB 显存；LTX-2.3 为 22B 原生 9:16；**自定义许可**（年营收≥1000万美元商用需付费，派生权重同许可分发）。
- **对本项目**：① 音画同步开源基线（配音环节省 TTS+配乐拼接，注意中文口型质量）；② 9:16 竖屏 4K 直出适配抖音/视频号；③ 蒸馏+量化版本适合低成本渲染节点。

### 13. ⭐ Wan 2.6（Alibaba, 2025-12, 闭源 API）
- **摘要**：阿里统一多模态生成模型，自动分镜+跨镜头主体一致+音画同步+R2V。
- **核心要点**：文本/图像/视频/音频联合训练；最长 15s（5/10/15s）；720p/1080p/24fps；R2V 参考生视频（角色+声音复刻，最多5参考）；中文指令适配度最高档；阿里云百炼 API。
- **对本项目**：① 自动分镜承接"脚本→分镜"环节，多智能体只需产出镜头级 prompt；② R2V 支持"当地讲解员/主持人"数字人复刻（文旅 IP 运营）；③ 15s+多镜头"一条生成≈一条成片"。

---

## 二、Storyboard（分镜生成）方向

### 14. StoryGen / Intelligent Grimm（SJTU/Meituan/SH AI Lab, CVPR 2024）
- **摘要**：自回归图像序列生成，前帧视觉上下文保证故事连贯性。
- **核心要点**：基于 SD v1.5；"视觉语言上下文模块"将前序帧去噪特征通过图像交叉注意力层融合（ControlNet 风格求和）；文本/视觉双路 CFG；远帧加噪作位置编码；StorySalon 数据集（关键帧抽取、去重、清洗、caption 生成）。
- **对本项目**：① "参考帧锚定"思路 → 分镜画面一致性控制；② StorySalon 数据流水线 → 文旅素材自动清洗建库；③ 双路 CFG 分离"忠实文案"与"画面连贯"权重。

### 15. Visual Storytelling 综述（Modi & Parde, NAACL 2019 SiVL）
- **摘要**：视觉故事生成最早的系统性综述，给出评测维度与错误分析清单。
- **核心要点**：梳理 AREL/GLACNet 等 2018 挑战赛模型；归纳错误类型（视觉接地失败、重复、不连贯）；指出 METEOR 等 n-gram 指标与人工判断相关性差；人工评测六维度（聚焦、结构连贯、可分享性、类人性、视觉接地、细节度）。
- **对本项目**：① 六维评测量表 → TravelGen 分镜 LLM-Judge 评估量表；② 分镜评测应做多维人工/LLM 评分而非相似度指标；③ 视觉接地 → 分镜需与城市实景锚定（RAG 注入地标描述）。

### 16. A Survey on LLMs for Story Generation（TAMU 等, Findings of EMNLP 2025）
- **摘要**：LLM 故事生成最新综述，叙事规划方法四类分类。
- **核心要点**：约束生成（OSOS、MLD-EA）；提示生成（MoPS 模块化提示链：主题→背景→人物→情节）；大纲生成（DOME 动态层级大纲+时间知识图谱+叙事理论，plan-then-write）；多智能体协作（CollabStory、SWAG 高层叙事动作判别器、CritiCS 批评家流水线）。归纳"层级大纲=叙事规划核心机制"。
- **对本项目**：① 文案→脚本→分镜分层流水线（各层输出为下一层约束）；② SWAG 叙事动作（悬念/反转/节奏点）→ 短视频节奏与情绪曲线控制；③ CritiCS 批评家 Agent → 分镜评审-修正回路。

### 17. DirectorLLM（Meta GenAI, 2024, BMVC 2025）
- **摘要**："导演"与"渲染"解耦：LLM 以 1FPS 预测人物姿态 token，扩散插值器稠密化，ControlNet 渲染。
- **核心要点**：微调 Llama 3 预测 OpenPose 18 关键点 + 残差 VQ-VAE 离散化 token；线性插值至 30FPS；VideoCrafter2 姿态 ControlNet 渲染；导演模块与渲染器无关；SSTK 结构化分层 prompt（仅取 Subject-Level）。
- **对本项目**：① "LLM 导演（结构化指令）+ 渲染器解耦" → 分镜 Agent 只产出结构化 JSON，T2I/T2V 可随时替换；② 姿态 token 化 → 文旅人物走位/指向/讲解手势动作分镜可控化。

### 18. Story2Board（HUJI/OriginAI, 2025）
- **摘要**：训练免费的剧本→分镜生成框架，LPA/RAVM 双机制保证一致性。
- **核心要点**：LLM Director 分解"共享参考面板 prompt + 场景面板 prompt"；两面板协同去噪；**Latent Panel Anchoring（LPA）**锚定参考 latent 保持角色外观；**Reciprocal Attention Value Mixing（RAVM）**混合 value 向量保留姿态自由度；Rich Storyboard Benchmark + Scene Diversity 指标。
- **对本项目**：① LPA/RAVM 免训练一致性 → "西湖+雷峰塔"固定景点外观跨镜头一致；② "固定参考+场景变化"两段式 prompt 模板 → 文旅分镜模板骨架；③ Scene Diversity → 分镜多样性自动评估。

### 19. ⭐ FilmAgent（HIT(深圳), SIGGRAPH Asia 2024）
- **摘要**：多智能体模拟剧组（导演/编剧/演员/摄影师），3D 虚拟环境端到端电影自动化。
- **核心要点**：三阶段（规划：角色档案+分场大纲 → 编剧：对话/走位/动作 → 摄影：逐句对白机位设计）；**Critique-Correct-Verify** 与 **Debate-Judge** 协作算法显著降幻觉；272 个预置镜头（9 种景别运镜）；ChatTTS 对白配音；四维人工评分 3.98/5。
- **对本项目**：① 剧组角色分工 → 分镜 Agent 组职责切分（脚本 Agent→分镜导演 Agent→镜头参数 Agent）；② 评审修正回路 → 分镜 JSON 自动评审；③ 预置镜头库 → 分镜 JSON 镜头参数受控枚举（避免自由文本越界）。

### 20. ⭐ VideoDirectorGPT（UNC, COLM 2024）
- **摘要**：LLM 规划（JSON 视频计划）+ 布局引导的多场景视频生成。
- **核心要点**：Video Planner LLM 输出 scenes/entities（bbox 布局）/background/consistency 分组的结构化计划；关键实体附语义描述词跨场景保持身份；Grounded Video Generator（Layout2Vid）按计划生成；仅图像级标注训练。
- **对本项目**：① JSON 视频计划模板 → TravelGen 分镜 JSON Schema 骨架（加 shot 级字段扩展）；② 实体一致性分组（跨场景 ID）→ 文旅人物/地标全局 ID 管理；③ 计划先行、生成器解耦 → 模型可迭代替换。

### 21. ⭐ StoryDiffusion（南开/字节, NeurIPS 2024 Spotlight）
- **摘要**：免训练一致性自注意力 + 语义运动预测器，长序列一致图像与视频。
- **核心要点**：Consistent Self-Attention 跨图像共享 Q/K/V 计算自注意力（滑动窗口消显存）；零样本热插拔 SD1.5/SDXL；Semantic Motion Predictor 在语义空间估计运动，稳定转为分钟级视频。
- **对本项目**：① 免训练一致性 → 无需改模型即获跨镜头一致文旅画面；② 语义运动预测器 → 分镜关键帧→AI 视频的 I2V 桥接模块选型；③ 滑窗批量 → 20+ 面板长分镜的分批生成与显存管理。

---

## 三、Multi-Agent（多智能体）方向

### 22. AutoGen（Microsoft, 2023, arXiv:2308.08155）
- **摘要**：对话编程（Conversation Programming）多智能体框架，"Conversable Agent"统一抽象。
- **核心要点**：AssistantAgent（LLM）+ UserProxyAgent（人/代码执行）自由组合；GroupChatManager 动态选发言者；消息传递+自动回复；控制流由终止词+Python 融合控制；无内置长期记忆；框架 2025-10 起维护模式。
- **对本项目**：① UserProxyAgent"人工参与+代码执行" → Review 人工审核节点与渲染执行器；② 对话式协同仅适合头脑风暴，确定性流水线应显式编排。

### 23. MetaGPT（DeepWisdom, ICLR 2024 Oral）
- **摘要**：SOP 装配线多智能体框架，Code = SOP(Team)，结构化文档为中间产物。
- **核心要点**：产品经理→架构师→项目经理→工程师→QA 角色流水线；共享黑板消息池发布/订阅（避免信息过载）；阶段产物验证后才进入下阶段；测试失败回溯源重试（最多3次）；约 66k stars 但社区迭代放缓（公司重心转向商用）。
- **对本项目**：① SOP+结构化文档 → 固化"分镜表 JSON Schema"作为 Agent 间契约；② 消息池发布订阅避免四 Agent 信息过载；③ 可执行反馈 = 渲染失败/审核驳回自动重试链路。

### 24. CAMEL（KAUST, NeurIPS 2023）
- **摘要**：角色扮演双智能体（AI User + AI Assistant）自主对话协同，验证智能体社会可行性。
- **核心要点**：Task Specifier 将想法细化为具体任务；Inception Prompting 启动；纯对话协同；论文自陈存在角色翻转、重复回复、消息死循环等失效模式。
- **对本项目**：① Task Specifier"想法→任务规格" → Planner 的"主题→视频规格"细化步骤；② 失效模式正是采用确定性编排+终止条件+最大轮数上限的理由。

### 25. CrewAI（CrewAI Inc., 2023-, 约55k stars）
- **摘要**：角色制多智能体协作框架（Agent/Task/Crew/Process 四原语），MVP 速度最快。
- **核心要点**：Process 支持 sequential/hierarchical/consensual；**Flows**（事件驱动装饰器）为生产推荐确定性形态；四类内置记忆（短期/长期/实体/上下文）；@tool 注册；无内置 checkpoint（失败整跑重来）、Agent 间 token 成本高、调试困难。
- **对本项目**：① Crews 快速搭 MVP、生产切 Flows；② 四类记忆承载城市知识/用户偏好上下文；③ 缺 checkpoint 是硬伤，长链路视频生成需自建状态持久化。

### 26. LangGraph（LangChain, v1.0 GA 2025-10, 约36k stars）
- **摘要**：状态图（Pregel 模型）低层编排框架，生产最成熟的开源 Agent 编排层。
- **核心要点**：StateGraph 节点+条件边+typed state（reducer 合并）；子图嵌套、supervisor 多 Agent；**Checkpointer**（sqlite/postgres 线程级持久化）+ Store 长期记忆；**HITL interrupt 可跨天恢复**、time travel 回放与分叉、super-step 失败恢复；LangSmith 观测；Uber/JPMorgan/Klarna 生产背书。
- **对本项目**：① 四阶段流水线直接映射：Planner→Script→Storyboard→Review 节点 + interrupt 人工审核 + 失败重试边；② checkpoint 断点续跑，视频生成失败不重跑全链路；③ 子图封装"Storyboard+渲染+Review"复用于多城市。

### 27. OpenManus（MetaGPT 团队, 2025-03, 约57k stars）
- **摘要**：通用自主 Agent（ReAct + PlanningFlow），Manus 开源复刻，3 小时原型现象级项目。
- **核心要点**：单 Agent ReAct（step→think→act→execute）；多 Agent PlanningFlow（Planner 产出线性计划→动态任务分派，正则匹配+默认回退）；共享 markdown 计划文件；BaseTool 抽象+ToolCollection；定位通用助手非业务流水线。
- **对本项目**：① "计划文件+任务分派"结构与 TravelGen 流水线同构，参考其计划文件格式；② 轻量快速落地路径 → MVP 端到端验证。

### 28. AutoGen 现状 / AG2 社区版（2025-26）
- **摘要**：微软 AutoGen 进入维护模式，官方继任为 Microsoft Agent Framework；AG2 为社区延续。
- **核心要点**：AutoGen 最后版本 v0.7.5（2025-09），与 Semantic Kernel 合并为 **Microsoft Agent Framework**（2026-04 GA v1.0，graph 编排+企业级 telemetry/HITL）；AG2 约 4.8k stars、v0.12.x，GroupChat 经典 API 迁至 ag2-classic 维护；生态分裂。
- **对本项目**：**不建议新项目选 AutoGen 原版或 AG2**；若走微软栈评估 Agent Framework v1.0；AutoGen 论文概念（conversable agent、终止条件）仍是编排设计理论底座。

### 29. ⭐ OpenAI Agents SDK（OpenAI, 2025-03, v0.17.7, 约19-22k stars）
- **摘要**：Swarm 的正式生产版后继，极简 Agent + Handoff 委派 + 三层 guardrails。
- **核心要点**：Agent（instructions+tools+handoffs+guardrails+output_type 结构化输出）；Handoff 委派（triage/router/supervisor）；Session 持久化；MCP/沙盒工具；默认内置 tracing（OTel）；无 checkpoint/time travel。
- **对本项目**：① guardrails 三层校验 → Review Agent 硬规则（主题合规、敏感词、时长限制、PII）；② 内置 tracing 满足可观测性；③ triage 模式适合多城市/多主题子工作流路由。

### 30. ⭐ Google ADK 2.0（Google, 2026-06 GA, 约20.8k stars）
- **摘要**：Agent-as-Graph 工作流引擎，graph-first + HITL 原生 + 内置 eval。
- **核心要点**：节点类型（function/agent/tool/join/dynamic/workflow/parallel）；条件路由/循环；子 Agent+AgentTool 组合；A2A 协议跨框架通信；Session state 记忆；MCP 工具；Retry-and-Reflect 自愈插件；OTel 原生观测+BigQuery 分析插件；多语言版本最全。
- **对本项目**：① graph-first 与原生 HITL = 四 Agent 流水线+人工审核节点直接映射；② 内置 eval 与观测闭环审核质量；③ 选型锁定 2.x 版本并评估演进风险。

---

## 四、RAG（知识增强）方向

### 31. RAG（Lewis et al., Meta AI, NeurIPS 2020）
- **摘要**：检索增强生成开山之作，"参数化记忆+非参数化索引"混合模型。
- **核心要点**：BART-large 生成器 + DPR 双塔检索器（Wikipedia 2100 万段、100 词块、FAISS MIPS）；RAG-Sequence（整句同文档）/RAG-Token（逐 token 切换）；端到端联合微调查询编码器与生成器（文档编码器冻结）；换索引即更新知识（2016→2018 索引使"世界领导人"类问题正确率 12%→68%）。
- **对本项目**：① 本项目 RAG 基线，最小"检索-生成"闭环；② 索引热替换适配文旅数据持续更新；③ "生成须基于检索证据"成为文案 Agent 设计原则。

### 32. Self-RAG（UW/AI2/IBM, ICLR 2024 Oral）
- **摘要**：让 LLM 在生成中自我反思——按需检索 + 支撑性/相关性批评 token。
- **核心要点**：反思 token 四类：Retrieve（yes/no/continue 检索门控）、ISREL（片段相关性）、ISSUP（支撑性 fully/partial/no）、ISUSE（效用1-5）；critic 在 GPT-4 蒸馏数据上以**标准 LM 目标**训练（非 RL，论文明确对比 PPO/RLHF）；segment-wise beam search 推理期可控加权；基于 Llama-2 7B/13B 六任务超越 ChatGPT。
- **对本项目**：① "相关性/支撑性"批评机制 → **分镜事实核查器**（校验分镜描述是否被知识库支撑）；② 文案 Agent 对 RAG 结果打标签后决定采纳/改写；③ 按需检索降低多 Agent 无效检索成本。

### 33. GraphRAG（Microsoft, 2024, 约35k stars, v3.1.1）
- **摘要**：知识图谱 + Leiden 社区检测 + 层级社区摘要，解决语料级全局问题。
- **核心要点**：索引：chunk→LLM 抽实体/关系→消解建 KG→Leiden 分层社区→LLM 生成社区摘要（community reports）；查询三模式：local（实体+邻居+文本块联合）、global（社区摘要 map-reduce）、drift（2024-11，HyDE primer + 迭代 local + reduce，全面性胜 local 78%）；默认 chunk 1200 token/overlap 100；成本高（比 LightRAG 贵 10-50 倍），微软后继 LazyGraphRAG 降本至 0.1%。
- **对本项目**：① 城市/景区/非遗/节庆实体知识图谱是核心资产，复用"实体-关系-社区摘要"管线；② global 适配城市宣传片全景主题、local 适配景区分镜；③ 先导入结构化数据再增量补抽取控制成本。

### 34. LightRAG（HKU, 2024, EMNLP 2025 Findings, 约37-38k stars, v1.4.16）
- **摘要**：轻量图+向量双层索引、双级检索，增量更新免全量重建。
- **核心要点**：LLM 抽实体/关系以 Key-Value 存储（图结构融合进文本索引）；local/global/hybrid/naive/mix 五查询模式（实体型/主题型自适应）；默认 chunk 1200/overlap 100、bge-m3；增量合并更新（对比 GraphRAG 社区重建约省 6000 倍 token）；v1.5 起多模态入库（PDF/图片/表格）；存储后端可插拔（Neo4j/Milvus/Qdrant 等）。
- **对本项目**：① 主线框架候选：轻量+增量更新适配知识库持续扩充；② local/global/mix 对应"分镜细节"与"宣传片主题"两级生成；③ 多模态支持便于宣传册/图文资料直接入库。

### 35. HippoRAG（OSU/Stanford, NeurIPS 2024）
- **摘要**：海马体索引理论启发的图记忆检索，PPR 单步完成多跳推理。
- **核心要点**：离线：LLM 以 OpenIE 抽开放三元组建无 schema KG + 同义边 + node specificity（类 IDF）；在线：查询实体链接→**Personalized PageRank** 单步图传播→稀疏矩阵线性映射打分，与稠密检索不确定性加权融合；比 IRCoT 少 10-30 倍 LLM 调用、快 6-13 倍；MuSiQue 上超越 SOTA 最高 20%；HippoRAG 2（ICML 2025）加 passage 节点+query-to-triple+再认记忆。
- **对本项目**：① "城市→非遗→传承人→节庆"跨实体多跳查询（如"杭州哪些丝绸非遗相关节庆"）→ PPR 单步多跳性价比最优；② 无 schema 图适合文旅半结构化数据快速导入；③ 海马体索引思想 → 多智能体共享"长期文旅记忆层"。

### 36. RAPTOR（Stanford, ICLR 2024）
- **摘要**：递归聚类-摘要树，多粒度层级语义检索。
- **核心要点**：叶子 chunk 嵌入→**GMM 软聚类**（UMAP 降维+BIC 选簇，非"LLM 主题聚类"）→GPT-3.5 逐簇摘要→递归至根；查询用**折叠树**（全树平铺 top-k，优于逐层遍历）；QuALITY+GPT-4 达 82.6%（+20 绝对点）；构建成本近线性（80k tokens）；摘要压缩率约 72%。
- **对本项目**：① 景区/非遗长文档 → "城市一句话总览"与"景点细节分镜"不同层级各取所需；② 摘要树直接产出"城市总稿→景区详情→段落素材"层级化文案中间件；③ 与向量检索互补的第二路检索通道。

### 37. ⭐ RAG 综述（Gao et al., 复旦/同济, 2024, arXiv:2312.10997）
- **摘要**：RAG 系统性综述，提出 Naive/Advanced/Modular 三阶段分类法。
- **核心要点**：Advanced RAG = 检索前（查询改写/路由/扩展）+ 检索后（重排/压缩）优化；Modular RAG = search/memory/fusion/routing/predict 功能模块可编排（Advanced 是 Modular 特例）；增强过程四类：单次/迭代（IRCoT）/递归/自适应（FLARE/Self-RAG）；评估：三质量分（context relevance/answer fidelity/answer relevance）+ 四能力（噪声鲁棒/拒答/信息整合/反事实鲁棒）+ RAGAS/ARES 工具。
- **对本项目**：① RAG 设计定位 Modular/Agentic 层，采纳查询改写/路由/重排/压缩组件清单；② RAGAS 建立文旅文案事实性量化验收标准；③ "何时检索"指导多智能体检索触发策略。

### 38. ⭐ CRAG（USTC/UCLA/Google, 2024, ACL 2025 Findings）
- **摘要**：检索质量评估 + Correct/Incorrect/Ambiguous 三动作纠错。
- **核心要点**：轻量 T5-large 评估器（-1~1 打分，弱标注训练）分类检索质量；Correct→decompose-then-recompose 精炼；Incorrect→丢原结果、改写查询触发 Web 权威搜索；Ambiguous→两者互补；即插即用（与 Self-RAG 组合成 Self-CRAG）；PopQA +7.0%、Biography FactScore +14.9%。
- **对本项目**：① **防幻觉关键**：知识库查不到（新开放景点/临时节庆）→ 权威源补充或明确拒答，而非编造；② 分镜文案 Agent"检索质量门控"——低置信转人工/官方源复核；③ 与 Self-RAG 组成双重事实校验链路。

### 39. ⭐ RAG-Fusion 与 ColBERT（检索重排工程组件）
- **RAG-Fusion**（Rackauckas, Infineon, 2024）：LLM 生成多查询变体→各自向量检索→**RRF**（Σ1/(k+rank)）融合重排；召回与全面性显著提升、无参数易接入；代价是多查询成本+个别跑题。**借鉴**：文旅查询表述多样（"杭州秋天去哪儿玩" vs "杭州最佳秋景观赏地"），多查询+RRF 提升召回与分镜素材多样性。
- **ColBERT**（Khattab & Zaharia, SIGIR 2020）：token 级晚期交互（Late Interaction）——查询/文档独立编码为 token 向量集，**MaxSim** 逐 token 最大相似度聚合；重排比 BERT ranker 快两个数量级、精度显著高于双塔；ColBERTv2（残差压缩）/PLAID（CIKM 2022）支持端到端大规模索引。**借鉴**：作为重排器提升中文文旅资料检索精度。

---

## 五、阅读笔记总结

### 对本项目技术路线的一句话总结（对应 Phase 4 系统设计输入）

1. **编排层**：LangGraph 状态图承载 Planner→Script→Storyboard→Review 四 Agent 流水线（checkpoint 断点续跑 + interrupt 人工审核 + 失败重试边）；
2. **知识层**：LightRAG 轻量图谱 + 增量更新为主线，GraphRAG 社区摘要、HippoRAG PPR 多跳、RAPTOR 摘要树为增强，ColBERT 重排 + RAG-Fusion 多查询召回 + RAGAS 评估；
3. **分镜层**：分镜 Agent 输出受控枚举的 scene→shot 两级 JSON（FilmAgent 镜头库 + VideoDirectorGPT 模板），画面一致性用参考帧锚定（Story2Board LPA/RAVM）+ 实体一致性分组，评审用 Critique-Correct-Verify 回路 + LLM-Judge 六维评分；
4. **生成层**：图片 FLUX.1-schnell/Kolors；视频自部署 Wan2.2-TI2V-5B 或 HunyuanVideo 1.5，高质量通道 Wan 2.6/Seedance API（多镜头+音画同步）；配音 CosyVoice2；
5. **防幻觉**：Self-RAG 支撑性批评 + CRAG 检索质量门控 + 证据可溯源（文旅内容真实性是赛题核心要求）。


