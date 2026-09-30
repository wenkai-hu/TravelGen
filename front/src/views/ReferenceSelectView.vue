<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAlert, NButton, NInput, NModal, useMessage } from "naive-ui";
import {
  PhArrowLeft,
  PhArrowRight,
  PhCheck,
  PhGear,
  PhLink,
  PhMapPin,
  PhPlus,
  PhUploadSimple,
  PhX,
} from "@phosphor-icons/vue";
import {
  addReferenceSource,
  confirmProjectReferences,
  getProjectReferences,
  retryProject,
} from "../api";
import { useProjectDraft } from "../composables/useProjectDraft";
import DraftStatus from "../components/DraftStatus.vue";
import { logout as clearSession } from "../auth";

const POLL_MS = 1800;
// 兜底值：真正的额度用后端返回的 max_selected / duration_cap，别在这里复制公式
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
const reviewing = ref(false); // 本地阶段：已点「下一步」，正在排顺序（不发请求）
const seeded = ref(false); // 自己加的图只在首次载入时播种一次，免得轮询反复复活
const uploading = ref(false);
const dragActive = ref(false);
const showLink = ref(false);
const linkUrl = ref("");
const showPicker = ref(false);
// false = 用户自己排（第 N 张配第 N 个镜头）；true = 交给 AI，在分镜阶段按内容配
const autoOrder = ref(false);
const orderModeSeeded = ref(false); // 只从服务端回填一次，之后轮询不许覆盖用户的选择
const extraCandidates = ref([]); // 刚加上、轮询还没带回的候选；带回后自动去重
const fileInput = ref(null);
const stripEl = ref(null); // 那一排缩略图，拖拽时用它算落点
let timer = null;
let ticking = false;
let notifiedNetworkError = false;

const status = computed(() => snapshot.value?.status || "loading");
const requestData = computed(() => snapshot.value?.request || {});

// 后端候选 + 刚加进来还没被轮询带回的，合并成同一份列表
const candidates = computed(() => {
  const base = snapshot.value?.candidates || [];
  const known = new Set(base.map((item) => item.candidate_id));
  return [
    ...base,
    ...extraCandidates.value.filter((item) => !known.has(item.candidate_id)),
  ];
});
const candidateById = computed(() =>
  Object.fromEntries(candidates.value.map((item) => [item.candidate_id, item])),
);
const selectedCount = computed(() => selectedIds.value.length);
// 有序清单：selectedIds 的顺序就是最终提交顺序
const orderedItems = computed(() =>
  selectedIds.value.map((id) => candidateById.value[id]).filter(Boolean),
);

// 额度：最多 8 张，且不超过时长能消化的张数（一图一镜，超出的图生成时会被丢掉）
const maxSelected = computed(
  () => snapshot.value?.max_selected ?? MAX_SELECTED,
);
const durationCap = computed(
  () => snapshot.value?.duration_cap ?? maxSelected.value,
);
const budgetLimit = computed(() =>
  Math.max(1, Math.min(maxSelected.value, durationCap.value)),
);
const remaining = computed(() =>
  Math.max(0, budgetLimit.value - selectedCount.value),
);
const canAddMore = computed(() => remaining.value > 0);
const budgetReason = computed(() =>
  durationCap.value < maxSelected.value
    ? `${requestData.value.duration_s} 秒的片子一图一镜，最多用得上 ${durationCap.value} 张图`
    : `最多 ${budgetLimit.value} 张参考图`,
);

const phase = computed(() => {
  if (!snapshot.value) return "loading";
  // 本地短路：确认前先让用户排顺序，点了确认才真正提交
  if (reviewing.value && status.value === "waiting_reference_confirm") {
    return "ordering";
  }
  if (status.value === "searching_references") return "searching";
  if (status.value === "waiting_reference_confirm") return "selecting";
  if (["analyzing_references", "planning"].includes(status.value)) {
    return "processing";
  }
  if (status.value === "failed") return "failed";
  return "other";
});

const activeStep = computed(() => {
  if (
    ["loading", "searching", "selecting", "ordering", "failed"].includes(
      phase.value,
    )
  ) {
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

function syncSelection() {
  const valid = new Set(candidates.value.map((item) => item.candidate_id));
  selectedIds.value = selectedIds.value.filter((id) => valid.has(id));
}

// 自己加的图（上传件或链接）在服务端带 provider="user"；首次载入据此恢复选中态。
// selectedIds 不落浏览器存储，刷新后全靠这一步还原。
function seedSelfProvided(data) {
  if (seeded.value || selectedIds.value.length) return;
  const ids = (data.candidates || [])
    .filter((item) => item.provider === "user")
    .map((item) => item.candidate_id);
  if (!ids.length) return; // 候选还没到齐，下次轮询再试
  selectedIds.value = ids.slice(0, budgetLimit.value);
  seeded.value = true;
}

// 「顺序谁定」同理：服务端记着上次的选择，首次载入回填一次就够，
// 之后轮询再回来也不许覆盖 —— 用户刚切到 AI，不能被一次轮询弹回自己排。
function seedOrderMode(data) {
  if (orderModeSeeded.value) return;
  orderModeSeeded.value = true;
  autoOrder.value = Boolean(data.auto_order);
}

async function tick(options = {}) {
  if (ticking || !pid.value) return;
  ticking = true;
  if (options.manual) refreshing.value = true;
  try {
    const data = await getProjectReferences(pid.value);
    snapshot.value = data;
    if (!draftRestored) {
      const saved = referenceDraft.restore(data.draft);
      if (saved) {
        selectedIds.value = saved.selectedIds || [];
        autoOrder.value = !!saved.autoOrder;
        reviewing.value = !!saved.reviewing;
        seeded.value = true;
        orderModeSeeded.value = true;
      }
      draftRestored = true;
    }
    seedSelfProvided(data);
    seedOrderMode(data);
    syncSelection();
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
    if (error.status === 401) {
      // 登录态失效（token 过期 / 后端重启后内存会话丢失）。这不是「网络抖动」，
      // 下面那条无限重试只会把页面吊死，得直接去重新登录
      stopPolling();
      clearSession();
      message.error("登录已失效（后端重启会清空登录态），请重新登录");
      router.replace("/login");
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
  if (selectedCount.value >= budgetLimit.value) {
    message.warning(`${budgetReason.value}，不能再多了`);
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

// ── 自己加参考图：上传文件或贴链接，加进来即入选、即占额度 ──

// 返回 "ok" | "quota" | "error"，调用方据此决定还要不要继续处理后面的文件
async function addSource(payload, label) {
  if (selectedCount.value >= budgetLimit.value) return "quota";
  uploading.value = true;
  try {
    const result = await addReferenceSource(pid.value, payload);
    const candidate = result?.candidate;
    if (candidate?.candidate_id) {
      if (!isSelected(candidate.candidate_id)) {
        selectedIds.value = [...selectedIds.value, candidate.candidate_id];
      }
      // 搜图还没结束时轮询还没带回它，先挂本地；带回后按 id 自动去重
      if (
        !extraCandidates.value.some(
          (item) => item.candidate_id === candidate.candidate_id,
        )
      ) {
        extraCandidates.value = [...extraCandidates.value, candidate];
      }
    }
    // 这些图服务端记着，别让播种逻辑再动它们
    seeded.value = true;
    message.success(`已添加 ${label}`);
    await tick(); // 顺带同步状态（搜图失败的项目会被后端拉回待确认）
    return "ok";
  } catch (error) {
    message.error(error.message || "添加参考图失败");
    return "error";
  } finally {
    uploading.value = false;
  }
}

async function addFiles(files) {
  for (const file of files) {
    const outcome = await addSource({ file }, file.name);
    if (outcome === "quota") {
      message.warning(`${budgetReason.value}，其余文件未添加`);
      return;
    }
    // 单个失败就跳过它继续试后面的 —— 可能只是这一个格式不对
  }
}

function pickFiles() {
  fileInput.value?.click();
}

async function onFilesPicked(event) {
  const files = Array.from(event.target.files || []);
  event.target.value = ""; // 清空才能再次选同一个文件
  await addFiles(files);
}

async function onDrop(event) {
  dragActive.value = false;
  await addFiles(Array.from(event.dataTransfer?.files || []));
}

async function addByLink() {
  const url = linkUrl.value.trim();
  if (!url) return;
  const outcome = await addSource({ url }, "图片链接");
  if (outcome === "quota") {
    message.warning(`${budgetReason.value}，不能再多了`);
  } else if (outcome === "ok") {
    linkUrl.value = "";
    showLink.value = false;
  }
}

// ── 有序清单：拖拽换序 + 增删 ──
//
// 原生指针事件，不引库。手感靠三件事撑起来：
//   1) 抓起来那张脱离布局，用 transform 跟住指针（且位移不能有过渡，否则拖起来发飘）
//   2) 其余卡片按「它要插到哪一格」整体让位 —— 让位带过渡，所以是滑开的不是跳开的
//   3) **松手才真正改数组顺序**。改完大家正好落在视觉上已经在的位置，不闪
// 鼠标按下即拖；触屏按住一下才拖，否则手指一滑就跟这一排的横向滚动打架。
const DRAG_THRESHOLD = 4; // px，超过才算拖，免得手抖把顺序碰乱
const TOUCH_HOLD_MS = 220; // 触屏按住这么久才算「抓起来了」
const EDGE_SCROLL_PX = 56; // 拖到这一排左右边缘这么宽以内就自动滚动
const SETTLE_MS = 240; // 松手后归位动画的时长，跟 CSS 里的过渡对齐

const dragId = ref(null); // 正被拖着的那张
const settleId = ref(null); // 松手后还在归位的那张（要留住浮起的层级）
const dragDx = ref(0); // 相对槽位的位移
const dragDy = ref(0);
const dragFrom = ref(-1); // 它原本在第几格
const dragOver = ref(-1); // 松手会落在第几格
const pitch = ref(160); // 相邻两格的间距，拖动开始时量一次

// 下面这几个基准都在「抓起来」那一刻量一次，拖动途中不再读 DOM：
// ref 更新到 DOM 落地之间隔着一帧，边拖边读 rect 会读到上一帧的位置，
// 跟当前位移对不上，越拖越偏（槽位基准还会跟着指针一起跑，落点整个算错）。
let baseLeft = 0; // 被拖那张的槽位位置（不含 transform）
let baseTop = 0;
let originLeft = 0; // 第 0 格的左边缘（不含让位）
let grabX = 0; // 抓在卡片内部的哪一点，保证跟手时不对不齐
let grabY = 0;
let startX = 0; // 按下时的指针位置，用来判断有没有跨过阈值
let startY = 0;
let lastX = 0; // 指针最新位置（触屏长按那段时间手可能已经挪了）
let lastY = 0;
let armed = false; // 已按下、还没真正开始拖
let holdTimer = null;
let settleTimer = null;

function cardNodes() {
  return stripEl.value
    ? Array.from(stripEl.value.querySelectorAll(".order-card"))
    : [];
}

function measurePitch() {
  const cards = cardNodes();
  if (cards.length >= 2) {
    return (
      cards[1].getBoundingClientRect().left -
      cards[0].getBoundingClientRect().left
    );
  }
  return cards.length ? cards[0].getBoundingClientRect().width + 12 : 160;
}

// 让位量：把 from 这张抽走，中间的卡片就得整体挪一格给它腾地方
function shiftFor(index) {
  const from = dragFrom.value;
  const over = dragOver.value;
  if (dragId.value === null || from < 0 || over < 0 || from === over) return 0;
  if (from < over && index > from && index <= over) return -pitch.value;
  if (from > over && index >= over && index < from) return pitch.value;
  return 0;
}

function cardStyle(index, id) {
  if (id === dragId.value || id === settleId.value) {
    return {
      transform: `translate3d(${dragDx.value}px, ${dragDy.value}px, 0)`,
    };
  }
  const shift = shiftFor(index);
  return shift ? { transform: `translate3d(${shift}px, 0, 0)` } : null;
}

function onCardPointerDown(event, index, id) {
  if (autoOrder.value) return; // 顺序交给 AI 了，这一排不可拖
  if (event.button > 0) return; // 只认左键/触摸
  if (event.target.closest(".order-del")) return; // 点删除不是拖
  if (settleId.value !== null) return; // 上一张还在归位，别叠上来
  armed = true;
  dragFrom.value = index;
  dragOver.value = index;
  startX = lastX = event.clientX;
  startY = lastY = event.clientY;
  const rect = event.currentTarget.getBoundingClientRect();
  grabX = event.clientX - rect.left;
  grabY = event.clientY - rect.top;
  pitch.value = measurePitch();
  // 挂在 window 上：指针划出卡片也要继续收事件
  window.addEventListener("pointermove", onPointerMove, { passive: false });
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("pointercancel", onPointerUp);
  if (event.pointerType === "touch") {
    holdTimer = setTimeout(startDrag, TOUCH_HOLD_MS);
  }
}

function startDrag() {
  clearTimeout(holdTimer);
  holdTimer = null;
  if (!armed) return;
  armed = false;
  const id = orderedItems.value[dragFrom.value]?.candidate_id;
  const el = cardNodes()[dragFrom.value];
  if (!id || !el) return;
  // 从按下到这会儿手可能已经挪了（触屏那 220ms），以当前点重算抓取点，
  // 否则卡片会先跳一下再开始跟手
  const rect = el.getBoundingClientRect(); // 此刻还没上 transform，量到的就是槽位本身
  baseLeft = rect.left;
  baseTop = rect.top;
  grabX = lastX - rect.left;
  grabY = lastY - rect.top;
  // 第 0 格的左边缘。让位还没开始（over == from），所以第一张就是没动过的基准
  originLeft = cardNodes()[0].getBoundingClientRect().left;
  dragDx.value = 0;
  dragDy.value = 0;
  dragId.value = id;
}

// 让卡片贴着指针。基准是抓起来那一刻量好的，只在自动滚边时才跟着挪
function follow(x, y) {
  dragDx.value = x - grabX - baseLeft;
  dragDy.value = y - grabY - baseTop;
}

// 指针压在第几格。用「没让位时」的格子算 —— 否则卡片一让位边界就跟着动，
// 指针停在交界处会来回横跳
function slotAtPointer(x, y) {
  const strip = stripEl.value;
  const cards = cardNodes();
  if (!strip || !cards.length) return -1;
  const box = strip.getBoundingClientRect(); // strip 自己不带 transform，读它不会滞后
  if (y < box.top || y > box.bottom) return -1; // 拖出这一排 = 放回去
  const index = Math.floor((x - originLeft) / pitch.value);
  return Math.max(0, Math.min(index, cards.length - 1));
}

function onPointerMove(event) {
  lastX = event.clientX;
  lastY = event.clientY;
  if (dragId.value === null) {
    if (!armed) return;
    if (
      Math.hypot(event.clientX - startX, event.clientY - startY) <
      DRAG_THRESHOLD
    ) {
      return;
    }
    // 触屏没按住就滑 = 用户想滚动这一排，别抢
    if (event.pointerType === "touch") return;
    startDrag();
    if (dragId.value === null) return;
  }
  event.preventDefault();
  follow(event.clientX, event.clientY);
  dragOver.value = slotAtPointer(event.clientX, event.clientY);
  edgeScroll(event.clientX);
}

function onPointerUp() {
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", onPointerUp);
  window.removeEventListener("pointercancel", onPointerUp);
  clearTimeout(holdTimer);
  holdTimer = null;
  armed = false;

  const id = dragId.value;
  const from = dragFrom.value;
  const over = dragOver.value;
  dragFrom.value = -1;
  dragOver.value = -1;
  if (id === null) return;

  if (over >= 0 && over !== from) {
    // 槽位要挪 (over - from) 格，位移里先减掉这一截：改完顺序的那一瞬间
    // 卡片视觉上停在原地不动，接着再把位移过渡回 0，才是「滑进格子」
    dragDx.value -= (over - from) * pitch.value;
    reorder(from, over);
  }

  // 交棒给 settleId：.lifted 一摘掉，过渡就重新生效了
  dragId.value = null;
  settleId.value = id;
  const landed = over >= 0 && over !== from ? over : from;
  nextTick(() => {
    // 先把「过渡前的状态」逼出来算一次。少了这一步，浏览器可能把
    // 换类和归零并进同一帧，过渡根本不会触发，卡片就直挺挺闪回去
    void cardNodes()[landed]?.offsetWidth;
    requestAnimationFrame(() => {
      dragDx.value = 0;
      dragDy.value = 0;
      clearTimeout(settleTimer);
      settleTimer = setTimeout(() => {
        if (settleId.value === id) settleId.value = null;
      }, SETTLE_MS);
    });
  });
}

function edgeScroll(x) {
  const strip = stripEl.value;
  if (!strip) return;
  const box = strip.getBoundingClientRect();
  let delta = 0;
  if (x < box.left + EDGE_SCROLL_PX) {
    delta = -(box.left + EDGE_SCROLL_PX - x) / 3;
  } else if (x > box.right - EDGE_SCROLL_PX) {
    delta = (x - (box.right - EDGE_SCROLL_PX)) / 3;
  }
  if (!delta) return;
  const was = strip.scrollLeft;
  strip.scrollLeft = was + delta;
  // 内容滚了，槽位在视口里的位置跟着挪 —— 缓存的基准也要挪，否则卡片会跟丢指针
  const moved = strip.scrollLeft - was;
  baseLeft -= moved;
  originLeft -= moved;
}

// 把 from 那张抽出来插到 to 的位置（拖动时连续调用，就是一路换过去）
function reorder(from, to) {
  const list = [...selectedIds.value];
  const [moved] = list.splice(from, 1);
  if (moved === undefined) return;
  list.splice(to, 0, moved);
  selectedIds.value = list;
}

// 键盘用户没有指针可拖，左右方向键走同一套位移
function moveItem(index, delta) {
  if (autoOrder.value) return; // 同拖拽：AI 排序时顺序不由用户改
  const target = index + delta;
  if (target < 0 || target >= selectedIds.value.length) return;
  reorder(index, target);
}

function togglePicker() {
  showPicker.value = !showPicker.value;
}

function removeItem(id) {
  selectedIds.value = selectedIds.value.filter((item) => item !== id);
}

function addFromPool(id) {
  if (isSelected(id)) return;
  if (selectedCount.value >= budgetLimit.value) {
    message.warning(`${budgetReason.value}，不能再多了`);
    return;
  }
  selectedIds.value = [...selectedIds.value, id];
}

// 「下一步」只切本地阶段，不提交 —— 排完顺序点「确认」才真正发给后端
function goReview() {
  if (!selectedCount.value) {
    message.warning("请至少选择 1 张能代表真实景点的图片");
    return;
  }
  showPicker.value = false;
  reviewing.value = true;
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
    await referenceDraft.flush();
    // autoOrder 时提交的只是「用这几张」，先后由模型在分镜阶段自己配
    const result = await confirmProjectReferences(
      pid.value,
      selectedIds.value,
      autoOrder.value,
    );
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

const referenceDraft = useProjectDraft(pid, "references");
let draftRestored = false;
watch(
  [selectedIds, autoOrder, reviewing],
  () => {
    if (draftRestored)
      referenceDraft.queue({
        selectedIds: selectedIds.value,
        autoOrder: autoOrder.value,
        reviewing: reviewing.value,
      });
  },
  { deep: true },
);

onMounted(() => {
  if (!pid.value) {
    router.replace("/");
    return;
  }
  tick();
});
onBeforeUnmount(() => {
  stopPolling();
  onPointerUp(); // 拖到一半就离开页面时，把挂在 window 上的监听摘掉
  clearTimeout(settleTimer);
});
watch(pid, (nextPid, oldPid) => {
  if (nextPid && nextPid !== oldPid) {
    stopPolling();
    snapshot.value = null;
    selectedIds.value = [];
    brokenIds.value = [];
    reviewing.value = false;
    seeded.value = false;
    autoOrder.value = false;
    orderModeSeeded.value = false;
    extraCandidates.value = [];
    tick();
  }
});
</script>

<template>
  <div class="page">
    <div class="page-status">
      <DraftStatus
        :state="referenceDraft.state.value"
        @retry="referenceDraft.flush().catch((e) => message.error(e.message))"
      />
    </div>

    <main class="stage">
      <!-- 常驻的隐藏 file input：上传区在 ordering 阶段不渲染，但「再传一张」还要用它 -->
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        class="file-input"
        @change="onFilesPicked"
      />

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
          <span class="step-dot">
            <PhCheck v-if="activeStep > index + 1" :size="14" weight="bold" />
            <template v-else>{{ index + 1 }}</template>
          </span>
          <span>{{ label }}</span>
        </div>
      </section>

      <!-- 自己的图：搜图还在跑时就能传（Q8），不必等搜完 -->
      <section
        v-if="['searching', 'selecting'].includes(phase)"
        class="card uploader fade-up"
      >
        <div class="uploader-head">
          <div>
            <h2>有自己拍的实景图？</h2>
            <p>上传的图会一起算入下方的可选清单。</p>
          </div>
          <span class="quota" :class="{ full: remaining <= 0 }">
            还能选 {{ remaining }} 张
          </span>
        </div>

        <div
          class="drop-zone"
          :class="{ dragging: dragActive, busy: uploading }"
          role="button"
          tabindex="0"
          @click="pickFiles"
          @keydown.enter.prevent="pickFiles"
          @keydown.space.prevent="pickFiles"
          @dragover.prevent="dragActive = true"
          @dragleave.prevent="dragActive = false"
          @drop.prevent="onDrop"
        >
          <PhUploadSimple :size="22" />
          <b>{{
            uploading ? "正在添加…" : "点击选择图片，或把文件拖到这里"
          }}</b>
          <small>支持 JPG / PNG / WEBP，单张不超过 12MB</small>
        </div>

        <div class="link-entry">
          <button
            type="button"
            class="link-toggle"
            @click="showLink = !showLink"
          >
            <PhLink :size="13" class="ico-inline" />
            {{ showLink ? "收起链接入口" : "或粘贴一个图片链接" }}
          </button>
          <div v-if="showLink" class="link-row">
            <NInput
              v-model:value="linkUrl"
              size="small"
              placeholder="https:// 开头的图片地址"
              @keydown.enter="addByLink"
            />
            <NButton
              size="small"
              type="primary"
              :disabled="!linkUrl.trim() || uploading"
              @click="addByLink"
            >
              添加
            </NButton>
          </div>
        </div>

        <p class="quota-note">{{ budgetReason }}</p>
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
            <p>选取的图片会用来约束镜头生成</p>
          </div>
          <div class="place-card">
            <span>本次创作</span>
            <b
              ><PhMapPin class="ico-inline" /> {{ requestData.city }} ·
              {{ requestData.location }}</b
            >
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
          一图一镜：这里的顺序就是镜头顺序，在后续步骤也可以调整
        </NAlert>

        <div class="gallery-head">
          <div>
            <h2>搜索结果</h2>
            <p>共 {{ candidates.length }} 张候选图</p>
          </div>
          <span class="count" :class="{ filled: selectedCount }">
            已选 {{ selectedCount }}/{{ budgetLimit }}
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
            :aria-label="`选择第 ${index + 1} 张图片`"
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
              <span class="check-mark" aria-hidden="true">
                <PhCheck
                  v-if="isSelected(candidate.candidate_id)"
                  :size="14"
                  weight="bold"
                />
              </span>
              <button
                v-if="!brokenIds.includes(candidate.candidate_id)"
                type="button"
                class="zoom-button"
                :aria-label="`放大查看第 ${index + 1} 张图片`"
                title="放大查看"
                @click.stop="openPreview(candidate)"
                @keydown.stop
              >
                <span aria-hidden="true"></span>
              </button>
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
                ? "下一步可以排序、增删，确认后才开始分析"
                : "只用自己的图也可以，跳过勾选直接下一步"
            }}</span>
          </div>
          <div class="action-buttons">
            <NButton size="large" @click="restartFromWorkbench"
              >都不符合，返回修改</NButton
            >
            <NButton
              type="primary"
              size="large"
              :disabled="!selectedCount"
              @click="goReview"
              >下一步<PhArrowRight :size="15" class="btn-ico"
            /></NButton>
          </div>
        </div>
      </template>

      <!-- 确认清单：一份有序列表，第 N 张配第 N 个镜头（Q7：本地切 phase，不发请求） -->
      <template v-else-if="phase === 'ordering'">
        <section class="hero fade-up">
          <div>
            <span class="eyebrow">确认清单</span>
            <h1 v-if="autoOrder">
              这几张图，<br /><span class="gradient-text"
                >交给 AI 自己配镜头</span
              >
            </h1>
            <h1 v-else>
              排好顺序，<br /><span class="gradient-text"
                >第 N 张配第 N 个镜头</span
              >
            </h1>
            <p v-if="autoOrder">
              一图一镜。你不用管先后 —— 生成分镜时 AI
              已经知道每个镜头要拍什么，会按内容把最合适的那张配给它，每张图仍然只用一次。
              也可以删掉或再加。
            </p>
            <p v-else>
              一图一镜，这里的顺序就是镜头顺序。按住缩略图拖动就能换位置，也可以删掉或再加
              —— 确认后 AI 会按这个顺序逐个镜头生成。
            </p>
          </div>
          <div class="place-card">
            <span>本次创作</span>
            <b
              ><PhMapPin class="ico-inline" /> {{ requestData.city }} ·
              {{ requestData.location }}</b
            >
            <small>{{ requestData.theme }} · {{ requestData.style }}</small>
          </div>
        </section>

        <section class="strip-wrap">
          <!-- 顺序谁定：默认用户自己排；切到 AI 后这一排只读（还能删、还能加） -->
          <div class="order-mode" :class="{ auto: autoOrder }">
            <div
              class="mode-switch"
              role="radiogroup"
              aria-label="镜头顺序由谁决定"
            >
              <button
                type="button"
                class="mode-opt"
                :class="{ on: !autoOrder }"
                role="radio"
                :aria-checked="!autoOrder"
                @click="autoOrder = false"
              >
                我自己排
              </button>
              <button
                type="button"
                class="mode-opt"
                :class="{ on: autoOrder }"
                role="radio"
                :aria-checked="autoOrder"
                @click="autoOrder = true"
              >
                让 AI 排
              </button>
            </div>
            <p class="mode-hint">
              {{
                autoOrder
                  ? "生成分镜时按每个镜头的内容逐张挑，每张图仍只用一次"
                  : "按住缩略图拖动换顺序，第 N 张配第 N 个镜头"
              }}
            </p>
          </div>

          <div class="strip-row">
            <div
              ref="stripEl"
              class="strip"
              :class="{ dragging: dragId !== null, readonly: autoOrder }"
              role="list"
              :aria-label="
                autoOrder
                  ? '参考图清单：顺序由 AI 决定，不可拖动。'
                  : '参考图顺序：第 N 张配第 N 个镜头。拖动可换位，键盘用户按左右方向键。'
              "
            >
              <article
                v-for="(item, index) in orderedItems"
                :key="item.candidate_id"
                class="order-card"
                :class="{
                  lifted: dragId === item.candidate_id,
                  settling: settleId === item.candidate_id,
                }"
                :style="cardStyle(index, item.candidate_id)"
                role="listitem"
                :tabindex="autoOrder ? -1 : 0"
                :aria-label="
                  autoOrder
                    ? `参考图，${item.provider === 'user' ? '我上传的' : '搜索勾选'}，顺序由 AI 决定`
                    : `第 ${index + 1} 张，${item.provider === 'user' ? '我上传的' : '搜索勾选'}，左右方向键调整位置`
                "
                @pointerdown="
                  onCardPointerDown($event, index, item.candidate_id)
                "
                @keydown.left.prevent="moveItem(index, -1)"
                @keydown.right.prevent="moveItem(index, 1)"
              >
                <img
                  class="order-thumb"
                  :src="item.image_url"
                  :alt="`第 ${index + 1} 张参考图`"
                  draggable="false"
                />
                <!-- 序号只在用户自己排的时候有意义，AI 排序时隐掉 -->
                <span v-if="!autoOrder" class="order-seq">{{ index + 1 }}</span>
                <button
                  type="button"
                  class="order-del"
                  title="移除这张"
                  @click.stop="removeItem(item.candidate_id)"
                >
                  <PhX :size="11" weight="bold" />
                </button>
                <span
                  class="order-src"
                  :class="{ mine: item.provider === 'user' }"
                >
                  {{ item.provider === "user" ? "我上传的" : "搜索勾选" }}
                </span>
              </article>
            </div>

            <!-- 钉在滚动区外面：一排图多到要横向滚时，「再加」也始终够得着 -->
            <button
              type="button"
              class="add-tile"
              :disabled="!canAddMore"
              :title="canAddMore ? '再挑几张' : budgetReason"
              @click="togglePicker"
            >
              <PhPlus :size="18" />
              <span>再加</span>
            </button>
          </div>
          <p class="strip-hint">
            <template v-if="autoOrder"
              >顺序已交给 AI · 这一排暂不可拖动，仍可删除或添加</template
            >
            <template v-else
              >按住缩略图拖动换顺序 · 第 N 张配第 N 个镜头</template
            >
            <template v-if="!canAddMore"> · {{ budgetReason }}</template>
          </p>
        </section>

        <section v-if="showPicker" class="add-panel">
          <div class="add-actions">
            <NButton
              size="small"
              quaternary
              type="primary"
              :disabled="uploading"
              @click="pickFiles"
            >
              <PhUploadSimple :size="14" class="btn-ico" />再传一张
            </NButton>
            <NButton size="small" quaternary @click="showPicker = false">
              <PhX :size="14" class="btn-ico" />收起
            </NButton>
          </div>

          <div class="pool">
            <button
              v-for="candidate in candidates"
              :key="candidate.candidate_id"
              type="button"
              class="pool-item"
              :class="{ on: selectedIds.includes(candidate.candidate_id) }"
              :disabled="selectedIds.includes(candidate.candidate_id)"
              :title="
                selectedIds.includes(candidate.candidate_id)
                  ? '已在清单里'
                  : '加到最后一位'
              "
              @click="addFromPool(candidate.candidate_id)"
            >
              <img
                :src="candidate.image_url"
                :alt="candidate.title || '候选图'"
              />
              <span
                v-if="selectedIds.includes(candidate.candidate_id)"
                class="pool-check"
              >
                <PhCheck :size="12" weight="bold" />
              </span>
            </button>
          </div>
        </section>

        <div class="action-dock">
          <div class="action-copy">
            <b>{{
              !selectedCount
                ? "至少要留一张参考图"
                : autoOrder
                  ? `${selectedCount} 张，顺序交给 AI 配`
                  : `${selectedCount} 张，按上面的顺序生成`
            }}</b>
            <span>{{ budgetReason }}</span>
          </div>
          <div class="action-buttons">
            <NButton size="large" @click="reviewing = false">
              <PhArrowLeft :size="15" class="btn-ico" />返回挑选
            </NButton>
            <NButton
              type="primary"
              size="large"
              :loading="confirming"
              :disabled="!selectedCount"
              @click="confirmSelection"
              >确认，开始生成</NButton
            >
          </div>
        </div>
      </template>

      <section v-else-if="phase === 'processing'" class="card processing-card">
        <div class="orbit" aria-hidden="true">
          <span class="orbit-core" role="img" aria-label="AI 正在思考">
            <PhGear />
          </span>
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
        <small>完成后将自动进入创作方案确认页，也可以稍后从项目页继续。</small>
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
          <NButton
            :loading="refreshing"
            @click="
              retryProject(pid)
                .then(() => tick({ manual: true }))
                .catch((e) => message.error(e.message))
            "
            >重试当前步骤</NButton
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
          <NButton
            :type="
              isSelected(previewCandidate.candidate_id) ? 'default' : 'primary'
            "
            size="large"
            @click="toggleCandidate(previewCandidate)"
          >
            <template v-if="isSelected(previewCandidate.candidate_id)">
              <PhCheck :size="15" weight="bold" class="btn-ico" />
              已选中，点击取消
            </template>
            <template v-else>选择图片</template>
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
      var(--glow-primary-soft),
      transparent 26%
    ),
    radial-gradient(circle at 92% 8%, var(--glow-gold-faint), transparent 24%),
    var(--color-bg);
  color: var(--color-ink);
  font-family: var(--font-sans);
}
.stage {
  max-width: 1200px;
  min-height: calc(100vh - 150px);
  margin: 0 auto;
  padding: 30px 24px 70px;
}
.card {
  background: var(--card-glass);
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
  color: var(--color-ink-muted);
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
  color: var(--color-on-primary);
  border-color: var(--color-primary);
  background: var(--color-primary);
  box-shadow: 0 0 0 5px var(--shadow-primary);
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
  color: var(--color-ink-muted);
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
  border-color: var(--color-error-border);
  background: var(--color-error-fade);
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
  background: var(--gradient-ring);
  box-shadow: 0 12px 35px var(--shadow-primary);
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
  background: var(--gradient-bar);
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
  background: var(--color-card);
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

/* ── 上传自己的实景图 ── */
.uploader {
  margin-bottom: 18px;
  padding: 20px 22px;
}
.uploader-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}
.uploader-head h2 {
  margin: 0 0 5px;
  font-family: var(--font-serif);
  font-size: 18px;
}
.uploader-head p {
  margin: 0;
  color: var(--color-ink-sub);
  font-size: 13px;
  line-height: 1.6;
}
.quota {
  flex-shrink: 0;
  padding: 6px 12px;
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
  border-radius: 99px;
  background: var(--color-primary-fade);
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}
.quota.full {
  color: var(--status-busy-fg);
  border-color: var(--status-warn-line);
  background: var(--status-busy-bg);
}
.drop-zone {
  margin-top: 14px;
  padding: 22px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  color: var(--color-ink-sub);
  border: 1px dashed var(--border-dashed);
  border-radius: 13px;
  background: var(--surface-sunken);
  cursor: pointer;
  text-align: center;
  transition:
    border-color 0.18s ease,
    background 0.18s ease;
}
.drop-zone:hover,
.drop-zone:focus-visible {
  border-color: var(--color-primary);
  background: var(--color-primary-fade);
  outline: none;
}
.drop-zone.dragging {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.drop-zone.busy {
  pointer-events: none;
  opacity: 0.65;
}
.drop-zone b {
  color: var(--color-ink);
  font-size: 14px;
}
.drop-zone small {
  color: var(--color-ink-muted);
  font-size: 12px;
}
.file-input {
  display: none;
}
.link-entry {
  margin-top: 11px;
}
.link-toggle {
  padding: 0;
  color: var(--color-ink-sub);
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12.5px;
}
.link-toggle:hover {
  color: var(--color-primary);
}
.link-row {
  margin-top: 9px;
  display: flex;
  gap: 9px;
}
.link-row :deep(.n-input) {
  flex: 1;
}
.quota-note {
  margin: 12px 0 0;
  color: var(--color-ink-muted);
  font-size: 12px;
}

/* ── 确认清单：一排缩略图，直接拖着换顺序 ── */
.strip-wrap {
  padding: 15px 17px 13px;
  margin-bottom: 14px;
  border: 1px solid var(--color-border);
  border-radius: 13px;
  background: var(--surface-sunken);
}
/* 候选池收起时它就是最后一个 section，得自己给吸底操作条让位 */
.strip-wrap:last-of-type {
  margin-bottom: 118px;
}
/* ── 顺序谁定：一排图上方的两态开关 ── */
.order-mode {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 11px;
}
.mode-switch {
  display: inline-flex;
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-card);
}
.mode-opt {
  padding: 4px 13px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-ink-muted);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.16s ease,
    color 0.16s ease;
}
.mode-opt:hover {
  color: var(--color-ink);
}
.mode-opt.on {
  background: var(--color-primary);
  color: #fff;
}
.mode-opt:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}
.mode-hint {
  margin: 0;
  color: var(--color-ink-muted);
  font-size: 12px;
}
.order-mode.auto .mode-hint {
  color: var(--color-primary);
}
.strip-row {
  display: flex;
  align-items: stretch;
  gap: 12px;
}
.strip {
  /* 图少时贴着「再加」排；多到装不下才由 flex-shrink 收窄并横向滚动 */
  flex: 0 1 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  overflow-x: auto;
  padding: 4px 2px 10px; /* 上留给抬起时的投影，下留给横向滚动条 */
  scrollbar-width: thin;
}
.order-card {
  position: relative;
  flex: 0 0 148px;
  width: 148px;
  padding: 0 0 6px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  border: 2px solid transparent;
  border-radius: 12px;
  background: var(--color-card);
  box-shadow: 0 3px 12px var(--shadow-soft);
  cursor: grab;
  /* 触屏：横滑先当滚动。按住不动才会被脚本接管成拖拽 */
  touch-action: pan-x;
  user-select: none;
  will-change: transform;
  /* 让位靠这条过渡滑开；归位也复用它 */
  transition:
    transform 0.24s cubic-bezier(0.22, 0.61, 0.36, 1),
    scale 0.18s ease,
    border-color 0.15s ease,
    box-shadow 0.18s ease,
    opacity 0.18s ease;
}
.order-card:focus-visible {
  outline: none;
  border-color: var(--color-primary);
}
/* 交给 AI 排时不装成可拖的样子：降一点视觉权重、指针也改成普通箭头，
   但还是看得见、点得着（删除按钮要照常能用） */
.strip.readonly .order-card {
  cursor: default;
  opacity: 0.72;
  box-shadow: none;
}
.strip.readonly .order-card:hover {
  opacity: 0.88;
}
/* 抓起来那张：跟手 + 放大浮起 */
.order-card.lifted {
  cursor: grabbing;
  z-index: 6;
  scale: 1.04; /* 独立的 scale 属性，跟 transform 各走各的，互不打架 */
  opacity: 0.94;
  border-color: var(--color-primary);
  box-shadow: 0 16px 30px var(--shadow-primary);
  /* 位移必须是 0 过渡，否则卡片追不上指针，拖起来发飘 */
  transition:
    transform 0s,
    scale 0.18s ease,
    border-color 0.15s ease,
    box-shadow 0.18s ease,
    opacity 0.18s ease;
}
/* 松手后还在滑回格子的那一下，保持浮在上层 */
.order-card.settling {
  z-index: 6;
}
/* 一旦拖起来就禁掉触屏滚动，免得浏览器把指针事件抢去滚这一排 */
.strip.dragging .order-card {
  touch-action: none;
  cursor: grabbing;
}
.order-thumb {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: block;
  object-fit: cover;
  border-radius: 10px 10px 0 0;
  background: var(--media-placeholder);
  /* 让 pointerdown 稳稳落在卡片上，图片自身的原生拖拽也不来插一脚 */
  pointer-events: none;
}
.order-seq {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 23px;
  height: 23px;
  display: grid;
  place-items: center;
  color: var(--color-on-primary);
  border-radius: 50%;
  background: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 2px 6px var(--shadow-soft);
}
.order-del {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 21px;
  height: 21px;
  display: grid;
  place-items: center;
  padding: 0;
  color: var(--on-photo);
  border: 0;
  border-radius: 50%;
  background: var(--badge-bad-bg);
  cursor: pointer;
  opacity: 0; /* 平时不挡图，指到或聚焦才浮出来 */
  transition: opacity 0.15s ease;
}
.order-card:hover .order-del,
.order-card:focus-within .order-del,
.order-del:focus-visible {
  opacity: 1;
}
/* 触屏没有 hover，一直露着才删得掉 */
@media (hover: none) {
  .order-del {
    opacity: 1;
  }
}
.order-src {
  padding: 0 8px;
  color: var(--color-ink-muted);
  font-size: 11px;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.order-src.mine {
  color: var(--color-gold-ink);
}
.add-tile {
  flex: 0 0 96px;
  min-height: 116px;
  /* 跟卡片对齐：抵消 .strip 给滚动条留的那 10px */
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--color-primary);
  border: 1.5px dashed var(--color-border);
  border-radius: 12px;
  background: transparent;
  font-size: 12px;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.add-tile:hover:not(:disabled),
.add-tile:focus-visible:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-fade);
  outline: none;
}
.add-tile:disabled {
  color: var(--color-ink-muted);
  cursor: default;
  opacity: 0.5;
}
.strip-hint {
  margin: 2px 0 0;
  color: var(--color-ink-muted);
  font-size: 12px;
}

/* ── 清单下方的「再加」 ── */
.add-panel {
  /* 吸底操作条是 fixed，给它让出让位空间 */
  margin-bottom: 118px;
  padding: 15px 17px;
  border: 1px solid var(--color-border);
  border-radius: 13px;
  background: var(--surface-sunken);
}
.add-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}
.pool {
  margin-top: 13px;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}
.pool-item {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 9px;
  background: var(--media-placeholder);
  cursor: pointer;
}
.pool-item img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.pool-item:hover:not(:disabled),
.pool-item:focus-visible:not(:disabled) {
  border-color: var(--color-primary);
  outline: none;
}
.pool-item:disabled {
  cursor: default;
  opacity: 0.4;
}
.pool-item.on {
  opacity: 1;
  border-color: var(--color-primary);
}
.pool-check {
  position: absolute;
  right: 6px;
  bottom: 6px;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  color: var(--color-on-primary);
  border-radius: 99px;
  background: var(--color-primary);
}
.image-card {
  min-width: 0;
  overflow: hidden;
  border: 2px solid transparent;
  border-radius: 13px;
  background: var(--color-card);
  box-shadow: 0 4px 18px var(--shadow-soft);
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
    0 0 0 3px var(--shadow-primary),
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
  background: var(--media-placeholder);
}
.image-wrap img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}
.check-mark {
  position: absolute;
  top: 10px;
  display: grid;
  place-items: center;
  color: var(--on-photo);
  border-radius: 99px;
  background: var(--scrim);
  backdrop-filter: blur(6px);
}
.check-mark {
  right: 10px;
  width: 27px;
  height: 27px;
  border: 1px solid var(--scrim-border);
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
  color: var(--on-photo);
  border: 1px solid var(--scrim-border);
  border-radius: 50%;
  background: var(--scrim);
  cursor: zoom-in;
  backdrop-filter: blur(6px);
  transition:
    background 0.15s ease,
    transform 0.15s ease;
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
    var(--checker-a),
    var(--checker-a) 10px,
    var(--checker-b) 10px,
    var(--checker-b) 20px
  );
}
.broken-placeholder small {
  font-size: 11px;
}
.preview-shell {
  width: min(1120px, calc(100vw - 48px));
  height: min(850px, calc(100vh - 48px));
  height: min(850px, calc(100dvh - 48px));
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--lightbox-hairline);
  border-radius: 16px;
  background: var(--lightbox-bg);
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
  color: var(--on-photo);
  border: 1px solid var(--on-photo-soft);
  border-radius: 50%;
  background: var(--scrim);
  cursor: pointer;
  font-size: 27px;
  line-height: 1;
  backdrop-filter: blur(6px);
}
.preview-close:hover {
  background: var(--scrim-hover);
}
.preview-image-wrap {
  min-width: 0;
  min-height: 0;
  flex: 1;
  background:
    radial-gradient(circle at center, var(--lightbox-sheen), transparent 55%),
    var(--lightbox-bg);
}
.preview-image-wrap img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}
.preview-footer {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  background: var(--lightbox-bg);
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
  left: calc(50% + var(--sidebar-width, 0px) / 2);
  bottom: 22px;
  width: min(1080px, calc(100% - var(--sidebar-width, 0px) - 48px));
  box-sizing: border-box;
  padding: 14px 17px 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border: 1px solid var(--divider-primary);
  border-radius: 16px;
  background: var(--card-glass);
  box-shadow: 0 15px 45px var(--shadow-deep);
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
  color: var(--color-on-primary);
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
  border: 2px solid var(--photo-divider);
  border-radius: 8px;
  object-fit: cover;
  box-shadow: 0 4px 12px var(--shadow-soft);
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
  color: var(--color-on-error);
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
  .pool {
    grid-template-columns: repeat(4, minmax(0, 1fr));
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
  .pool {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  /* 窄屏卡片收窄，一屏能多露几张（横向滚动照旧） */
  .order-card {
    flex-basis: 112px;
    width: 112px;
  }
  .add-tile {
    flex-basis: 78px;
  }
  .add-panel {
    margin-bottom: 196px;
  }
  .strip-wrap:last-of-type {
    margin-bottom: 196px;
  }
  .action-dock {
    bottom: 10px;
    width: calc(100% - var(--sidebar-width, 0px) - 20px);
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
    height: calc(100vh - 20px);
    height: calc(100dvh - 20px);
  }
  .preview-footer {
    justify-content: stretch;
  }
  .preview-footer .n-button {
    width: 100%;
  }
}
</style>
