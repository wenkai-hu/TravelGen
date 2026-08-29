<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NInput, useMessage } from "naive-ui";
import logoUrl from "../images/logo.png";
import { getProject, confirmPlan } from "../api";

const message = useMessage();
const route = useRoute();
const router = useRouter();

const POLL_MS = 2000;
const pid = computed(() => route.params.pid);

// ── 项目数据（轮询刷新） ──
const project = ref(null);
const copywritingText = ref(""); // 旁白文案（可编辑，确认时原样 PUT 回去，后端重新解析）
const confirming = ref(false);
let timer = null;

// 页面阶段：loading 首查 / generating 生成中 / confirm 待确认 / confirmed 已确认 / failed 失败
const stage = computed(() => {
  const p = project.value;
  if (!p) return "loading";
  if (p.status === "planning") return "generating";
  if (p.status === "waiting_confirm") return "confirm";
  if (p.status === "plan_confirmed") return "confirmed";
  if (p.status === "failed") return "failed";
  return "other"; // storyboarding 等后续阶段（正常流程不会停留在本页）
});

// ── 轮询 ──
function stopPolling() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

let ticking = false;
let firstFailNotified = false;
async function tick() {
  if (ticking) return; // 单飞守卫：上次请求未返回时跳过，避免重叠响应乱序覆盖状态
  ticking = true;
  try {
    const p = await getProject(pid.value);
    project.value = p;
    if (!copywritingText.value && p.copywriting_text) {
      copywritingText.value = p.copywriting_text;
    }
    if (p.status !== "planning") stopPolling();
    if (p.status === "plan_confirmed") {
      // 方案已确认：进入分镜编辑页
      router.replace(`/plan/${pid.value}/storyboard`);
      return;
    }
  } catch (e) {
    if (e.status === 404) {
      // 项目不存在：回工作台，避免卡在 loading 死胡同
      stopPolling();
      router.replace("/");
      return;
    }
    // 瞬时网络错误/5xx：保留轮询让下个 tick 自愈；只提示一次，不刷屏
    if (!firstFailNotified) {
      firstFailNotified = true;
      message.error(e.message || "查询项目状态失败，自动重试中…");
    }
  } finally {
    ticking = false;
  }
}

function startPolling() {
  stopPolling();
  project.value = null;
  copywritingText.value = "";
  tick();
  timer = setInterval(tick, POLL_MS);
}

onMounted(() => {
  if (!pid.value) {
    const saved = sessionStorage.getItem("travelgen_project_id");
    router.replace(saved ? `/plan/${saved}` : "/");
    return;
  }
  startPolling();
});
onBeforeUnmount(stopPolling);
watch(pid, (np, op) => {
  if (np && np !== op) startPolling();
});

// ── 确认方案：把编辑后的旁白文本 PUT 回后端 ──
async function onConfirm() {
  confirming.value = true;
  try {
    await confirmPlan(pid.value, copywritingText.value);
    message.success("方案已确认，进入分镜阶段");
    await tick(); // 拉取确认后的状态（plan_confirmed）
  } catch (e) {
    message.error(e.message || "确认失败");
  } finally {
    confirming.value = false;
  }
}

// ── 展示用计算属性（容错空值） ──
const req = computed(() => project.value?.request || {});
const progress = computed(() => project.value?.progress ?? 0);
const msg = computed(() => project.value?.message || "");
const planId = computed(() => project.value?.plan_id || "");
const outline = computed(() => project.value?.planning?.outline || []);
const titles = computed(() => project.value?.copywriting?.titles || []);
const hashtags = computed(() => project.value?.copywriting?.hashtags || []);

function fmtDur(s) {
  return s ? `${s}s` : "";
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
        </nav>
      </div>
    </header>

    <main class="stage">
      <!-- 首查加载中 -->
      <div v-if="stage === 'loading'" class="card center">
        <div class="spin-ring"></div>
        <p class="center-text">正在读取项目…</p>
      </div>

      <!-- ① 生成创作方案中 -->
      <div v-else-if="stage === 'generating'" class="card gen">
        <div class="gen-badge">✦ AI 生成创作方案中</div>
        <h2 class="gen-title">{{ req.theme }}</h2>
        <p class="gen-sub">📍 {{ req.city }} · {{ req.location }}</p>
        <div class="bar-track">
          <div class="bar-fill"></div>
        </div>
        <p class="gen-msg">{{ msg || "生成创作方案" }}</p>
        <p class="gen-tip">通常约 10~60 秒，页面会自动刷新，请勿关闭</p>
      </div>

      <!-- ② 方案待确认 -->
      <div v-else-if="stage === 'confirm'" class="confirm">
        <!-- 项目概要 -->
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
        </section>

        <!-- 使用引导：首次用户三步骤 -->
        <div class="guide fade-up-1">
          <span class="guide-icon">💡</span>
          <div class="guide-body">
            <b>创作方案确认</b>
            <p>
              ① 先看左侧创作方案，是 AI 生成的内容大纲 · ②
              右侧旁白文案可按需修改 · ③ 点「确认方案」，AI
              将按此文案拆分镜并生成视频
            </p>
          </div>
        </div>

        <div class="cols">
          <!-- 左：创作方案（拍摄大纲） -->
          <section class="card outline fade-up-1">
            <h3 class="block-title">🎞 创作方案</h3>
            <p class="card-sub">
              AI 生成的内容大纲（3-5 段），预览视频的叙事结构与节奏
            </p>
            <p v-if="!outline.length" class="empty-hint">方案内容生成中…</p>
            <ol class="timeline">
              <li v-for="(o, i) in outline" :key="i" class="timeline-item">
                <span class="tl-idx">{{ i + 1 }}</span>
                <div class="tl-body">
                  <div class="tl-head">
                    <b>{{ o.title }}</b>
                    <span class="tl-dur">{{ fmtDur(o.duration_s) }}</span>
                  </div>
                  <p class="tl-content">{{ o.content }}</p>
                </div>
              </li>
            </ol>
          </section>

          <!-- 右：文案 + 素材 -->
          <div class="side">
            <section class="card cw fade-up-2">
              <h3 class="block-title">📝 旁白文案（可编辑）</h3>
              <p class="card-sub">
                视频的配音脚本，可直接改写措辞，确认后按此拆分镜
              </p>
              <NInput
                v-model:value="copywritingText"
                type="textarea"
                :autosize="{ minRows: 6, maxRows: 14 }"
                placeholder="按时间轴编辑旁白…"
              />
            </section>

            <section
              v-if="titles.length || hashtags.length"
              class="card tags fade-up-2"
            >
              <h3 class="block-title">🏷 标题候选 · 话题标签</h3>
              <p class="card-sub">
                成片发布时可挑选的封面标题与传播话题（可复制到抖音/视频号）
              </p>
              <p v-if="titles.length" class="tag-line">
                <span class="tag-label">标题</span>
                <span v-for="t in titles" :key="t" class="chip-title">{{
                  t
                }}</span>
              </p>
              <p v-if="hashtags.length" class="tag-line">
                <span class="tag-label">标签</span>
                <span v-for="h in hashtags" :key="h" class="chip-hash">{{
                  h
                }}</span>
              </p>
            </section>
          </div>
        </div>

        <!-- 确认操作条 -->
        <div class="op-bar">
          <NButton size="large" @click="router.push('/')">← 返回修改</NButton>
          <NButton
            class="confirm-btn"
            size="large"
            type="primary"
            :loading="confirming"
            @click="onConfirm"
          >
            ✓ 确认方案
          </NButton>
        </div>
      </div>

      <!-- ③ 已确认 -->
      <div v-else-if="stage === 'confirmed'" class="card done">
        <div class="done-icon">🎉</div>
        <h2 class="done-title">方案已确认</h2>
        <p class="done-line" v-if="planId">计划 ID：{{ planId }}</p>
        <p class="done-line">进度 {{ progress }}% — {{ msg }}</p>
        <p class="done-tip">下一步：AI 拆分镜，正在进入分镜编辑页…</p>
        <NButton
          class="confirm-btn"
          size="large"
          type="primary"
          @click="router.replace(`/plan/${pid}/storyboard`)"
        >
          进入分镜编辑
        </NButton>
      </div>

      <!-- ④ 其他阶段（正常不会停留本页） -->
      <div v-else-if="stage === 'other'" class="card done">
        <div class="done-icon">🛠</div>
        <h2 class="done-title">项目已进入下一阶段</h2>
        <p class="done-line">状态：{{ project?.status }}（{{ progress }}%）</p>
        <NButton size="large" @click="router.push('/')">回到工作台</NButton>
      </div>

      <!-- ⑤ 失败 -->
      <div v-else class="card err">
        <div class="err-icon">⚠️</div>
        <h2 class="err-title">方案生成失败</h2>
        <p class="err-msg">{{ project?.message || "未知错误" }}</p>
        <p class="err-tip">
          可检查后端日志（kimi key 是否正确），或回到工作台重新创建项目
        </p>
        <div class="op-bar">
          <NButton size="large" @click="router.push('/')">返回修改</NButton>
          <NButton size="large" type="primary" @click="startPolling"
            >刷新状态</NButton
          >
        </div>
      </div>
    </main>

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

/* ---------- 导航（与工作台一致） ---------- */
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

.block-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--color-primary-deep);
  margin: 0 0 14px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--color-border);
}
.empty-hint {
  color: var(--color-ink-sub);
  font-size: 13px;
  margin: 0;
}
.card-sub {
  margin: -4px 0 14px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-sub);
}

/* 使用引导条 */
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

/* ---------- ① 生成中 ---------- */
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
  animation: indeterminate 1.4s ease-in-out infinite; /* 不确定进度：来回扫描，表达"生成中"而非卡在 5% */
}
@keyframes indeterminate {
  0%   { margin-left: -45%; }
  50%  { margin-left: 100%; }
  100% { margin-left: -45%; }
}
.gen-msg {
  margin-top: 18px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
}
.gen-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-ink-sub);
}

/* ---------- ② 待确认 ---------- */
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

.cols {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: 18px;
  align-items: stretch; /* 左栏创作方案与右栏（文案+标签）等高的关键 */
}

/* 左：创作方案时间线 */
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.timeline-item {
  display: flex;
  gap: 12px;
  padding: 10px 0;
}
.timeline-item + .timeline-item {
  border-top: 1px dashed var(--color-border);
}
.tl-idx {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}
.tl-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.tl-head b {
  font-size: 14px;
  color: var(--color-ink);
}
.tl-dur {
  font-size: 11px;
  color: var(--color-gold);
  font-weight: 600;
}
.tl-content {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--color-ink-sub);
}

/* 右栏 */
.side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.cw-note {
  font-size: 11px;
  color: var(--color-ink-sub);
  margin: 8px 0 0;
}
.tag-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  font-size: 12.5px;
}
.tag-label {
  color: var(--color-ink-sub);
  flex-shrink: 0;
}
.chip-title {
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-primary-fade);
  color: var(--color-primary-deep);
  font-weight: 600;
}
.chip-hash {
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid var(--color-gold);
  background: var(--color-gold-fade);
  color: var(--color-gold-ink);
  font-size: 12px;
}
/* 确认操作条 */
.op-bar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
}
.confirm-btn {
  background: linear-gradient(120deg, #0f766e, #115e59) !important;
}

/* ---------- ③ 已确认 / 其他 ---------- */
.done {
  text-align: center;
  padding: 56px 32px;
}
.done-icon,
.err-icon {
  font-size: 42px;
}
.done-title {
  font-family: var(--font-serif);
  font-size: 26px;
  margin: 14px 0 8px;
}
.done-line {
  font-size: 13.5px;
  color: var(--color-ink-sub);
  margin: 6px 0;
}
.done-tip {
  font-size: 12.5px;
  color: var(--color-gold);
  margin: 10px 0 20px;
}
.done .confirm-btn {
  margin-top: 4px;
}

/* ---------- ④ 失败 ---------- */
.err {
  text-align: center;
  padding: 48px 32px;
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
.err .op-bar {
  justify-content: center;
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
  .cols {
    grid-template-columns: 1fr;
  }
}
</style>
