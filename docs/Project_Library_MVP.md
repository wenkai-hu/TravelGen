# 项目与素材模块（精简版）

## 页面

- `/projects`：项目列表，搜索、状态筛选、重命名、删除、继续创作。旧 `/history` 自动跳转。
- `/library`：视频按来源项目归组，默认展示每个输出的最新成功版本，可打开历史版本。
- `/library?tab=voices`：用户生成的音色，支持试听、下载、重命名、移除、用于其他项目。
- 分镜页的「我的音色」使用同一个音色库。

## 数据库：用户表 + 四张业务表

使用原来的 MySQL 配置 `experiments/config.json` 的 `db.async_url`，不创建第二套数据库。
用户表维持不变。分镜仍保存在项目的 JSON 存档中。

| 表 | 字段 | 用途 |
|---|---|---|
| `users` | `id, username, password_hash` | 原有登录账号 |
| `projects` | `id, user_id, name, status, data, draft, created_at, updated_at, deleted_at` | 一次创作的完整存档和草稿 |
| `tasks` | `id, project_id, kind, status, data, created_at, updated_at` | 音色、视频片段、合成任务的请求、执行状态和结果 |
| `assets` | `id, user_id, project_id, task_id, kind, output_key, name, storage_key, metadata, created_at, deleted_at` | 已生成文件的目录，`task_id + output_key` 唯一 |
| `voices` | `id, user_id, asset_id, name, description, created_at, deleted_at` | 用户可跨项目复用的音色，关联真实 WAV 素材 |

具体类型及外键见 `backend/db/models.py`。`projects.data` 是现有工作流的完整 JSON，
包括输入、参考图、视觉分析、方案、分镜、音色/BGM 选择及任务 ID。
`draft` 按 `input / references / plan / storyboard` 区分尚未确认的编辑内容。
`data` 内也保留草稿便于现有工作流恢复；两个字段在同一个保存事务中写入。
`tasks.data` 保留各个 Segment 的执行状态和外部任务 ID，不需要单独的镜头表或子任务表。

## 数据迁移和文件

服务启动先建缺少的表，再幂等导入 `experiments/results/05_pipeline/` 中的旧项目及任务。
只有用户名能对应到已有账号的记录才导入；不猜测匿名旧记录的归属。
数据库已有记录不会被 JSON 覆盖，已删除的项目不会被重新导入。
原 JSON 文件保留；运行中的新保存以数据库为准，不继续双写旧文件。

音色生成后自动收录真实 WAV；视频每成功一段就入库，不必等待整批成功。
失败任务不制造空素材。数据库存相对 `assets/` 的文件路径，文件本身仍放在磁盘。
同一成功输出重复保存不会重复入库。新合成使用任务独立目录，避免覆盖已收录的旧视频。
原声版与配乐版分别展示。超长镜头的续写片段保留对应片段记录。

项目和音色删除均为软删除。删除项目不会删除素材；从音色库移除音色也不会删除
已经被旧项目使用的 WAV。下载接口和列表校验账号归属；现有工作流的 `/assets` 静态预览机制沿用。

## 自动保存和中断

需求填写过程中自动建立草稿项目，URL 带项目 ID。文案、参考图选择/排序、镜头编辑和
自定义音色描述会自动保存。前端先留本机缓存，再串行、防抖同步数据库；失败时明确提示，
未同步缓存会在再次进入时恢复。跨设备恢复以成功同步到数据库的内容为准。

关闭网页不取消服务端任务。重新进入时读取服务器最新进度。
服务进程重启后，旧进程未完成的任务标记为中断，已成功片段和素材保留；用户可显式重试。
第一版不自动恢复外部平台正在运行的付费任务，不自动重新提交生成请求。
现有登录会话仍在内存中，服务重启后需要重新登录，项目数据不会丢失。

此版本沿用单服务进程的项目内存对象及同步保存接口；多进程调度和多用户协同编辑尚未实现。

## 本地验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p test_library_storage.py -v
cd front
npm run build
```

测试覆盖数据库重载、草稿恢复、用户隔离、成功输出去重、失败重试保留成果、
音色跨项目复用、删除后素材保留、旧记录幂等迁移和中断任务处理。
