<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NInput, useMessage } from "naive-ui";
import logoUrl from "../images/logo.png";
import {
  createAudio,
  createRender,
  createStoryboard,
  generateSegments,
  getProject,
  regenerateSegment,
  updateSegment,
  updateShot,
} from "../api";
import { isLoggedIn } from "../auth";

const POLL_MS = 2000;
const message = useMessage();
const route = useRoute();
const router = useRouter();
const pid = computed(() => route.params.pid);

const project = ref(null);
const loading = ref(true);
const editingShotId = ref(null);
const editPrompt = ref("");
const savingShot = ref(false);
const segmentNotes = reactive({});
const localActive = reactive({});
const actionBusy = ref(false);
let timer = null;
let refreshing = false;
let audioTriggered = false;
let storyboardTriggered = false;

const req = computed(() => project.value?.request || {});
const scenes = computed(() => project.value?.storyboard?.scenes || []);
const segments = computed(() => project.value?.storyboard?.segments || []);
const audio = computed(() => project.value?.audio || {});
const segmentResults = computed(() => project.value?.segment_results || {});
const finalVideo = computed(() => project.value?.final_video || {});
const shotById = computed(() => {
  const rows = {};
  for (const scene of scenes.value) {
    for (const shot of scene.shot_list || []) {
      rows[shot.shot_id] = { ...shot, scene_title: scene.title };
    }
  }
  return rows;
});
const referenceById = computed(() =>
  Object.fromEntries(
    (project.value?.visual_assets?.ref_images || []).map((item) => [item.asset_id, item]),
  ),
);

const phase = computed(() => {
  const status = project.value?.status;
  if (!project.value || loading.value) return "loading";
  if (["plan_confirmed", "audio_generating", "audio_ready", "storyboarding"].includes(status)) return "preparing";
  if (status === "waiting_storyboard_confirm") return "editing";
  if (status === "generating") return "generating";
  if (status === "video_ready") return "video_ready";
  if (status === "composing") return "composing";
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "other";
});

const activeIds = computed(() => new Set(project.value?.active_segment_ids || []));

function shotsFor(segment) {
  return (segment.shot_ids || []).map((id) => shotById.value[id]).filter(Boolean);
}

function refsFor(shot) {
  return (shot.reference_asset_ids || []).map((id) => referenceById.value[id]).filter(Boolean);
}

function stateFor(segment) {
  if (activeIds.value.has(segment.segment_id) || localActive[segment.segment_id]) {
    return { status: "generating" };
  }
  return segmentResults.value[segment.segment_id] || { status: segment.status || "pending" };
}

function statusLabel(status) {
  return ({
    pending: "待生成",
    stale: "需重新生成",
    generating: "生成中",
    completed: "已生成",
    failed: "生成失败",
    ready: "已生成",
  })[status] || status;
}

function fmtMs(ms) {
  return `${(Number(ms || 0) / 1000).toFixed(1)}s`;
}

function syncProject(p) {
  project.value = p;
  for (const segment of p.storyboard?.segments || []) {
    if (!(segment.segment_id in segmentNotes)) {
      segmentNotes[segment.segment_id] = segment.transition_note || "";
    }
    const result = p.segment_results?.[segment.segment_id];
    if (!(p.active_segment_ids || []).includes(segment.segment_id) && result?.status !== "generating") {
      delete localActive[segment.segment_id];
    }
  }
}

async function advancePipeline(p) {
  if (p.status === "plan_confirmed" && !audioTriggered) {
    audioTriggered = true;
    try {
      await createAudio(pid.value, {
        voice: "zh-CN-XiaoxiaoNeural",
        music: "ambient",
      });
      message.info("正在生成完整旁白与背景音乐…");
    } catch (e) {
      if (e.status !== 409) message.error(e.message || "音频生成启动失败");
    }
    return;
  }
  if (p.status === "audio_ready" && !(p.storyboard?.scenes || []).length && !storyboardTriggered) {
    storyboardTriggered = true;
    try {
      await createStoryboard(pid.value, p.plan_id);
      message.info("正在按音频时间轴规划 Segment…");
    } catch (e) {
      if (e.status !== 409) message.error(e.message || "分镜生成启动失败");
    }
  }
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const p = await getProject(pid.value);
    syncProject(p);
    await advancePipeline(p);
  } catch (e) {
    if (e.status === 404) router.replace("/");
  } finally {
    loading.value = false;
    refreshing = false;
  }
}

function startPolling() {
  stopPolling();
  loading.value = true;
  audioTriggered = false;
  storyboardTriggered = false;
  refresh();
  timer = setInterval(refresh, POLL_MS);
}

function stopPolling() {
  if (timer) clearInterval(timer);
  timer = null;
}

onMounted(startPolling);
onBeforeUnmount(stopPolling);
watch(pid, (next, previous) => {
  if (next && next !== previous) startPolling();
});

function startEdit(shot) {
  editingShotId.value = shot.shot_id;
  editPrompt.value = shot.prompt || "";
}

function cancelEdit() {
  editingShotId.value = null;
  editPrompt.value = "";
}

async function saveShot(shot) {
  const prompt = editPrompt.value.trim();
  if (!prompt) return message.warning("Prompt 不能为空");
  savingShot.value = true;
  try {
    const response = await updateShot(pid.value, shot.shot_id, { prompt });
    cancelEdit();
    message.success(`${response.invalidated_segment_id || "所属 Segment"} 已标记为需重新生成`);
    await refresh();
  } catch (e) {
    message.error(e.message || "Shot 保存失败");
  } finally {
    savingShot.value = false;
  }
}

async function saveSegmentNote(segment) {
  actionBusy.value = true;
  try {
    await updateSegment(pid.value, segment.segment_id, {
      transition_note: segmentNotes[segment.segment_id] || "",
    });
    message.success(`${segment.segment_id} 的转场要求已保存`);
    await refresh();
  } catch (e) {
    message.error(e.message || "保存失败");
  } finally {
    actionBusy.value = false;
  }
}

async function startSegments(ids, regenerate = false) {
  if (!ids.length) return;
  actionBusy.value = true;
  ids.forEach((id) => { localActive[id] = true; });
  try {
    if (regenerate && ids.length === 1) {
      await regenerateSegment(pid.value, ids[0], {
        reason: "用户从 Segment 卡片重新生成",
        transition_note: segmentNotes[ids[0]] || "",
      });
    } else {
      await generateSegments(pid.value, ids);
    }
    message.info(`${ids.length} 个 Segment 已进入生成队列`);
    await refresh();
  } catch (e) {
    ids.forEach((id) => { delete localActive[id]; });
    message.error(e.message || "Segment 生成启动失败");
  } finally {
    actionBusy.value = false;
  }
}

function generateRemaining() {
  const ids = segments.value
    .filter((segment) => !["completed", "generating"].includes(stateFor(segment).status))
    .map((segment) => segment.segment_id);
  if (!ids.length) return message.info("所有 Segment 均已生成");
  startSegments(ids);
}

async function renderFinal() {
  actionBusy.value = true;
  try {
    await createRender(pid.value, { segment_ids: segments.value.map((s) => s.segment_id) });
    message.info("正在拼接画面并回铺完整 Master Audio…");
    await refresh();
  } catch (e) {
    message.error(e.message || "成片合成启动失败");
  } finally {
    actionBusy.value = false;
  }
}

async function retryFailedStage() {
  actionBusy.value = true;
  try {
    if (audio.value.status === "failed") {
      await createAudio(pid.value, {
        voice: audio.value.voice_profile?.voice || "zh-CN-XiaoxiaoNeural",
        music: "ambient",
      });
      message.info("正在重新生成完整音轨…");
    } else if (audio.value.status === "ready" && !segments.value.length) {
      await createStoryboard(pid.value, project.value?.plan_id);
      message.info("正在重新规划 Segment…");
    } else {
      return router.push(`/plan/${pid.value}`);
    }
    await refresh();
  } catch (e) {
    message.error(e.message || "重试失败");
  } finally {
    actionBusy.value = false;
  }
}
</script>

<template>
  <div class="page">
    <header class="nav">
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
      <section v-if="phase === 'loading'" class="card center">
        <div class="spin-ring"></div>
        <p>正在读取项目…</p>
      </section>

      <section v-else-if="phase === 'preparing'" class="card preparing">
        <span class="eyebrow">音频优先工作流</span>
        <h1>{{ req.theme || "准备视频时间轴" }}</h1>
        <p>{{ project?.message }}</p>
        <div class="bar"><i :style="{ width: `${project?.progress || 12}%` }"></i></div>
        <ol class="steps">
          <li :class="{ done: ['audio_ready', 'storyboarding'].includes(project?.status) }">1. Edge-TTS 生成完整旁白并混合 BGM</li>
          <li :class="{ done: project?.status === 'storyboarding' }">2. 按句尾与场景边界规划 4–15 秒 Segment</li>
          <li>3. 在每个 Segment 内安排多个 Shot 与图片参考</li>
        </ol>
      </section>

      <template v-else-if="segments.length">
        <section class="card summary">
          <div>
            <span class="eyebrow">Master Audio + Segment</span>
            <h1>{{ req.theme }}</h1>
            <p>📍 {{ req.city }} · {{ req.location }}　⏱ {{ req.duration_s }}s　{{ req.aspect_ratio }}</p>
          </div>
          <div class="summary-status">
            <b>{{ project?.progress || 0 }}%</b>
            <span>{{ project?.message }}</span>
          </div>
        </section>

        <section class="card audio-card">
          <div>
            <h2>完整音轨</h2>
            <p>所有 Segment 都用对应的母带切片驱动画面；最终只回铺这一条原始母带。</p>
          </div>
          <audio v-if="audio.master_url" :src="audio.master_url" controls preload="metadata"></audio>
          <span class="audio-meta">v{{ audio.version }} · {{ fmtMs(audio.duration_ms) }}</span>
        </section>

        <div class="guide">
          <b>生成单位已经改为 Segment</b>
          <span>每段包含多个 Shot。Shot prompt 仍可编辑，但保存后需要重新生成所属的整段，以维持段内连续性。</span>
        </div>

        <section v-for="segment in segments" :key="segment.segment_id" class="segment-card">
          <header class="segment-head">
            <div>
              <div class="segment-title">
                <h2>{{ segment.segment_id }}</h2>
                <span class="status" :class="stateFor(segment).status">{{ statusLabel(stateFor(segment).status) }}</span>
              </div>
              <p>{{ fmtMs(segment.timeline_start_ms) }} – {{ fmtMs(segment.timeline_end_ms) }} · {{ shotsFor(segment).length }} 个 Shot · {{ segment.reference_asset_ids?.length || 0 }} 张参考图</p>
            </div>
            <NButton
              type="primary"
              :loading="stateFor(segment).status === 'generating'"
              :disabled="actionBusy || stateFor(segment).status === 'generating'"
              @click="startSegments([segment.segment_id], stateFor(segment).status !== 'pending')"
            >
              {{ stateFor(segment).status === 'completed' ? '重新生成此段' : '生成此段' }}
            </NButton>
          </header>

          <div class="transition-row">
            <NInput v-model:value="segmentNotes[segment.segment_id]" placeholder="描述段内镜头如何自然衔接" />
            <NButton :disabled="actionBusy" @click="saveSegmentNote(segment)">保存转场要求</NButton>
          </div>

          <div class="shot-list">
            <article v-for="shot in shotsFor(segment)" :key="shot.shot_id" class="shot-card">
              <div class="shot-meta">
                <b>Shot {{ shot.shot_id }}</b>
                <span>{{ fmtMs(shot.timeline_start_ms - segment.timeline_start_ms) }} – {{ fmtMs(shot.timeline_end_ms - segment.timeline_start_ms) }}</span>
                <span>{{ shot.scene_title }}</span>
              </div>
              <div class="shot-body">
                <template v-if="editingShotId === shot.shot_id">
                  <NInput v-model:value="editPrompt" type="textarea" :autosize="{ minRows: 3, maxRows: 7 }" />
                  <div class="inline-actions edit-actions">
                    <NButton @click="cancelEdit">取消</NButton>
                    <NButton type="primary" :loading="savingShot" @click="saveShot(shot)">保存并使整段失效</NButton>
                  </div>
                </template>
                <template v-else>
                  <p class="prompt">{{ shot.prompt }}</p>
                  <div class="inline-actions">
                    <span>{{ shot.shot_size }} · {{ shot.subject }}</span>
                    <NButton size="small" quaternary :disabled="stateFor(segment).status === 'generating'" @click="startEdit(shot)">编辑 Shot</NButton>
                  </div>
                </template>
              </div>
              <div v-if="refsFor(shot).length" class="refs">
                <a v-for="refImage in refsFor(shot)" :key="refImage.asset_id" :href="refImage.source_page_url || refImage.url" target="_blank">
                  <img :src="refImage.url" :alt="refImage.name || '实景参考'" />
                </a>
              </div>
            </article>
          </div>

          <div v-if="stateFor(segment).status === 'completed'" class="segment-preview">
            <video v-if="stateFor(segment).video_url" :src="stateFor(segment).video_url" controls preload="metadata"></video>
            <a v-if="stateFor(segment).video_url" :href="stateFor(segment).video_url" download>下载该段 Master Audio 预览版</a>
          </div>
          <p v-else-if="stateFor(segment).status === 'failed'" class="error-text">{{ stateFor(segment).error || '生成失败，请重新生成此 Segment' }}</p>
        </section>

        <section class="card final-actions">
          <div>
            <h2>{{ phase === 'completed' ? '成片已完成' : '完成所有 Segment 后合成' }}</h2>
            <p>画面按时间轴硬切拼接，并一次性回铺完整 Master Audio，避免跨段音色和 BGM 跳变。</p>
          </div>
          <div class="button-row">
            <NButton v-if="!['video_ready', 'composing', 'completed'].includes(phase)" type="primary" :disabled="actionBusy" @click="generateRemaining">生成所有待完成 Segment</NButton>
            <NButton v-if="phase === 'video_ready'" type="primary" :loading="actionBusy" @click="renderFinal">合成最终视频</NButton>
            <NButton v-if="phase === 'composing'" type="primary" loading>正在回铺 Master Audio</NButton>
          </div>
        </section>

        <section v-if="phase === 'completed' && finalVideo.url" class="card final-video">
          <video :src="finalVideo.url" controls preload="metadata"></video>
          <a :href="finalVideo.url" download>下载最终成片</a>
        </section>
      </template>

      <section v-else-if="phase === 'failed'" class="card center error-box">
        <h2>流程执行失败</h2>
        <p>{{ project?.message }}</p>
        <div class="button-row">
          <NButton v-if="audio.status === 'failed'" @click="router.push(`/plan/${pid}`)">缩短或修改旁白</NButton>
          <NButton type="primary" :loading="actionBusy" @click="retryFailedStage">重试当前阶段</NButton>
        </div>
      </section>

      <section v-else class="card center">
        <h2>项目状态：{{ project?.status }}</h2>
        <p>{{ project?.message }}</p>
        <NButton @click="refresh">刷新</NButton>
      </section>
    </main>

    <footer class="footer">TravelGen · 面向浙江文旅的 AIGC 短视频生成系统</footer>
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--color-bg); color: var(--color-ink); font-family: var(--font-sans); }
.nav { position: sticky; top: 0; z-index: 20; background: #fcf8f1; border-bottom: 1px solid var(--color-border); box-shadow: 0 2px 12px rgba(31, 41, 55, .05); }
.nav-inner { max-width: 1180px; margin: 0 auto; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
.logo { display: flex; align-items: center; gap: 13px; cursor: pointer; }
.logo-mark { width: 68px; height: 68px; border-radius: 12px; object-fit: cover; }
.logo-text { font-family: var(--font-serif); font-size: 24px; font-weight: 700; }
.nav-links { display: flex; gap: 20px; }
.nav-links a { color: var(--color-ink-sub); text-decoration: none; }
.stage { max-width: 1180px; margin: 0 auto; padding: 34px 24px 64px; }
.card, .segment-card { background: var(--color-card); border: 1px solid var(--color-border); border-radius: 14px; box-shadow: var(--shadow-card); }
.card { padding: 22px; }
.center { min-height: 260px; display: grid; place-items: center; align-content: center; gap: 14px; text-align: center; }
.spin-ring { width: 34px; height: 34px; border: 3px solid var(--color-primary-light); border-top-color: var(--color-primary); border-radius: 50%; animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.eyebrow { color: var(--color-primary); font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h1, h2, p { margin-top: 0; }
h1 { margin: 7px 0 8px; font-family: var(--font-serif); }
.preparing { padding: 42px; }
.preparing > p { color: var(--color-ink-sub); }
.bar { height: 9px; margin: 24px 0; overflow: hidden; border-radius: 99px; background: var(--color-border); }
.bar i { display: block; min-width: 8%; height: 100%; background: linear-gradient(90deg, #0f766e, #18a397); transition: width .3s; }
.steps { display: grid; gap: 10px; padding-left: 22px; color: var(--color-ink-sub); }
.steps li.done { color: var(--color-success); }
.summary { display: flex; justify-content: space-between; gap: 24px; align-items: center; margin-bottom: 16px; }
.summary p { margin-bottom: 0; color: var(--color-ink-sub); }
.summary-status { min-width: 210px; text-align: right; display: grid; gap: 3px; }
.summary-status b { font-size: 24px; color: var(--color-primary); }
.summary-status span { color: var(--color-ink-sub); font-size: 12px; }
.audio-card { margin-bottom: 16px; display: grid; grid-template-columns: 1fr minmax(260px, 420px) auto; gap: 18px; align-items: center; }
.audio-card h2 { margin-bottom: 6px; font-size: 18px; }
.audio-card p { margin-bottom: 0; color: var(--color-ink-sub); font-size: 13px; }
.audio-card audio { width: 100%; }
.audio-meta { color: var(--color-primary); font-size: 12px; white-space: nowrap; }
.guide { margin-bottom: 18px; padding: 13px 16px; display: flex; gap: 10px; border: 1px solid var(--color-primary-light); border-radius: 10px; background: var(--color-primary-fade); color: var(--color-ink-sub); font-size: 13px; }
.guide b { color: var(--color-primary-deep); white-space: nowrap; }
.segment-card { margin-bottom: 18px; padding: 20px; }
.segment-head { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding-bottom: 15px; border-bottom: 1px dashed var(--color-border); }
.segment-title { display: flex; align-items: center; gap: 10px; }
.segment-title h2 { margin: 0; font-size: 19px; color: var(--color-primary-deep); }
.segment-head p { margin: 5px 0 0; color: var(--color-ink-sub); font-size: 12px; }
.status { padding: 3px 9px; border-radius: 99px; font-size: 11px; background: #f2f2ef; color: var(--color-ink-sub); }
.status.completed, .status.ready { background: var(--color-primary-fade); color: var(--color-success); }
.status.generating { background: var(--color-gold-fade); color: var(--color-gold-ink); }
.status.failed, .status.stale { background: #fdf0ee; color: var(--color-error); }
.transition-row { display: grid; grid-template-columns: 1fr auto; gap: 10px; margin: 15px 0; }
.shot-list { display: grid; gap: 10px; }
.shot-card { display: grid; grid-template-columns: 210px 1fr auto; gap: 16px; padding: 14px; border: 1px solid var(--color-border); border-radius: 10px; background: #fffdfa; }
.shot-meta { display: flex; flex-direction: column; gap: 5px; color: var(--color-ink-sub); font-size: 12px; }
.shot-meta b { color: var(--color-primary-deep); font-size: 14px; }
.shot-body { min-width: 0; }
.prompt { margin-bottom: 10px; color: var(--color-ink); font-size: 13px; line-height: 1.7; }
.inline-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; color: var(--color-ink-sub); font-size: 11px; }
.inline-actions span { margin-right: auto; }
.edit-actions { margin-top: 8px; }
.refs { display: flex; gap: 6px; align-items: flex-start; max-width: 180px; flex-wrap: wrap; }
.refs a { width: 54px; height: 42px; border-radius: 6px; overflow: hidden; border: 1px solid var(--color-primary-light); }
.refs img { width: 100%; height: 100%; object-fit: cover; }
.segment-preview { margin-top: 15px; display: grid; gap: 8px; }
.segment-preview video, .final-video video { width: 100%; max-height: 520px; border-radius: 10px; background: #000; }
.segment-preview a, .final-video a { width: fit-content; color: var(--color-primary); text-decoration: none; font-size: 13px; }
.error-text { color: var(--color-error); font-size: 13px; }
.final-actions { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 22px; }
.final-actions h2 { margin-bottom: 6px; font-size: 18px; }
.final-actions p { margin-bottom: 0; color: var(--color-ink-sub); font-size: 13px; }
.button-row { flex-shrink: 0; }
.final-video { margin-top: 16px; display: grid; gap: 12px; }
.error-box h2 { color: var(--color-error); }
.footer { max-width: 1180px; margin: 0 auto; padding: 22px 24px 30px; border-top: 1px solid var(--color-border); text-align: center; color: var(--color-ink-sub); font-size: 12px; }
@media (max-width: 820px) {
  .summary, .final-actions, .guide { align-items: stretch; flex-direction: column; }
  .summary-status { text-align: left; }
  .audio-card { grid-template-columns: 1fr; }
  .shot-card { grid-template-columns: 1fr; }
  .refs { max-width: none; }
  .transition-row { grid-template-columns: 1fr; }
}
</style>
