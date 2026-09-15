// 后端 API 封装 —— V1 分阶段契约（/api/*），与 backend/v1_router.py 一一对应
// 开发时走 vite 代理（vite.config.js → http://127.0.0.1:8000）；
// 独立部署时在 .env 里填 VITE_API_BASE。
import { getToken } from "../auth";

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

async function request(path, options = {}) {
  let res
  // 登录态自动带 Authorization；未登录（如 /api/auth/login）则不发
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }
  try {
    // 20s 超时兜底：后端请求挂起时不能永久阻塞调用方（转圈按钮 / 轮询调用方会被挂死）
    res = await fetch(`${API_BASE}${path}`, {
      headers,
      ...options,
      signal: options.signal ?? AbortSignal.timeout(20000),
    })
  } catch (e) {
    if (e?.name === 'AbortError') {
      const err = new Error('请求超时（20s），请检查后端服务是否运行')
      err.status = 0
      throw err
    }
    throw e
  }
  let data = null
  try {
    data = await res.json()
  } catch {
    /* 空响应体 */
  }
  if (!res.ok) {
    // 后端统一错误结构 { detail: { code, message, detail } }
    const err = new Error(data?.detail?.message || `请求失败 (${res.status})`)
    err.code = data?.detail?.code
    err.status = res.status
    throw err
  }
  return data
}

// 接口1：创建项目（POST /api/projects，202）→ { project_id, status, ... }
export function createProject(payload) {
  return request('/api/projects', { method: 'POST', body: JSON.stringify(payload) })
}

// 轮询入口：项目全量状态（GET /api/projects/{pid}）
export function getProject(pid) {
  return request(`/api/projects/${pid}`)
}

// 接口1.1：查询联网搜图 / VLM 分析阶段状态与候选图片
export function getProjectReferences(pid) {
  return request(`/api/projects/${pid}/references`)
}

// 接口1.2：用户确认真实景点参考图，后端随后下载并调用 VLM
export function confirmProjectReferences(pid, referenceIds) {
  return request(`/api/projects/${pid}/references/confirm`, {
    method: 'POST',
    body: JSON.stringify({ reference_ids: referenceIds }),
  })
}

// 接口2：确认/修改方案（PUT /api/projects/{pid}/plan）→ 返回 { plan_id, ... }
export function confirmPlan(pid, copywriting) {
  return request(`/api/projects/${pid}/plan`, {
    method: 'PUT',
    body: JSON.stringify({ copywriting }),
  })
}

// 接口3：生成分镜（POST /api/projects/{pid}/storyboard，202），plan_id 防并发覆盖
export function createStoryboard(pid, planId) {
  return request(`/api/projects/${pid}/storyboard`, {
    method: 'POST',
    body: JSON.stringify({ plan_id: planId ?? null }),
  })
}

// 接口4：修改单个镜头（PUT /api/projects/{pid}/shots/{shot_id}），只传要改的字段
export function updateShot(pid, shotId, patch) {
  return request(`/api/projects/${pid}/shots/${shotId}`, {
    method: 'PUT',
    body: JSON.stringify(patch),
  })
}

// 接口5：批量生成视频（POST /api/projects/{pid}/generate，202）→ { task_id, ... }
export function generateShots(pid, shotIds) {
  return request(`/api/projects/${pid}/generate`, {
    method: 'POST',
    body: JSON.stringify({ shots: shotIds, generate_video: true, generate_image: false }),
  })
}

// 接口6：视频任务状态（GET /api/tasks/{task_id}），单镜头状态看 shots[]
export function getVideoTask(taskId) {
  return request(`/api/tasks/${taskId}`)
}

// 单镜头重生成（POST /api/projects/{pid}/shots/{shot_id}/regenerate，202）
export function regenerateShot(pid, shotId, payload) {
  return request(`/api/projects/${pid}/shots/${shotId}/regenerate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// 知识库检索（GET /api/kb/search?q=&top_k=），供知识点预览
export function searchKb(q, topK = 5) {
  return request(`/api/kb/search?q=${encodeURIComponent(q)}&top_k=${topK}`)
}

// 登录注册（/api/auth/*，后端 backend/db/auth.py）
export function register(payload) {
  return request('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) })
}
export function login(payload) {
  return request('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) })
}

// 历史记录：我的项目列表（GET /api/projects，仅返回当前用户的项目）
export function listProjects() {
  return request('/api/projects')
}
