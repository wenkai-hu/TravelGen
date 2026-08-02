# TravelGen 文献调研报告（Related Work）

**项目**：TravelGen——基于多智能体协同与知识增强的浙江文旅 AIGC 城市短视频自动生成平台
**阶段**：Phase 1 文献调研（Week1~Week2）
**负责人**：成员A（AI算法负责人）
**调研日期**：2026-08-02
**赛题**：中国移动杯·第二届浙江省大学生人工智能竞赛 JBGS-2026-01《面向浙江文旅传播的AIGC城市短视频自动生成系统》

---

## 一、项目背景与调研目标

TravelGen 采用"多智能体（Multi-Agent）+ 知识增强（RAG）+ 多模态生成（Multimodal AIGC）"的整体架构，根据用户输入（浙江城市、景区、节庆活动、非遗文化、校园宣传、视频风格、时长、面向人群），自动完成 文案生成 → 脚本生成 → 分镜设计 → AI图片 → AI视频 → AI配音 → 背景音乐推荐 → 视频自动合成 的完整流水线，遵循 **Planning → Generation → Composition → Review** 工作流程。

赛题评分标准（JBGS-2026-01）：
| 维度 | 权重 | 关键考察点 |
|---|---|---|
| 场景完整性与应用价值 | 25% | 贴合浙江文旅传播真实需求、场景清晰、推广价值 |
| AIGC生成效果 | 30% | 文案/图片/配音/音乐/视频质量、**画面美感、风格一致性**、传播感染力 |
| 技术方案与创新性 | 25% | **多模态生成、素材融合、智能体协同**、个性化生成、内容编排 |
| 系统体验与作品完整度 | 20% | 交互流程、生成效率、编辑预览、导出能力、演示效果、报告完整性 |

本阶段围绕四大方向完成文献调研：**① AIGC视频生成、② Storyboard分镜生成、③ Multi-Agent多智能体、④ RAG知识增强**。调研结论将直接支撑 Phase 3 Benchmark（统一Prompt比较文案/分镜/视频）、Phase 4 系统设计、Phase 5 核心模块（Planner/Script/Storyboard Agent + RAG）开发。

**调研范围说明**：任务清单共 27 项（视频10 + 分镜5 + 多智能体6 + RAG 6），结合 2025-2026 最新技术动态与项目需求**新增 10 项**（标注 ⭐新增），总计 37 项。所有关键事实（发布时间、厂商、开源/API状态、参数规格、stars等）均经多轮网络检索多源交叉核实。

---

## 二、方向一：AIGC 视频生成（Text-to-Video / Image-to-Video）

**关键词**：Text-to-Video、Video Generation、Image-to-Video、Diffusion Transformer（DiT）、World Model

### 2.0 方向小结

视频生成技术已从"扩散U-Net（SD的时序扩展）"全面演进到 **Diffusion Transformer（DiT）** 与 **自回归** 双路线，2025-2026 年关键趋势：

1. **DiT + flow-matching 成为主流**：Sora 确立时空 patch + DiT 范式后，Wan2.2（MoE DiT）、Seedance 1.0（解耦时空MM-DiT）、HunyuanVideo 1.5（SSTA稀疏注意力）均沿此路线；
2. **开源模型消费级化**：Wan2.2-TI2V-5B（24G显存）、HunyuanVideo 1.5（14G显存）、LTX-2（12-24G）等让自部署成为可能，Apache 2.0 许可保证商用无碍；
3. **多镜头与跨镜头一致性**：Seedance（原生多镜头10s）、Wan 2.6（自动分镜15s+R2V参考生视频）直接面向"一条生成≈一条成片"的短视频需求；
4. **音画同步**：LTX-2（视频+音频联合生成）、Wan 2.6（原生音画同步）、Seedance 1.5（音素级口型）正在消灭"视频+配音后期拼接"；
5. **中文能力**：Wan系列（视频内中文文字渲染）、HunyuanVideo 1.5（字形感知文本编码、Qwen2.5-VL文本编码）是中文文旅场景的关键优势。

### 2.1 Sora Technical Report（OpenAI）

- **团队/时间**：OpenAI，2024-02-15（《Video generation models as world simulators》）
- **模型类型**：Diffusion Transformer（DiT）
- **技术路线**：视频压缩网络（时空双向压缩）将像素映射到 latent，切成**时空 patch** 作为 transformer token 做扩散去噪；训练不裁剪缩放，支持可变分辨率/时长/宽高比；文本采用 GPT 扩写 + DALL·E 3 式重标注
- **输入输出**：Text-to-Video（框架可扩展）；演示**最长 60s、最高 1080p**、任意宽高比；参数量未公开
- **核心创新**：时空 patch + DiT 的可扩展统一框架；涌现 3D 一致性、物体恒存、基础物理交互
- **优点**：长时长与分辨率弹性；演示质量里程碑
- **缺点**：物理不精确（玻璃碎裂等）、长程连贯有限；闭源
- **是否开源**：否
- **是否提供API**：是——Sora 2（2025-09-30发布，原生音频+口型）API 于 2025-10-06 DevDay 预览：12s/720p $0.10/s，Sora 2 Pro 最高 1792×1024 $0.30/s；**国内不可直连**
- **对项目借鉴**：① "重标注 + prompt 扩写"提示工程可迁移到 RAG 文案→脚本环节，由 LLM 扩写为镜头级导演提示词；② 时空 patch 与可变时长思想支持按镜头粒度生成再拼接；③ 作为质量与物理一致性的评测参照系

### 2.2 Seedance 1.0 Technical Report（ByteDance）⭐

- **团队/时间**：字节跳动 Seed 团队，技术报告 arXiv:2506.09113（2025-06-10），与 1.0 Pro 商用发布同步（火山引擎 FORCE 大会）
- **模型类型**：DiT（flow-matching 扩散）
- **技术路线**：MMDiT 式**解耦时空层**（空间层做文本-视觉跨模态交互，时间层跨帧注意力+窗口划分获全局时间感受野）；3D 多模态 RoPE；时间因果 VAE 时空压缩 (4,16,16)、48 通道；文本编码为微调 decoder-only LLM（Qwen2.5-14B级）；480p 基础模型+级联 refiner 上采样至 720p/1080p
- **输入输出**：T2V/I2V（统一掩码框架）；**5s 单镜头、原生多镜头 10s（2-3 镜头无缝切换）、1080p**
- **核心创新**：多来源双语数据策展+精确字幕（Tarsier2）；解耦时空 MM-DiT+MM-RoPE；后训练（细粒度 SFT + 视频 RLHF 三奖励模型：基础 VLM/运动/美学）
- **优点**：中文指令理解强、多镜头叙事、发布时 Artificial Analysis T2V/I2V 双榜第一
- **缺点**：闭源仅 API；参数量/训练细节不公开；1.0 单镜头仅 5s
- **是否开源**：否
- **是否提供API**：是——火山引擎方舟 **Doubao-Seedance-1.0-pro**（5s/1080p 约 0.73 元/条，fast 版约 0.21 元/条）
- **对项目借鉴**：① 原生多镜头可直接承载"分镜→成片"，免去后处理拼接与跨镜一致性问题；② 三奖励模型 RLHF 提示平台可用投放数据（完播率/点赞）做风格反馈迭代；③ 中英双语字幕数据策展流程可复用到浙江文旅知识库与训练数据构建

### 2.3 Wan2.2 Technical Report（Alibaba）⭐

- **团队/时间**：阿里通义实验室 Wan-AI，2025-07-28 发布；技术报告 arXiv:2503.20314
- **模型类型**：扩散（flow-matching）**MoE DiT**
- **技术路线**：UMT5-XXL 文本编码（≤512 tokens）；3D 因果时空 VAE（4×16×16 压缩）；A14B 系列为两专家 MoE（**总参 27B、每步激活 14B**，按 SNR 切分高/低噪声专家）；TI2V-5B 为 dense；电影级美学控制数据（光照/构图/对比度/色调标注）
- **输入输出**：T2V/I2V；开源版 **480p/720p、5s、24fps**；商用 API（wan2.2-t2v-plus）支持 **1080p**
- **核心创新**：首个 MoE 视频扩散模型；数据量较 2.1 增 65.6%（图）/83.2%（视频）；后续衍生 Flash（快12倍）、S2V（语音驱动）、Animate（角色动画）
- **优点**：开源生态最好（ComfyUI/Diffusers/ModelScope 全集成）；A14B 质量接近商用模型；**中文视频内文字能力强**（国内首创）
- **缺点**：单镜头 5s 上限、无多镜头；A14B 需 ≥80GB 显存（TI2V-5B 24GB 可跑）；技术报告未覆盖 2.2 细节
- **是否开源**：是——**Apache 2.0**，GitHub Wan-Video/Wan2.2
- **是否提供API**：是——阿里云百炼/DashScope wan2.2-t2v-plus、wan2.2-i2v-plus（1080p/5s，异步任务）
- **对项目借鉴**：① 首选自部署骨干（Apache 2.0 商用无碍），用 LoRA 做"浙江山水/古镇/茶园"风格一致性微调；② 高/低噪声专家分工可启发平台"构图-细节"两段式质检；③ TI2V-5B 供低配 GPU 批量出片，与高价 API 形成成本分层

### 2.4 HunyuanVideo（Tencent）

- **团队/时间**：腾讯混元，2024-12-03，技术报告 arXiv:2412.03603
- **模型类型**：DiT（flow-matching）
- **技术路线**：双流→单流混合 transformer（20 双流块 + 40 单流块）；3D 因果 VAE（4×时间、8×空间压缩，16 通道）；文本编码为 **MLLM（LLaVA-llama-3-8B）+ 双向 token refiner + CLIP**
- **输入输出**：T2V/I2V；**720p、24fps、129 帧（约5s）**；多宽高比（16:9、9:16、4:3、3:4、1:1）
- **核心创新**：当时最大开源视频模型（**13B**）；MLLM 文本编码显著提升指令理解
- **优点**：质量当时开源第一梯队；原生竖屏宽高比
- **缺点**：5s 短；13B 部署门槛高；社区许可非 OSI 标准许可
- **是否开源**：是——GitHub Tencent-Hunyuan/HunyuanVideo；**Tencent Hunyuan Community License**（全球除 EU/UK/KR 商用免版税，MAU>1 亿或区域外需另行授权）
- **是否提供API**：是——腾讯云混元生视频（异步任务，720p，默认带水印）
- **对项目借鉴**：① 原生 9:16 适配抖音/视频号形态；② MLLM 编码验证"视觉-语言联合编码提升中文指令理解"；③ 其社区许可条款可作为平台开源选型法律评估范本

### 2.5 CogVideoX（Zhipu AI）

- **团队/时间**：智谱 AI，2024-08-06 开源 2B、2024-08-27 开源 5B
- **模型类型**：DiT（专家 Transformer）
- **技术路线**：**3D 因果 VAE**（压缩至约2%体积）+ 冻结 T5-XXL 文本编码 + DiT（3D RoPE 融合时间/空间）
- **输入输出**：T2V；**720×480、8fps、6s**（初版仅英文 prompt）；X1.5-5B（2024-11）升级 **1360×768、16fps、5s/10s**、新增 I2V
- **核心创新**：开源节奏快、2B/5B 参数弹性；3D VAE 高效压缩
- **优点**：轻量易部署；官方集成 diffusers；flash API 免费
- **缺点**：分辨率/时长上限低；画质逊于同期大模型；初版仅英文
- **是否开源**：是（2B 与 X1.5 为 **Apache 2.0**；5B 为自定义 CogVideoX License 需登记商用）
- **是否提供API**：是——智谱 bigmodel.cn：cogvideox-flash（免费）、cogvideox-2（闭源）、cogvideox-3（4K、30/60fps、AI音效）
- **对项目借鉴**：① 2B 模型可作流水线"低质快速预览稿"引擎（先看构图分镜再出正片，省 API 成本）；② 免费 flash API 适合脚本/分镜可行性批量测试

### 2.6 Open-Sora（HPC-AI Tech）

- **团队/时间**：上海 AI Lab Colossal-AI 团队，1.0 于 2024-03-18，2.0 于 2025-03-12
- **模型类型**：DiT（STDiT → MMDiT 双流/单流混合）
- **技术路线**：1.x 基于 PixArt-α 初始化的时空 DiT；1.2 起 3D VAE + rectified flow；2.0 用 **Video DC-AE（4×32×32 压缩）** + T5-XXL + CLIP-L
- **输入输出**：T2V/I2V/V2V；2.0 为 **768×768、约5s（128帧）**、多宽高比；2.0 含 T2I2V 管线
- **核心创新**：全开源复现 Sora 路线；2.0 端到端训练成本约 **20万美元**（4160 GPU天），VBench 与 Sora 差距缩至 0.69%
- **优点**：Apache 2.0 全栈开源（权重+训练+推理代码）；低成本训练方法论
- **缺点**：质量与商业模型仍有差距；2.0 后未见新大版本
- **是否开源**：是——Apache 2.0，GitHub hpcaitech/Open-Sora
- **是否提供API**：否（仅 HF Spaces 在线演示）
- **对项目借鉴**：① 低成本训练报告提示平台可用开放数据+文旅领域数据做小规模微调/蒸馏；② 全栈代码是自研视频骨干的最佳起点（可改造 conditioning 注入分镜/机位信息）；③ DC-AE 高压缩思路降低存储与带宽成本

### 2.7 VideoPoet（Google）

- **团队/时间**：Google Research，2023-12-19（ICML 2024）
- **模型类型**：**自回归**（decoder-only LLM 预测视频/音频 token）
- **技术路线**：MAGVIT V2（视频）+ SoundStream（音频）tokenizer；T5 文本编码；多任务预训练后按任务适配；以"最后1秒为条件"自回归续写
- **输入输出**：T2V / I2V / 视频风格化 / 编辑修复 / **视频转音频**；单次最长 **10s**，可无限续写
- **核心创新**：视频+音频统一 token 的自回归范式（非扩散）；长视频自回归延展
- **优点**：生成+编辑+音频一网打尽；10s 长片段
- **缺点**：未开源未商用；当时画质与扩散路线有差距
- **是否开源**：否　**是否提供API**：否
- **对项目借鉴**：① "续帧"思想可映射到平台"片段间过渡"（以前镜结尾为条件生成转场）；② 视频+音频联合生成范式已被 Seedance/LTX 等落地，平台配音环节可探索"生成即带声"

### 2.8 VideoCrafter2（腾讯AI Lab）

- **团队/时间**：腾讯 AI Lab，2024-01，CVPR 2024
- **模型类型**：扩散 U-Net（基于 SD 2.1 的时间 inflate）
- **技术路线**：**运动-外观数据解耦**：低质视频（WebVid-10M）学运动，高质量图像（SDXL/Midjourney 合成）学画质；全量预训练后用高质量图像仅微调空间模块
- **输入输出**：T2V（320×512、16fps、秒级短片段）；I2V（DynamiCrafter，640×1024）
- **核心创新**：解决高质量视频数据稀缺问题的数据级训练配方
- **优点**：训练配方简单有效；全开源
- **缺点**：分辨率/时长低；仅英文；已被新架构超越
- **是否开源**：是——Apache 2.0，GitHub VideoCrafter/VideoCrafter
- **是否提供API**：否
- **对项目借鉴**：① 数据解耦配方可直接复用于"文旅风格微调"：运动学实拍视频、画质学专业摄影图集；② DynamiCrafter 可作"分镜首帧→视频"的降级备选

### 2.9 AnimateDiff

- **团队/时间**：guoyww 等（HKU/上海AI Lab），arXiv 2023-07-10，ICLR 2024 Spotlight
- **模型类型**：扩散插件（plug-and-play motion module）
- **技术路线**：在冻结的个性化 T2I U-Net（SD1.5）时间轴上插入**运动模块**（时序自注意力+正弦位置编码）；v3 含 Domain Adapter LoRA 与 SparseCtrl；**MotionLoRA 提供 8 种镜头运动**
- **输入输出**：I2V/T2V（依赖基础模型分辨率，典型 512×512、2s 级）
- **核心创新**：一次训练即插即用、不破坏 T2I 能力；生态庞大（A1111/ComfyUI/diffusers）
- **优点**：低成本动画化既有图片；镜头运动可控
- **缺点**：时长短、动作幅度小；质量上限低
- **是否开源**：是——Apache 2.0，GitHub guoyww/AnimateDiff；配套 AnimateDiff-Lightning（字节2024-03，4步推理）
- **是否提供API**：否
- **对项目借鉴**：① MotionLoRA 镜头运动库可为"西湖游船/古镇巷道"设计固定运镜模板，保证镜头语言统一；② 配合风格化图片做"图片→微动效"低成本物料（海报级短视频）

### 2.10 Emu Video（Meta）

- **团队/时间**：Meta（FAIR），arXiv:2311.10709（2023-11），ECCV 2024
- **模型类型**：扩散（**factorized diffusion**，U-Net latent）
- **技术路线**：先 T2I 生成首帧（去掉时间层），再以文本+首帧为条件做 I2V；Emu T2I 初始化，冻结 2.7B 空间参数、训练 1.7B 时间参数
- **输入输出**：T2V/I2V；**512×512、4s、16fps**
- **核心创新**：分解式两阶段（文本→首帧→视频）解耦空间与时间学习
- **优点**：训练稳定、显存友好；首帧可控性强（首帧即关键帧）
- **缺点**：分辨率低；未开源
- **是否开源**：否　**是否提供API**：否
- **对项目借鉴**：① 两阶段架构与平台"AI图片→AI视频"环节天然对应——先由多智能体定关键帧（构图/机位），再动画化；② 首帧条件化保证镜头画面一致性（主体/光影/机位继承）

### 2.11 ⭐新增 HunyuanVideo 1.5（腾讯，2025-11，开源）

- **团队/时间**：腾讯混元，**2025-11-20 开源**推理代码与权重（12-05 追加训练代码与 480p I2V 蒸馏版）
- **模型类型**：DiT（flow-matching + **SSTA 稀疏滑窗注意力**）
- **技术路线**：54 层 DiT；3D 因果 VAE（32 通道）；文本编码 **Qwen2.5-VL（7B）+ T5 双编码**；**字形感知文本编码（glyph-aware）支持视频内中文文字渲染**
- **输入输出**：T2V/I2V；480p/720p 原生 + 超分至 1080p；**5-10s**；中英双语；相机运动控制；**14GB 显存可跑**
- **核心创新**：8.3B 轻量旗舰；视频内中英文字渲染；SSTA 提速约 1.87×；RTX 4090 上蒸馏版省时 75%
- **优点**：Apache 2.0 全开源、消费级显卡可部署、中文能力开源最佳
- **缺点**：物理/长镜头一致性有限；1080p 需外挂超分
- **是否开源**：是——**Apache 2.0**（HF tencent/HunyuanVideo-1.5）　**是否提供API**：是——腾讯云/TokenHub（hy-video-1.5）
- **对项目借鉴**：① 平台自部署骨干首选：中文指令 + 视频内中文字幕（景点名/诗句字幕直出，免合成字幕）；② 14GB 门槛适合团队 GPU 批量出片与风格 LoRA 微调；③ Qwen2.5-VL 文本编码可与平台中文 RAG 检索链路共用视觉语言模型

### 2.12 ⭐新增 LTX-2（Lightricks，2025-10 首发 / 2026-01 开源）

- **团队/时间**：Lightricks，2025-10-23 首发，**2026-01-06 开源权重**；LTX-2.3（2026-03-05，22B、原生 9:16）
- **模型类型**：扩散双流 DiT（非对称：视频 14B + 音频 5B ≈ 19B）
- **技术路线**：视频/音频两个 latent 流经双向交叉注意力耦合，单次前向同步生成声画（48kHz 音频、音素级口型）；含 8 步蒸馏版、LoRA 微调、FP8/FP4 量化
- **输入输出**：T2V/I2V；**原生 4K（3840×2160）、最高 50fps、约 10-20s**；音画同步（口型/音效/配乐）；12-24GB 显存可跑
- **核心创新**：首个开源"视频+音频联合生成"4K 模型
- **优点**：开源度最高之一（权重+训练代码+蒸馏+上采样器）；竖屏适配；音画一次成
- **缺点**：自定义许可（**年营收 ≥1000 万美元商用需付费授权**，派生权重须同许可分发）；中文文字渲染弱
- **是否开源**：是（LTX-2 Open Weights License）　**是否提供API**：是（Lightricks 平台及第三方托管）
- **对项目借鉴**：① 音画同步开源基线——配音环节可用其原生音频降本（省 TTS+配乐拼接，但需注意中文口型质量）；② 9:16 竖屏 4K 直出适配抖音/视频号发布规格；③ 蒸馏+量化版本适合平台低成本渲染节点

### 2.13 ⭐新增 Wan 2.6（阿里，2025-12，API）

- **团队/时间**：阿里通义 Wan-AI，**2025-12-16** 发布（闭源 API）
- **模型类型**：统一多模态扩散模型（文本/图像/视频/音频联合训练，flow-matching 主干）
- **技术路线**：**自动分镜（多镜头叙事）+ 跨镜头主体一致性**；原生音画同步；**R2V 参考生视频**（角色+声音复刻，最多 5 个参考）
- **输入输出**：T2V/I2V/R2V；**最长 15s（5/10/15s 可选）、720p/1080p、24fps**；新增 4:3、3:4 宽高比
- **核心创新**：自动分镜与跨镜头主体一致；原生音画同步；国内首个 R2V
- **优点**：中文指令适配度最高档；15s 覆盖短视频单条时长；阿里云生态接入简单
- **缺点**：闭源仅 API；按秒计费需测算成本；本地不可定制
- **是否开源**：否　**是否提供API**：是——阿里云百炼/DashScope（及 OpenRouter 等第三方）
- **对项目借鉴**：① 自动分镜能力直接承接平台"脚本→分镜"环节输出，多智能体只需产出镜头级 prompt；② R2V 支持"当地讲解员/主持人"数字人复刻，服务文旅 IP 运营；③ 15s+多镜头让"一条生成≈一条成片"，降低合成环节复杂度

### 2.14 前沿速览（2025-2026，调研中同步核实）

- **Seedance 系列（闭源/火山引擎 API）**：1.5（2025-12-16）首个音视频联合生成模型，4-12s、音素级口型、支持四川话/粤语；2.0（2026-02）多模态输入（9图+3视频+3音频）、4-15s、2K；2.5（2026-07-31 上线）单次 30s、原生 4K 10bit、最多 50 参考输入、长视频 beta 约 3 分钟
- **Veo 3.1（Google，2025-10-15）**：1080p 原生（2026-01 支持原生 4K）、最多 3 张参考图做风格/角色控制、场景扩展拼 1 分钟+；Gemini API 标准 $0.40/s、Fast $0.15/s、Lite（2026-03）$0.05-0.08/s；**国内不可直连**
- **Kling 3.0（快手，2026-02-05）**：原生 4K、单次最多 6 分镜且跨镜头主体一致、原生音画同步、相机控制；klingai API 提供主体参考（类 IP adapter）
- **Mochi 1（Genmo，2024-10/11）**：10B AsymmDiT、**Apache 2.0**、480p/24fps/5.4s，开源高质量基线（"Mochi 2"不存在）
- **学术前沿**：MultiShotMaster（2025-12，参考图注入实现跨镜头一致性）、ShotDirector 等镜头控制工作可作为平台"分镜一致性"研究起点
- **事实修正**：不存在"HunyuanVideo 2.0/2.1"（2025 年迭代实为 1.5）；"混元 3.0"是 2026-03 通用多模态大模型（4K、百万长上下文），非开源视频模型；Sora 2 于 2025-09-30 发布；Emu Video 1.5、VideoPoet API 等均无官方依据

### 2.15 横向对比表

| 模型 | 厂商 | 类型 | 最大分辨率 | 最大时长 | 是否开源 | 是否API | 适配度(1-5)及理由 |
|---|---|---|---|---|---|---|---|
| Sora TR | OpenAI | DiT | 1080p（TR演示） | 60s | 否 | 是(Sora 2 API) | 2：质量标杆，但国内不可直连、$0.10-0.30/s 成本高，仅作评测参照 |
| Seedance 1.0 | ByteDance | DiT | 1080p | 10s（多镜头） | 否 | 是(火山方舟) | 5：中文指令+原生多镜头+国内 API 直连，0.21-0.73 元/条性价比高 |
| Wan2.2 | Alibaba | 扩散MoE DiT | 开源720p / API 1080p | 5s | 是(Apache 2.0) | 是(百炼) | 5：自部署骨干+中文文字能力，LoRA 风格微调可行 |
| HunyuanVideo | Tencent | DiT | 720p | ~5s | 是(社区许可) | 是(腾讯云) | 4：开源 13B、商用免版税，质量强但显存门槛高 |
| CogVideoX | Zhipu AI | DiT | 768p(1.5) | 10s(1.5) | 是(Apache 2.0) | 是(bigmodel) | 3：轻量预览稿引擎，flash 免费 API 可批量试稿 |
| Open-Sora | HPC-AI Tech | DiT | 768×768 | ~5s | 是(Apache 2.0) | 否 | 3：自研改造起点、训练方法论价值高，质量一般 |
| VideoPoet | Google | 自回归LLM | 中分辨率 | 10s | 否 | 否 | 2：范式借鉴（音频联合/续帧），不可实际使用 |
| VideoCrafter2 | 腾讯AI Lab | 扩散U-Net | 512×320 | ~1-2s | 是(Apache 2.0) | 否 | 2：训练配方可借鉴，直接产线已过时 |
| AnimateDiff | guoyww/HKU | 运动模块插件 | 512×512 | ~2s | 是(Apache 2.0) | 否 | 3：海报动效/运镜模板等辅助物料，成本极低 |
| Emu Video | Meta | 分解式扩散 | 512×512 | 4s | 否 | 否 | 2：首帧→视频范式与流水线对应，但不可用 |
| ⭐HunyuanVideo 1.5 | Tencent | DiT | 720p→1080p | 5-10s | 是(Apache 2.0) | 是 | 5：开源+中文文字渲染+14GB 可跑，自部署首选 |
| ⭐LTX-2 | Lightricks | 双流扩散DiT | 4K / 50fps | ~10-20s | 是(自定义开源) | 是 | 4：开源音画同步+竖屏 4K 直出，注意 1000 万美元营收许可线 |
| ⭐Wan 2.6 | Alibaba | 统一多模态扩散 | 1080p | 15s | 否 | 是(百炼) | 5：自动分镜+多镜头+R2V，直连流水线分镜环节，中文生态最优 |

**视频生成层初步选型**：自部署骨干选 **Wan2.2 / HunyuanVideo 1.5**（Apache 2.0，中文文字渲染，LoRA 风格微调），商用高质量通道选 **Wan 2.6 / Seedance 系列**（国内 API 直连、多镜头+音画同步、中文强），竖屏音画直出考察 **LTX-2**（开源但中文渲染与许可受限），Veo 3.1 仅作海外质量参照。最终经 Phase 3 Benchmark 确定。

---

## 三、方向二：Storyboard（分镜生成）

**关键词**：Storyboard Generation、Visual Storytelling、Narrative Planning、Scene Planning、Shot Planning

### 3.0 方向小结

"LLM 导演规划 + 生成器执行"的解耦架构已是业界共识：LLM（或LLM Agent）只负责把故事拆解为 Scene/Shot 级别的结构化分镜，文生图/文生视频模型作为可替换的渲染后端。关键能力点：Story→Scene→Shot 三级划分、结构化 JSON 分镜输出（含景别/运镜/构图/时长/转场）、固定参考（地标/角色）+场景变化的两段式 prompt 模板、以及画面一致性控制（参考帧锚定 / 一致性自注意力 / 实体一致性分组 / 角色档案复用）。分镜质量评估应使用多维人工/LLM评分（聚焦度、结构连贯、视觉接地、细节度），而非 n-gram 相似度指标。

### 3.1 StoryGen（Intelligent Grimm）— 视觉故事图像序列生成

- **论文名称**：Intelligent Grimm – Open-ended Visual Storytelling via Latent Diffusion Models（项目名 StoryGen）
- **作者/机构**：Chang Liu、Haoning Wu、Yujie Zhong 等（上海交通大学、美团、上海人工智能实验室）｜**年份**：2024｜**会议**：CVPR 2024（arXiv:2306.00973）
- **核心方法**：基于 SD v1.5 的自回归图像序列生成模型，创新点是"视觉语言上下文模块"：将前序帧在各自 caption 引导下的扩散去噪特征作为视觉上下文，通过并行于文本交叉注意力的图像交叉注意力层融合（ControlNet 风格求和），文本/视觉双路 classifier-free guidance；对时序距离更远的前帧加更多噪声作为天然位置编码；两阶段训练（单帧风格微调 + 冻结主网络训练上下文模块）
- **LLM 生成 Storyboard 流程**：不涉及 LLM 规划。输入为逐帧文本 storyline，逐帧"当前文本 + 前序图对"自回归生成图像序列
- **Story→Scene→Shot**：无 Scene/Shot 元数据划分，以"图像序列=镜头画面序列"替代分镜规划
- **Prompt 设计**：纯文本逐帧提示词，图像条件来自前帧，无结构化模板
- **镜头规划**：无（不控制景别、运镜、构图、时长、转场）
- **Scene 划分**：数据层面由 StorySalon 数据集按故事情节划分图像-文本序列
- **是否使用多模态信息**：是。文生图（SD）+ 前帧图像视觉条件联合条件化，图文协同生成的经典范式
- **优缺点**：优点——开放域故事、新角色零微调泛化、字符一致性优于 StoryDALL·E 等基线；缺点——无任何镜头/电影化参数控制、上下文模块训练成本高、长序列误差累积
- **对项目借鉴**：① 前帧图像特征作视觉条件、参考帧加噪式时序编码 → TravelGen 分镜画面一致性控制可复用"参考帧锚定"思路；② StorySalon 数据流水线（关键帧抽取、去重、清洗、caption 生成）→ 文旅素材自动清洗建库；③ 双路 CFG 分离文本/视觉一致性权重 → 分镜生成中"忠实文案"与"画面连贯"的平衡旋钮

### 3.2 Visual Storytelling（选定论文：Modi & Parde 2019 综述）

- **选定论文**：*The Steep Road to Happily Ever After: An Analysis of Current Visual Storytelling Models*
- **作者/机构**：Yatri Modi、Natalie Parde（伊利诺伊大学芝加哥分校）｜**年份**：2019｜**发表**：NAACL 2019 SiVL 研讨会（ACL Anthology W19-1805）
- **选定理由**：视觉故事生成方向系统性综述，最早澄清任务定义（多图序列的连贯叙事生成 vs 单图描述）；评测体系建立在 VIST 基准之上
- **核心方法**：梳理 2018 视觉故事挑战赛前后模型（AREL 对抗奖励学习、GLACNet 全局-局部注意力级联、Contextualize-Show-Tell），对公开模型做深度错误分析，归纳常见错误类型（视觉接地失败、重复、不连贯），指出 METEOR 等 n-gram 指标与人工判断相关性差
- **LLM 生成 Storyboard**：不涉及（CNN-RNN 时代）；本方向"以文本生成器做叙事规划"的雏形是 question-answer 蓝图（plan-and-write）
- **多模态信息**：视觉输入（图序列）→ 文本输出，与文生图无关
- **优缺点**：优点——首次系统定义任务、给出人工评测六维度（聚焦、结构连贯、可分享性、类人性、视觉接地、细节度）与错误分析清单；缺点——方法均为预 LLM 时代，对 AIGC 流水线的直接参考有限
- **对项目借鉴**：① 评测维度（聚焦度、结构连贯、视觉接地、细节度）→ TravelGen 分镜质量 LLM-Judge 评估量表；② "n-gram 指标失真"结论 → 分镜评测应做多维人工/LLM 评分而非相似度指标；③ 视觉接地缺陷 → 分镜生成需与城市实景、景点知识锚定（RAG 注入地标描述）

### 3.3 Narrative Planning with LLM（选定论文：EMNLP 2025 综述）

- **选定论文**：*A Survey on LLMs for Story Generation*
- **作者/机构**：Maria Teleki 等（德州农工大学等）｜**年份**：2025｜**发表**：Findings of EMNLP 2025（ACL Anthology 2025.findings-emnlp.750）
- **选定理由**：2025 年最新、对叙事规划类 LLM 方法分类最完整（补充：IEEE 论文 *Can LLMs Generate Good Stories? Insights and Challenges from a Narrative Planning Perspective*）
- **核心方法**：两大范式（LLM 独立生成 / LLM 辅助作者），规划相关方法四类：约束生成（OSOS、MLD-EA 逻辑情感修补）；提示生成（MoPS 将前提拆为主题→背景→人物→情节的模块化提示链）；大纲生成（DOME：动态层级大纲 + 时间知识图谱 + 叙事理论注入，plan-then-write）；多智能体协作（CollabStory 多 LLM 接龙、SWAG 用"动作判别器"选择高层叙事动作、CritiCS 批评家 LLM 流水线）
- **Story→Scene→Shot**：综述层面归纳"层级大纲 = 叙事规划的核心机制"，与 Story→Scene→Shot 分层天然同构
- **对项目借鉴**：① 先规划后生成（DOME 层级大纲 + 记忆）→ TravelGen 文案→脚本→分镜的分层流水线，各层输出为下一层输入约束；② SWAG 高层叙事动作（悬念、反转、节奏点）→ 文旅短视频的节奏与情绪曲线控制；③ CritiCS 批评家 Agent → 分镜生成后的评审-修正 Agent（LLM-Judge 回路）

### 3.4 DirectorLLM

- **论文名称**：Llama Learns to Direct: DirectorLLM for Human-Centric Video Generation
- **作者/机构**：Kunpeng Song 等（罗格斯大学、Meta GenAI）｜**年份**：2024（arXiv:2412.14484）｜**会议**：BMVC 2025
- **核心方法**：将"导演"与"渲染"解耦的三阶段流水线：① DirectorLLM（微调 Llama 3）解读文本提示，以 1FPS 预测人物姿态 token（OpenPose 18 关键点 + 残差 VQ-VAE 离散化，标准 next-token 预测）；② 线性扩散插值器将稀疏姿态稠密化至 30FPS 平滑轨迹；③ 基于 VideoCrafter2 的姿态 ControlNet 渲染最终视频。导演模块与渲染器无关（UNet/DiT 皆可接入）
- **LLM 生成 Storyboard 流程**：LLM 产出"动作/姿态指令序列"而非图像分镜，本质是运动分镜
- **Prompt 设计**：结构化提示词——SSTK 数据上由视频 caption 模型生成分层的结构化 prompt，仅取 Subject-Level Prompt 用于姿态预测
- **镜头规划**：不涉及景别/构图/运镜（"导演"指动作编排而非镜头设计）
- **多模态信息**：是。LLM（文本）+ 姿态模态（关键点）+ 文生视频（VideoCrafter2）+ ControlNet 空间条件
- **优缺点**：优点——解决文生视频中人体姿态解剖错误、导演模块可插拔复用、姿态 token 化让 LLM 以原生语言建模方式学运动；缺点——仅覆盖人物动作、需逐人物处理、姿态离散化有信息损失
- **对项目借鉴**：① "LLM 导演（结构化指令）+ 渲染器解耦" → TravelGen 分镜 Agent 只产出结构化分镜 JSON，T2I/T2V 后端可随时替换；② 姿态/动作 token 化方案 → 文旅中"人物走位、指向、讲解手势"等动作分镜可控化；③ SSTK 结构化 subject-prompt → 分镜 prompt 模板按主体级/场景级分层组织

### 3.5 Script-to-Storyboard（选定论文：Story2Board，2025）

- **选定论文**：*Story2Board: A Training-Free Approach for Expressive Storyboard Generation*
- **作者/机构**：David Dinkevich 等（耶路撒冷希伯来大学、OriginAI）｜**年份**：2025｜**发表**：arXiv:2508.09983（另见 Computer Graphics Forum）
- **选定理由**：2024-2026 唯一以"Storyboard Generation"直接命名的免训练框架，与 TravelGen 场景（故事文本→分镜面板）最贴合。备选：*Dialogue Director*（arXiv:2412.20725，三智能体将对话剧本转为多视角分镜）
- **核心方法**：训练免费（直接使用 SD3/Flux 等 DiT 模型）的一致性框架：LLM Director 将自由故事分解为"共享参考面板 prompt + 各场景级面板 prompt"；两面板一批协同去噪（co-denosing）。一致性双机制：**Latent Panel Anchoring（LPA）**在去噪中锚定参考 latent 保持角色外观；**Reciprocal Attention Value Mixing（RAVM）**按互注意力强度混合 token 间的 value 向量
- **LLM 生成 Storyboard 流程**：LLM 做结构化分解（参考面板 + 场景面板 prompt），扩散模型画面板，无训练、无微调
- **Story→Scene→Shot**：LLM 完成 Story→Scene（场景级面板）分解；面板即镜头画面，无显式景别/运镜元数据
- **Prompt 设计**：两段式模板——"共享参考描述（角色/地标固定外观）+ 每场景变化描述（地点、动作、构图）"，对一致性是决定性设计
- **镜头规划**：不涉及
- **评估**：Rich Storyboard Benchmark（100 个开放域故事 × 每故事 7 个场景 prompt）+ Scene Diversity 场景多样性指标
- **优缺点**：优点——零训练即得角色一致的故事板、LPA/RAVM 与模型无关、保留构图自由度；缺点——无镜头语言、长序列依赖滑窗扩展、面板数量受显存限制
- **对项目借鉴**：① LPA/RAVM 免训练一致性机制 → TravelGen 直接接入即可保证"西湖+雷峰塔"等固定景点外观跨镜头一致；② "共享参考 prompt + 场景 prompt"两段式模板 → 文旅分镜 prompt 模板的骨架（固定地标描述 + 场景/时间/活动变化）；③ Scene Diversity 指标 → 分镜多样性自动评估，防止画面雷同

### 3.6 ⭐新增 FilmAgent — 多智能体电影自动化（SIGGRAPH Asia 2024）

- **论文名称**：FilmAgent: A Multi-Agent Framework for End-to-End Film Automation in Virtual 3D Spaces
- **作者/机构**：Zhenran Xu 等（哈尔滨工业大学（深圳）等）｜**年份**：2024｜**发表**：SIGGRAPH Asia 2024 Technical Communication（arXiv:2501.12909）
- **核心方法**：以 LLM Agent 模拟剧组角色——导演、编剧、演员、摄影师，三阶段流水线：① 规划：导演建角色档案、把故事点子扩展为分场大纲（每场：where/what/who）；② 编剧：导演+编剧+演员协作生成对话、走位、动作；③ 摄影：摄影师+导演为每句对白设计机位。两种多智能体协作算法：**Critique-Correct-Verify**（生成→批评→修正→验证）与 **Debate-Judge**（双 Agent 多轮辩论 + 裁判裁决），显著降低幻觉
- **Story→Scene→Shot**：三级齐全。Scene=分场大纲（地点/事件/人物），Shot=每句对白一个镜头（含机位选择）
- **镜头规划**：完整。Unity 3D 环境 15 个地点、65 个演员位置、**272 个预置镜头**（165 静态 + 107 动态，覆盖特写/中景/远景/摇/推/跟拍等 9 种景别运镜）、21 个动作（Mixamo）、ChatTTS 对白配音
- **Prompt 设计**：角色扮演式系统提示（各 Agent 分工职责 + 结构化大纲 JSON 传递）；协作轮次以批评文本迭代
- **多模态信息**：视频渲染在 Unity 3D 而非文生视频，但"结构化计划 + 执行器"模式与文生视频通用
- **优缺点**：优点——工业级剧组分工建模、镜头参数可枚举可控、协作算法可复现；缺点——需人工搭建 3D 场景、缺乏文生图/文生视频直接接入
- **对项目借鉴**：① 导演/编剧/摄影 Agent 角色分工 → TravelGen 分镜 Agent 组的职责切分模板（脚本 Agent → 分镜导演 Agent → 镜头参数 Agent）；② Critique-Correct-Verify 与 Debate-Judge → 分镜 JSON 的自动评审修正回路；③ 预置镜头库（9 类景别+运镜枚举）→ 分镜 JSON 中镜头参数的受控枚举规范，避免自由文本越界

### 3.7 ⭐新增 VideoDirectorGPT — LLM 引导的多场景视频规划（COLM 2024）

- **论文名称**：VideoDirectorGPT: Consistent Multi-scene Video Generation via LLM-Guided Planning
- **作者/机构**：Han Lin、Abhay Zala、Jaemin Cho、Mohit Bansal（北卡罗来纳大学教堂山分校）｜**年份**：2024｜**发表**：COLM 2024（arXiv:2309.15091）
- **核心方法**：两阶段"规划+落地"：① Video Planner LLM（GPT-4）将单一文本 prompt 扩展为结构化视频计划——场景描述、实体及其空间布局（bbox）、各场景背景、实体一致性分组；关键实体附语义描述词以跨场景保持身份；② Grounded Video Generator（Layout2Vid）按计划中的布局与一致性分组生成多场景视频
- **LLM 生成 Storyboard 流程**：LLM 直接产出 JSON 视频计划（即文本分镜），生成器按计划逐场景执行
- **Story→Scene→Shot**：Story→Scene 由 LLM 完成（场景级划分），Shot 级由生成器内部完成，Scene 划分是最核心的 LLM 职责
- **Prompt 设计**：结构化 JSON 模板输出（scenes 数组、每场景 entities 布局、consistency 分组、background），是最接近"分镜 JSON"的设计
- **镜头规划**：无景别/运镜参数，通过实体布局（bbox）实现构图控制
- **多模态信息**：是。LLM 计划 + 文生视频 + 布局条件（空间控制）联动；支持用户提供图像做视频延续
- **优缺点**：优点——把多场景长视频分解为可规划的单元、实体一致性分组机制简洁有效、训练成本低；缺点——布局粒度粗、复杂剧情表现弱、依赖 GPT-4 与 ModelScopeT2V
- **对项目借鉴**：① JSON 视频计划模板（scenes/entities/layout/background/consistency）→ TravelGen 分镜 JSON Schema 的骨架（可加 shot 级字段扩展）；② 实体一致性分组（跨场景 ID 保持）→ 文旅人物/地标实体的全局 ID 管理；③ "LLM 计划先行、生成器解耦"→ 分镜 Agent 与 T2I/T2V 完全解耦，模型可迭代替换

### 3.8 ⭐新增 StoryDiffusion — 免训练长序列画面一致性（NeurIPS 2024）

- **论文名称**：StoryDiffusion: Consistent Self-Attention for Long-Range Image and Video Generation
- **作者/机构**：Yupeng Zhou 等（南开大学、字节跳动）｜**年份**：2024｜**会议**：NeurIPS 2024 Spotlight（arXiv:2405.01434）
- **核心方法**：① **Consistent Self-Attention**——生成一批图像时在批量内跨图像计算自注意力（共享 Q/K/V 权重，滑动窗口消解显存对文本长度的依赖）；零样本、免训练、热插拔进 SD1.5/SDXL；② **Semantic Motion Predictor**——在语义空间估计两图间运动条件，把一致图像序列平滑转为视频，比 SEINE/SparseCtrl 更稳，可扩展到分钟级
- **LLM 生成 Storyboard 流程**：不依赖 LLM；输入 ≥3 条故事分段文本 prompt，直接批量生成一致故事图
- **Story→Scene→Shot**：文本 prompt 列表 = 场景序列；无场景/镜头元数据，但其"批量内一致性"天然适合分镜面板批量生成
- **镜头规划**：不涉及
- **多模态信息**：是。文生图（一致性图像序列）→ 图生视频（语义运动预测器）两段式，正是"分镜图→短视频"的标准桥接路径
- **优缺点**：优点——免训练即用、身份与服装一致性出色、视频生成稳定可长；缺点——无镜头语言控制、一致性依赖 prompt 内共享描述、批量生成受显存约束
- **对项目借鉴**：① 免训练一致性自注意力 → TravelGen 无需改模型即可获得跨镜头一致的文旅画面（固定建筑、服饰角色）；② 语义空间运动预测器 → 分镜关键帧到 AI 视频的 image-to-video 桥接模块选型；③ 滑窗批量策略 → 长分镜序列（20+ 面板）的分批生成与显存管理方案

### 3.9 对本项目分镜生成模块设计的启示（总结）

综合 8 篇文献，"LLM 导演规划 + 生成器执行"的解耦架构已是业界共识，TravelGen 分镜 Agent 应**严格只产出结构化分镜 JSON**（scene → shot 两级，shot 含景别/运镜/构图/时长/转场枚举），T2I/T2V 全部作为可替换后端。Story→Scene→Shot 三级划分可复用 VideoDirectorGPT 的 JSON 模板（scenes/entities/consistency）并扩展 FilmAgent 式镜头参数枚举（9 类景别运镜），保证参数受控。画面一致性有四条成熟路径：参考帧锚定（Story2Board LPA/RAVM）、免训练一致性自注意力（StoryDiffusion）、实体一致性分组（VideoDirectorGPT）、角色档案复用（AesopAgent），前两者可直接插件化接入。提示词采用"固定参考（地标/角色）+ 场景变化"两段式模板，并内置叙事规划与评审回路（DOME 层级大纲、Critique-Correct-Verify、LLM-Judge 六维评分），形成规划—生成—评审的完整闭环，文旅地标身份信息经 RAG 注入保证视觉接地。

---

## 四、方向三：Multi-Agent（多智能体）

**关键词**：LLM Agent、CrewAI、LangGraph、AutoGen、OpenManus

### 4.0 方向小结

多智能体框架已从"自由对话协同"（AutoGen 对话编程、CAMEL 角色扮演）演进到"确定性工作流编排"（LangGraph 状态图、CrewAI Flows、Google ADK 2.0）。对本项目关键结论：TravelGen 的 Planner→Script→Storyboard→Review 四阶段流水线具有明确阶段产物、人工审核节点与失败重试需求，本质是**确定性工作流而非自由对话**，应选用 Graph 式编排框架。论文侧的 MetaGPT"SOP+结构化文档契约"、CAMEL"任务规格化"思想直接可移植。

### 4.1 AutoGen（论文）

- **名称**：AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation
- **类型**：论文+开源框架 ｜ **作者**：Qingyun Wu、Chi Wang 等，微软研究院 ｜ **年份**：2023（arXiv:2308.08155）
- **Agent架构**：统一抽象"Conversable Agent"（LLM/人/工具能力自由组合）；内置 AssistantAgent（LLM）与 UserProxyAgent（人类代理+代码执行代理）
- **协同方式**：多Agent多轮对话（"对话编程"）；GroupChatManager 动态选择下一发言者
- **通信机制**：消息传递（send/receive + 自动回复机制），组聊为广播式
- **Workflow设计**：对话驱动（Conversation-Driven），控制流由提示词终止词与 Python 代码融合控制
- **Memory**：会话历史即短期上下文；无内置长期记忆
- **Tool Calling**：工具与代码执行经 UserProxyAgent 封装（execute code/function call）
- **优缺点**：抽象简洁、上手快；但自由对话易发散/死循环，精确控制与可观测性弱。框架已进入维护模式（见 4.7）
- **对项目借鉴**：① UserProxyAgent"人工参与+代码执行"模式可作为 Review 人工审核节点与视频渲染执行器；② 对话式协同仅适合头脑风暴，TravelGen 确定性流水线应显式编排

### 4.2 MetaGPT（论文，ICLR 2024）

- **名称**：MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework
- **类型**：论文（ICLR 2024 Oral，top 1.2%）+开源框架 ｜ **作者**：Sirui Hong 等，DeepWisdom ｜ **年份**：2024
- **Agent架构**：流水线角色制：产品经理（PRD）→架构师（设计文档）→项目经理（任务分解）→工程师（代码）→QA（测试）；核心哲学 **Code = SOP(Team)**
- **协同方式**：协作式装配线（assembly line），将人类 SOP 编码进提示序列，阶段产物需验证后才能进入下一阶段
- **通信机制**：**共享黑板**——全局消息池发布/订阅，角色只订阅相关消息避免信息过载；以结构化文档为中间产物
- **Workflow设计**：Sequential 阶段化+可执行反馈（测试失败回溯源至 PRD 重试，最多 3 次）
- **Memory**：全局消息池（短期）+ 产出文档（长期工件）
- **Tool Calling**：以代码执行结果（测试运行）作为反馈注入，非独立工具系统
- **优缺点**：结构化产出显著抑制级联幻觉，token 效率高；但角色与 SOP 面向软件工程，迁移到视频创作需重写；社区迭代已放缓
- **对项目借鉴**：① SOP+结构化文档模式正对应 TravelGen 阶段产物（创意稿/脚本/分镜表），可固化"分镜表 JSON Schema"作为 Agent 间契约；② 消息池发布订阅避免四 Agent 信息过载；③ 可执行反馈=渲染失败/审核驳回的自动重试链路

### 4.3 CAMEL（论文，NeurIPS 2023）

- **名称**：CAMEL: Communicative Agents for "Mind" Exploration of LLM Society
- **类型**：论文（NeurIPS 2023）+开源库 ｜ **作者**：Guohao Li 等，KAUST ｜ **年份**：2023
- **Agent架构**：角色扮演双智能体：AI User（任务规划、发指令）+AI Assistant（执行、给方案），另有 **Task Specifier** 将人类想法细化为具体任务
- **协同方式**：协作式对话（多轮指令-执行），模拟智能体社会
- **通信机制**：自然语言消息传递，Inception Prompting（初始提示注入）启动
- **Workflow设计**：Collaborative（纯对话至任务完成，无显式编排）
- **Memory**：仅对话上下文，无独立记忆模块
- **Tool Calling**：论文版无工具调用（侧重对话与数据集生成）
- **优缺点**：开创性验证了自主对话协同可行性；但存在角色翻转、重复回复、消息死循环等失效模式，非生产导向
- **对项目借鉴**：① Task Specifier"想法→任务规格"可移植为 Planner 的"主题→视频规格"细化步骤；② 其失效模式正是 TravelGen 采用确定性编排+终止条件+最大轮数上限的理由

### 4.4 CrewAI（框架）

- **名称**：CrewAI ｜ **类型**：框架（MIT，Python 3.10-3.13） ｜ **团队**：CrewAI Inc. ｜ **现状**：2026 年为 1.x 线（v1.15.x，2026-06），约 55k stars、约 130 万月安装量
- **Agent架构**：四原语：Agent（角色+目标+背景+工具）、Task、Crew、Process；角色制组织
- **协同方式**：协作式（Process 支持 sequential/hierarchical/consensual）；层级模式有通用 manager agent
- **通信机制**：任务输出结果在 Agent 间传递，无显式黑板
- **Workflow设计**：两层——Crews（自治、运行时决定形态，适合探索）+ **Flows**（事件驱动，@start/@listen/@router 装饰器，确定性，官方推荐生产首选）
- **Memory**：四类内置记忆（短期/长期/实体/上下文）+向量库集成
- **Tool Calling**：@tool 装饰器注册简单；企业版提供 RBAC 等权限控制
- **优缺点**：原型速度最快（约 20 行）、文档生态最好；但无内置 checkpoint（失败整跑重来）、Agent 间消息 token 成本高、调试最困难，生产定级 "Tier 2"
- **对项目借鉴**：① Crews 快速搭 MVP、生产切 Flows（确定性+人工审核节点）；② 四类记忆可承载城市知识/用户偏好等上下文；③ 缺 checkpoint 是硬伤，长链路视频生成需自建状态持久化

### 4.5 LangGraph（框架，LangChain）

- **名称**：LangGraph ｜ **类型**：框架（MIT，Python/JS） ｜ **团队**：LangChain, Inc. ｜ **现状**：v1.0 GA（2025-10），2026-07 v1.2.8，约 36k stars、约 9000 万月下载，Uber/JPMorgan/Klarna 等生产背书
- **Agent架构**：StateGraph——节点=函数/LLM 调用，边=（条件）转移；typed state 由 reducer 合并；支持子图嵌套、supervisor 多 Agent 模式
- **协同方式**：图工作流显式控制（协作/层级均可编码为图拓扑）
- **通信机制**：Graph 边 + 共享 State（显式状态传递，非自由对话）
- **Workflow设计**：Graph（顺序/条件分支/并行 fan-out Send/循环），任意拓扑
- **Memory**：Checkpointer（sqlite/postgres，线程级持久化）+ Store（跨线程长期记忆）
- **Tool Calling**：任意 Python 函数/LangChain 工具，节点内直用
- **优缺点**：生产最成熟——HITL interrupt 可跨天恢复、time travel 回放与分叉、super-step 失败恢复、LangSmith 观测；缺点：学习曲线陡、样板代码多、调试成本高
- **对项目借鉴**：① 与 TravelGen 四阶段流水线高度匹配：Planner→Script→Storyboard→Review 四节点+interrupt 人工审核+失败重试边；② checkpoint 提供断点续跑与视频生成失败恢复，不重跑全链路；③ 子图封装"Storyboard+渲染+Review"可复用于多城市

### 4.6 OpenManus（框架）

- **名称**：OpenManus ｜ **类型**：框架（MIT，Python） ｜ **团队**：MetaGPT 团队（现归 Foundation Agents 组织） ｜ **现状**：2025-03 发布（3 小时原型），约 57k stars，持续迭代
- **Agent架构**：单 Agent ReAct（step→think→act→execute）+多 Agent PlanningFlow（规划→动态任务分配）
- **协同方式**：Planner 产出线性计划后，按任务临时分派给最合适的专业 Agent（执行时动态匹配）
- **通信机制**：共享计划文件（markdown plan）+任务输入输出传递
- **Workflow设计**：动态规划（Sequential/Hierarchical 混合）
- **Memory**：计划文件+会话上下文；2026 版支持浏览器/计算机自动化
- **Tool Calling**：BaseTool 抽象+ToolCollection；工具集决定 Agent 专长
- **优缺点**：极简上手、通用任务执行力强；但定位"通用助手"而非业务流水线，动态分配机制简单，缺生产级编排/观测/HITL
- **对项目借鉴**：① "计划文件+任务分派"结构与 TravelGen 流水线同构，可参考其计划文件格式设计阶段产物；② 验证了轻量框架快速落地路径，适合 TravelGen MVP 验证端到端链路

### 4.7 AutoGen 框架现状 / AG2 社区版

- **名称**：AutoGen 框架（microsoft/autogen）与 AG2 社区版（ag2ai/ag2） ｜ **团队**：微软研究院；二人 2024-11 离微软后创立 AG2 社区版
- **当前状态**：AutoGen 2025-10 起进入**维护模式**（最后版本 v0.7.5），微软将其与 Semantic Kernel 合并为 **Microsoft Agent Framework**（2026-04 GA v1.0，graph 编排+企业级 telemetry/HITL）；AG2 延续原 0.2 API，当前 v0.12.x，约 4.8k stars
- **Agent架构**：0.2 版为 ConversableAgent+GroupChat/GroupChatManager；0.4+ 为事件驱动 actor 模型
- **协同方式**：群聊动态选发言者、对话编程（旧）→ graph 编排（新框架）
- **Memory**：会话上下文；AG2 新增 MemoryStream，持久化仍弱
- **Tool Calling**：代码执行+函数调用；AG2 新增 typed tools、多 provider
- **优缺点**：学术影响力最大、概念经典；但原版停止新特性、AG2 社区体量小且存在维护风险
- **对项目借鉴**：① AutoGen 论文概念（conversable agent、终止条件）仍是编排设计的理论底座；② **不建议新项目选 AutoGen 原版（维护模式）或 AG2（社区小）**；若走微软栈应评估 Agent Framework v1.0

### 4.8 ⭐新增 OpenAI Agents SDK（框架）

- **名称**：OpenAI Agents SDK（openai/openai-agents-python） ｜ **团队**：OpenAI（Swarm 的正式生产版后继） ｜ **现状**：2025-03 发布，2026-06 v0.17.7，约 19-22k stars
- **Agent架构**：极简 Agent（instructions+tools+handoffs+guardrails+可选 output_type 结构化输出）；Runner 执行循环
- **协同方式**：Handoff 委派（triage/router 路由、supervisor 模式）+Agent-as-tool；对话历史随切换传递
- **通信机制**：对话历史随 handoff 传递
- **Workflow设计**：单 Agent 循环+handoff 链（动态、线性为主）
- **Memory**：Session 持久化（SQLite/Redis/内存）
- **Tool Calling**：函数工具、MCP 服务器、hosted tools、Sandbox Agents（沙盒执行）
- **优缺点**：开箱即用、默认内置 tracing（OTel）与三层 guardrails（输入/输出/工具）、评价工具完善；但无 checkpoint/time travel、handoff 链路调试难
- **对项目借鉴**：① guardrails 三层校验可直接承载 Review Agent 的硬规则（主题合规、敏感词、时长限制、PII）；② 内置 tracing 满足可观测性要求；③ triage 模式适合多城市/多主题子工作流路由，可作 LangGraph 中的单节点补充

### 4.9 ⭐新增 Google ADK（框架）

- **名称**：Agent Development Kit（google/adk-python） ｜ **团队**：Google ｜ **现状**：2025-03 首版；ADK 2.0 于 2026-06 GA（Python 2.1.x），约 20.8k stars（python）、约 2830 万月下载，多语言版本最全
- **Agent架构**：Agent-as-Graph 2.0 工作流引擎：节点类型（function/agent/tool/join/dynamic/workflow/parallel）；边支持条件路由、循环；LlmAgent 可直接嵌入图
- **协同方式**：层级（coordinator-subagents）+graph 工作流+A2A 协议跨框架通信
- **Workflow设计**：Graph 原生（Sequential/并行/循环/HITL 中断均可表达）；Chat/Task/SingleTurn 模式
- **Memory**：Session state，图节点可绑定状态参数
- **Tool Calling**：工具节点、MCP、AgentTool 封装；插件系统（如 Retry-and-Reflect 自愈插件）
- **优缺点**：graph-first+HITL 原生（可跨进程恢复）、OTel 原生观测+BigQuery 分析插件、内置 eval；缺点：年轻迭代快（2.0 API 变动大）、Gemini 生态倾斜
- **对项目借鉴**：① graph-first 与原生 HITL = TravelGen 四 Agent 流水线+人工审核节点的直接映射；② 内置 eval 与观测可闭环审核质量；③ 选型需锁定版本（2.x）并评估演进风险

### 4.10 对本项目多智能体架构的选型建议（总结）

TravelGen 四阶段流水线（Planner→Script→Storyboard→Review）具有明确的阶段产物、人工审核节点与失败重试需求，本质是**确定性工作流而非自由对话**。据此：
- **首选 LangGraph**——typed state 对应分镜表等阶段产物，checkpoint 提供断点续跑与 time travel 回放（渲染失败不重跑全链路），interrupt 原生支撑 Review 人工审核节点，生产成熟度最高（v1.x 稳定、头部企业背书）；
- **备选 Google ADK 2.0**（graph 原生+HITL+观测，但 API 演进快需锁版本）或 **CrewAI Flows**（起步最快，但缺 checkpoint 需自建持久化）；
- **OpenAI Agents SDK** 的 guardrails 与 tracing 可作为 Review 节点与观测的补充组件；OpenManus 用于 MVP 端到端验证；
- 论文侧借鉴 MetaGPT 的 SOP+结构化文档契约与 CAMEL 的任务规格化，但放弃自由对话协同；AutoGen 原版已维护模式，不建议新项目采用。

---

## 五、方向四：RAG（知识增强）

**关键词**：Retrieval Augmented Generation、Knowledge Retrieval、Graph RAG

### 5.0 方向小结

RAG 已从"朴素检索-生成"演进到 **Modular/Agentic RAG**（查询改写、路由、重排、压缩、按需检索）与**图结构增强**（GraphRAG/LightRAG/HippoRAG 将知识库构建为"实体-关系"图谱）。对本项目核心结论：浙江文旅知识库应采用"**知识图谱 + 向量 + 摘要层级**"混合路线，支持宣传片全局主题（global）与分镜细节（local）两级生成；防幻觉需三道闸门（Self-RAG 式支撑性批评、CRAG 式检索质量门控、检索证据可溯源）。

### 5.1 Retrieval-Augmented Generation（原始RAG，Lewis et al. 2020）

- **名称**：Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
- **作者/机构**：Patrick Lewis 等 12 人，Meta AI（FAIR）+ UCL + NYU
- **年份/会议**：2020，NeurIPS 2020（arXiv:2005.11401）
- **知识增强方式**：检索增强——预训练参数化记忆（BART-large 生成器）＋非参数化记忆（DPR 稠密索引）
- **检索流程**：索引构建（2018-12 Wikipedia 快照切 100 词块，约 2100 万文档，FAISS/HNSW 建 MIPS 向量索引）→查询用 DPR 双塔编码器编码→top-K 稠密检索（无重排）→生成（RAG-Sequence 整句用同一文档、RAG-Token 逐 token 切换文档，端到端边缘化联合微调查询编码器与生成器）
- **Chunk策略**：100 词小块，粒度极细，无分层
- **Embedding方法**：DPR bi-encoder（BERT-BASE）双塔
- **是否Graph**：否　**迭代/多跳**：否（单次检索）
- **优缺点**：开山之作，确立"检索-生成"端到端范式，索引可热切换（知识更新无需重训）、生成更具事实性且幻觉更少；缺点是固定 top-K 无条件检索、块粒度过细缺乏全局语义、无重排与反馈机制
- **对项目借鉴**：① 作为本项目 RAG 基线，搭建最小"检索-生成"闭环；② 索引热替换机制适配文旅数据持续更新（新节庆、新活动上线即可生效）；③ "生成须基于检索证据"应成为文案 Agent 的设计原则，分镜脚本需绑定知识库字段

### 5.2 Self-RAG（Asai et al., ICLR 2024 Oral）

- **名称**：Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection
- **作者/机构**：Akari Asai 等（华盛顿大学/AI2/IBM Research）｜**年份**：2024，ICLR 2024 Oral（Top 1%，arXiv:2310.11511）
- **知识增强方式**：自我反思（self-reflection）+ 按需检索——训练单一 LLM（Llama2 7B/13B）在生成中输出反思 token
- **检索流程**：生成过程中模型自主决定是否检索（[Retrieve] token，可多次检索也可跳过）→需要时检索 top-K→对每片段打相关性标签 ISREL→逐段生成并批评（ISSUP 支撑性、ISUSE 效用）→segment-wise beam search 按效用筛选；批评 token 兼具重排与溯源功能
- **Chunk策略**：沿用现成检索器片段粒度　**Embedding方法**：复用现成检索器（Contriever 类）
- **是否Graph**：否　**迭代/多跳**：支持——生成中可多次触发按需检索
- **优缺点**：优点：避免无关检索污染、按需检索省调用、输出自带支撑性声明可核查、推理期可控无需重训；缺点：需专门微调专属模型（不支持黑盒闭源 API 模型）、训练数据依赖 GPT-4 生成反思 token
- **对项目借鉴**：① "相关性/支撑性"批评机制可直接转为**分镜事实核查器**——校验"分镜描述是否被知识库片段支撑"；② 多智能体中让文案 Agent 对 RAG 结果打标签后再决定采纳或改写；③ 按需检索降低多 Agent 协同中的无效检索成本
- **代码**：github.com/AkariAsai/self-rag（模型在 HF：selfrag/selfrag_llama2_7b 等）

### 5.3 GraphRAG（Microsoft）

- **名称**：From Local to Global: A Graph RAG Approach to Query-Focused Summarization（GraphRAG）
- **作者/机构**：Darren Edge 等，Microsoft Research ｜**年份**：2024（arXiv:2404.16130；2024-07 开源）
- **知识增强方式**：图结构增强——知识图谱 + Leiden 社区检测 + 层级社区摘要
- **检索流程**：索引构建：文档 chunk→LLM 抽取实体/关系三元组→合并去重建 KG→Leiden 算法社区检测→对社区递归生成层级摘要→文本块/摘要均向量化入库。查询：**local search**（实体+相邻社区+文本块联合检索）、**global search**（查询先与社区摘要做相关性映射再 map-reduce 生成）、**drift search**（2024 年底推出，查询上下文逐步漂移的多步探索）
- **Chunk策略**：文本块粒度可配（约 300 token），以实体抽取突破 chunk 边界　**Embedding方法**：可插拔，向量与图双通道存储
- **是否Graph**：是——LLM 抽取实体关系建 KG，社区检测与层级摘要即图结构利用　**迭代/多跳**：drift search 支持多步探索
- **优缺点**：优点：全局性问题（"浙江非遗有哪些代表性项目并如何分布"）回答质量高、溯源清晰、适合结构化知识；缺点：索引成本高（LLM 抽取+社区摘要 token 开销大）、local 查询质量依赖实体抽取精度
- **GitHub现状**：microsoft/graphrag，约 35k star（2026-07），v3.1.1（2026-07-18），活跃维护
- **对项目借鉴**：① 以城市/景区/非遗/节庆为实体构建浙江文旅知识图谱是核心资产，可直接复用"实体-关系-社区摘要"管线；② global search 适配城市宣传片全景主题，local search 适配具体景区分镜；③ 对已有结构化文旅数据可先导入再增量补抽取，控制成本

### 5.4 LightRAG（HKUDS）

- **名称**：LightRAG: Simple and Fast Retrieval-Augmented Generation
- **作者/机构**：Zirui Guo 等（香港大学 HKUDS 团队）｜**年份**：2024（arXiv:2410.05779；EMNLP 2025 Findings）
- **知识增强方式**：图+向量双层结构、双级检索（低层实体级/高层主题级）
- **检索流程**：索引构建：chunk→LLM 抽取实体与关系建图，实体及其关联关系文本以 Key-Value 存储（图结构融合进文本索引）→支持**增量合并更新与删除**（无需全量重建）。查询：local/global/hybrid/naive/mix 五种模式，按查询类型（实体型/主题型）自动选择或混合
- **Chunk策略**：文本块为实体抽取输入，中等粒度（默认 chunk_token_size=1200、overlap=100）
- **Embedding方法**：可插拔（默认 bge-m3 等）　**是否Graph**：是——轻量图（KV 存储实现），无需完整图数据库
- **迭代/多跳**：图结构支撑多跳语义关联；mix 模式融合多路检索
- **优缺点**：优点：轻量低成本（比 GraphRAG 大幅减少 LLM 调用）、增量更新适配动态数据、检索延迟低；缺点：无社区摘要与层级聚合，全局综合能力弱于 GraphRAG
- **GitHub现状**：HKUDS/LightRAG，约 37-38k star，v1.4.16（2026-05），v1.5 起支持多模态入库（可解析 PDF/图片/表格）
- **对项目借鉴**：① 作为本项目主线框架候选：轻量+增量更新适配文旅知识库持续扩充（新增景区/节庆直接合并入图）；② local/global/mix 模式天然对应"分镜细节（具体实体）"与"宣传片主题（宏观概括）"两级生成；③ 多模态支持便于宣传册、图文资料直接入库

### 5.5 HippoRAG（NeurIPS 2024）

- **名称**：HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models
- **作者/机构**：Bernal Jiménez Gutiérrez 等（俄亥俄州立大学+斯坦福大学）｜**年份**：2024，NeurIPS 2024（arXiv:2405.14831）
- **知识增强方式**：图结构记忆索引（海马体索引理论）+ 单步多跳检索
- **检索流程**：离线索引：LLM 以 OpenIE 从段落抽取开放三元组→构建无 schema 知识图谱→相似概念间加同义边→实体节点 embedding 入库。在线检索：LLM 从查询中识别实体→实体链接到图节点→以查询节点为种子运行 **Personalized PageRank（PPR）**图遍历→节点概率按段落聚合排序→送入 LLM 生成
- **Chunk策略**：段落级索引（三元组自段落抽取）　**Embedding方法**：ColBERTv2/Contriever 类检索编码器
- **是否Graph**：是——OpenIE 三元组 KG + PPR 图遍历　**迭代/多跳**：是——**PPR 单步完成多跳推理**，比迭代检索（IRCoT）少 10-30 倍 LLM 调用、快 6-13 倍
- **优缺点**：优点：多跳检索成本极低、MuSiQue 等基准上超越 SOTA 最高 20%；缺点：索引需每段落 2 次 LLM 调用且实体嵌入规模约为段落数 8 倍，超大语料扩展受限。后续 HippoRAG 2（ICML 2025）引入"短语节点+段落节点"双层图，多跳检索进一步强化
- **对项目借鉴**：① "城市→非遗→传承人→节庆"这类跨实体关联正是典型多跳查询（如"杭州有哪些与丝绸非遗相关的节庆"），PPR 单步多跳是本项目性价比最优的多跳方案；② 无 schema 图结构适合文旅半结构化数据的快速导入；③ 海马体索引思想可为多智能体共享的"长期文旅记忆层"提供架构参考
- **代码**：github.com/OSU-NLP-Group/HippoRAG（约 3.8k stars，2026-06 仍活跃）

### 5.6 RAPTOR（ICLR 2024）

- **名称**：RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval
- **作者/机构**：Parth Sarthi 等，斯坦福大学｜**年份**：2024，ICLR 2024（arXiv:2401.18059）
- **知识增强方式**：递归摘要树（分层语义检索）
- **检索流程**：索引构建：长文档切块→叶节点 embedding→GMM（高斯混合模型）软聚类（节点可属多簇、无需预设簇数）→LLM（GPT-3.5）对每簇生成摘要形成父层→递归至根节点，构建自底向上多粒度摘要树。查询：树遍历（自顶向下逐层选 top-k）或**折叠树**（全树节点扁平化统一检索至 token 上限，实验证明折叠树更优）
- **Chunk策略**：叶节点小块（百 token 级）+多层摘要节点（压缩率约 72%）
- **Embedding方法**：SBERT 类预训练模型嵌入全部节点　**是否Graph**：否（树结构而非图）
- **迭代/多跳**：不支持图式多跳，但跨块/跨文档主题整合能力强
- **优缺点**：优点：解决"信息分散于非连续段落"问题、按需粒度检索（细节在叶层、总览在根层）、支撑 80k token 长文档且构建成本线性；缺点：每层构建都调 LLM 摘要（成本随层数累积）、静态树更新需重建、对事实点级查询无明显增益
- **对项目借鉴**：① 景区/非遗资料多为长文档，RAPTOR 树让"城市一句话总览"与"景点细节分镜"在不同语义层级各取所需；② 摘要树可直接产出"城市介绍总稿→景区详情→段落素材"的层级化文案中间件，供多智能体复用；③ 可作为与向量检索互补的第二路检索通道
- **代码**：github.com/parthsarthi03/raptor

### 5.7 ⭐新增 RAG 综述（Gao et al., 2024）

- **名称**：Retrieval-Augmented Generation for Large Language Models: A Survey
- **作者/机构**：Yunfan Gao 等 11 人，复旦大学+同济大学（王昊奋通讯）｜**年份**：2024（arXiv:2312.10997）
- **知识增强方式**：综述——提出 **Naive/Advanced/Modular RAG** 三阶段分类法（Advanced 是 Modular 的特例）
- **检索流程**：系统梳理"检索-生成-增强"三方基石：检索端（分块、语义模型微调、查询改写/扩展如 query2doc、混合检索）；生成端（重排、压缩、防曝光偏差）；增强三问（检索什么/何时检索/如何用），归纳单次/迭代/递归/自适应检索过程与多模态扩展。另给出评估体系：三质量分（context relevance、answer fidelity、answer relevance）、四大能力（噪声鲁棒、拒答、信息整合、反事实鲁棒）及 RAGAS/ARES/RGB 等基准工具
- **对项目借鉴**：① 本项目 RAG 设计应定位在 Modular/Agentic RAG 层，直接采纳其查询改写/路由/重排/压缩组件清单；② 用其评估体系（context relevance/answer fidelity + RAGAS）为文旅文案事实性建立量化验收标准；③ "何时检索"（按需/自适应）思想指导多智能体调度中检索触发策略
- **代码**：github.com/Tongji-KGLLM/RAG-Survey

### 5.8 ⭐新增 CRAG（Corrective RAG，复旦）

- **名称**：Corrective Retrieval Augmented Generation
- **作者/机构**：Shi-Qi Yan 等（中国科学技术大学+UCLA+Google；注：非复旦）｜**年份**：2024（arXiv:2401.15884；ACL 2025 Findings）
- **知识增强方式**：纠正式检索——检索质量评估 + 三动作纠错
- **检索流程**：检索→轻量 T5-large 评估器对整体检索质量打分→触发三分类动作：**Correct**（直接进入精炼）、**Incorrect**（丢弃原结果，改写查询后触发 Web/外部权威搜索补充）、**Ambiguous**（保留原结果并外部补充）→decompose-then-recompose 算法精炼出相关片段→生成
- **Chunk策略**：在检索片段粒度上操作（"知识条"级细粒度过滤）　**Embedding方法**：复用原有检索器，不新增
- **是否Graph**：否　**迭代/多跳**：部分支持（Incorrect/Ambiguous 时可触发补充检索轮次）
- **优缺点**：优点：即插即用（可与 Self-RAG 组合成 Self-CRAG）、显著提升对检索失败的鲁棒性；缺点：评估器需微调、外部搜索依赖 API 与成本
- **对项目借鉴**：① 文旅知识库覆盖不全时（新开放景点、临时节庆活动），"评估→纠错→外部补充"机制是**防幻觉关键**：知识库查不到时应触发权威源补充或明确拒答，而非编造；② 可为分镜文案 Agent 增加"检索质量门控"——低置信度时转人工/官方数据源复核；③ 与 Self-RAG 反思 token 可组合成双重事实校验链路
- **代码**：github.com/HuskyInSalt/CRAG

### 5.9 ⭐新增 RAG-Fusion 与 ColBERT（检索重排工程组件）

- **RAG-Fusion**（Rackauckas，Infineon，2024；arXiv:2402.03367）——**知识增强方式**：多查询生成 + 倒数排名融合（RRF）。**检索流程**：原查询→LLM 生成多个变体查询（多视角改写）→各自向量检索→RRF 公式 Σ1/(k+rank) 融合重排去重→生成。**优缺点**：召回与全面性显著提升、无参数易接入；代价是多查询增加调用成本、个别变体可能跑题。**借鉴**：文旅用户查询表述多样（"杭州秋天去哪儿玩" vs "杭州最佳秋景观赏地"），多查询+RRF 可同时提升召回与分镜素材多样性
- **ColBERT**（Khattab & Zaharia，斯坦福，SIGIR 2020，arXiv:2004.12832）——**知识增强方式**：token 级晚期交互（Late Interaction）检索：查询与文档分别编码为 token 向量集，以 MaxSim 逐 token 最大相似度聚合打分。**优点**：文档向量离线预计算、检索精度显著高于双塔、重排比 BERT ranker 快两个数量级。**借鉴**：作为本项目重排器（reranker）可显著提升中文文旅资料检索精度；ColBERTv2（NAACL 2022）/PLAID（CIKM 2022）支持端到端检索与大规模索引，且有中文微调可用。**代码**：github.com/stanford-futuredata/ColBERT

### 5.10 对本项目文旅知识库 RAG 设计的启示（总结）

TravelGen 的文旅知识库应采用"**知识图谱 + 向量 + 摘要层级**"混合路线而非单一向量检索：以城市/景区/非遗/节庆/传承人为实体构建轻量知识图谱（借鉴 GraphRAG 的社区摘要、LightRAG 的增量图更新与 HippoRAG 的无 schema 三元组），结合 RAPTOR 式递归摘要形成"主题级-实体级-细节级"三级语义索引，支撑宣传片全局主题（global）与分镜细节（local）两级生成。防幻觉需三道闸门：Self-RAG 式支撑性批评 token、CRAG 式检索质量门控（低置信触发权威源补充或拒答）、检索证据随文案可溯源。混合检索采用多查询变体+RRF 融合+ColBERT 重排，并按 RAG 综述评估体系（context relevance/answer fidelity/RAGAS）建立文旅文案事实性验收标准；LightRAG 式增量更新保证节庆活动等动态信息即时生效。

---

## 六、综合结论：文献调研对项目的直接支撑

### 6.1 与赛题评分标准的映射

| 赛题评分维度 | 文献调研支撑点 |
|---|---|
| AIGC生成效果（30%，风格一致性/画面美感） | Story2Board LPA/RAVM、StoryDiffusion 一致性自注意力 → 跨镜头地标/角色一致性；Wan2.2/HunyuanVideo 1.5 中文文字渲染 + LoRA 风格微调 → 画面风格统一；FilmAgent 预置镜头库 → 专业镜头语言 |
| 技术方案与创新性（25%，多模态生成/智能体协同） | LangGraph Graph 编排四 Agent 流水线（MetaGPT SOP 契约）；RAG 图谱+向量混合知识库（GraphRAG/LightRAG/HippoRAG）；分镜 JSON Schema（VideoDirectorGPT 模板） |
| 场景完整性与应用价值（25%） | RAG 知识库承载浙江城市/景区/非遗/节庆真实信息，保证内容真实性（赛题强调"真实性"）；多镜头视频模型（Seedance/Wan 2.6）一条成片 |
| 系统体验与作品完整度（20%） | LangGraph checkpoint/HITL → 断点续跑与人工审核；评审回路（Critique-Correct-Verify）→ 生成质量可控 |

### 6.2 初步技术选型（衔接 Phase 3 Benchmark / Phase 4 系统设计）

- **编排层**：LangGraph（首选，Graph+checkpoint+HITL）｜备选 Google ADK 2.0 / CrewAI Flows
- **知识层**：LightRAG 为主线（增量图更新+轻量），GraphRAG 社区摘要思想补充，HippoRAG PPR 多跳，ColBERT 重排，RAG-Fusion 多查询召回；评估用 RAGAS
- **视频生成层**：自部署 Wan2.2-TI2V-5B / HunyuanVideo 1.5（Apache 2.0）；高质量通道 **Seedance 2.0 API**（约1元/秒、15s多镜头+自动分镜+双声道，2026-04起方舟全面开放，详见 GithubSurvey.xlsx 补充调研）或 Wan 2.6（自动分镜+R2V）；原生4K/主体参考/数字演员场景选**可灵 3.0**（方言口型+Omni特征库）；预览与数字人播报档位用混元生视频 API（0.3-0.6元/s）；图生视频桥接参考 StoryDiffusion 语义运动预测器
- **图片生成层**：FLUX.1-schnell（风景封面，可商用）+ Kolors（中文文字海报）；SDXL 作风格 LoRA 底模
- **分镜层**：分镜 Agent 只输出结构化 JSON（scene→shot 两级，镜头参数受控枚举），T2I/T2V 全解耦可替换；评审回路用 LLM-Judge 六维评分
- **配音层**：CosyVoice2（Apache 2.0 中文方言最强）；专属音色 GPT-SoVITS 微调（详见 Phase 2 GitHub 调研）
- **合成层**：MoviePy + FFmpeg + AutoEditor（详见 Phase 2 GitHub 调研）

### 6.3 调研发现的关键事实修正（避免后续阶段踩坑）

1. AutoGen 原版已于 2025-10 进入维护模式，微软继任者为 Microsoft Agent Framework；AG2 社区版生态较小——新项目不建议选型
2. "HunyuanVideo 2.0/2.1" 不存在（2025 年迭代实为 1.5）；混元 3.0 是非开源多模态大模型
3. Wan2.5 走 API 线（非完全开源），开源主线为 Wan2.2；Wan 2.6 为闭源 API（2025-12）
4. Sora 2 于 2025-09-30 发布（原生音频+口型），国内不可直连
5. MoviePy 已实质停摆（最后版本 v2.2.1，2025-05），需锁定版本并做好兜底
6. Remotion 并非 MIT 开源（源可用许可，≥4 人团队商用需付费）；ComfyUI 为 GPL-3.0（商用集成需注意许可传染性）
7. RAPTOR 的聚类是 GMM 软聚类而非"LLM 主题聚类"；Self-RAG 用标准 LM 目标训练批评 token，非 RL

---

**参考文献汇总**：Sora TR（openai.com/index/video-generation-models-as-world-simulators）｜Seedance 1.0（arXiv:2506.09113）｜Wan2.2（arXiv:2503.20314, github.com/Wan-Video/Wan2.2）｜HunyuanVideo（arXiv:2412.03603）｜CogVideoX（github.com/THUDM/CogVideo）｜Open-Sora（github.com/hpcaitech/Open-Sora）｜VideoPoet（arXiv:2310.05737）｜VideoCrafter2（CVPR 2024）｜AnimateDiff（arXiv:2307.04725）｜Emu Video（arXiv:2311.10709）｜HunyuanVideo 1.5（HF tencent/HunyuanVideo-1.5, arXiv:2511.18870）｜LTX-2（Lightricks, 2026-01）｜Wan 2.6（阿里云百炼, 2025-12）｜StoryGen（arXiv:2306.00973, CVPR 2024）｜Visual Storytelling 综述（ACL W19-1805）｜LLM Story Generation 综述（2025.findings-emnlp.750）｜DirectorLLM（arXiv:2412.14484）｜Story2Board（arXiv:2508.09983）｜FilmAgent（arXiv:2501.12909, SIGGRAPH Asia 2024）｜VideoDirectorGPT（arXiv:2309.15091, COLM 2024）｜StoryDiffusion（arXiv:2405.01434, NeurIPS 2024）｜AutoGen（arXiv:2308.08155）｜MetaGPT（ICLR 2024）｜CAMEL（NeurIPS 2023）｜LangGraph（docs.langchain.com）｜CrewAI（docs.crewai.com）｜OpenManus（github.com/mannaandpoem/OpenManus）｜OpenAI Agents SDK（github.com/openai/openai-agents-python）｜Google ADK（google/adk-python）｜RAG（arXiv:2005.11401, NeurIPS 2020）｜Self-RAG（arXiv:2310.11511, ICLR 2024）｜GraphRAG（arXiv:2404.16130, github.com/microsoft/graphrag）｜LightRAG（arXiv:2410.05779, github.com/HKUDS/LightRAG）｜HippoRAG（arXiv:2405.14831, github.com/OSU-NLP-Group/HippoRAG）｜RAPTOR（arXiv:2401.18059, github.com/parthsarthi03/raptor）｜RAG 综述（arXiv:2312.10997）｜CRAG（arXiv:2401.15884, github.com/HuskyInSalt/CRAG）｜RAG-Fusion（arXiv:2402.03367）｜ColBERT（arXiv:2004.12832, SIGIR 2020）


