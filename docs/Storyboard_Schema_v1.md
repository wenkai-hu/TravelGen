# 分镜 JSON Schema 契约 — v1（定稿）

**定稿日期**：2026-08-05｜**定稿依据**：Phase 3 实验2 最优输出（kimi-k2.6，`experiments/results/best_storyboard.json`）
**作用**：Phase 5 Storyboard Agent 的输出契约，也是 Video Composer（成员B）解析分镜、生成视频任务的**唯一接口**。双方以此字段为准，改动需升级版本号并知会对方。

## 1. 顶层结构

```json
{
  "theme": "string  视频主题（如：杭州西湖宣传片）",
  "scenes": [ { "scene_id": int, "location": "string", "time": "string", "shot_list": [ ... ] } ]
}
```

## 2. 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `theme` | string | ✅ | 视频主题，用于标题/封面 |
| `scenes[].scene_id` | int | ✅ | 场景编号，从 1 递增 |
| `scenes[].location` | string | ✅ | 场景地点（如：西湖湖面） |
| `scenes[].time` | string | ✅ | 场景时段（清晨/上午/午后/黄昏/入夜） |
| `scenes[].shot_list[].shot_id` | int | ✅ | 镜头编号，全局从 1 递增 |
| `scenes[].shot_list[].duration_s` | int | ✅ | 镜头时长（秒） |
| `scenes[].shot_list[].camera.type` | string | ✅ | 机位类型（航拍/无人机/固定机位/地面机位/移动机位） |
| `scenes[].shot_list[].camera.movement` | string | ✅ | 运镜，**枚举**：固定/推/拉/摇/移/跟/升降/环绕 |
| `scenes[].shot_list[].camera.angle` | string | ✅ | 角度（俯拍/平拍/仰拍/侧拍） |
| `scenes[].shot_list[].shot_size` | string | ✅ | 景别，**枚举**：大远景/全景/中景/近景/特写 |
| `scenes[].shot_list[].subject` | string | ✅ | 画面主体（人物/地标/景物） |
| `scenes[].shot_list[].background` | string | ✅ | 环境背景（时段+天气+氛围） |
| `scenes[].shot_list[].prompt` | string | ✅ | 可直接用于文生图/文生视频的完整提示词（含主体/环境/光线/质感） |

## 3. 硬性约束（Storyboard Agent 必须满足）

1. **镜头数量**：全局 shot 总数 6-8 个
2. **总时长**：所有 `duration_s` 之和 ≈ 60 秒（±5 秒）
3. **地标一致性**：同一地标跨镜头描述不得冲突（如雷峰塔样式、湖色色调）
4. **枚举合规**：`movement` / `shot_size` 必须落在枚举内
5. **可执行性**：每个 `prompt` 必须可直接交给 T2V 模型（缺主体/环境/光线/质感视为不合格）
6. **输出纯净**：只输出 JSON 对象，禁止代码块标记、注释与任何解释文字

## 4. 参考实现

权威样例：`experiments/results/best_storyboard.json`（7 场景 / 8 镜头 / 60s，清晨→入夜时间线）。
校验脚本：`experiments/run_llm_benchmark.py` 的 `validate_storyboard_json()`。

## 5. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-08-05 | 定稿（源自实验2 最优输出 kimi_01） |
