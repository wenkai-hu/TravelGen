<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAlert, NButton, NModal, useMessage } from "naive-ui";
import logoUrl from "../images/logo.png";
import { confirmProjectReferences, getProjectReferences } from "../api";
import { isLoggedIn } from "../auth";

const POLL_MS = 1800;
const MAX_SELECTED = 8;

const route = useRoute();
const router = useRouter();
const message = useMessage();
const pid = computed(() => String(route.params.pid || ""));

const snapshot = ref(null);
const selectedIds = ref([]);
const brokenIds = ref([]);
const confirming = ref(false);
const refreshing = ref(false);
const previewOpen = ref(false);
const previewCandidate = ref(null);
let timer = null;
let ticking = false;
let notifiedNetworkError = false;

const status = computed(() => snapshot.value?.status || "loading");
const requestData = computed(() => snapshot.value?.request || {});
const candidates = computed(() => snapshot.value?.candidates || []);
const selectedCount = computed(() => selectedIds.value.length);

const phase = computed(() => {
  if (!snapshot.value) return "loading";
  if (status.value === "searching_references") return "searching";
  if (status.value === "waiting_reference_confirm") return "selecting";
  if (["analyzing_references", "planning"].includes(status.value)) {
    return "processing";
  }
  if (status.value === "failed") return "failed";
  return "other";
});

const activeStep = computed(() => {
  if (["loading", "searching", "selecting", "failed"].includes(phase.value)) {
    return 1;
  }
  if (status.value === "analyzing_references") return 2;
  return 3;
});

const processingTitle = computed(() =>
  status.value === "planning" ? "正在生成创作方案" : "正在理解实景参考图",
);
const processingHint = computed(() =>
  status.value === "planning"
    ? "图片中的地标、建筑、环境和不可臆造项已经注入创作上下文。"
    : "VLM 正在逐张识别地标特征，并整理成统一的景点视觉档案。",
);

function stopPolling() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
}

function schedulePolling() {
  stopPolling();
  timer = setTimeout(tick, POLL_MS);
}

function syncSelection(data) {
  const valid = new Set(
    (data.candidates || []).map((item) => item.candidate_id),
  );
  selectedIds.value = selectedIds.value.filter((id) => valid.has(id));
}

async function tick(options = {}) {
  if (ticking || !pid.value) return;
  ticking = true;
  if (options.manual) refreshing.value = true;
  try {
    const data = await getProjectReferences(pid.value);
    snapshot.value = data;
    syncSelection(data);
    notifiedNetworkError = false;

    if (data.status === "waiting_confirm") {
      stopPolling();
      router.replace(`/plan/${pid.value}`);
      return;
    }
    if (
      [
        "plan_confirmed",
        "storyboarding",
        "waiting_storyboard_confirm",
        "generating",
        "completed",
      ].includes(data.status)
    ) {
      stopPolling();
      router.replace(`/plan/${pid.value}/storyboard`);
      return;
    }

    if (
      ["searching_references", "analyzing_references", "planning"].includes(
        data.status,
      )
    ) {
      schedulePolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    if (error.status === 404) {
      stopPolling();
      message.error("项目不存在或已失效");
      router.replace("/");
      return;
    }
    if (!notifiedNetworkError) {
      notifiedNetworkError = true;
      message.error(error.message || "获取参考图片失败，正在自动重试");
    }
    schedulePolling();
  } finally {
    ticking = false;
    refreshing.value = false;
  }
}

function isSelected(id) {
  return selectedIds.value.includes(id);
}

function toggleCandidate(candidate) {
  const id = candidate.candidate_id;
  if (brokenIds.value.includes(id)) return;
  if (isSelected(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id);
    return;
  }
  if (selectedCount.value >= MAX_SELECTED) {
    message.warning(`最多选择 ${MAX_SELECTED} 张参考图`);
    return;
  }
  selectedIds.value = [...selectedIds.value, id];
}

function markBroken(id) {
  if (!brokenIds.value.includes(id)) {
    brokenIds.value = [...brokenIds.value, id];
  }
  selectedIds.value = selectedIds.value.filter((item) => item !== id);
}

function openPreview(candidate) {
  previewCandidate.value = candidate;
  previewOpen.value = true;
}

function clearPreview() {
  previewCandidate.value = null;
}

async function confirmSelection() {
  if (!selectedCount.value) {
    message.warning("请至少选择 1 张能代表真实景点的图片");
    return;
  }
  confirming.value = true;
  try {
    const result = await confirmProjectReferences(pid.value, selectedIds.value);
    snapshot.value = {
      ...snapshot.value,
      status: result.status,
      progress: result.progress,
      message: "正在理解实景参考图",
    };
    message.success(`已提交 ${selectedCount.value} 张参考图`);
    schedulePolling();
  } catch (error) {
    message.error(error.message || "提交参考图失败");
  } finally {
    confirming.value = false;
  }
}

function restartFromWorkbench() {
  router.push("/");
}

onMounted(() => {
  if (!pid.value) {
    router.replace("/");
    return;
  }
  tick();
});
onBeforeUnmount(stopPolling);
watch(pid, (nextPid, oldPid) => {
  if (nextPid && nextPid !== oldPid) {
    stopPolling();
    snapshot.value = null;
    selectedIds.value = [];
    brokenIds.value = [];
    tick();
  }
});
</script>

<template>
  <div class="page">
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
      <section class="workflow fade-up">
        <div
          v-for="(label, index) in ['选择实景', 'AI 理解', '创作方案']"
          :key="label"
          class="workflow-step"
          :class="{
            active: activeStep === index + 1,
            done: activeStep > index + 1,
          }"
        >
          <span class="step-dot">{{
            activeStep > index + 1 ? "✓" : index + 1
          }}</span>
          <span>{{ label }}</span>
        </div>
      </section>

      <section v-if="phase === 'loading'" class="card state-card">
        <div class="spin-ring"></div>
        <h2>正在读取项目</h2>
        <p>稍等一下，马上为你准备实景图片。</p>
      </section>

      <section v-else-if="phase === 'searching'" class="card state-card">
        <div class="search-illustration" aria-hidden="true">
          <span>⌕</span>
        </div>
        <span class="state-badge">联网检索中</span>
        <h2>正在寻找 {{ requestData.location || "景点" }} 的真实样貌</h2>
        <p>{{ snapshot.message || "正在从网络图片中筛选候选素材" }}</p>
        <div class="bar-track">
          <span class="bar-fill searching-bar"></span>
        </div>
        <small>通常需要几秒，搜索完成后会自动出现图片。</small>
      </section>

      <template v-else-if="phase === 'selecting'">
        <section class="hero fade-up">
          <div>
            <span class="eyebrow">实景视觉校准</span>
            <h1>
              哪些图片最像你心中的<br /><span class="gradient-text">{{
                requestData.location || "目的地"
              }}</span
              >？
            </h1>
            <p>
              请只勾选地点真实、角度有代表性的图片。后续 AI
              会从中提取地标、建筑、环境与色彩特征，约束方案和每个镜头。
            </p>
          </div>
          <div class="place-card">
            <span>本次创作</span>
            <b>📍 {{ requestData.city }} · {{ requestData.location }}</b>
            <small>{{ requestData.theme }} · {{ requestData.style }}</small>
          </div>
        </section>

        <NAlert
          v-if="snapshot.message?.includes('失败')"
          type="warning"
          :bordered="false"
          class="notice"
        >
          {{ snapshot.message }}。请更换图片后再次提交。
        </NAlert>
        <NAlert type="info" :bordered="false" class="notice">
          建议选择 3–6
          张，兼顾地标全景、标志性建筑与环境细节。搜索图片仅用于视觉参考
        </NAlert>

        <div class="gallery-head">
          <div>
            <h2>搜索结果</h2>
            <p>共 {{ candidates.length }} 张候选图，点击卡片即可选择</p>
          </div>
          <span class="count" :class="{ filled: selectedCount }">
            已选 {{ selectedCount }}/{{ MAX_SELECTED }}
          </span>
        </div>

        <section v-if="candidates.length" class="gallery">
          <article
            v-for="(candidate, index) in candidates"
            :key="candidate.candidate_id"
            class="image-card"
            :class="{
              selected: isSelected(candidate.candidate_id),
              broken: brokenIds.includes(candidate.candidate_id),
            }"
            role="checkbox"
            :aria-checked="isSelected(candidate.candidate_id)"
            :tabindex="brokenIds.includes(candidate.candidate_id) ? -1 : 0"
            @click="toggleCandidate(candidate)"
            @keydown.enter.prevent="toggleCandidate(candidate)"
            @keydown.space.prevent="toggleCandidate(candidate)"
          >
            <div class="image-wrap">
              <img
                v-if="!brokenIds.includes(candidate.candidate_id)"
                :src="candidate.image_url"
                :alt="candidate.title || `${requestData.location}参考图`"
                loading="lazy"
                referrerpolicy="no-referrer"
                @error="markBroken(candidate.candidate_id)"
              />
              <div v-else class="broken-placeholder">
                <span>图片暂时无法预览</span>
                <small>请刷新页面或选择其他图片</small>
              </div>
              <span class="index-tag">{{
                String(index + 1).padStart(2, "0")
              }}</span>
              <span class="check-mark">{{
                isSelected(candidate.candidate_id) ? "✓" : ""
              }}</span>
              <button
                v-if="!brokenIds.includes(candidate.candidate_id)"
                type="button"
                class="zoom-button"
                aria-label="放大查看图片"
                title="放大查看"
                @click.stop="openPreview(candidate)"
                @keydown.stop
              >
                <span aria-hidden="true"></span>
              </button>
            </div>
            <div class="image-info">
              <h3>
                {{ candidate.title || `${requestData.location}实景参考` }}
              </h3>
              <div class="source-row">
                <span>{{ candidate.provider || "网络搜索" }}</span>
                <span>点击卡片选择</span>
              </div>
            </div>
          </article>
        </section>

        <section v-else class="card empty-card">
          <b>暂时没有可用图片</b>
          <p>可以刷新状态，或返回工作台换一个更具体的景点名称。</p>
          <NButton :loading="refreshing" @click="tick({ manual: true })"
            >刷新状态</NButton
          >
        </section>

        <div class="action-dock">
          <div class="action-copy">
            <b>{{
              selectedCount
                ? `已选 ${selectedCount} 张真实参考图`
                : "先选择能代表真实景点的图片"
            }}</b>
            <span>{{
              selectedCount
                ? "确认后将自动进行 VLM 视觉理解"
                : "建议 3–6 张，最多 8 张"
            }}</span>
          </div>
          <div class="action-buttons">
            <NButton size="large" @click="restartFromWorkbench"
              >都不符合，返回修改</NButton
            >
            <NButton
              type="primary"
              size="large"
              :loading="confirming"
              :disabled="!selectedCount"
              @click="confirmSelection"
              >确认图片并继续</NButton
            >
          </div>
        </div>
      </template>

      <section v-else-if="phase === 'processing'" class="card processing-card">
        <div class="orbit" aria-hidden="true">
          <span
            class="orbit-core iconfont icon-huabansikao"
            role="img"
            aria-label="AI 正在思考"
          ></span>
          <i v-for="n in 3" :key="n" :class="`orbit-dot dot-${n}`"></i>
        </div>
        <span class="state-badge">{{
          status === "planning" ? "视觉档案已就绪" : "VLM 分析中"
        }}</span>
        <h2>{{ processingTitle }}</h2>
        <p>{{ snapshot.message }}</p>
        <p class="processing-hint">{{ processingHint }}</p>
        <div class="selected-strip">
          <img
            v-for="candidate in candidates
              .filter((item) => selectedIds.includes(item.candidate_id))
              .slice(0, 6)"
            :key="candidate.candidate_id"
            :src="candidate.image_url"
            alt="已选参考图"
            referrerpolicy="no-referrer"
          />
        </div>
        <div class="bar-track">
          <span class="bar-fill analyzing-bar"></span>
        </div>
        <small>完成后将自动进入创作方案确认页，请勿关闭。</small>
      </section>

      <section
        v-else-if="phase === 'failed'"
        class="card state-card failed-card"
      >
        <div class="failed-icon">!</div>
        <span class="state-badge error">本次搜索未完成</span>
        <h2>没有拿到可用的实景图片</h2>
        <p>{{ snapshot.message }}</p>
        <div class="state-actions">
          <NButton :loading="refreshing" @click="tick({ manual: true })"
            >重新检查</NButton
          >
          <NButton type="primary" @click="restartFromWorkbench"
            >返回修改景点</NButton
          >
        </div>
      </section>

      <section v-else class="card state-card">
        <h2>项目正在进入下一阶段</h2>
        <p>{{ snapshot.message }}</p>
        <NButton type="primary" @click="router.push(`/plan/${pid}`)"
          >查看项目</NButton
        >
      </section>
    </main>

    <NModal
      v-model:show="previewOpen"
      :auto-focus="false"
      @after-leave="clearPreview"
    >
      <section v-if="previewCandidate" class="preview-shell">
        <button
          type="button"
          class="preview-close"
          aria-label="关闭大图"
          title="关闭"
          @click="previewOpen = false"
        >
          ×
        </button>
        <div class="preview-image-wrap">
          <img
            :src="previewCandidate.image_url"
            :alt="previewCandidate.title || `${requestData.location}参考图大图`"
            referrerpolicy="no-referrer"
          />
        </div>
        <footer class="preview-footer">
          <div>
            <h3>
              {{ previewCandidate.title || `${requestData.location}实景参考` }}
            </h3>
            <p>可查看画面细节，判断是否符合真实景点</p>
          </div>
          <NButton
            :type="isSelected(previewCandidate.candidate_id) ? 'default' : 'primary'"
            size="large"
            @click="toggleCandidate(previewCandidate)"
          >
            {{
              isSelected(previewCandidate.candidate_id)
                ? "✓ 已选中，点击取消"
                : "选择这张图片"
            }}
          </NButton>
        </footer>
      </section>
    </NModal>

    <footer class="footer">
      TravelGen · 真实视觉参考将贯穿方案、分镜与视频生成
    </footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background:
    radial-gradient(
      circle at 8% 18%,
      rgba(15, 118, 110, 0.08),
      transparent 26%
    ),
    radial-gradient(
      circle at 92% 8%,
      rgba(201, 162, 39, 0.09),
      transparent 24%
    ),
    var(--color-bg);
  color: var(--color-ink);
  font-family: var(--font-sans);
}
.nav {
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(252, 248, 241, 0.94);
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 2px 12px rgba(31, 41, 55, 0.05);
  backdrop-filter: blur(12px);
}
.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.logo-mark {
  width: 58px;
  height: 58px;
  border-radius: 11px;
  object-fit: cover;
}
.logo-text {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
}
.nav-links {
  display: flex;
  gap: 22px;
}
.nav-links a {
  color: var(--color-ink-sub);
  font-size: 15px;
  text-decoration: none;
}
.nav-links a:hover {
  color: var(--color-primary);
}
.stage {
  max-width: 1200px;
  min-height: calc(100vh - 150px);
  margin: 0 auto;
  padding: 30px 24px 70px;
}
.card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
}
.workflow {
  max-width: 660px;
  margin: 0 auto 36px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  position: relative;
}
.workflow::before {
  content: "";
  position: absolute;
  left: 16.5%;
  right: 16.5%;
  top: 18px;
  border-top: 1px solid var(--color-border);
}
.workflow-step {
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #9ca3af;
  font-size: 13px;
}
.step-dot {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-bg);
  font-weight: 700;
}
.workflow-step.active {
  color: var(--color-primary-deep);
  font-weight: 700;
}
.workflow-step.active .step-dot {
  color: white;
  border-color: var(--color-primary);
  background: var(--color-primary);
  box-shadow: 0 0 0 5px rgba(15, 118, 110, 0.1);
}
.workflow-step.done {
  color: var(--color-primary);
}
.workflow-step.done .step-dot {
  color: var(--color-primary);
  border-color: var(--color-primary-light);
  background: var(--color-primary-fade);
}
.state-card,
.processing-card {
  min-height: 370px;
  padding: 54px 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.state-card h2,
.processing-card h2 {
  margin: 14px 0 8px;
  font-family: var(--font-serif);
  font-size: 27px;
  color: var(--color-primary-deep);
}
.state-card p,
.processing-card p {
  max-width: 650px;
  margin: 0 0 22px;
  color: var(--color-ink-sub);
  line-height: 1.7;
}
.state-card small,
.processing-card small {
  color: #9ca3af;
}
.state-badge,
.eyebrow {
  padding: 5px 11px;
  border: 1px solid var(--color-primary-light);
  border-radius: 99px;
  color: var(--color-primary);
  background: var(--color-primary-fade);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.state-badge.error {
  color: var(--color-error);
  border-color: rgba(176, 58, 46, 0.22);
  background: rgba(176, 58, 46, 0.06);
}
.spin-ring {
  width: 38px;
  height: 38px;
  border: 3px solid var(--color-primary-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.85s linear infinite;
}
.search-illustration,
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
.search-illustration span {
  font: 48px/1 var(--font-serif);
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
.hero {
  margin: 10px 0 28px;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 36px;
}
.hero h1 {
  margin: 13px 0 10px;
  font-family: var(--font-serif);
  font-size: clamp(30px, 4vw, 45px);
  line-height: 1.22;
}
.hero p {
  max-width: 750px;
  margin: 0;
  color: var(--color-ink-sub);
  line-height: 1.75;
}
.place-card {
  min-width: 255px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  border: 1px solid var(--color-gold-light);
  border-radius: 13px;
  background: var(--color-gold-fade);
}
.place-card span,
.place-card small {
  color: var(--color-ink-sub);
}
.place-card b {
  color: var(--color-gold-ink);
  font-size: 16px;
}
.notice {
  margin-bottom: 14px;
}
.gallery-head {
  margin: 30px 0 16px;
  display: flex;
  align-items: end;
  justify-content: space-between;
}
.gallery-head h2 {
  margin: 0 0 4px;
  font-family: var(--font-serif);
}
.gallery-head p {
  margin: 0;
  color: var(--color-ink-sub);
  font-size: 13px;
}
.count {
  padding: 7px 12px;
  color: var(--color-ink-sub);
  border: 1px solid var(--color-border);
  border-radius: 99px;
  background: white;
  font-size: 13px;
}
.count.filled {
  color: var(--color-primary);
  border-color: var(--color-primary-light);
}
.gallery {
  padding-bottom: 112px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 17px;
}
.image-card {
  min-width: 0;
  overflow: hidden;
  border: 2px solid transparent;
  border-radius: 13px;
  background: white;
  box-shadow: 0 4px 18px rgba(31, 41, 55, 0.08);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}
.image-card:hover,
.image-card:focus-visible {
  transform: translateY(-3px);
  outline: none;
  box-shadow: var(--shadow-card-hover);
}
.image-card.selected {
  border-color: var(--color-primary);
  box-shadow:
    0 0 0 3px rgba(15, 118, 110, 0.12),
    var(--shadow-card-hover);
}
.image-card.broken {
  cursor: default;
  opacity: 0.75;
}
.image-wrap {
  aspect-ratio: 4 / 3;
  position: relative;
  overflow: hidden;
  background: #e8edea;
}
.image-wrap img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  transition: transform 0.35s ease;
}
.image-card:hover .image-wrap img {
  transform: scale(1.035);
}
.index-tag,
.check-mark {
  position: absolute;
  top: 10px;
  display: grid;
  place-items: center;
  color: white;
  border-radius: 99px;
  background: rgba(17, 24, 39, 0.7);
  backdrop-filter: blur(6px);
}
.index-tag {
  left: 10px;
  min-width: 27px;
  height: 27px;
  font-size: 11px;
}
.check-mark {
  right: 10px;
  width: 27px;
  height: 27px;
  border: 1px solid rgba(255, 255, 255, 0.7);
}
.selected .check-mark {
  border-color: var(--color-primary);
  background: var(--color-primary);
}
.zoom-button {
  width: 34px;
  height: 34px;
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: grid;
  place-items: center;
  padding: 0;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 50%;
  background: rgba(17, 24, 39, 0.72);
  cursor: zoom-in;
  backdrop-filter: blur(6px);
  transition: background 0.15s ease, transform 0.15s ease;
}
.zoom-button:hover {
  background: var(--color-primary);
  transform: scale(1.06);
}
.zoom-button span {
  width: 12px;
  height: 12px;
  position: relative;
  display: block;
  border: 2px solid currentColor;
  border-radius: 50%;
}
.zoom-button span::after {
  content: "";
  width: 7px;
  position: absolute;
  right: -6px;
  bottom: -4px;
  border-top: 2px solid currentColor;
  transform: rotate(45deg);
  transform-origin: left center;
}
.broken-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: var(--color-ink-sub);
  background: repeating-linear-gradient(
    135deg,
    #f4f3ef,
    #f4f3ef 10px,
    #eceae4 10px,
    #eceae4 20px
  );
}
.broken-placeholder small {
  font-size: 11px;
}
.image-info {
  padding: 12px 13px 13px;
}
.image-info h3 {
  margin: 0 0 10px;
  overflow: hidden;
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: #9ca3af;
  font-size: 11px;
}
.preview-shell {
  width: min(1120px, calc(100vw - 48px));
  max-height: calc(100vh - 48px);
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  background: #101815;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}
.preview-close {
  z-index: 2;
  width: 38px;
  height: 38px;
  position: absolute;
  top: 14px;
  right: 14px;
  display: grid;
  place-items: center;
  padding: 0 0 3px;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 50%;
  background: rgba(17, 24, 39, 0.72);
  cursor: pointer;
  font-size: 27px;
  line-height: 1;
  backdrop-filter: blur(6px);
}
.preview-close:hover { background: rgba(15, 118, 110, 0.9); }
.preview-image-wrap {
  height: min(72vh, 760px);
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.06), transparent 55%),
    #101815;
}
.preview-image-wrap img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}
.preview-footer {
  padding: 15px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  color: var(--color-ink);
  background: white;
}
.preview-footer h3 {
  max-width: 760px;
  margin: 0 0 4px;
  overflow: hidden;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-footer p {
  margin: 0;
  color: var(--color-ink-sub);
  font-size: 12px;
}
.empty-card {
  padding: 48px;
  text-align: center;
}
.empty-card p {
  color: var(--color-ink-sub);
}
.action-dock {
  position: fixed;
  z-index: 20;
  left: 50%;
  bottom: 22px;
  width: min(1080px, calc(100% - 48px));
  padding: 14px 17px 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.93);
  box-shadow: 0 15px 45px rgba(17, 94, 89, 0.2);
  backdrop-filter: blur(16px);
  transform: translateX(-50%);
}
.action-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.action-copy b {
  color: var(--color-primary-deep);
}
.action-copy span {
  color: var(--color-ink-sub);
  font-size: 12px;
}
.action-buttons {
  display: flex;
  gap: 10px;
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
.processing-hint {
  padding: 9px 14px;
  border-radius: 8px;
  background: var(--color-primary-fade);
  font-size: 13px;
}
.selected-strip {
  height: 58px;
  margin: 5px 0 20px;
  display: flex;
  justify-content: center;
}
.selected-strip img {
  width: 78px;
  height: 58px;
  margin-left: -9px;
  border: 2px solid white;
  border-radius: 8px;
  object-fit: cover;
  box-shadow: 0 4px 12px rgba(31, 41, 55, 0.14);
}
.selected-strip img:first-child {
  margin-left: 0;
}
.failed-icon {
  width: 54px;
  height: 54px;
  margin-bottom: 16px;
  display: grid;
  place-items: center;
  color: white;
  border-radius: 50%;
  background: var(--color-error);
  font-size: 28px;
  font-weight: 700;
}
.state-actions {
  display: flex;
  gap: 10px;
}
.footer {
  padding: 24px;
  color: var(--color-ink-sub);
  border-top: 1px solid var(--color-border);
  text-align: center;
  font-size: 12px;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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
@media (max-width: 900px) {
  .gallery {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .hero {
    align-items: stretch;
    flex-direction: column;
  }
  .place-card {
    min-width: 0;
  }
}
@media (max-width: 620px) {
  .nav-inner {
    padding: 10px 15px;
  }
  .logo-mark {
    width: 45px;
    height: 45px;
  }
  .logo-text {
    font-size: 20px;
  }
  .stage {
    padding: 24px 14px 50px;
  }
  .workflow {
    margin-bottom: 28px;
  }
  .hero h1 {
    font-size: 30px;
  }
  .gallery {
    grid-template-columns: 1fr;
    padding-bottom: 176px;
  }
  .action-dock {
    bottom: 10px;
    width: calc(100% - 20px);
    align-items: stretch;
    flex-direction: column;
  }
  .action-buttons {
    display: grid;
    grid-template-columns: 1fr;
  }
  .state-card,
  .processing-card {
    min-height: 330px;
    padding: 38px 18px;
  }
  .preview-shell {
    width: calc(100vw - 20px);
    max-height: calc(100vh - 20px);
  }
  .preview-image-wrap { height: 65vh; }
  .preview-footer { align-items: stretch; flex-direction: column; }
}
</style>
