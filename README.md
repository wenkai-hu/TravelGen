# TravelGen：基于多智能体协同与知识增强的浙江文旅AIGC城市短视频自动生成平台

面向浙江文旅传播场景的 AIGC 城市短视频自动生成平台，采用"多智能体（Multi-Agent）+ 知识增强（RAG）+ 多模态生成（Multimodal AIGC）"整体架构，根据用户输入自动完成 文案→脚本→分镜→AI图片→AI视频→配音→背景音乐→自动合成 的一站式流程。

赛题：中国移动杯·第二届浙江省大学生人工智能竞赛 **JBGS-2026-01**《面向浙江文旅传播的AIGC城市短视频自动生成系统》

## 团队分工

| 成员 | 角色 | 职责 |
|---|---|---|
| 成员A | AI算法负责人 | 文献调研、多模态模型、Prompt工程、Multi-Agent、RAG、脚本/分镜生成、Benchmark实验、技术报告算法部分 |
| 成员B | 系统负责人 | 系统架构、前后端、视频合成、数据管理、UI、部署、演示视频、PPT |

**协作规范请先阅读 [docs/COLLABORATION.md](docs/COLLABORATION.md)**（分支/提交/大文件/密钥安全）

## 目录结构

```
├── docs/                  # 阶段文档（调研报告、交接方案、实验报告…）
├── survey/                # 调研表（GithubSurvey.xlsx 等）
├── experiments/           # Phase 3 Benchmark 实验（脚本+Prompt+结果）
├── papers/                # 论文资料
├── backend/               # 后端（Phase 5+）
├── frontend/              # 前端（Phase 5+）
├── models/                # 模型相关（Phase 5+）
├── assets/                # 素材（大文件不入库，见 .gitignore）
├── demo/                  # 演示材料（Phase 6+）
└── README.md
```

## 阶段进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 项目规划 | ✅ |
| Phase 1 | 文献调研（RelatedWork.md / ReadingNotes.md / Product Benchmark） | ✅ 调研完成 |
| Phase 2 | GitHub调研（GithubSurvey.xlsx） | ✅ |
| Phase 3 | Benchmark（experiments/） | 🔄 进行中 |
| Phase 4 | 系统设计 | ⏳ |
| Phase 5-8 | 开发/平台/实验/材料 | ⏳ |

## 关键文档速览

- [需求文档](TravelGen：基于多智能体协同与知识增强的浙江文旅AIGC城市短视频自动生成平台.md)
- [文献调研报告](docs/RelatedWork.md) ｜ [阅读笔记](docs/ReadingNotes.md)
- [GitHub调研表](survey/GithubSurvey.xlsx)
- [Phase 3 交接与协作方案](docs/Phase3_Handoff_Plan.md) ｜ [Phase 3 实验操作指南](experiments/README.md)
