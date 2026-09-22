<script setup>
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NInput, NSlider, useMessage } from "naive-ui";
import logoUrl from "../images/logo.png";
import {
  createRender,
  createStoryboard,
  createVoiceCandidate,
  generateSegments,
  getBgmCatalog,
  getProject,
  getRenderStatus,
  getVoicePresets,
  mixRender,
  regenerateSegment,
  refreshBgmRecommendations,
  selectBgm,
  selectVoice,
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
const voicePresets = ref([]);
const bgmTracks = ref([]);
const customVoiceDescription = ref(
  "温暖、自然、像真实旅行讲述者，普通话清晰但不过度播音",
);
const editingShotId = ref(null);
const editPrompt = ref("");
const editNarration = ref("");
const editDuration = ref(4);
const savingShot = ref(false);
const segmentNotes = reactive({});
const localActive = reactive({});
const actionBusy = ref(false);
const mixPending = ref(false);
const selectedVariant = ref("with_bgm");
const bgmGainDb = ref(0);
const videoGainDb = ref(0);
const previewVideo = ref(null);
const previewBgm = ref(null);
let timer = null;
let refreshing = false;
let storyboardTriggered = false;
let seenFinalVersion = null;
let seenMixVersion = null;
let previewAudioStarting = false;

const req = computed(() => project.value?.request || {});
const scenes = computed(() => project.value?.storyboard?.scenes || []);
const segments = computed(() => project.value?.storyboard?.segments || []);
const voice = computed(() => project.value?.voice || {});
const music = computed(() => project.value?.music || {});
const voiceCandidates = computed(() => project.value?.voice_candidates || []);
const segmentResults = computed(() => project.value?.segment_results || {});
const finalVideo = computed(() => project.value?.final_video || {});
const voiceReady = computed(() => voice.value.status === "selected");
const musicReady = computed(() =>
  ["selected", "explicit_none"].includes(music.value.status),
);
const soundReady = computed(() => voiceReady.value && musicReady.value);
const mixChanged = computed(() =>
  Number(videoGainDb.value) !== Number(finalVideo.value.bgm_mix?.video_gain_db ?? 0) ||
  Number(bgmGainDb.value) !== Number(finalVideo.value.bgm_mix?.bgm_gain_db ?? 0),
);
const sortedBgmTracks = computed(() => [...bgmTracks.value].sort((a, b) =>
  Number(b.scene_type === req.value.scene_type) - Number(a.scene_type === req.value.scene_type),
));
const recommendation = computed(() => music.value.recommendation || null);
const finalSource = computed(() => {
  if (selectedVariant.value === "mix_preview" && finalVideo.value.bgm_bed?.url)
    return finalVideo.value.clean?.url;
  if (selectedVariant.value === "with_bgm" && finalVideo.value.with_bgm?.url)
    return finalVideo.value.with_bgm.url;
  return finalVideo.value.clean?.url || finalVideo.value.url;
});
const shotById = computed(() => {
  const rows = {};
  for (const scene of scenes.value) {
    for (const shot of scene.shot_list || [])
      rows[shot.shot_id] = { ...shot, scene_title: scene.title };
  }
  return rows;
});
const referenceById = computed(() =>
  Object.fromEntries(
    (project.value?.visual_assets?.ref_images || []).map((item) => [
      item.asset_id,
      item,
    ]),
  ),
);
const phase = computed(() => {
  const status = project.value?.status;
  if (!project.value || loading.value) return "loading";
  if (["plan_confirmed", "storyboarding"].includes(status)) return "preparing";
  if (status === "waiting_storyboard_confirm") return "editing";
  if (status === "generating") return "generating";
  if (status === "video_ready") return "video_ready";
  if (status === "composing") return "composing";
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "other";
});
const activeIds = computed(
  () => new Set(project.value?.active_segment_ids || []),
);

function shotsFor(segment) {
  return (segment.shot_ids || [])
    .map((id) => shotById.value[id])
    .filter(Boolean);
}
function refsFor(shot) {
  return (shot.reference_asset_ids || [])
    .map((id) => referenceById.value[id])
    .filter(Boolean);
}
function stateFor(segment) {
  if (
    activeIds.value.has(segment.segment_id) ||
    localActive[segment.segment_id]
  )
    return { status: "generating" };
  return (
    segmentResults.value[segment.segment_id] || {
      status: segment.status || "pending",
    }
  );
}
function statusLabel(status) {
  return (
    {
      pending: "待生成",
      stale: "需重新生成",
      generating: "生成中",
      completed: "已生成",
      failed: "生成失败",
      ready: "已生成",
    }[status] || status
  );
}
function fmtMs(ms) {
  return `${(Number(ms || 0) / 1000).toFixed(1)}s`;
}
function playAudioPreview(event) {
  for (const audio of document.querySelectorAll(".selector-card audio")) {
    if (audio !== event.target) audio.pause();
  }
}
function isRecommended(track) {
  return track.scene_type === req.value.scene_type;
}

function syncPreviewAudio() {
  const video = previewVideo.value;
  const audio = previewBgm.value;
  if (!video || !audio || selectedVariant.value !== "mix_preview") return;
  if (Math.abs(audio.currentTime - video.currentTime) > 0.3)
    audio.currentTime = video.currentTime;
  audio.playbackRate = video.playbackRate;
  if (video.paused || video.ended) audio.pause();
  else if (audio.paused && !previewAudioStarting) {
    previewAudioStarting = true;
    audio.play().catch((error) => {
      if (selectedVariant.value === "mix_preview" && error.name !== "AbortError")
        message.warning("BGM 试听播放失败，请重试播放");
    }).finally(() => { previewAudioStarting = false; });
  }
}

function stopPreviewAudio() {
  previewBgm.value?.pause();
  previewAudioStarting = false;
}

function applyPreviewVolumes() {
  if (previewVideo.value) {
    previewVideo.value.muted = false;
    previewVideo.value.volume = selectedVariant.value === "mix_preview"
      ? gainToVolume(videoGainDb.value) : 1;
  }
  if (previewBgm.value) previewBgm.value.volume = gainToVolume(bgmGainDb.value);
}

function gainToVolume(db) {
  return db <= -60 ? 0 : 10 ** (db / 20);
}

function gainLabel(db) {
  return db <= -60 ? "静音" : `${db} dB`;
}

function onVideoVolumeChange() {
  const video = previewVideo.value;
  if (!video || selectedVariant.value !== "mix_preview") return;
  const next = video.muted || !video.volume ? -60 :
    Math.max(-60, Math.round(20 * Math.log10(video.volume)));
  if (next !== videoGainDb.value) videoGainDb.value = next;
}

watch([videoGainDb, bgmGainDb], applyPreviewVolumes);
watch(selectedVariant, () => { stopPreviewAudio(); applyPreviewVolumes(); });

function syncProject(next) {
  project.value = next;
  if (
    finalVideo.value.version &&
    finalVideo.value.version !== seenFinalVersion
  ) {
    seenFinalVersion = finalVideo.value.version;
    selectedVariant.value = finalVideo.value.bgm_bed ? "mix_preview" :
      finalVideo.value.with_bgm ? "with_bgm" : "clean";
  }
  const mixVersion = `${finalVideo.value.version || 0}:${finalVideo.value.mix_version || 0}`;
  if (mixVersion !== seenMixVersion) {
    seenMixVersion = mixVersion;
    videoGainDb.value = Number(finalVideo.value.bgm_mix?.video_gain_db ?? 0);
    bgmGainDb.value = Number(finalVideo.value.bgm_mix?.bgm_gain_db ?? 0);
  } else if (
    !finalVideo.value.with_bgm &&
    selectedVariant.value === "with_bgm"
  ) {
    selectedVariant.value = "clean";
  }
  for (const segment of next.storyboard?.segments || []) {
    if (!(segment.segment_id in segmentNotes))
      segmentNotes[segment.segment_id] = segment.transition_note || "";
    const result = next.segment_results?.[segment.segment_id];
    if (
      !(next.active_segment_ids || []).includes(segment.segment_id) &&
      result?.status !== "generating"
    )
      delete localActive[segment.segment_id];
  }
}

async function advancePipeline(next) {
  if (next.status !== "plan_confirmed" || storyboardTriggered) return;
  storyboardTriggered = true;
  try {
    await createStoryboard(pid.value, next.plan_id);
    message.info("正在准备 Shot 镜头方案和音乐…");
  } catch (error) {
    if (error.status !== 409)
      message.error(error.message || "分镜生成启动失败");
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const next = await getProject(pid.value);
    syncProject(next);
    if (mixPending.value) {
      const status = await getRenderStatus(pid.value);
      if (status.status === "completed") {
        mixPending.value = false;
        message.success("双轨音量已导出，可下载带 BGM 版");
      } else if (status.status === "failed") {
        mixPending.value = false;
        message.error(status.message || "混音失败，原成片仍可使用");
      }
    }
    await advancePipeline(next);
  } catch (error) {
    if (error.status === 404) router.replace("/");
  } finally {
    loading.value = false;
    refreshing = false;
  }
}
async function loadCatalogs() {
  try {
    const [voices, bgm] = await Promise.all([
      getVoicePresets(),
      getBgmCatalog(),
    ]);
    voicePresets.value = voices.voices || [];
    bgmTracks.value = bgm.tracks || [];
  } catch (error) {
    message.error(error.message || "音色或 BGM 素材加载失败");
  }
}
function stopPolling() {
  if (timer) clearInterval(timer);
  timer = null;
}
function startPolling() {
  stopPolling();
  loading.value = true;
  storyboardTriggered = false;
  refresh();
  timer = setInterval(refresh, POLL_MS);
}
onMounted(() => {
  loadCatalogs();
  startPolling();
});
onBeforeUnmount(() => { stopPolling(); stopPreviewAudio(); });
watch(pid, (next, previous) => {
  if (next && next !== previous) {
    stopPreviewAudio();
    mixPending.value = false;
    seenFinalVersion = null;
    seenMixVersion = null;
    startPolling();
  }
});

async function chooseVoice(payload) {
  actionBusy.value = true;
  try {
    await selectVoice(pid.value, payload);
    message.success("参考音色已确认，后续所有 Segment 都会使用它");
    await refresh();
  } catch (error) {
    message.error(error.message || "音色确认失败");
  } finally {
    actionBusy.value = false;
  }
}
async function generateCustomVoice() {
  const description = customVoiceDescription.value.trim();
  if (description.length < 2) return message.warning("请先描述希望的声音");
  actionBusy.value = true;
  try {
    await createVoiceCandidate(pid.value, description);
    message.info("Seedance 正在生成试听样本，完成后可试听并确认");
    await refresh();
  } catch (error) {
    message.error(error.message || "自定义音色生成失败");
  } finally {
    actionBusy.value = false;
  }
}
async function chooseBgm(bgmId = null) {
  actionBusy.value = true;
  try {
    await selectBgm(
      pid.value,
      bgmId
        ? { bgm_id: bgmId }
        : { explicit_none: true },
    );
    message.success(
      bgmId ? "BGM 已确认，仅在最终合成时加入" : "已确认导出时不添加 BGM",
    );
    await refresh();
  } catch (error) {
    message.error(error.message || "BGM 确认失败");
  } finally {
    actionBusy.value = false;
  }
}
async function applyMix() {
  if (!finalVideo.value.bgm_bed) return message.warning("请先合成带 BGM 的视频");
  actionBusy.value = true;
  try {
    await mixRender(pid.value, {
      video_gain_db: videoGainDb.value,
      bgm_gain_db: bgmGainDb.value,
    });
    mixPending.value = true;
    message.info("正在按试听音量导出，Segment 无需重新生成");
    await refresh();
  } catch (error) {
    message.error(error.message || "混音导出失败");
  } finally {
    actionBusy.value = false;
  }
}
async function rerunRecommendations() {
  actionBusy.value = true;
  try {
    await refreshBgmRecommendations(pid.value);
    message.info("KIMI 正在根据方案、旁白和分镜分析选曲方向…");
    await refresh();
  } catch (error) {
    message.error(error.message || "BGM 推荐启动失败");
  } finally {
    actionBusy.value = false;
  }
}

function startEdit(shot) {
  editingShotId.value = shot.shot_id;
  editPrompt.value = shot.prompt || "";
  editNarration.value = shot.narration || "";
  editDuration.value = Number(shot.duration_s || 4);
}
function cancelEdit() {
  editingShotId.value = null;
  editPrompt.value = "";
  editNarration.value = "";
}
async function saveShot(shot) {
  const prompt = editPrompt.value.trim();
  if (!prompt) return message.warning("Prompt 不能为空");
  savingShot.value = true;
  try {
    const patch = { prompt, narration: editNarration.value.trim() };
    if (Number(editDuration.value) !== Number(shot.duration_s))
      patch.duration_s = editDuration.value;
    const response = await updateShot(pid.value, shot.shot_id, patch);
    cancelEdit();
    message.success(
      response.invalidated_segment_ids?.length > 1
        ? "时长已更新，全部 Segment 已重新动态分组"
        : "所属 Segment 已标记为需重新生成",
    );
    await refresh();
  } catch (error) {
    message.error(error.message || "Shot 保存失败");
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
  } catch (error) {
    message.error(error.message || "保存失败");
  } finally {
    actionBusy.value = false;
  }
}
async function startSegments(ids, regenerate = false) {
  if (!soundReady.value) return message.warning("请先确认参考音色和 BGM 选择");
  if (!ids.length) return;
  actionBusy.value = true;
  ids.forEach((id) => {
    localActive[id] = true;
  });
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
  } catch (error) {
    ids.forEach((id) => {
      delete localActive[id];
    });
    message.error(error.message || "Segment 生成启动失败");
  } finally {
    actionBusy.value = false;
  }
}
function generateRemaining() {
  const ids = segments.value
    .filter(
      (segment) =>
        !["completed", "generating"].includes(stateFor(segment).status),
    )
    .map((segment) => segment.segment_id);
  if (!ids.length) return message.info("所有 Segment 均已生成");
  startSegments(ids);
}
async function renderFinal() {
  actionBusy.value = true;
  try {
    await createRender(pid.value, {
      segment_ids: segments.value.map((segment) => segment.segment_id),
    });
    message.info("正在拼接 Seedance 原生音视频，并在完整时间线上混合所选 BGM…");
    await refresh();
  } catch (error) {
    message.error(error.message || "成片合成启动失败");
  } finally {
    actionBusy.value = false;
  }
}
async function retryFailedStage() {
  actionBusy.value = true;
  try {
    await createStoryboard(pid.value, project.value?.plan_id);
    message.info("正在重新准备 Shot 镜头方案和音乐…");
    await refresh();
  } catch (error) {
    message.error(error.message || "重试失败");
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
          <img :src="logoUrl" class="logo-mark" alt="TravelGen" /><span
            class="logo-text gradient-text"
            >TravelGen</span
          >
        </div>
        <nav class="nav-links">
          <a href="#" @click.prevent="router.push('/')">工作台</a
          ><router-link v-if="isLoggedIn()" to="/history">我的创作</router-link>
        </nav>
      </div>
    </header>
    <main class="stage">
      <section v-if="phase === 'loading'" class="card center">
        <div class="spin-ring"></div>
        <p>正在读取项目…</p>
      </section>
      <section v-else-if="phase === 'preparing'" class="card processing-card">
        <div class="orbit" aria-hidden="true">
          <span
            class="orbit-core iconfont icon-huabansikao"
            role="img"
            aria-label="AI 正在思考"
          ></span>
          <i v-for="n in 3" :key="n" :class="`orbit-dot dot-${n}`"></i>
        </div>
        <span class="state-badge">创作准备中</span>
        <h2>正在准备 Shot 镜头方案和音乐</h2>
        <p>正在根据已确认的文案与画面参考完善镜头，并匹配合适的音乐建议</p>
        <div class="bar-track" aria-hidden="true">
          <span class="bar-fill"></span>
        </div>
        <small>准备完成后将自动进入镜头方案页面，请勿关闭。</small>
      </section>

      <template v-else-if="segments.length">
        <section class="card summary">
          <div>
            <span class="eyebrow">Seedance Native Audio Pipeline</span>
            <h1>{{ req.theme }}</h1>
            <p>
              📍 {{ req.city }} · {{ req.location }}　⏱
              {{ req.duration_s }}s　{{ req.aspect_ratio }}
            </p>
          </div>
          <div class="summary-status">
            <b>{{ project?.progress || 0 }}%</b
            ><span>{{ project?.message }}</span>
          </div>
        </section>

        <section class="card selector-card">
          <div class="section-head">
            <div>
              <h2>1. 选择统一参考音色</h2>
              <p>
                同一个参考音频会注入每个 Segment。Seedance
                只参考说话人身份，并自行生成本段旁白与环境声。
              </p>
            </div>
            <span class="selection-state" :class="{ ready: voiceReady }">{{
              voiceReady ? `已选：${voice.name}` : "尚未选择"
            }}</span>
          </div>
          <div class="media-grid voices">
            <article
              v-for="item in voicePresets"
              :key="item.voice_id"
              class="media-option"
              :class="{ selected: voice.voice_id === item.voice_id }"
            >
              <div>
                <b>{{ item.name }}</b>
                <p>{{ item.description }}</p>
                <small>{{ (item.recommended_scenes || []).join(" · ") }}</small>
              </div>
              <audio :src="item.preview_url" controls preload="none" @play="playAudioPreview"></audio
              ><NButton
                size="small"
                :type="voice.voice_id === item.voice_id ? 'primary' : 'default'"
                :disabled="actionBusy"
                @click="chooseVoice({ voice_id: item.voice_id })"
                >{{
                  voice.voice_id === item.voice_id ? "已选择" : "使用此音色"
                }}</NButton
              >
            </article>
          </div>
          <div class="custom-voice">
            <div>
              <b>预设都不合适？让 Seedance 生成试听音色</b>
              <p>
                描述年龄感、音高、气质、语速和口音；系统会抽取生成视频中的音轨作为候选参考。
              </p>
            </div>
            <NInput
              v-model:value="customVoiceDescription"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
            /><NButton
              type="primary"
              :disabled="actionBusy"
              @click="generateCustomVoice"
              >生成试听</NButton
            >
          </div>
          <div v-if="voiceCandidates.length" class="candidate-list">
            <article
              v-for="candidate in [...voiceCandidates].reverse()"
              :key="candidate.task_id"
              class="candidate"
            >
              <div>
                <b>自定义候选</b>
                <p>{{ candidate.request?.description }}</p>
                <small>{{ candidate.message || candidate.status }}</small>
              </div>
              <audio
                v-if="candidate.result?.preview_url"
                :src="candidate.result.preview_url"
                controls
                preload="none"
                @play="playAudioPreview"
              ></audio
              ><NButton
                v-if="candidate.status === 'completed'"
                size="small"
                :type="
                  voice.voice_id === candidate.result?.voice_id
                    ? 'primary'
                    : 'default'
                "
                :disabled="actionBusy"
                @click="chooseVoice({ candidate_task_id: candidate.task_id })"
                >{{
                  voice.voice_id === candidate.result?.voice_id
                    ? "已选择"
                    : "确认此音色"
                }}</NButton
              ><NButton
                v-else-if="candidate.status === 'generating'"
                size="small"
                loading
                >生成中</NButton
              ><span v-else class="error-text">{{
                candidate.error || "生成失败"
              }}</span>
            </article>
          </div>
        </section>

        <section class="card selector-card">
          <div class="section-head">
            <div>
              <h2>2. 选择后期 BGM</h2>
              <p>
                同场景类型的曲目已用绿色标出。BGM 会在视频拼接后加入，音量可在成片页试听调整。
              </p>
            </div>
            <div class="head-actions">
              <span class="selection-state" :class="{ ready: musicReady }">{{
                music.status === "selected"
                  ? `已选：${music.selected?.title}`
                  : music.status === "explicit_none"
                    ? "已选：无 BGM"
                    : "尚未选择"
              }}</span
              ><NButton
                size="small"
                :loading="music.recommendation_status === 'recommending'"
                :disabled="actionBusy"
                @click="rerunRecommendations"
                >不满意现有曲目？让 KIMI 建议选曲方向</NButton
              >
            </div>
          </div>
          <div v-if="recommendation" class="recommendations">
            <b>KIMI 给出的独立选曲方向</b>
            <p><strong>类型：</strong>{{ recommendation.style }} · <strong>节奏：</strong>{{ recommendation.tempo }}</p>
            <p><strong>乐器/音色：</strong>{{ recommendation.instruments }} · <strong>情绪：</strong>{{ recommendation.mood }}</p>
            <p>{{ recommendation.reason }}</p>
            <p v-if="recommendation.search_keywords?.length">检索词：{{ recommendation.search_keywords.join('、') }}</p>
            <p v-if="recommendation.example_tracks?.length">参考曲目：{{ recommendation.example_tracks.join('、') }}</p>
          </div>
          <p v-if="music.recommendation_status === 'failed'" class="error-text">{{ music.warning }}</p>
          <div class="media-grid bgms">
            <article
              v-for="track in sortedBgmTracks"
              :key="track.bgm_id"
              class="media-option"
              :class="{
                selected: music.selected?.bgm_id === track.bgm_id,
                recommended: isRecommended(track),
              }"
            >
              <div>
                <b
                  >{{ track.title }}
                  <i v-if="isRecommended(track)">匹配类型</i></b
                >
                <p>{{ track.description }}</p>
                <small
                  >{{ track.scene }} · {{ track.artist }} ·
                  {{ track.duration }}</small
                >
              </div>
              <audio :src="track.preview_url" controls preload="none" @play="playAudioPreview"></audio>
              <NButton
                size="small"
                :type="
                  music.selected?.bgm_id === track.bgm_id
                    ? 'primary'
                    : 'default'
                "
                :disabled="actionBusy"
                @click="chooseBgm(track.bgm_id)"
                >{{
                  music.selected?.bgm_id === track.bgm_id
                    ? "已选择"
                    : "选择此 BGM"
                }}</NButton
              >
            </article>
          </div>
          <div class="no-bgm">
            <div>
              <b>不添加 BGM</b>
              <p>
                最终只保留 Seedance
                生成的旁白、自然环境声和克制拟音，方便导入剪辑软件自行配乐。
              </p>
            </div>
            <NButton
              :type="music.status === 'explicit_none' ? 'primary' : 'default'"
              :disabled="actionBusy"
              @click="chooseBgm()"
              >{{
                music.status === "explicit_none" ? "已选择" : "选择无 BGM"
              }}</NButton
            >
          </div>
        </section>

        <div class="guide" :class="{ blocked: !soundReady }">
          <b>{{
            soundReady
              ? "声音设置已确认，可以生成 Segment"
              : "生成前还需要确认声音设置"
          }}</b
          ><span
            >Segment 只是 Seedance 15 秒限制下的调用容器；完整 Shot 不会为了填满
            15 秒而被拆开。Seedance 被强约束为不生成任何 BGM。</span
          >
        </div>

        <section
          v-for="segment in segments"
          :key="segment.segment_id"
          class="segment-card"
        >
          <header class="segment-head">
            <div>
              <div class="segment-title">
                <h2>{{ segment.segment_id }}</h2>
                <span class="status" :class="stateFor(segment).status">{{
                  statusLabel(stateFor(segment).status)
                }}</span
                ><span class="no-music-badge">禁止 Seedance BGM</span>
              </div>
              <p>
                {{ fmtMs(segment.timeline_start_ms) }} –
                {{ fmtMs(segment.timeline_end_ms) }} · 实际
                {{ fmtMs(segment.duration_ms) }} ·
                {{ shotsFor(segment).length }} 个完整 Shot
              </p>
            </div>
            <NButton
              type="primary"
              :loading="stateFor(segment).status === 'generating'"
              :disabled="
                actionBusy ||
                !soundReady ||
                stateFor(segment).status === 'generating'
              "
              @click="
                startSegments(
                  [segment.segment_id],
                  stateFor(segment).status === 'completed',
                )
              "
              >{{
                stateFor(segment).status === "completed"
                  ? "重新生成此段"
                  : "生成此段"
              }}</NButton
            >
          </header>
          <div class="narration">
            <b>本段旁白</b>
            <p>
              {{ segment.narration_text || "本段没有旁白，仅保留自然环境声" }}
            </p>
          </div>
          <div class="transition-row">
            <NInput
              v-model:value="segmentNotes[segment.segment_id]"
              placeholder="描述段内镜头如何自然衔接"
            /><NButton :disabled="actionBusy" @click="saveSegmentNote(segment)"
              >保存转场要求</NButton
            >
          </div>
          <div class="shot-list">
            <article
              v-for="shot in shotsFor(segment)"
              :key="shot.shot_id"
              class="shot-card"
            >
              <div class="shot-meta">
                <b>Shot {{ shot.shot_id }}</b
                ><span
                  >{{ fmtMs(shot.segment_local_start_ms) }} –
                  {{ fmtMs(shot.segment_local_end_ms) }}</span
                ><span>{{ shot.scene_title }}</span>
              </div>
              <div class="shot-body">
                <template v-if="editingShotId === shot.shot_id"
                  ><label>画面 Prompt</label
                  ><NInput
                    v-model:value="editPrompt"
                    type="textarea"
                    :autosize="{ minRows: 3, maxRows: 7 }"
                  /><label>本 Shot 旁白</label
                  ><NInput
                    v-model:value="editNarration"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                  /><label>时长（改变后会重新动态分组）</label
                  ><NInputNumber
                    v-model:value="editDuration"
                    :min="1"
                    :max="15"
                    :precision="0"
                  />
                  <div class="inline-actions edit-actions">
                    <NButton @click="cancelEdit">取消</NButton
                    ><NButton
                      type="primary"
                      :loading="savingShot"
                      @click="saveShot(shot)"
                      >保存</NButton
                    >
                  </div></template
                ><template v-else
                  ><p class="prompt">{{ shot.prompt }}</p>
                  <p class="shot-narration">
                    旁白：{{ shot.narration || "无" }}
                  </p>
                  <div class="inline-actions">
                    <span
                      >{{ shot.duration_s }}s · {{ shot.shot_size }} ·
                      {{ shot.subject }}</span
                    ><NButton
                      size="small"
                      quaternary
                      :disabled="stateFor(segment).status === 'generating'"
                      @click="startEdit(shot)"
                      >编辑 Shot</NButton
                    >
                  </div></template
                >
              </div>
              <div v-if="refsFor(shot).length" class="refs">
                <a
                  v-for="refImage in refsFor(shot)"
                  :key="refImage.asset_id"
                  :href="refImage.source_page_url || refImage.url"
                  target="_blank"
                  ><img :src="refImage.url" :alt="refImage.name || '实景参考'"
                /></a>
              </div>
            </article>
          </div>
          <div
            v-if="stateFor(segment).status === 'completed'"
            class="segment-preview"
          >
            <video
              v-if="stateFor(segment).video_url"
              :src="stateFor(segment).video_url"
              controls
              preload="metadata"
            ></video>
            <div class="preview-meta">
              <span
                >此处播放 Seedance 原生音轨：旁白 + 环境声 + 拟音，无后期
                BGM</span
              ><span v-if="stateFor(segment).audio_qa"
                >音轨 {{ stateFor(segment).audio_qa.has_audio ? "✓" : "⚠" }} ·
                时长 {{ stateFor(segment).audio_qa.duration_ok ? "✓" : "⚠" }} ·
                BGM 需人工试听</span
              >
            </div>
            <a
              v-if="stateFor(segment).video_url"
              :href="stateFor(segment).video_url"
              download
              >下载该段原生音视频</a
            >
          </div>
          <p
            v-else-if="stateFor(segment).status === 'failed'"
            class="error-text"
          >
            {{ stateFor(segment).error || "生成失败，请重新生成此 Segment" }}
          </p>
        </section>

        <section class="card final-actions">
          <div>
            <h2>
              {{
                phase === "completed" ? "成片已完成" : "完成所有 Segment 后合成"
              }}
            </h2>
            <p>
              拼接完成后可在下方同时调节视频原声（旁白和环境声）与 BGM，试听后导出新的混音版。
            </p>
          </div>
          <div class="button-row">
            <NButton
              v-if="!['video_ready', 'composing', 'completed'].includes(phase)"
              type="primary"
              :disabled="actionBusy || !soundReady"
              @click="generateRemaining"
              >生成所有待完成 Segment</NButton
            ><NButton
              v-if="phase === 'video_ready'"
              type="primary"
              :loading="actionBusy"
              @click="renderFinal"
              >合成最终视频</NButton
            ><NButton
              v-if="phase === 'completed' && music.status === 'selected' && !finalVideo.bgm_bed?.url"
              :loading="actionBusy"
              @click="renderFinal"
              >重新合成声轨</NButton
            ><NButton v-if="phase === 'composing'" type="primary" loading
              >正在合成双版本</NButton
            >
          </div>
        </section>
        <section
          v-if="phase === 'completed' && finalSource"
          class="card final-video"
        >
          <div class="variant-tabs">
            <NButton
              :type="selectedVariant === 'clean' ? 'primary' : 'default'"
              @click="selectedVariant = 'clean'"
              >纯净版：旁白 + 环境声</NButton
            ><NButton
              v-if="finalVideo.bgm_bed?.url"
              :type="selectedVariant === 'mix_preview' ? 'primary' : 'default'"
              @click="selectedVariant = 'mix_preview'"
              >双轨调音试听</NButton
            ><NButton
              v-if="finalVideo.with_bgm"
              :type="selectedVariant === 'with_bgm' ? 'primary' : 'default'"
              @click="selectedVariant = 'with_bgm'"
              >展示版：加入 BGM</NButton
            >
          </div>
          <video
            ref="previewVideo"
            :key="finalSource"
            :src="finalSource"
            controls
            preload="metadata"
            @play="syncPreviewAudio"
            @pause="stopPreviewAudio"
            @ended="stopPreviewAudio"
            @seeked="syncPreviewAudio"
            @timeupdate="syncPreviewAudio"
            @ratechange="syncPreviewAudio"
            @loadedmetadata="applyPreviewVolumes"
            @volumechange="onVideoVolumeChange"
          ></video>
          <audio
            v-if="finalVideo.bgm_bed?.url"
            ref="previewBgm"
            :src="finalVideo.bgm_bed.url"
            preload="auto"
            @loadedmetadata="applyPreviewVolumes"
          ></audio>
          <div v-if="finalVideo.bgm_bed?.url" class="bgm-gain-control">
            <div class="bgm-gain-head">
              <div>
                <b>双轨音量</b>
                <p>切到“双轨调音试听”后播放视频，边听边调整旁白与配乐的比例。0 dB 为原始音量。</p>
              </div>
            </div>
            <div class="mix-track">
              <label>视频原声 <small>旁白 + 环境声</small></label>
              <NSlider v-model:value="videoGainDb" :min="-60" :max="0" :step="1" :tooltip="true"
                :disabled="mixPending" @update:value="selectedVariant = 'mix_preview'" />
              <strong>{{ gainLabel(videoGainDb) }}</strong>
            </div>
            <div class="mix-track">
              <label>BGM <small>{{ music.selected?.title }}</small></label>
              <NSlider v-model:value="bgmGainDb" :min="-60" :max="0" :step="1" :tooltip="true"
                :disabled="mixPending" @update:value="selectedVariant = 'mix_preview'" />
              <strong>{{ gainLabel(bgmGainDb) }}</strong>
            </div>
            <NButton type="primary" :loading="actionBusy || mixPending" :disabled="actionBusy || mixPending || !mixChanged"
              @click="applyMix">按当前音量导出混音版</NButton>
            <p class="mix-note">下载“带 BGM 版”可获取最近一次导出的音量。</p>
          </div>
          <p v-else-if="finalVideo.with_bgm" class="mix-note">此成片尚无独立 BGM 声轨，请点“重新合成声轨”后调音。</p>
          <div class="download-row">
            <a
              v-if="finalVideo.clean?.url"
              :href="finalVideo.clean.url"
              download
              >下载纯净版</a
            ><a
              v-if="finalVideo.with_bgm?.url"
              :href="finalVideo.with_bgm.url"
              download
              >下载带 BGM 版</a
            >
          </div>
        </section>
      </template>

      <section v-else-if="phase === 'failed'" class="card center error-box">
        <h2>流程执行失败</h2>
        <p>{{ project?.message }}</p>
        <div class="button-row">
          <NButton @click="router.push(`/plan/${pid}`)">返回修改文案</NButton
          ><NButton
            type="primary"
            :loading="actionBusy"
            @click="retryFailedStage"
            >重新生成分镜</NButton
          >
        </div>
      </section>
      <section v-else class="card center">
        <h2>项目状态：{{ project?.status }}</h2>
        <p>{{ project?.message }}</p>
        <NButton @click="refresh">刷新</NButton>
      </section>
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
  color: var(--color-ink);
  font-family: var(--font-sans);
}
.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #fcf8f1;
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 2px 12px rgba(31, 41, 55, 0.05);
}
.nav-inner {
  max-width: 1180px;
  margin: 0 auto;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo {
  display: flex;
  align-items: center;
  gap: 13px;
  cursor: pointer;
}
.logo-mark {
  width: 68px;
  height: 68px;
  border-radius: 12px;
  object-fit: cover;
}
.logo-text {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
}
.nav-links {
  display: flex;
  gap: 20px;
}
.nav-links a {
  color: var(--color-ink-sub);
  text-decoration: none;
}
.stage {
  max-width: 1180px;
  margin: 0 auto;
  padding: 34px 24px 64px;
}
.card,
.segment-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  box-shadow: var(--shadow-card);
}
.card {
  padding: 22px;
}
.center {
  min-height: 260px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 14px;
  text-align: center;
}
.spin-ring {
  width: 34px;
  height: 34px;
  border: 3px solid var(--color-primary-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.eyebrow {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
h1,
h2,
p {
  margin-top: 0;
}
h1 {
  margin: 7px 0 8px;
  font-family: var(--font-serif);
}
.summary p {
  color: var(--color-ink-sub);
}
.processing-card {
  min-height: 370px;
  padding: 54px 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.processing-card h2 {
  margin: 14px 0 8px;
  font-family: var(--font-serif);
  font-size: 27px;
  color: var(--color-primary-deep);
}
.processing-card p {
  max-width: 650px;
  margin: 0 0 22px;
  color: var(--color-ink-sub);
  line-height: 1.7;
}
.processing-card small {
  color: #9ca3af;
}
.state-badge {
  padding: 5px 11px;
  border: 1px solid var(--color-primary-light);
  border-radius: 99px;
  color: var(--color-primary);
  background: var(--color-primary-fade);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.orbit {
  width: 92px;
  height: 92px;
  margin-bottom: 20px;
  display: grid;
  place-items: center;
  position: relative;
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
  border-radius: 50%;
  background: linear-gradient(145deg, #fff, var(--color-primary-fade));
  box-shadow: 0 12px 35px rgba(15, 118, 110, 0.12);
}
.orbit-core {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: var(--color-primary);
  font-family: var(--font-serif);
  font-size: 20px;
}
.orbit-dot {
  width: 9px;
  height: 9px;
  position: absolute;
  border-radius: 50%;
  background: var(--color-gold);
  animation: orbit 2.2s linear infinite;
}
.dot-2 {
  animation-delay: -0.73s;
}
.dot-3 {
  animation-delay: -1.46s;
}
.bar-track {
  width: min(460px, 90%);
  height: 7px;
  margin: 4px 0 15px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--color-primary-light);
}
.bar-fill {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-primary), #2dd4bf);
  animation: loading 1.6s ease-in-out infinite;
}
.summary {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  margin-bottom: 16px;
}
.summary p {
  margin-bottom: 0;
}
.summary-status {
  min-width: 210px;
  text-align: right;
  display: grid;
  gap: 3px;
}
.summary-status b {
  font-size: 24px;
  color: var(--color-primary);
}
.summary-status span {
  color: var(--color-ink-sub);
  font-size: 12px;
}
.selector-card {
  margin-bottom: 16px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.section-head h2 {
  margin-bottom: 5px;
  font-size: 19px;
}
.section-head p {
  margin-bottom: 0;
  color: var(--color-ink-sub);
  font-size: 13px;
}
.selection-state {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 99px;
  background: #fff0e5;
  color: #a44b17;
  font-size: 12px;
}
.selection-state.ready {
  background: #e2f4ec;
  color: #127252;
}
.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.media-grid {
  display: grid;
  gap: 10px;
}
.media-grid.voices {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.media-grid.bgms {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.media-option {
  min-width: 0;
  padding: 13px;
  display: grid;
  align-content: start;
  gap: 9px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fffdfa;
}
.media-option.selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(15, 118, 110, 0.12);
}
.media-option.recommended {
  background: #f3fbf8;
}
.media-option b {
  font-size: 14px;
}
.media-option b i {
  margin-left: 5px;
  padding: 2px 6px;
  border-radius: 99px;
  background: #dff4ed;
  color: var(--color-primary);
  font-size: 10px;
  font-style: normal;
}
.media-option p {
  margin: 4px 0 0;
  color: var(--color-ink-sub);
  font-size: 12px;
  line-height: 1.5;
}
.media-option small {
  color: #8a7464;
}
.media-option audio,
.candidate audio {
  width: 100%;
  height: 32px;
}
.media-option .reason {
  color: var(--color-primary-deep);
}
.custom-voice,
.no-bgm {
  margin-top: 14px;
  padding: 14px;
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) 1fr auto;
  gap: 12px;
  align-items: center;
  border: 1px dashed #b9aa98;
  border-radius: 10px;
}
.custom-voice p,
.no-bgm p {
  margin: 4px 0 0;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.candidate-list {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}
.candidate {
  padding: 10px 12px;
  display: grid;
  grid-template-columns: 1fr minmax(240px, 380px) auto;
  gap: 12px;
  align-items: center;
  border-radius: 8px;
  background: #f7f3ed;
}
.candidate p {
  margin: 3px 0;
  font-size: 12px;
}
.candidate small {
  color: var(--color-ink-sub);
}
.recommendations {
  margin-bottom: 13px;
  padding: 12px 14px;
  border-left: 3px solid var(--color-primary);
  background: #f0f8f6;
}
.recommendations > p {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.6;
}
.recommendations span {
  color: var(--color-ink-sub);
}
.bgm-gain-control {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid var(--color-primary-light);
  border-radius: 10px;
  background: linear-gradient(135deg, #f7fcfa, #fffdfa);
}
.bgm-gain-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.bgm-gain-head p {
  margin: 4px 0 0;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.bgm-gain-head strong {
  flex-shrink: 0;
  color: var(--color-primary-deep);
  font-size: 14px;
}
.mix-track {
  display: grid;
  grid-template-columns: minmax(130px, 190px) minmax(160px, 1fr) 58px;
  align-items: center;
  gap: 14px;
  margin: 14px 0;
}
.mix-track label {
  font-weight: 600;
  font-size: 13px;
}
.mix-track small {
  display: block;
  font-weight: 400;
  color: var(--color-ink-sub);
}
.mix-track strong {
  color: var(--color-primary-deep);
  text-align: right;
  white-space: nowrap;
}
.mix-note {
  margin: 10px 0 0;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.bgm-gain-editor {
  margin-top: 15px;
  display: grid;
  grid-template-columns: auto minmax(180px, 1fr) auto 120px auto;
  align-items: center;
  gap: 12px;
}
.bgm-gain-editor > span {
  color: var(--color-ink-sub);
  font-size: 11px;
}
.bgm-gain-marks {
  margin: 6px 264px 0 48px;
  display: flex;
  justify-content: space-between;
  color: #9a897a;
  font-size: 10px;
}
.guide {
  margin: 18px 0;
  padding: 13px 16px;
  display: flex;
  gap: 10px;
  border: 1px solid #b8dcd1;
  border-radius: 10px;
  background: #eef8f5;
  color: #235e51;
  font-size: 13px;
}
.guide.blocked {
  border-color: #e3c4a5;
  background: #fff6ec;
  color: #8f4a1e;
}
.guide b {
  flex-shrink: 0;
}
.segment-card {
  margin-bottom: 16px;
  padding: 20px;
}
.segment-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.segment-title {
  display: flex;
  align-items: center;
  gap: 9px;
}
.segment-title h2 {
  margin-bottom: 0;
  font-size: 19px;
}
.segment-head p {
  margin: 7px 0 0;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.status,
.no-music-badge {
  padding: 3px 8px;
  border-radius: 99px;
  font-size: 11px;
}
.status.pending {
  background: #eee9e1;
}
.status.generating {
  color: #9a5b0a;
  background: #fff0c7;
}
.status.completed,
.status.ready {
  color: #11684c;
  background: #def2e9;
}
.status.failed,
.status.stale {
  color: #a2382a;
  background: #fae5df;
}
.no-music-badge {
  color: #6b4e85;
  background: #f0e8f8;
}
.narration {
  margin-top: 14px;
  padding: 10px 13px;
  border-radius: 8px;
  background: #f8f4ee;
}
.narration p {
  margin: 5px 0 0;
  line-height: 1.6;
  font-size: 13px;
}
.transition-row {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.shot-list {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}
.shot-card {
  padding: 12px;
  display: grid;
  grid-template-columns: 150px 1fr auto;
  gap: 14px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
}
.shot-meta {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.shot-meta b {
  color: var(--color-primary-deep);
  font-size: 14px;
}
.shot-body {
  min-width: 0;
}
.shot-body label {
  display: block;
  margin: 9px 0 4px;
  color: var(--color-ink-sub);
  font-size: 11px;
}
.prompt {
  margin-bottom: 7px;
  font-size: 13px;
  line-height: 1.7;
}
.shot-narration {
  margin-bottom: 9px;
  color: #795d47;
  font-size: 12px;
}
.inline-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  color: var(--color-ink-sub);
  font-size: 11px;
}
.inline-actions span {
  margin-right: auto;
}
.edit-actions {
  margin-top: 9px;
}
.refs {
  display: flex;
  gap: 6px;
  max-width: 180px;
  flex-wrap: wrap;
}
.refs a {
  width: 54px;
  height: 42px;
  overflow: hidden;
  border: 1px solid var(--color-primary-light);
  border-radius: 6px;
}
.refs img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.segment-preview {
  margin-top: 15px;
  display: grid;
  gap: 8px;
}
.segment-preview video,
.final-video video {
  width: 100%;
  max-height: 560px;
  border-radius: 10px;
  background: #000;
}
.segment-preview a,
.final-video a {
  width: fit-content;
  color: var(--color-primary);
  text-decoration: none;
  font-size: 13px;
}
.preview-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.error-text {
  color: var(--color-error);
  font-size: 13px;
}
.final-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 22px;
}
.final-actions h2 {
  margin-bottom: 6px;
  font-size: 18px;
}
.final-actions p {
  margin-bottom: 0;
  color: var(--color-ink-sub);
  font-size: 13px;
}
.button-row,
.variant-tabs,
.download-row {
  display: flex;
  gap: 9px;
}
.final-video {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}
.error-box h2 {
  color: var(--color-error);
}
.footer {
  max-width: 1180px;
  margin: 0 auto;
  padding: 22px 24px 30px;
  border-top: 1px solid var(--color-border);
  text-align: center;
  color: var(--color-ink-sub);
  font-size: 12px;
}
@keyframes loading {
  0% {
    transform: translateX(-110%);
  }
  55%,
  100% {
    transform: translateX(240%);
  }
}
@keyframes orbit {
  from {
    transform: rotate(0deg) translateX(39px) rotate(0deg);
  }
  to {
    transform: rotate(360deg) translateX(39px) rotate(-360deg);
  }
}
@media (max-width: 920px) {
  .media-grid.voices,
  .media-grid.bgms {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .bgm-gain-editor {
    grid-template-columns: auto minmax(150px, 1fr) auto 105px;
  }
  .bgm-gain-editor .n-button {
    grid-column: 1 / -1;
  }
  .bgm-gain-marks {
    margin-right: 0;
  }
}
@media (max-width: 720px) {
  .mix-track {
    grid-template-columns: minmax(0, 1fr) 58px;
  }
  .mix-track label {
    grid-column: 1 / -1;
  }
  .variant-tabs,
  .download-row {
    flex-wrap: wrap;
  }
  .processing-card {
    min-height: 330px;
    padding: 38px 18px;
  }
  .summary,
  .final-actions,
  .guide,
  .section-head,
  .bgm-gain-head {
    align-items: stretch;
    flex-direction: column;
  }
  .summary-status {
    text-align: left;
  }
  .media-grid.voices,
  .media-grid.bgms {
    grid-template-columns: 1fr;
  }
  .custom-voice,
  .no-bgm,
  .candidate,
  .shot-card,
  .transition-row {
    grid-template-columns: 1fr;
  }
  .bgm-gain-editor {
    grid-template-columns: auto minmax(100px, 1fr) auto;
  }
  .bgm-gain-editor .n-input-number,
  .bgm-gain-editor .n-button {
    grid-column: 1 / -1;
    width: 100%;
  }
  .bgm-gain-marks {
    margin-left: 0;
  }
  .refs {
    max-width: none;
  }
  .segment-head {
    flex-direction: column;
  }
  .head-actions,
  .preview-meta {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
