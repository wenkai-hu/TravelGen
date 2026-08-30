<script setup>
// 分镜编辑页（文档页面3「脚本与分镜」+ 页面4「生成进度」一体）
// 状态流：方案确认后进入 → 自动触发分镜生成 → 待确认(编辑 Shot/重新生成) → 确认并批量生成视频 → 轮询任务看进度
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NInput, NModal, useMessage } from "naive-ui";
import logoUrl from "../images/logo.png";
import {
  createStoryboard,
  generateShots,
  getProject,
  getVideoTask,
  regenerateShot,
  updateShot,
} from "../api";
import { isLoggedIn } from "../auth";

const message = useMessage();
const route = useRoute();
const router = useRouter();

const POLL_MS = 2000;
const pid = computed(() => route.params.pid);

// ── 项目数据 ──
const project = ref(null);
let projectTimer = null;

// ── 镜头生成结果（task 轮询 + project.video_clips 合并），驱动卡片状态 ──
const shotResults = reactive({}); // shot_id -> { status, video_url, error }
const videoErrors = reactive({}); // shot_id -> true（浏览器解码失败，Seedance 输出 4:2:2 编码）
const taskTimers = new Map();

// 批量生成任务状态
const batchTaskId = ref(null);
const batchState = ref("idle"); // idle | running | done | partial_failed
const batchProgress = ref(0);
const batchMessage = ref("");

// ── 分镜编辑态 ──
const editingShotId = ref(null);
const editPrompt = ref("");
const regenShotId = ref(null); // 重新生成对话框目标 shot
const regenPrompt = ref("");
const regenSubmitting = ref(false); // 提交中：开始生成按钮转圈，防重复提交

let storyboardTriggered = false; // 每段会话内只自动触发一次分镜生成

// ── 派生数据 ──
const req = computed(() => project.value?.request || {});
const scenes = computed(() => project.value?.storyboard?.scenes || []);
const allShots = computed(() => scenes.value.flatMap((s) => s.shot_list || []));
const totalShots = computed(() => allShots.value.length);

// 顶部横幅：加载 / 分镜生成中 / 编辑 / 生成中 / 完成 / 部分失败 / 失败 / 其他
const banner = computed(() => {
  const p = project.value;
  if (!p) return "loading";
  if (p.status === "plan_confirmed" || p.status === "storyboarding")
    return "storyboarding";
  if (batchState.value === "running") return "generating";
  if (batchState.value === "done") return "done";
  if (batchState.value === "partial_failed") return "failed";
  if (p.status === "waiting_storyboard_confirm") return "edit";
  if (p.status === "completed") return "done";
  if (p.status === "failed") return "failed";
  return "other";
});

function shotState(shot) {
  return shotResults[shot.shot_id] || {};
}
function isGen(sid) {
  return shotResults[sid]?.status === "generating";
}
function onVideoError(sh) {
  videoErrors[sh.shot_id] = true; // 浏览器解码失败 → 显示下载兜底
}
function isPlayable(url) {
  // 可播：远程 http(s) URL，或后端静态挂载的本地转存相对路径（/assets/videos/...）
  return (
    typeof url === "string" &&
    (/^https?:\/\//i.test(url) || url.startsWith("/assets/"))
  );
}

// ── 工具：任务轮询（batch / 单镜重生成统一入口） ──
function applyTask(t) {
  for (const s of t.shots || []) {
    shotResults[s.shot_id] = {
      status: s.status === "pending" ? "pending" : s.status,
      video_url: s.video_url || s.local_path || null,
      error: s.error || null,
    };
  }
  if (batchTaskId.value === t.task_id) {
    batchProgress.value = t.progress ?? 0;
    batchMessage.value = t.message || "";
  }
}

function startTaskPoll(taskId, onDone) {
  if (taskTimers.has(taskId)) return;
  let guard = false;
  const iv = setInterval(async () => {
    if (guard) return;
    guard = true;
    try {
      const t = await getVideoTask(taskId);
      applyTask(t);
      if (t.status === "completed" || t.status === "failed") {
        clearInterval(iv);
        taskTimers.delete(taskId);
        if (onDone) onDone(t);
        // 单镜重生成的 task 完成后不刷新项目：recompute_project_status 会把
        // waiting_storyboard_confirm 顶成 completed，导致编辑页横幅误报"全部完成"
        if (batchTaskId.value === taskId) await refreshProject();
      }
    } catch {
      /* 瞬时网络错误：下个 tick 自愈 */
    } finally {
      guard = false;
    }
  }, POLL_MS);
  taskTimers.set(taskId, iv);
}

// ── 工具：项目全量刷新 + 合并终态镜头结果 ──
function mergeTerminal(p) {
  for (const [sid, r] of Object.entries(p.video_clips || {})) {
    const cur = shotResults[sid];
    if (!cur || cur.status !== "generating") {
      shotResults[sid] = {
        status: r.status,
        video_url: r.video_url || r.local_path || null,
        error: r.error || null,
      };
    }
  }
}

async function refreshProject() {
  try {
    const p = await getProject(pid.value);
    project.value = p;
    mergeTerminal(p);
  } catch {
    /* 读取失败忽略 */
  }
}

// ── 分镜生成阶段的项目轮询（plan_confirmed → waiting_storyboard_confirm） ──
function startProjectPoll() {
  stopProjectPoll();
  let guard = false;
  projectTimer = setInterval(async () => {
    if (guard) return;
    guard = true;
    try {
      const p = await getProject(pid.value);
      project.value = p;
      if (p.status === "plan_confirmed") {
        // 首查竞态：还没触发过则补触发
        if (!storyboardTriggered) {
          storyboardTriggered = true;
          await createStoryboard(pid.value, p.plan_id);
          message.info("正在生成分镜…");
        }
        return;
      }
      mergeTerminal(p);
      if (p.status === "waiting_storyboard_confirm") stopProjectPoll();
    } catch {
      /* 自愈 */
    } finally {
      guard = false;
    }
  }, POLL_MS);
}

function stopProjectPoll() {
  if (projectTimer) {
    clearInterval(projectTimer);
    projectTimer = null;
  }
}

function stopTaskPolls() {
  for (const iv of taskTimers.values()) clearInterval(iv);
  taskTimers.clear();
}

// ── 进入页面：按项目状态分流 ──
async function start() {
  stopProjectPoll();
  stopTaskPolls();
  try {
    const p = await getProject(pid.value);
    project.value = p;
    mergeTerminal(p);
    if (p.status === "plan_confirmed") {
      storyboardTriggered = true;
      await createStoryboard(pid.value, p.plan_id);
      message.info("正在生成分镜…");
      startProjectPoll();
    } else if (p.status === "storyboarding") {
      startProjectPoll();
    } else if (p.status === "generating") {
      // 刷新/回到本页时已在生成视频：接管最近一次任务
      const list = p.video_tasks || [];
      const tid = list[list.length - 1];
      if (tid) {
        batchTaskId.value = tid;
        batchState.value = "running";
        startTaskPoll(tid, onBatchDone);
      }
    }
  } catch (e) {
    if (e.status === 404) {
      router.replace("/");
      return;
    }
    message.error(e.message || "读取项目失败");
  }
}

onMounted(() => {
  if (!pid.value) {
    router.replace("/");
    return;
  }
  start();
});
onBeforeUnmount(() => {
  stopProjectPoll();
  stopTaskPolls();
});
watch(pid, (np, op) => {
  if (np && np !== op) start();
});

// ── 编辑 Shot 的 Prompt（只读字段不入编辑接口，契约 §十一） ──
function startEdit(shot) {
  editingShotId.value = shot.shot_id;
  editPrompt.value = shot.prompt;
}
function cancelEdit() {
  editingShotId.value = null;
}
async function saveEdit(shot) {
  const text = editPrompt.value.trim();
  if (!text) {
    message.warning("Prompt 不能为空");
    return;
  }
  try {
    await updateShot(pid.value, shot.shot_id, { prompt: text });
    shot.prompt = text;
    editingShotId.value = null;
    message.success(`Shot ${shot.shot_id} 已保存`);
  } catch (e) {
    message.error(e.message || "保存失败");
  }
}

// ── 单 Shot 重新生成（局部可控生成） ──
function openRegen(shot) {
  regenShotId.value = shot.shot_id;
  regenPrompt.value = shot.prompt;
}
function cancelRegen() {
  regenShotId.value = null;
}
async function submitRegen() {
  const sid = regenShotId.value;
  regenSubmitting.value = true;
  try {
    const t = await regenerateShot(pid.value, sid, {
      prompt: regenPrompt.value.trim(),
    });
    cancelRegen();
    shotResults[sid] = { status: "generating" };
    message.info(`Shot ${sid} 重新生成中…`);
    startTaskPoll(t.task_id);
  } catch (e) {
    message.error(e.message || "重新生成失败");
  } finally {
    regenSubmitting.value = false;
  }
}

// ── 单镜头试生成（低成本测试：只生成选中的一个镜头看质量） ──
async function onTestShot(sh) {
  const sid = sh.shot_id;
  try {
    const t = await generateShots(pid.value, [sid]);
    shotResults[sid] = { status: "generating" };
    message.info(`Shot ${sid} 单镜试生成中…`);
    startTaskPoll(t.task_id);
  } catch (e) {
    message.error(e.message || "单镜生成失败");
  }
}

// ── 确认分镜并批量生成视频（后端语义：POST generate 即视为确认分镜） ──
function onBatchDone(t) {
  const rows = t.shots || [];
  const ok = rows.filter((s) => s.status === "completed").length;
  batchState.value = ok === rows.length ? "done" : "partial_failed";
  batchMessage.value = t.message || `完成 ${ok}/${rows.length} 个镜头`;
}

async function onConfirmStoryboard() {
  if (!totalShots.value) {
    message.warning("分镜尚未生成");
    return;
  }
  // 跳过已生成完成的镜头（单镜测试过的不重复扣费）
  const pending = allShots.value
    .filter((s) => shotState(s).status !== "completed")
    .map((s) => s.shot_id);
  if (!pending.length) {
    message.info("所有镜头均已生成完成");
    return;
  }
  try {
    const t = await generateShots(pid.value, pending);
    batchTaskId.value = t.task_id;
    batchState.value = "running";
    batchProgress.value = 0;
    batchMessage.value = "开始生成视频…";
    startTaskPoll(t.task_id, onBatchDone);
  } catch (e) {
    message.error(e.message || "开始生成失败");
  }
}

function backToPlan() {
  router.push(`/plan/${pid.value}`);
}
function fmtDur(s) {
  return s ? `${s}s` : "";
}
function statusLabel(s) {
  return (
    {
      pending: "待生成",
      generating: "生成中",
      completed: "已完成",
      failed: "失败",
    }[s] || s
  );
}
</script>

<template>
  <div class="page">
    <!-- 顶部导航 -->
    <header class="nav fade-up">
      <div class="nav-inner">
        <div class="logo" @click="router.push('/')">
          <img :src="logoUrl" class="logo-mark" alt="TravelGen" />
          <span class="logo-text gradient-text">TravelGen</span>
        </div>
        <nav class="nav-links">
          <a href="#" @click.prevent="router.push('/')">工作台</a>
          <router-link v-if="isLoggedIn()" to="/history">我的创作</router-link>
        </nav>
      </div>
    </header>

    <main class="stage">
      <!-- ① 首查加载 -->
      <div v-if="banner === 'loading'" class="card center">
        <div class="spin-ring"></div>
        <p class="center-text">正在读取项目…</p>
      </div>

      <!-- ② 分镜生成中 -->
      <div v-else-if="banner === 'storyboarding'" class="card gen">
        <div class="gen-badge">✦ AI 拆分分镜中</div>
        <h2 class="gen-title">{{ req.theme }}</h2>
        <p class="gen-sub">📍 {{ req.city }} · {{ req.location }}</p>
        <div class="bar-track">
          <div class="bar-fill"></div>
        </div>
        <p class="gen-msg">{{ project?.message || "按旁白文案拆分镜头" }}</p>
        <p class="gen-tip">通常约 10~60 秒，页面会自动刷新，请勿关闭</p>
      </div>

      <template v-else>
        <!-- 顶部横幅：编辑 / 生成中 / 完成 / 失败 -->
        <section class="card summary fade-up">
          <div class="summary-head">
            <h2 class="s-title">{{ req.theme }}</h2>
            <span class="s-tag">{{ req.scene_type }}</span>
          </div>
          <div class="summary-meta">
            <span>📍 {{ req.city }} · {{ req.location }}</span>
            <span>🎨 {{ req.style }}</span>
            <span>👥 {{ req.audience }}</span>
            <span
              >⏱ {{ req.duration_s }}s｜{{ req.aspect_ratio }}｜{{
                req.resolution
              }}</span
            >
          </div>

          <!-- 生成中：进度条 -->
          <template v-if="banner === 'generating'">
            <div class="gen-inline">
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ width: batchProgress + '%' }"
                ></div>
              </div>
              <p class="gen-msg">{{ batchMessage }}</p>
            </div>
          </template>

          <!-- 完成 / 失败：结果摘要 -->
          <template v-else-if="banner === 'done'">
            <p class="done-line">🎉 全部 {{ totalShots }} 个镜头已生成完成</p>
            <p class="gen-tip">单镜头仍可点击卡片「重新生成」局部重做</p>
          </template>
          <template v-else-if="banner === 'failed'">
            <p class="fail-line">⚠️ {{ batchMessage || "部分镜头生成失败" }}</p>
            <p class="gen-tip">失败镜头可在卡片上点击「重生成视频」重做</p>
          </template>

          <!-- 编辑态：确认操作条 -->
          <div v-if="banner === 'edit'" class="op-bar">
            <NButton size="large" @click="backToPlan">← 返回方案</NButton>
            <NButton
              class="confirm-btn"
              size="large"
              type="primary"
              @click="onConfirmStoryboard"
            >
              🎬 确认分镜并生成视频
            </NButton>
          </div>
        </section>

        <!-- 使用引导 -->
        <div class="guide fade-up-1">
          <span class="guide-icon">💡</span>
          <div class="guide-body">
            <b>分镜确认</b>
            <p>① 每张卡片是一个镜头</p>
            <p>
              ② 卡片左侧主体/背景/机位是AI提炼的画面要点
              （只读展示），视频生成实际只用右侧可编辑的 Prompt
            </p>
            <p>
              ③ 可点「单镜试生成」先测一个镜头看质量，或「编辑」改 Prompt 后重做
            </p>
            <p>④满意后点「确认分镜并生成视频」（已生成过的镜头自动跳过）</p>
          </div>
        </div>

        <!-- 分镜卡片 -->
        <section v-if="scenes.length" class="scenes fade-up-2">
          <div v-for="sc in scenes" :key="sc.scene_id" class="scene-card">
            <div class="scene-head">
              <span class="scene-tag">场景 {{ sc.scene_id }}</span>
              <b>{{ sc.location }}</b>
              <span class="scene-time">{{ sc.time }}</span>
            </div>
            <div class="shot-grid">
              <div
                v-for="sh in sc.shot_list"
                :key="sh.shot_id"
                class="shot-card"
              >
                <div class="shot-main">
                  <!-- 左：识别信息（只读展示） -->
                  <div class="shot-left">
                    <div class="shot-head">
                      <!-- <span class="shot-idx">#{{ String(sh.shot_id).padStart(2, "0") }}</span> -->
                      <div class="prompt-label">📋 prompt要点·只读</div>
                      <div>
                        <span class="shot-chip">{{
                          fmtDur(sh.duration_s)
                        }}</span>
                        <span class="shot-chip">{{ sh.shot_size }}</span>
                        <span class="shot-chip"
                          >{{ sh.camera?.type }}·{{ sh.camera?.movement }}·{{
                            sh.camera?.angle
                          }}</span
                        >
                      </div>
                    </div>
                    <dl class="shot-meta">
                      <div>
                        <dt>主体</dt>
                        <dd>{{ sh.subject }}</dd>
                      </div>
                      <div>
                        <dt>背景</dt>
                        <dd>{{ sh.background }}</dd>
                      </div>
                    </dl>
                  </div>

                  <!-- 右：Prompt 模块（可编辑） -->
                  <div class="shot-right">
                    <template v-if="editingShotId === sh.shot_id">
                      <NInput
                        v-model:value="editPrompt"
                        type="textarea"
                        :autosize="{ minRows: 3, maxRows: 6 }"
                        placeholder="修改画面提示词…"
                      />
                      <div class="shot-actions">
                        <NButton size="small" quaternary @click="cancelEdit"
                          >取消</NButton
                        >
                        <NButton
                          size="small"
                          type="primary"
                          @click="saveEdit(sh)"
                          >✓ 保存</NButton
                        >
                      </div>
                    </template>
                    <template v-else>
                      <span class="prompt-label"
                        >🎞 视频 Prompt · 可自行编辑</span
                      >
                      <p class="shot-prompt">{{ sh.prompt }}</p>
                      <div class="shot-actions">
                        <span
                          class="res-chip"
                          :class="shotState(sh).status"
                          v-if="shotState(sh).status"
                        >
                          <span
                            v-if="shotState(sh).status === 'generating'"
                            class="chip-spinner"
                          ></span>
                          {{ statusLabel(shotState(sh).status) }}
                        </span>
                        <NButton
                          v-if="banner === 'edit'"
                          size="small"
                          type="primary"
                          quaternary
                          :disabled="isGen(sh.shot_id)"
                          @click="onTestShot(sh)"
                        >
                          单镜试生成
                        </NButton>
                        <NButton size="small" quaternary @click="startEdit(sh)"
                          >编辑</NButton
                        >
                        <NButton
                          v-if="shotState(sh).status"
                          size="small"
                          quaternary
                          :disabled="
                            isGen(sh.shot_id) || banner === 'generating'
                          "
                          @click="openRegen(sh)"
                        >
                          重新生成
                        </NButton>
                      </div>
                    </template>
                  </div>
                </div>

                <!-- 生成结果：可播放视频 / 解码失败兜底 / 下载（整卡通栏） -->
                <div
                  v-if="shotState(sh).status === 'completed'"
                  class="shot-result"
                >
                  <template
                    v-if="
                      isPlayable(shotState(sh).video_url) &&
                      !videoErrors[sh.shot_id]
                    "
                  >
                    <video
                      :src="shotState(sh).video_url"
                      controls
                      preload="metadata"
                      class="shot-video"
                      @error="onVideoError(sh)"
                    ></video>
                  </template>
                  <p
                    v-else-if="isPlayable(shotState(sh).video_url)"
                    class="res-error"
                  >
                    ⚠️ 浏览器无法解码此视频（Seedance 输出 4:2:2
                    编码），请点下方按钮下载后用播放器观看
                  </p>
                  <p v-else class="res-empty">
                    已生成 · 当前无在线预览（模拟/本地）
                  </p>
                  <div v-if="shotState(sh).video_url" class="shot-dl">
                    <a :href="shotState(sh).video_url" download class="dl-btn">
                      ⬇ 下载视频
                    </a>
                  </div>
                </div>
                <p
                  v-else-if="shotState(sh).status === 'failed'"
                  class="res-error"
                >
                  {{ shotState(sh).error || "生成失败，可重新生成" }}
                </p>
              </div>
            </div>
          </div>
        </section>

        <!-- 分镜生成失败兜底 -->
        <div v-else-if="banner === 'failed'" class="card center">
          <div class="err-icon">⚠️</div>
          <h2 class="err-title">分镜生成失败</h2>
          <p class="err-msg">{{ project?.message || "未知错误" }}</p>
          <p class="err-tip">可回到方案页重新确认后再次生成</p>
          <div class="op-bar">
            <NButton size="large" @click="router.push('/')">回到工作台</NButton>
            <NButton size="large" type="primary" @click="start"
              >刷新状态</NButton
            >
          </div>
        </div>
      </template>
    </main>

    <!-- 重新生成对话框
         不用 preset="dialog"：naive-ui 会把 @positive-click/@negative-click/@close
         与内部 handler 合并成数组传给 Dialog，调用时抛 TypeError → 按钮全部"点不动"。
         改为普通 NModal + 自建按钮（纯 @click），点遮罩/Esc 由 @update:show 关闭。 -->
    <NModal
      :show="regenShotId !== null"
      :mask-closable="true"
      @update:show="
        (v) => {
          if (!v) cancelRegen();
        }
      "
    >
      <div class="regen-modal">
        <div class="regen-modal__head">
          <span class="regen-modal__title">重新生成</span>
          <NButton
            class="regen-modal__close"
            quaternary
            circle
            size="small"
            @click="cancelRegen"
          >
            ✕
          </NButton>
        </div>
        <p class="modal-tip">调整prompt 重新生成视频</p>
        <NInput
          v-model:value="regenPrompt"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 6 }"
          class="modal-field"
        />
        <div class="regen-modal__actions">
          <NButton @click="cancelRegen">取消</NButton>
          <NButton
            type="primary"
            :loading="regenSubmitting"
            @click="submitRegen"
          >
            开始生成
          </NButton>
        </div>
      </div>
    </NModal>

    <footer class="footer">
      TravelGen · 面向浙江文旅的 AIGC 短视频生成系统
    </footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--color-bg);
  font-family: var(--font-sans);
  color: var(--color-ink);
}

/* ---------- 导航 ---------- */
.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #fcf8f1;
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 2px 12px rgba(31, 41, 55, 0.05);
}
.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo {
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
}
.logo-mark {
  width: 76px;
  height: 76px;
  border-radius: 12px;
  object-fit: cover;
  display: block;
}
.logo-text {
  font-family: var(--font-serif);
  font-size: 25px;
  font-weight: 700;
  letter-spacing: 1px;
}
.nav-links a {
  color: var(--color-ink-sub);
  text-decoration: none;
  font-size: 16px;
  transition: color 0.15s;
}
.nav-links a:hover {
  color: var(--color-primary);
}

/* ---------- 主区 ---------- */
.stage {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px 60px;
}
.card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  box-shadow: var(--shadow-card);
  padding: 22px;
}
.card.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 260px;
}
.center-text {
  margin-top: 14px;
  color: var(--color-ink-sub);
  font-size: 13px;
}
.spin-ring {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 3px solid var(--color-primary-light);
  border-top-color: var(--color-primary);
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---------- 分镜生成中 ---------- */
.gen {
  text-align: center;
  padding: 56px 32px;
}
.gen-badge {
  display: inline-block;
  font-size: 13px;
  padding: 6px 16px;
  border-radius: 999px;
  background: var(--color-primary-fade);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
  margin-bottom: 20px;
}
.gen-title {
  font-family: var(--font-serif);
  font-size: 30px;
  margin: 0 0 8px;
  color: var(--color-ink);
}
.gen-sub {
  color: var(--color-ink-sub);
  font-size: 14px;
  margin: 0 0 28px;
}
.bar-track {
  max-width: 480px;
  height: 10px;
  margin: 0 auto;
  border-radius: 999px;
  background: var(--color-border);
  overflow: hidden;
}
.bar-fill {
  width: 45%;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #0f766e, #17a398);
  animation: indeterminate 1.4s ease-in-out infinite;
}
.bar-fill[style] {
  animation: none;
}
@keyframes indeterminate {
  0% {
    margin-left: -45%;
  }
  50% {
    margin-left: 100%;
  }
  100% {
    margin-left: -45%;
  }
}
.gen-msg {
  margin-top: 18px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
  text-align: center;
}
.gen-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-ink-sub);
  text-align: center;
}

/* ---------- 顶部横幅 ---------- */
.summary {
  padding: 18px 22px;
  margin-bottom: 18px;
}
.summary-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.s-title {
  font-family: var(--font-serif);
  font-size: 22px;
  margin: 0;
  color: var(--color-primary-deep);
}
.s-tag {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--color-gold-light);
  color: var(--color-gold-ink);
  border: 1px solid var(--color-gold);
  white-space: nowrap;
}
.summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--color-ink-sub);
}
.gen-inline {
  margin-top: 16px;
}
.gen-inline .bar-track {
  max-width: none;
  margin: 0;
}
.gen-inline .gen-msg {
  text-align: left;
  margin-top: 10px;
}
.done-line {
  margin: 12px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-success);
}
.fail-line {
  margin: 12px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-error);
}
.summary .gen-tip {
  text-align: left;
}

/* ---------- 操作条 ---------- */
.op-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
}
.confirm-btn {
  background: linear-gradient(120deg, #0f766e, #115e59) !important;
}

/* ---------- 使用引导 ---------- */
.guide {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--color-primary-fade);
  border: 1px solid var(--color-primary-light);
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 18px;
}
.guide-icon {
  font-size: 16px;
  line-height: 1.4;
}
.guide-body b {
  font-size: 13.5px;
  color: var(--color-primary-deep);
}
.guide-body p {
  margin: 3px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--color-ink-sub);
}

/* ---------- 场景与镜头 ---------- */
.scene-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  box-shadow: var(--shadow-card);
  padding: 18px;
  margin-bottom: 18px;
}
.scene-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--color-border);
  margin-bottom: 14px;
}
.scene-tag {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--color-primary-fade);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
}
.scene-head b {
  font-size: 15px;
  color: var(--color-ink);
}
.scene-time {
  font-size: 12px;
  color: var(--color-gold);
  font-weight: 600;
}
.shot-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
.shot-card {
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
  background: var(--color-card);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow 0.15s;
}
.shot-card:hover {
  box-shadow: var(--shadow-card-hover);
}
.shot-main {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}
.shot-left {
  flex-shrink: 0;
  width: 235px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.shot-right {
  flex: 1;
  min-width: 0; /* 长 prompt 不撑爆 flex */
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.shot-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.shot-idx {
  font-weight: 700;
  font-size: 14px;
  color: var(--color-primary-deep);
}
.shot-chip {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--color-primary-fade);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
}
.shot-meta {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13.5px;
}
.shot-meta div {
  display: flex;
  gap: 8px;
}
.shot-meta dt {
  color: var(--color-ink-sub);
  flex-shrink: 0;
  width: 2.5em;
}
.shot-meta dd {
  margin: 0;
  color: var(--color-ink);
}
.prompt-label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-primary);
  margin-bottom: 4px;
}
.shot-prompt {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-sub);
  background: var(--color-primary-fade);
  border-radius: 8px;
  padding: 10px 12px;
}
.shot-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
}
.res-chip {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  margin-right: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.chip-spinner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--color-gold-light);
  border-top-color: var(--color-gold);
  animation: chip-spin 0.8s linear infinite;
}
@keyframes chip-spin {
  to {
    transform: rotate(360deg);
  }
}
.res-chip.completed {
  background: var(--color-primary-fade);
  color: var(--color-success);
  border: 1px solid var(--color-primary-light);
}
.res-chip.failed {
  background: #fdf1ef;
  color: var(--color-error);
  border: 1px solid #ecd0cb;
}
.res-chip.generating {
  background: var(--color-gold-fade);
  color: var(--color-gold-ink);
  border: 1px solid var(--color-gold-light);
}
.shot-dl {
  margin-top: 8px;
}
.dl-btn {
  display: inline-block;
  font-size: 12.5px;
  padding: 6px 14px;
  border-radius: 8px;
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
  background: var(--color-primary-fade);
  text-decoration: none;
  transition: background 0.15s;
}
.dl-btn:hover {
  background: var(--color-primary-light);
}
.res-chip.pending {
  background: var(--color-card);
  color: var(--color-ink-sub);
  border: 1px solid var(--color-border);
}
.shot-result {
  margin-top: 2px;
}
.shot-video {
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: #000;
  max-height: 260px;
}
.res-empty {
  margin: 0;
  font-size: 11.5px;
  color: var(--color-ink-sub);
}
.res-error {
  margin: 0;
  font-size: 12px;
  color: var(--color-error);
}

/* ---------- 失败兜底 ---------- */
.err-icon {
  font-size: 42px;
}
.err-title {
  font-family: var(--font-serif);
  font-size: 26px;
  margin: 14px 0 8px;
  color: var(--color-error);
}
.err-msg {
  font-size: 13.5px;
  color: var(--color-ink-sub);
  margin: 6px 0;
}
.err-tip {
  font-size: 12px;
  color: var(--color-ink-sub);
  margin: 0 0 20px;
}

/* ---------- 对话框 ---------- */
.modal-tip {
  font-size: 12.5px;
  color: var(--color-ink-sub);
  margin: 0 0 12px;
}
.modal-field {
  margin-bottom: 12px;
}
/* 自建重新生成弹窗（不用 preset="dialog"） */
.regen-modal {
  width: 520px;
  max-width: 90vw;
  padding: 20px;
  border-radius: 12px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
}
.regen-modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.regen-modal__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}
.regen-modal__close {
  color: var(--color-ink-sub);
}
.regen-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

/* ---------- 页脚 ---------- */
.footer {
  max-width: 1200px;
  margin: 0 auto;
  padding: 22px 24px 30px;
  border-top: 1px solid var(--color-border);
  font-size: 12.5px;
  color: var(--color-ink-sub);
  text-align: center;
}

/* ---------- 响应式 ---------- */
@media (max-width: 900px) {
  .shot-main {
    flex-direction: column;
  }
  .shot-left {
    width: auto;
  }
}
</style>
