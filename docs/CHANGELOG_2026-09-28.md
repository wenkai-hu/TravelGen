# 改动记录 · 2026-09-28

| | |
|---|---|
| 提交 | `33722d3` 参考图上传与排序：拖拽换序、顺序可交给 AI；项目页 401 不再吊死 |
| 分支 | `b-dev` → `origin/b-dev` |
| 规模 | 88 个文件（62 新增 / 25 修改 / 1 改名），+39841 / −453 |

行数里 **37317 行是 `experiments/results/` 的跑批快照**，真正的代码改动只有 2524 行。所以「88 个文件」听着吓人，实际要看的是这 **28 个源文件**：

```
backend/   constants.py  schemas.py  v1_router.py  requirements.txt
           pipeline/  ark_client.py  pipeline.py  validate.py  visual_rag.py
front/     index.html  package.json  package-lock.json
           src/  App.vue  main.js  theme.js  constants.js  api/index.js
                 styles/tokens.css
                 components/  CraftSlot.vue  SceneTypeSelector.vue  ThemeToggle.vue
                 views/  HomeView.vue  LoginView.vue  HistoryView.vue
                         ReferenceSelectView.vue  PlanConfirmView.vue  StoryboardView.vue
根目录     start.bat  .gitignore
```

这批改动是同一条线：**把「参考图」从首页贴 URL 改造成选图页的真·文件上传，并在确认前给用户一个排顺序的环节**——顺序要么自己排，要么交给 AI。顺带修掉了「后端一重启，项目页就吊死」的问题。

改动累计了好几轮才提交，所以本文按**功能**组织，不按时间。

---

## 一、参考图流程重构：首页 URL 面板 → 选图页真上传

### 为什么要改

首页工作台右下角原来有个「参考图片」槽位，是让用户**贴图片 URL** 的——这是开发者视角的入口，普通用户手里只有文件，没有 URL。而且那一步根本还不知道搜出来什么图，顺序也就无从谈起。

搬到选图页顺带解开一个原本够不着的约束：**顺序只有在选完之后才有意义**。

### 改了什么

**首页**（[HomeView.vue](../front/src/views/HomeView.vue)）
- 补充选项循环从 3 项减到 2 项（补充说明 / 模型选择），删掉 `assets` 面板
- `form.assets` 字段整体移除。后端 `GenerateRequest.assets` 保留默认值 `[]` 不删——**API 契约没动**，只是前端不再发它
- 完成度进度条：`assetsFilled` 那个 `+1` 在分子分母里**成对**出现，成对删掉后百分比不变，不会出现「删了功能进度条就跳」

**后端**
- 新增 `POST /api/projects/{pid}/reference-uploads`，收 `UploadFile`，复用 `visual_rag.cache_candidate()`（落盘到 `assets/references/{pid}/`、PIL 校验、12MB 上限、按内容 sha 命名），不需要新的静态路由
- 新增依赖 `python-multipart>=0.0.9`（FastAPI 收文件必需）
- 新增 `MAX_SELECTED_REFERENCES = 8` 到 [constants.py](../backend/constants.py)。**这是单一真源**：前端 `MAX_SELECTED`、`ConfirmReferencesRequest` 的上限、上传端点的额度校验都从它取
- 新增 `max_useful_references(target_s)`（[validate.py](../backend/pipeline/validate.py)），从 `shot_count_range` 里**纯提取**，行为不变。公式 `min(target_s // SHOT_MIN, max(1, round(target_s / 7)))`

### 两条设计约束

**额度公式只在后端一处。** `GET /api/projects/{pid}/references` 返回 `duration_cap` 和 `max_selected`，前端只读这两个数、不复制公式——否则时长规则一改，前后端就不同步了。界面上的提示要说清**理由**（「30 秒的片子一图一镜，最多用得上 4 张图」），而不是只甩一个数字。

**上传即入选，占额度。** 用户传的图直接进清单并占一个名额，所以上限就是 8；传第 9 张没有意义，直接提示拒绝。搜索勾选的图与上传的图在**同一个有序列表**里（不是分成两组——分组和「第 N 张配第 N 个镜头」的全局序号是冲突的），每项带序号徽标 + 来源徽标（我上传的 / 搜索勾选）区分来源。

---

## 二、确认清单：拖拽换序

点「下一步」**不发请求**，只切本地 phase（`reviewing`），排完顺序点「确认」才 POST。这样用户可以反复调，不产生中间状态。

### 为什么不用拖拽库

`sortablejs` / `vuedraggable` 及其传递依赖在全仓为零。原生 Pointer Events 够用，也避免为一个交互引一整套依赖。

### 手感是怎么做出来的

第一版做完用户反馈「太生硬，看不出在拖」。根因是**拖动途中就改数组顺序**——每越过一个边界卡片瞬移一次，而且被拖的那张自己没动。

改成「**拖动期间只做视觉，松手才提交**」，靠三件事撑起来：

1. **抓起来那张脱离布局**，用 `translate3d` 跟住指针。位移**必须无过渡**，否则卡片追不上指针，拖起来发飘；放大浮起用独立的 `scale` 属性（跟 `transform` 各走各的，互不打架）
2. **其余卡片整体让位**——按「要插到哪一格」算位移，**让位带过渡**，所以是滑开的不是跳开的
3. **松手才真正改数组**。改完按格距做一次位移补偿（`dragDx -= (over - from) * pitch`），让卡片视觉上停在原地不动，再把位移过渡回 0 → 看着就是「滑进格子」

### 踩过的坑（改动这里前务必看）

**拖动过程中绝对不能读 `getBoundingClientRect()`。** ref 更新到 DOM 落地之间隔着一帧，边拖边读会读到上一帧的位置，跟当前位移对不上，**越拖越偏**。更糟的是落点计算：`slotAtPointer` 原本从 `cards[0]` 的左边缘取基准，而拖动第 0 张时那就是**被抬起的那张**，基准会跟着指针一起跑，落点整个算错（实测拖到第 3 格被算成第 2 格）。

修法：**在「抓起来」那一刻量一次** `baseLeft` / `baseTop` / `originLeft`，拖动途中一次 DOM 都不读；只有边缘自动滚动（`edgeScroll`）按滚动增量调整这几个基准。

**触屏要跟横向滚动抢。** 手指一滑本来是想滚这一排，所以触屏必须**按住 220ms** 才算「抓起来了」；鼠标则是按下即拖。

**松手后的归位动画需要先逼一次 reflow**（`void cardNodes()[landed]?.offsetWidth`），否则浏览器可能把「换类」和「位移归零」并进同一帧，过渡根本不触发，卡片直挺挺闪回去。

### 键盘

卡片可聚焦，左右方向键走同一套位移逻辑，`aria-label` 说明当前位置。没有指针的用户不至于用不了。

---

## 三、顺序交给 AI

### 决策

用户不想自己排时，**在哪一步决定哪张图配哪个镜头**？选的方案是：**生成分镜时逐镜头挑**。

理由是那时模型已经知道每个镜头要拍什么（主体、机位、景别），有条件按内容把最合适的那张配过去。如果改成「确认时就定死」，模型还没写分镜，只能按图片自身的标签瞎配。

### 交互

一排缩略图**上方**一个两态开关：「我自己排 ⇄ 让 AI 排」。切到 AI 时：

- 缩略图**还在**（还能删、还能加）——AI 只管顺序，不管用哪几张
- 但**不能拖**：`onCardPointerDown` 与 `moveItem` 双双短路，`cursor` 从 `grab` 变默认，序号徽标隐掉，`tabindex=-1`（键盘也够不到）
- 提示文案整体改口，不再说「第 N 张配第 N 个镜头」

选「开关 + 变灰」而不是「隐藏整排」，是为了不让人以为功能消失了。

### 后端

- `ConfirmReferencesRequest.auto_order: bool = False`；确认时记进 `project.request["auto_order"]`，分镜阶段读它
- 约束 9 拆成三段（[pipeline.py](../backend/pipeline/pipeline.py)）：`ORDER_RULE_BY_USER` / `ORDER_RULE_BY_AI` / `ORDER_RULE_COMMON`，由 `order_rule(auto_order)` 拼装
  - 自己排 = 照目录顺序一一对应，并**据此反向编排每个 Shot 的画面**
  - 交给 AI = 「对照每个 Shot 的主体、机位、景别与各张图的可见元素，把最贴题的那张配给最能发挥它的 Shot」
  - **唯一性是两种口径共用的硬约束**：每张图全片最多出现一次，不因交给 AI 就放宽
- 兜底（[visual_rag.py](../backend/pipeline/visual_rag.py)）：新增 `_best_unused()`。auto 模式下模型漏挑的按**内容相关性**补（而不是按位置补）；同分时按目录先后取，**保证结果可复现**——同样的输入不会每次跑出不同的绑定
- 非 auto 模式的兜底改成**按位置**取第一张未占用的图，不再按语义打分。顺带修掉一个现存脆弱点：原来的打分兜底要求分数 > 0，否则报「可用参考图不足」的假失败

`_catalog_score` **没有删**——`grounding_strength` 还在用它，那是给下游看「这张图跟这个镜头贴不贴」的质量信号，与绑定顺序是两件事。

### 实测对照

同一组镜头、同一份目录，只有开关不同：

```
manual: ['ref_aaa', 'ref_bbb', 'ref_ccc']   ← 按位置一一对应
auto  : ['ref_ccc', 'ref_bbb', 'ref_aaa']   ← 按内容（灯火→夜景图，荷叶→特写图，远景→湖面图）
```

---

## 四、修复：后端一重启，项目页就吊死

`db/auth.py` 的 `SESSIONS` 是**内存 dict**，所以每次重启后端，所有人的 token 立即失效。而三个项目页对 401 的处理都是错的：

| 页面 | 原来的行为 |
|---|---|
| [StoryboardView.vue](../front/src/views/StoryboardView.vue) | **完全静默吞掉**（只处理 404）。页面永远转圈，不报错也不跳转 |
| [PlanConfirmView.vue](../front/src/views/PlanConfirmView.vue) | 当成「瞬时网络抖动」，**无限重试**，只提示一次「查询项目状态失败，自动重试中…」 |
| [ReferenceSelectView.vue](../front/src/views/ReferenceSelectView.vue) | 同样无限重试，提示「获取参考图片失败」 |

401 重试一万次还是 401。现在三个页面统一：**停轮询 → 清 session → 跳 `/login` → 说明「登录已失效（后端重启会清空登录态）」**。

> 注意：用户看到的「报错 500」未必是后端报的。后端没在跑时，**Vite 开发代理**连不上上游会返回 500，那个 500 的意思是「后端不见了」。

---

## 五、主题切换（浅色 / 深色）

- [theme.js](../front/src/theme.js)：`theme` 是 `ref`，切换时写 `<html data-theme>`，CSS 变量跟着换值。localStorage 的读写都包了 `try/catch`——隐私模式下 storage 被禁不能把整个应用搞崩
- [index.html](../front/index.html)：**首屏防闪的内联脚本**。必须在样式表生效前定好主题，否则深色用户会先闪一下白。判定规则要与 `theme.js` 的 `readStored()` **保持一致**，改一个记得改另一个
- [App.vue](../front/src/App.vue)：`lightOverrides` / `darkOverrides`。浅色顺带补了状态色——原先没设，`NAlert type="info"` 会漏出 naive 默认蓝 `#2080f0`、报错文案漏出玫红 `#d03050`，是全项目仅有的两个体系外颜色。深色必须把基础表面色一并覆盖，否则 naive 自带的冷灰跟暖墨底明显撞色
- [tokens.css](../front/src/styles/tokens.css)：+268 行，深色变量与新语义变量
- [ThemeToggle.vue](../front/src/components/ThemeToggle.vue)：图标显示的是「点下去会切到哪一边」

**默认浅色，不跟随系统。**

---

## 六、图标系统：emoji → Phosphor

全站图标从 emoji / 自建 iconfont 统一到 `@phosphor-icons/vue`。

- `main.js` 删掉 iconfont 的 CSS 引入
- [constants.js](../front/src/constants.js)：场景类型的 `emoji` 字段改成 `icon`，值是**组件**，渲染用 `<component :is="s.icon" />`
- [CraftSlot.vue](../front/src/components/CraftSlot.vue)：`icon` prop 类型从 `String` 改成 `Object`——**这是个破坏性改动**，所有传 `icon` 的地方都要跟着改成传组件
- 顺带把硬编码的颜色（`#fff`、`rgba(...)`）换成 token 变量，主题切换才能覆盖到

---

## 七、其他

**ark_client 网络层分层**（[ark_client.py](../backend/pipeline/ark_client.py)）
- 新增 `NetworkError`：网络层异常（SSL EOF / 超时 / 连接重置）与业务失败**区分开**——前者稍后重试即可，后者重试也没用
- 新增 `submit_safe` / `get_task_safe`：批次里**一条片段的网络抖动不应该让整批生成失败**；`get_task_safe` 把网络错误按「仍在进行」返回，让轮询继续（由轮询上限兜底）
- 坑：`HTTPError` 是 `URLError` 的**子类**，必须先 catch

**`.gitignore`**
- `experiments/config.json.*`：防住 `config.json.bak` 这类变体。**`experiments/config.json` 含真实 API key，绝不提交**
- `/*.pdf` 和 `/报名材料/`：竞赛材料不随代码库走（前导斜杠锚定根目录，不误伤别处 PDF）
- `*.mp4` 是**早已存在**的规则，无斜杠模式匹配任意层级，所以 `experiments/results/03_video/` 下 117MB 的对比实验视频本来就没入库，该目录只进了 1 个新的小 CSV（外加把 `experiments/03_video/README.md` 挪到 `experiments/results/03_video/03_video/`，内容没动，就是上面那个「1 改名」）

**`start.bat`**（新增，94 行）：一键启动，给新同学用。流程是：体检（python / npm / 依赖 / `config.json`）→ 必要时 `net start MySQL84` → 释放 8000/5173（**只杀本项目的那两个进程名**，被别的程序占用就报错退出，不乱杀）→ 起前后端 → 轮询等前端就绪再开浏览器。`start.bat check` 只体检不启动，排查「为什么起不来」时用。

> 改这个文件注意两条：**必须存 GBK 编码**（文件开头用 `chcp 936` 把控制台代码页对齐到文件自身的编码）；**`rem` 注释里不能出现 `>`**，会被当成重定向。

**数据快照**：`experiments/results/05_pipeline/` 下 58 个 JSON 快照入库（该目录现有 137 个）。这是**一直在攒的跑批留痕**——每建一个项目、每跑一个 segment/render 任务就落一个 JSON，所以每次提交都会带上一批。按 `.gitignore` 第 35 行的约定，该目录的 `.md/.csv/.json` 文本结果要提交（可复现），只排除视频音频。

---

## 验证情况

> ⚠️ 下面三个脚本在 `backend/tests/` 下，而**该目录已停止跟踪**（见 `0c34bb2`，`.gitignore` 第 51 行），所以仓库里没有它们——这份记录得配合本地那份测试代码看。是否要把测试重新纳入版本管理，值得单独决定一次。

| 脚本（`backend/tests/`） | 覆盖 | 结果 |
|---|---|---|
| `test_reference_upload_ui.py` | 上传/配额、候选池勾选、一行布局、拖拽中途与归位、键盘换位、增删、AI 开关 14 项、夜间模式、确认后落库顺序 | **60 / 60** |
| `test_reference_order_unit.py` | 绑定口径 A/B 对照、模型显式挑选、图不够报错、唯一性 | **19 / 19** |
| `test_auth_expiry_ui.py` | 三个页面登录失效后跳转、清 token、文案；含「有效 token 不会被踢」反证 | **10 / 10** |

另外：`npm run build` 通过；UI 实跑全程零页面级 JS 报错、零自家接口失败（过滤掉了外站图源的 502——搜到的图源本来就时好时坏，与本项目无关）。

浏览器验证用 `p.chromium.launch(channel="msedge")`：**playwright 下载 chromium 会静默卡死**，直接用系统 Edge。

---

## 遗留与已知限制

1. **触屏长按拖拽没有在真机验过**——只有鼠标路径被完整测试。另外如果浏览器已经开始横向滚动，再长按也抢不回来
2. **排序页未确认前刷新会丢本地态**：开关回到「我自己排」，已勾选的搜索图也会丢（`selectedIds` 不落浏览器存储，是既有行为）。确认之后就跟着项目走了
3. **改 `backend/` 下任何 `.py` 都会触发热重载并清空登录态**，包括 `backend/tests/` 里的测试脚本。`uvicorn.run(..., reload=True)` 没配 `reload_excludes`，盯的是整个 `backend/`。想避免的话可以加上排除目录
4. 上传的图与手动勾选的候选，在刷新后靠服务端 `provider === "user"` 标记恢复；搜索勾选的图本来就会丢（现状，本次未动）
