# TravelGen 后端数据流

按阶段记录"输入 → 中间结构 → 输出"的真实形状，字段名与代码一一对应。
当前覆盖：**阶段①② 参考图（搜图 → 用户确认 → 下载缓存 → VLM → 视觉档案）**。
plan / copy / shot / Seedance / 合成各段待补。

状态机字段是 `Project.status`（[projects.py](projects.py)），本段涉及：
`searching_references → waiting_reference_confirm → analyzing_references → planning → waiting_confirm`。

---

## 阶段① 搜图（千帆，只出候选）

| 环节 | 位置 |
|---|---|
| 入口 | `POST /api/projects` → [v1_router.py:400](v1_router.py#L400) |
| 异步协程 | [_run_reference_search](v1_router.py#L301) |
| 检索实现 | [reference_search.search_images](pipeline/reference_search.py#L55) |
| 结果解析 | [reference_search._extract_images](pipeline/reference_search.py#L11) |

**请求关键词 = 城市 + 地点 + 固定后缀「实景 风景」，空格拼接**（[reference_search.py:60](pipeline/reference_search.py#L60)）：

```python
query = " ".join(part for part in (city, location, "实景 风景") if part)
# 例：「杭州 西溪湿地 实景 风景」
```

请求体（OpenAI 兼容端点，`base_url + /web_search`）：

```json
{"messages": [{"content": "杭州 西溪湿地 实景 风景", "role": "user"}],
 "search_source": "baidu_search_v2",
 "resource_type_filter": [{"type": "image", "top_k": 30}]}
```

- `top_k` = `clamp(入参 or provider.top_k or 30, 1, 30)`
- 解析只认 `references[].type == "image"` 的 `image.url`；该字段为空时兜底取 `references[].web_extensions.images[].url`（部分结果把图挂在网页结果下）
- 同 URL 去重；`candidate_id = "ref_" + sha256(image_url)[:16]`
- **此阶段不下载图片、不判断地点真伪**，只产出候选

用户创建项目时自带的图（`request.assets[].url`）也登记为候选，但走另一条构造：[visual_rag.candidate_from_user_asset](pipeline/visual_rag.py#L28)，`provider="user"`、`title="用户提供的参考图"`，与搜索结果按 URL 去重合并（[v1_router.py:316](v1_router.py#L316)）。

候选落库 `Project.reference_candidates`，真实样例（`experiments/results/05_pipeline/projects/p_20260923_121945_d0da6f.json`）：

```json
{"candidate_id": "ref_6b7708fe8c5e669d",
 "query": "杭州 西溪湿地 实景 风景",
 "image_url": "http://aigc-image.bj.bcebos.com/miaobi/.../0.png",
 "title": "🌳探秘杭州西溪湿地🌿",
 "source_page_url": "http://mbd.baidu.com/newspage/data/dtlandingsuper?nid=dt_4375238706611860670",
 "provider": "qianfan_image_search"}
```

一条都没有 → 整个项目 `failed`（[v1_router.py:326](v1_router.py#L326)）。

---

## 阶段② 确认 → 下载缓存 → VLM 逐图观察

| 环节 | 位置 |
|---|---|
| 入口 | `POST /api/projects/{pid}/references/confirm` → [v1_router.py:444](v1_router.py#L444) |
| 异步协程 | [_run_reference_analysis](v1_router.py#L338) |
| 下载缓存 | [visual_rag.cache_candidate](pipeline/visual_rag.py#L59) |
| VLM 调用 | [vlm_client.analyze_image](pipeline/vlm_client.py#L73) |
| 提示词 | [VISUAL_OBSERVATION_PROMPT](pipeline/vlm_client.py#L13) |
| 档案汇总 | [visual_rag.build_visual_profile](pipeline/visual_rag.py#L121) |

入参 `reference_ids`：**1–8 张**（[schemas.py:34](schemas.py#L34)），必须是上一阶段候选里的 `candidate_id`。
`asyncio.Semaphore(3)` 并发，每张图两步：

**① 缓存**（`cache_candidate`）——只允许 http/https；45s 超时；单图 ≤12MB；PIL `verify()` 校验可解析；
落盘 `assets/references/{project_id}/{asset_id}.{ext}`，`asset_id = "ref_" + sha256(图片内容)[:16]`（**按内容哈希，与 URL 无关**，同图不同 URL 会去重）。
`place_id = "place_" + sha256("city|location")[:16]`，同一城市+地点的所有图共享一个 place_id。

**② VLM 看图**——见下。

单图失败不致命：进 `analysis_failures`；全部失败才 raise（[v1_router.py:375](v1_router.py#L375)）。

### VLM 的输入

**只有一个 user message，没有 system，也没有任何行程上下文**：

```json
{"model": "doubao-seed-2-1-turbo-260628",
 "messages": [{"role": "user", "content": [
   {"type": "text", "text": "<VISUAL_OBSERVATION_PROMPT 全文>"},
   {"type": "image_url", "image_url": {"url": "data:image/webp;base64,...", "detail": "high"}}]}],
 "thinking": {"type": "disabled"},
 "temperature": 0.1,
 "max_completion_tokens": 1600}
```

关键设计：**没有把 city / location / 用户描述传给 VLM**。模型只知道"有一张图"，不知道是哪里，
所以它无法顺着用户暗示断言地名——`uncertain` 里必然出现"地点名称无法确认"。
地点名只能靠图里真正可见的文字（如景观石上的"西溪国家湿地公园"）读出来。

provider 配置来自 `experiments/config.json` 的 `providers[vlm]`（[model_client.load_vlm_config](pipeline/model_client.py#L77)），走方舟而非千帆。

### VLM 的提示词

`VISUAL_OBSERVATION_PROMPT`（[vlm_client.py:13-43](pipeline/vlm_client.py#L13)）三条禁令 + 一个 JSON 骨架：

1. 不根据文件名、用户暗示或常识断言具体地点；无法从画面确认的地名进 `uncertain`
2. 不编造建筑年代、历史事件、精确地理位置、不可见区域
3. 只输出严格 JSON，不要代码块

输入图片是 base64 data URI，单条消息一次调用一张图（不做多图对比）。

### VLM 的输出

模型 `content` 是 JSON 字符串 → `_extract_json` 剥 ``` 包裹后 `json.loads` → 外层包元数据（[vlm_client.py:114](pipeline/vlm_client.py#L114)）：

```json
{"model": "doubao-seed-2-1-turbo-260628",
 "prompt_version": "visual_observation_v1",
 "elapsed_s": 14.813,
 "usage": {"prompt_tokens": 1736, "completion_tokens": 733, "total_tokens": 2469},
 "analysis": { ...15 个字段，见下... }}
```

整包存进 `asset["observation"]`，`asset["analysis_status"] = "completed"`。

`analysis` 的 15 个字段（真实样例，杭州西溪湿地一张航拍图，已省略部分数组项）：

```json
{"summary": "高空俯瞰视角下的大面积湿地景观，区域内水网密布，植被繁茂…",
 "visible_elements": ["大面积茂密的绿色植被", "交错分布的蓝绿色水系河道与湖泊", "多组低层现代风格建筑", "林间的小型步道"],
 "spatial_layout": ["水系在画面中下部及中部交错环绕，将植被区域分割为多个岛状地块",
                    "城市建筑群位于画面远方的地平线上，横亘在湿地与远山之间"],
 "architecture_and_materials": ["建筑多为2-4层的低层建筑，造型偏现代简约", "建筑外墙以浅灰、白色调为主"],
 "viewpoint": {"camera_position": "高位", "angle": "俯视", "shot_size": "远景",
               "orientation_clues": ["画面下方为近景湿地区域，上方为远方城市与山峦"]},
 "lighting_weather_season": {"time_of_day": "白天，光线充足，推测为上午或下午",
                             "weather": "晴朗，有少量零散云朵",
                             "season": "植被繁茂呈深绿、鲜绿色，推测为夏季或春末夏初"},
 "must_keep_candidates": ["水网环绕植被岛的湿地整体格局", "中下部集中的几组低层建筑的布局与形态",
                          "远方城市建筑群与湿地的层次关系"],
 "allowed_changes": ["天空中云朵的形态与位置", "水面的波纹与光影动态", "步道上的行人动态"],
 "suitable_shots": ["高空大远景航拍推进镜头，展现湿地整体风貌到远方城市的层次",
                    "环绕中下部建筑组的航拍环绕镜头"],
 "unsupported_or_risky_shots": ["建筑内部空间的镜头", "湿地背面、被植被完全遮挡区域的镜头",
                                "近距离仰视建筑的特写镜头"],
 "visible_text": [],
 "uncertain": ["湿地的具体名称与所在城市", "建筑的具体功能与名称", "远方城市与山峦的具体名称"]}
```

字段的下游消费方：

| 字段 | 去向 |
|---|---|
| `must_keep_candidates` | → `stable_features` / `must_keep` → 最终拼进 Seedance 的"必须保持：…" |
| `allowed_changes` | → `allowed_changes` → 拼进"允许改变：…" |
| `unsupported_or_risky_shots` | → 图级进 `view_catalog`，地点级取交集进 `unsupported_shots` |
| `suitable_shots` / `viewpoint` | 只进 `view_catalog`，用作分镜绑图的打分依据（[_catalog_score](pipeline/visual_rag.py#L195)） |
| `visible_elements` | → 档案 `visible_elements`，进 planner / copywriting 的 grounding 块 |
| `uncertain` | → 档案 `uncertain`，提示词里声明"不得当作事实" |
| `summary` / `spatial_layout` / `architecture_and_materials` / `lighting_weather_season` | 只进 `view_catalog` |
| `visible_text` | **无人消费**（白提；地点名靠它读到也没往下传，最终靠 `must_keep_candidates` 兜住） |

### 绑定：VLM 输出 ↔ 图片（三层，没有 ID 映射表）

**绑定① 同一次调用内就地写键**（[v1_router.py:352-361](v1_router.py#L352)）：

```python
asset = await asyncio.to_thread(visual_rag.cache_candidate, project.project_id, candidate, city, location)
asset["observation"] = await asyncio.to_thread(vlm_client.analyze_image, provider, asset["local_path"])
asset["analysis_status"] = "completed"
```

`analyze_image(provider, image_path)` 的签名里**没有 asset_id / candidate_id**——VLM 根本不知道自己在分析哪张候选图。
运行期唯一的关联键是 `local_path`："这张图的分析结果"= "这个 asset 字典上的 `observation` 键被赋值"。

**绑定② `gather` 之后按位置回收**（[v1_router.py:366-374](v1_router.py#L366)）：
`asyncio.gather` 保证返回顺序 = `selected` 顺序 = 用户 `reference_ids` 顺序（[v1_router.py:450](v1_router.py#L450) 用 `dict.fromkeys` 保序去重），
再 `zip(selected, results)` 把候选和资产配回去——`candidate_id` 在这里只用于报错。
去重是**按图片内容**（`asset_id = sha256(bytes)`）：两张候选指向同一张图时第二张直接丢掉，
但它不算失败，`failures` 里那条 `error` 是 `None`，会以"error 为 null 的条目"出现在 `analysis_failures` 里。

**绑定③ 汇总时按 `asset_id` 展开**（[build_visual_profile:126-153](pipeline/visual_rag.py#L126)）：
`aid` 只写进两处，这是档案里仅有的带得动回指的结构——

- `stable_features[].evidence_asset_ids = [aid]` → **一条特征 ↔ 一张图**（最细粒度）
- `view_catalog[].asset_id = aid` → **一整张图的全部观测 ↔ 这张图**

而 `_unique` 拼出来的 `visible_elements / allowed_changes / uncertain / must_keep` 是**扁平投影，证据链在这一步断了**：
档案说"带顶棚的木质摇橹船必须保持"，但没人知道它出自哪张图。`must_keep` 只能靠 `stable_features` 反查
（[visual_rag.py:167](pipeline/visual_rag.py#L167) 正是从这个列表投影出来的）。

档案的稳定主键是两个：`place_id`（city|location 哈希）+ `reference_asset_ids`（成功图，顺序 = 用户勾选顺序），
profile 其余字段都是这两者的一张投影表。`reference_version += 1`（[v1_router.py:382](v1_router.py#L382)）用于让上游产物失效——
分镜、生成任务、合成任务的快照里都带 `reference_version`。

### 地点级禁区为什么会是空的

`unsupported_shots` 取**所有图的字面交集**（[visual_rag.py:155-157](pipeline/visual_rag.py#L155)）：

```python
unsupported = ([risk for risk in risk_lists[0]
                if all(risk in other for other in risk_lists[1:])]
               if risk_lists else [])
```

两个性质叠加导致它实际上是死字段：

1. 候选只能来自**第一张图**的条目（`risk_lists[0]` 是唯一的迭代源）
2. 判等是**字符串精确匹配**，而 VLM 每张图独立自由表述，同一语义几乎不可能同字面

真实数据（`p_20260923_121945_d0da6f`，4 张图各 4/4/4/5 条 risk，全部落空）：

```
[ref_3199…] 建筑内部空间的镜头 / 湿地背面、被植被完全遮挡区域的镜头 / 近距离仰视建筑的特写镜头
[ref_cfeb…] 景观石后方区域的穿越镜头 / 俯瞰整个公园的高空俯视镜头 / 景观石背面的展示镜头
[ref_d7b6…] 高空俯视整个河道全貌的镜头 / 进入船只内部的特写镜头 / 河道尽头未知区域的镜头
[ref_2d44…] 建筑内部的视角镜头 / 大树顶部的俯视镜头 / 环绕建筑360度的运动镜头
```

注意第一、四张语义几乎同一条（禁建筑内部），字面却是「建筑内部**空间的镜头**」vs「建筑内部**的视角镜头**」→ 交集空。
扫描全部 29 个项目：13 个有 `view_catalog` 的项目里，`unsupported_shots` **非空数为 0**。

后果要分开看，别一棍子打死：

| 层 | 是否起作用 |
|---|---|
| 地点级 `unsupported_shots` | 空转——planner/copywriting 提示词里"不得规划 unsupported_shots 中的画面"没有内容可约束 |
| 图级 `view_catalog[].unsupported_or_risky_shots` | **有效**：分镜提示词带 catalog，模型能看见每张图的禁区 |
| Shot 上的 `shot["unsupported_or_risky_shots"]` | 由绑定图取值写入（[visual_rag.py:248-252](pipeline/visual_rag.py#L248)），但**只被旧链路读**（[compile_shot_input:275](pipeline/visual_rag.py#L275)）；现流程走的 [compile_segment_input](pipeline/visual_rag.py#L286) **不读这个字段** → 风险不进 Seedance prompt |

---

## 视觉档案 visual_profile（4 张图的汇总样例）

`build_visual_profile` 只收 `analysis_status == "completed"` 的图（[visual_rag.py:123](pipeline/visual_rag.py#L123)），
输出 `profile_version = "place_visual_profile_v1"`，落库 `Project.visual_profile`：

```json
{"profile_version": "place_visual_profile_v1",
 "place_id": "place_54ce759a1f38be91", "place_name": "西溪湿地", "city": "杭州",
 "reference_asset_ids": ["ref_3199fab57ff00f59", "ref_cfeb6723ad89f004",
                         "ref_d7b6379dfb7ac016", "ref_2d44f58bbf73bc48"],
 "user_verified_place_identity": true,
 "visible_elements": ["大面积茂密的绿色植被", "青绿色河道", "带顶棚的木船", "..."],
 "stable_features": [{"text": "水网环绕植被岛的湿地整体格局",
                      "evidence_asset_ids": ["ref_3199fab57ff00f59"],
                      "strength": "image_observed"}],
 "must_keep": ["水网环绕植被岛的湿地整体格局", "刻有“西溪国家湿地公园”字样的棕褐色景观石主体", "..."],
 "allowed_changes": ["天空中云朵的形态与位置", "船上乘客的数量、姿态", "..."],
 "unsupported_shots": [],
 "uncertain": ["湿地的具体名称与所在城市", "无法确认该地点是否为真实的西溪国家湿地公园主入口", "..."],
 "view_catalog": [{"asset_id": "ref_3199fab57ff00f59", "summary": "…", "viewpoint": {...},
                   "suitable_shots": [...], "unsupported_or_risky_shots": [...]}],
 "analysis_failures": []}
```

汇总规则：

- `stable_features` 保留**逐条证据来源**（`evidence_asset_ids` + `strength="image_observed"`），`must_keep` 是它的纯文本投影（限 20 条）
- `visible_elements` / `allowed_changes` / `uncertain` 跨图去重拼接（限 30 / 15 / 15 条），**不标注来自哪张图**
- `unsupported_shots` 是**所有图的字面交集**，实测永远为空，详见上文「地点级禁区为什么会是空的」
- `user_verified_place_identity` 只要有图分析成功就是 true（用户勾选 = 身份背书）

### 给 LLM 的两种投影

[grounding_for_prompt](pipeline/visual_rag.py#L175) 把档案压成 JSON 文本注入提示词，有两档：

| 档位 | 字段 | 用在哪 |
|---|---|---|
| 默认 | place_id / place_name / city / visible_elements / stable_features / must_keep / allowed_changes / unsupported_shots / uncertain | copywriting 提示词（不含 catalog，省 token） |
| `include_catalog=True` | 上面 9 个 + `view_catalog`（逐图机位与可支持镜头） | planner、storyboard 提示词 |

没有任何参考图时返回一句硬约束：
`（用户尚未确认可用的实景参考图；不得编造特定地标外观或不受支持的机位。）`

注意：运维字段（`elapsed_s` / `usage` / `analysis_failures`）**不进提示词**，只留在项目 JSON 里。

---

## 本段已知缺口

- `visible_text` VLM 提了但后端不消费（[vlm_client.py:41](pipeline/vlm_client.py#L41) 是唯一出现处）
- `lighting_weather_season`（时间/天气/季节）只到 `view_catalog`，分镜提示词的约束里没有对应项，LLM 写 `scene.time` 时看不到参考图的真实光线
- "不得把 uncertain 当事实"只写在提示词里，**没有代码校验**；三处注入都靠模型自觉
- VLM 单图调用不做多图对比，同一地点不同视角的矛盾（如 A 图说平视、B 图说俯视）不会被发现，只是并列进 catalog
- `stable_features[].evidence_asset_ids` 是唯一的逐条证据链，但**没有任何代码校验或消费**：planner 提示词要求大纲每段回填 `evidence_asset_ids`（[pipeline.py:29](pipeline/pipeline.py#L29)），后端只把它拼进下一段提示词（[pipeline.py:506](pipeline/pipeline.py#L506)），从不检查 ID 是否存在、是否对得上 `visual_targets`
- 内容相同的两张候选图会被静默去重，并在 `analysis_failures` 里留下 `error: null` 的条目，与真实失败混在一起（[v1_router.py:373](v1_router.py#L373)）
- 图级 `unsupported_or_risky_shots` 止步于 `shot` 字段，现流程的 Seedance 编译不读它（见上文表格）
