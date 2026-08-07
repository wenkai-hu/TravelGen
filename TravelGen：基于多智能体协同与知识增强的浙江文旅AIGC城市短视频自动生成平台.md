# TravelGen：基于多智能体协同与知识增强的浙江文旅AIGC城市短视频自动生成平台

# Project Introduction



TravelGen 是一套面向浙江文旅传播场景的 AIGC 城市短视频自动生成平台。



系统采用"多智能体\(Multi\-Agent\)\+知识增强\(RAG\)\+多模态生成\(Multimodal AIGC\)"的整体架构，能够根据用户输入的城市、景区、节庆活动、非遗文化等信息，自动完成视频策划、宣传文案生成、脚本生成、分镜设计、AI图片生成、AI视频生成、AI配音、背景音乐推荐及视频自动合成。



与传统AIGC视频工具不同，本系统针对浙江文旅场景构建专属知识库，并采用多智能体协同完成内容规划、素材生成与质量审核，使最终生成的视频具有更高的真实性、风格一致性与传播效果。



整个系统遵循"Planning → Generation → Composition → Review"的工作流程，实现文旅宣传视频的一站式智能生成。

---



# 一、项目目标



构建一套面向浙江文旅传播场景的 AIGC 城市短视频自动生成系统。



系统能够根据用户输入：



- 浙江城市

- 景区

- 节庆活动

- 非遗文化

- 校园宣传

- 视频风格

- 视频时长

- 面向人群

    

自动生成：



- 文旅宣传文案

- 视频脚本

- 分镜设计

- AI图片

- AI视频

- AI配音

- AI背景音乐

- 自动剪辑

- MP4短视频

    

---



# 二、项目整体开发流程



Project Planning

│

▼

Literature Survey

│

▼

Technical Investigation

│

▼

Benchmark Test

│

▼

System Design

│

▼

Core Module Development

│

▼

Platform Development

│

▼

Experiment \& Optimization

│

▼

Competition Materials



---



# 三、团队分工



## 成员A（AI算法负责人）



负责：



- 文献阅读

- 多模态模型调研

- Prompt Engineering

- Multi\-Agent设计

- RAG知识库

- AI脚本生成

- AI分镜生成

- Benchmark实验

- 技术报告算法部分

    

---



## 成员B（系统负责人）



负责：



- 系统架构

- 前端开发

- 后端接口

- 视频合成

- 数据管理

- UI设计

- 系统部署

- 演示视频

- PPT制作

    

---



# 四、开发阶段



---



# Phase 0 项目规划（Week1）



目标：



完成项目整体设计。



## 任务



- 阅读赛题

- 明确评分标准

- 确定创新点

- 绘制系统架构

- 制定开发计划

    

输出：



- Project Proposal

- Architecture V1

    

负责人：



A\+B



---



# Phase 1 文献调研（Week1\~Week2）



目标：



完成 Related Work。



---



# A负责

## AIGC视频生成

**关键词：**

Text\-to\-Video

Video Generation

Image\-to\-Video

Diffusion Transformer（DiT）

World Model

### 推荐论文：

1. Sora Technical Report（OpenAI） 

2. Seedance 1\.0 Technical Report（ByteDance）⭐（新增） 

3. Wan2\.2 Technical Report（Alibaba） 

4. HunyuanVideo（Tencent） 

5. CogVideoX（Zhipu AI） 

6. Open\-Sora 

7. VideoPoet（Google） 

8. VideoCrafter2 

9. AnimateDiff 

10. Emu Video 

> **删除：MagicVideo**（已不是当前主流技术路线，被新一代 DiT 视频模型取代）
> 
> 

### 总结内容：

- 模型（DiT / Diffusion / Autoregressive 等） 

- 技术路线（整体架构） 

- 输入输出（Text\-to\-Video、Image\-to\-Video、Video Editing） 

- 核心创新 

- 优缺点 

- 是否开源 

- 是否提供 API 

- 对项目的借鉴 

---

# Storyboard

**关键词：**

Storyboard Generation

Visual Storytelling

Narrative Planning

Scene Planning

Shot Planning

### 推荐论文：

1. StoryGen 

2. Visual Storytelling 

3. Narrative Planning with LLM 

4. DirectorLLM ⭐（新增） 

5. Script\-to\-Storyboard ⭐（新增） 

### 总结内容：

- LLM 如何自动生成 Storyboard（分镜） 

- Story → Scene → Shot 的生成流程 

- Prompt 设计方式 

- 镜头规划（Shot Planning） 

- Scene 划分方法 

- 是否使用多模态信息 

- 优缺点 

- 对项目的借鉴 

---

# Multi\-Agent

**关键词：**

LLM Agent

CrewAI

LangGraph

AutoGen

OpenManus

### 推荐论文：

1. AutoGen 

2. CrewAI 

3. LangGraph 

4. MetaGPT 

5. CAMEL 

> **补充：**
> 
> OpenManus 建议阅读 GitHub 和官方文档即可，不一定有代表性论文。
> 
> 

### 总结内容：

- Agent 架构 

- Agent 协同方式 

- 通信机制 

- Planner 设计 

- Workflow 设计 

- Memory 机制 

- Tool Calling 

- 优缺点 

- 对项目的借鉴 

---

# RAG

**关键词：**

Retrieval Augmented Generation

Knowledge Retrieval

Graph RAG

### 推荐论文：

1. Retrieval\-Augmented Generation（RAG） 

2. Self\-RAG 

3. GraphRAG 

4. LightRAG 

5. HippoRAG 

6. RAPTOR 

### 总结内容：

- 知识增强方式 

- 检索流程 

- Chunk 策略 

- Embedding 方法 

- 是否使用 Graph 

- 是否支持迭代检索 

- 优缺点 

- 对项目的借鉴

---



## B负责



调研AI产品。



包括：



- 可灵

- 即梦

- 剪映AI

- Runway

- Pika

- Veo

- Sora

- 腾讯混元

- 豆包AI

- MiniMax

- HeyGen

    

建立：



Product Benchmark\.xlsx



内容：



\|产品\|文案\|图片\|视频\|数字人\|API\|



---



输出



Related Work\.md



Reading Notes



Benchmark\.xlsx



---



# Phase2 Github调研（Week2）



目标：



学习已有项目。



---



## Video



Open\-Sora



https://github\.com/hpcaitech/Open\-Sora



Wan2\.2



CogVideoX



AnimateDiff



VideoCrafter



ComfyUI



DiffSynth



---



## Agent



LangGraph



CrewAI



OpenManus



AutoGen



Dify



FastGPT



OpenClaw



---



## Voice



CosyVoice2



Fish Speech



GPT\-SoVITS



EdgeTTS



Bark



---



## Image



FLUX



Kolors



SDXL



Hunyuan Image



---



## Editing



MoviePy



FFmpeg



AutoEditor



Remotion



---



输出：



Github Survey\.xlsx



---



# Phase3 Benchmark（Week3）



目标：



确定最终模型。



统一Prompt：



> 请生成一段杭州西湖一分钟宣传视频。
> 
> 



比较：



## 文案



GPT



Claude



Qwen



Gemini



DeepSeek



Kimi



---



## 分镜



统一Prompt



比较：



镜头质量



镜头逻辑



画面一致性



---



## 视频



Runway



Wan2\.2



可灵



Veo



MiniMax



比较：



画质



一致性



速度



---



输出：



Experiment Report



---



# Phase4 系统设计（Week4）



完成：



系统架构



数据库设计



接口设计



工作流设计



输出：



Architecture\.drawio



Workflow\.drawio



Database\.md



API\.md



---



# Phase5 核心模块开发（Week5\~Week7）



A负责：



- Planner Agent

- Script Agent

- Storyboard Agent

- Prompt优化

- RAG

    

B负责：



- Frontend

- Backend

- Video Composer

- MoviePy

- FFmpeg

- 用户管理

    

---



# Phase6 平台开发（Week7\~Week8）



完成：



用户输入



↓



自动生成



↓



可编辑



↓



导出MP4



功能：



- 首页

- 文案生成

- 分镜生成

- 视频生成

- 配音

- 音乐

- 导出

    

---



# Phase7 实验（Week8）



实验1



Prompt比较



实验2



不同LLM比较



实验3



不同视频模型比较



实验4



用户体验测试



输出：



Experiment\.xlsx



---



# Phase8 比赛材料（Week9）



完成：



PPT



演示视频



技术报告



部署文档



README



Docker



---



# 五、建议目录结构



AIGC\-Zhejiang\-Tourism



├── docs/

│

├── papers/

│

├── survey/

│

├── backend/

│

├── frontend/

│

├── models/

│

├── experiments/

│

├── assets/

│

├── demo/

│

├── README\.md

│

└── PROJECT\_PLAN\.md



---



# 六、阶段成果



|阶段|成果|
|---|---|
|Phase0|项目方案|
|Phase1|Related Work|
|Phase2|Github Survey|
|Phase3|Benchmark|
|Phase4|Architecture|
|Phase5|Core Modules|
|Phase6|Platform|
|Phase7|Experiments|
|Phase8|Competition Materials|



---



# 七、项目创新点（拟定）



- 浙江文旅知识增强（RAG）

- Multi\-Agent视频生成流程

- 自动分镜生成

- 多模态内容协同生成

- 风格一致性控制

- AI自动视频编排

- 可编辑式AIGC视频平台

    

---



# 八、最终目标



构建一套可部署、可演示、可扩展的浙江文旅AIGC城市短视频自动生成平台，实现从用户输入到视频导出的完整自动化流程，并形成完整的项目文档、实验结果及竞赛材料。

