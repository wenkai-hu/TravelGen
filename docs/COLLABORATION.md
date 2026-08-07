# TravelGen 团队协作规范（成员A / 成员B）

> 目标：2人小团队也能安全、高效、不踩坑地共用 GitHub 仓库。**读完本文件再动手提交。**

## 1. 仓库与托管

- **主仓库**：GitHub（私有仓库，功能最全：PR/Issues/Projects/免费私有）
- **备选**：若 GitHub 访问不稳定，可用 **Gitee（码云）** 作镜像：push 到 GitHub 后手动同步到 Gitee，或直接以 Gitee 为主仓（团队在国内，Gitee 速度更稳；比赛材料提交也在国内环境，二选一即可，**不要两头各改各的**）

## 2. 分支策略（2人简化版 GitHub Flow）

```
main            ← 始终可用的主分支（永远不直接改！）
  ├── a-dev     ← 成员A的开发分支
  └── b-dev     ← 成员B的开发分支
```

- **日常开发**：在 `main` 上 `git pull` 拉最新 → 在**自己的分支**上写代码 → push 自己的分支 → 合并到 main
- **合并方式**（2人简化）：
  - 双方互相看过代码后合并（A合并自己分支时 B 有空就瞄一眼，反之亦然）
  - 或开启 GitHub 的 **分支保护**（Settings → Branches → 要求PR合并），适合阶段交付物合并时用
- **谁负责哪些目录，尽量不互相改**（减少冲突）：

| 目录 | 主要归属 |
|---|---|
| docs/、survey/、experiments/、papers/、models/ | A |
| backend/、frontend/、demo/、assets/ | B |
| README.md、.gitignore、根配置 | 双方（改前打招呼） |

## 3. 提交规范

**提交时机**：每天结束前 push 一次（防止代码丢失）；实验/文档每完成一项提交一次。

**提交信息格式**（简洁，中文说明即可）：
```
类型(范围): 说明
示例：
feat(script): 新增 Phase3 文案对比执行脚本
fix(judge): 修复分镜JSON校验误判
docs(survey): 补充Seedance系列调研
test(backend): 增加视频合成接口单元测试
```
类型：feat / fix / docs / test / refactor / chore

**禁止事项**：
- ❌ 提交 `config.json`（含API Key）——.gitignore 已排除，push 前确认 `git status` 无它
- ❌ 提交大视频/音频文件（>50MB）——走网盘（见第5节）
- ❌ 一次提交塞入大量无关改动

## 4. 日常协作流程（每天）

```bash
# 开工前
git checkout main && git pull        # 拉最新
git checkout a-dev && git merge main # 同步到自己的分支

# 开发中
... 写代码 ...

# 收工前
git add <具体文件>                   # 不要 git add .
git commit -m "feat(xxx): 说明"
git push origin a-dev                # push 自己的分支
git checkout main && git merge a-dev # 合并（2人简化流程）
git push origin main
```

**冲突处理**：两人改到同一文件时先沟通谁改哪段；合并冲突时用 VS Code 的合并编辑器解决，解决后 `git add + commit`，**不要慌，解决冲突是正常的**。

## 5. 大文件与素材策略（重要）

- **视频/音频/大图/数据集一律不入库**（GitHub 单文件限制 100MB，仓库体积膨胀后 clone 很慢）
- 统一放 **网盘**（阿里云盘/百度网盘），在对应文档里写"文件名+链接+版本日期"
  - 例如 `experiments/results/03_video/样片链接清单.md` 里列各通道样片链接
- 可选：项目后期（Phase 8 演示素材多）再上 **Git LFS**（`git lfs track "*.mp4"`）
- `.gitignore` 已排除常见大文件后缀，push 前留意提示

## 6. 安全红线

| 事项 | 做法 |
|---|---|
| API Key / Token | 只存在 `experiments/config.json`（已gitignore）；需要给B用就私聊发，**永不提交、永不发群文件** |
| 泄露处置 | 一旦发现 Key 进了仓库历史 → 立即去对应平台**作废重建 Key**，再删文件 |
| 网盘链接 | 含Key的配置文件不要传网盘公共链接 |

## 7. 任务管理（GitHub Projects 看板）

建议在 GitHub 仓库开一个 **Projects 看板**（或直接用仓库 Issues），三列：
```
To Do（待办）→ In Progress（进行中）→ Done（完成）
```
每条任务：负责人 + 对应 Phase + 交付物名。例：
- [ ] Phase 3 视频API账号开通（B，D5前）
- [x] Phase 3 统一Prompt定稿（A，D1）
- [ ] Phase 3 Experiment Report（A，D7）

**每周一短会**：过一遍看板 + 锁阶段交付物版本（每次会议在 `docs/meeting-notes/` 记一行：日期、结论、待办）。

## 8. 阶段交付物管理

- 每个 Phase 完成时：**打 tag**（例：`v0.1-phase1-2`、`v0.2-phase3`），比赛材料/报告可直接引用版本号
- 关键决策（选型结论、Prompt定稿、Schema定稿）在对应文档顶部写"定稿日期+版本号"，改动时升级版本号

## 9. 提交前 Checklist

- [ ] `git status`：没有 config.json / 大文件 / 意外文件
- [ ] 提交信息符合规范
- [ ] 代码在自己分支上自测过（脚本能跑通）
- [ ] 文档类改动：链接路径正确、没有泄露密钥
