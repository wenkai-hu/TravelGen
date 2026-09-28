<script setup>
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NInput,
  NPopover,
  NSlider,
  useMessage,
} from "naive-ui";
import {
  PhBuildings,
  PhCaretRight,
  PhCircleDashed,
  PhFilmSlate,
  PhGear,
  PhHammer,
  PhImage,
  PhLightbulb,
  PhMapPin,
  PhNotePencil,
  PhPalette,
  PhPuzzlePiece,
  PhSparkle,
  PhTelevision,
  PhTimer,
  PhUsersThree,
  PhUser,
} from "@phosphor-icons/vue";
import CraftSlot from "../components/CraftSlot.vue";
import ThemeToggle from "../components/ThemeToggle.vue";
import logoUrl from "../images/logo.png";
import { createProject } from "../api";
import { getUsername, isLoggedIn, logout as clearSession } from "../auth";
import {
  ASPECT_RATIOS,
  DEFAULT_AUDIENCE,
  DEFAULT_STYLE,
  DURATION_RANGE,
  RESOLUTIONS,
  SCENE_TYPES,
  VIDEO_MODELS,
} from "../constants";

const message = useMessage();
const router = useRouter();

// ── 登录态（localStorage；退出仅清前端会话） ──
const loggedIn = ref(isLoggedIn());
const username = ref(getUsername() || "");
function onLogout() {
  clearSession();
  loggedIn.value = false;
  username.value = "";
  message.success("已退出登录");
}

// ── 配方（表单）—— 与后端 schemas.py GenerateRequest 一一对应 ──
const form = reactive({
  city: "",
  location: "",
  theme: "",
  scene_type: "", // 留空：邀请用户亲手"放入"场景块
  audience: DEFAULT_AUDIENCE,
  style: DEFAULT_STYLE,
  duration_s: DURATION_RANGE.default,
  aspect_ratio: "9:16",
  resolution: "1080p",
  video_model: "seedance-2.0-pro",
  description: "",
});

// 人群 / 风格：预设块 + 可自定义
const AUDIENCE_PRESETS = [
  "18-35岁年轻游客",
  "亲子家庭",
  "银发康养游客",
  "商务差旅",
  "学生党",
];
const STYLE_PRESETS = [
  "大气唯美",
  "国风古韵",
  "青春活力",
  "文艺清新",
  "水墨诗意",
  "赛博未来",
];

const scenePop = ref(false);
const audiencePop = ref(false);
const stylePop = ref(false);
const customAudience = ref("");
const customStyle = ref("");

// ── 九宫格键盘导航：↑↓←→ 跨格，光标/组内贴边才出格 ──
const benchRef = ref(null);
const NAV = {
  ArrowUp: [-1, 0],
  ArrowDown: [1, 0],
  ArrowLeft: [0, -1],
  ArrowRight: [0, 1],
};
const FOCUSABLE = "input, textarea, button, [tabindex]:not([tabindex='-1'])";

// 按实测位置分行分列：响应式塌成单列时也自动成立。
// 用 rect 而非 offsetTop —— 补充槽与九宫格不在同一 offsetParent 下。
function slotMatrix() {
  const boxes = [...benchRef.value.querySelectorAll(".craft-slot")].map((slot) => {
    const rect = slot.getBoundingClientRect();
    return { slot, top: rect.top, left: rect.left };
  });
  const rows = [];
  for (const box of boxes) {
    const row = rows.find((r) => Math.abs(r.top - box.top) < 8);
    if (row) row.boxes.push(box);
    else rows.push({ top: box.top, boxes: [box] });
  }
  return rows.map((r) =>
    r.boxes.sort((a, b) => a.left - b.left).map((b) => b.slot),
  );
}

function locate(matrix, el) {
  for (let r = 0; r < matrix.length; r++) {
    const c = matrix[r].findIndex((slot) => slot.contains(el));
    if (c !== -1) return { r, c };
  }
  return null;
}

// 光标是否已贴到该方向的外缘
function atEdge(el, key) {
  const v = el.value;
  if (el.tagName === "TEXTAREA") {
    if (key === "ArrowUp") return !v.slice(0, el.selectionStart).includes("\n");
    if (key === "ArrowDown") return !v.slice(el.selectionEnd).includes("\n");
  }
  if (key === "ArrowLeft") return (el.selectionStart ?? 0) === 0;
  if (key === "ArrowRight") return (el.selectionEnd ?? v.length) === v.length;
  return true; // 单行输入没有"行"，↑↓ 直接出格
}

// 分段按钮组（画幅/分辨率/模型）内左右走，已到组边缘则交给跨格
function segMove(el, key) {
  if (key !== "ArrowLeft" && key !== "ArrowRight") return false;
  const seg = el.closest(".mini-seg");
  if (!seg) return false;
  const btns = [...seg.querySelectorAll("button")];
  const j = btns.indexOf(el) + (key === "ArrowLeft" ? -1 : 1);
  if (j < 0 || j >= btns.length) return false;
  btns[j].focus();
  return true;
}

function onGridKey(e) {
  const dir = NAV[e.key];
  if (!dir || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const el = e.target;
  if (!el) return;
  if (el.closest(".n-slider")) {
    if (dir[0] === 0) return; // 滑块的 ←→ 是调值键；↑↓ 与调值重复，放行跳格
  } else if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
    if (!atEdge(el, e.key)) return; // 光标没贴边，先让给它
  } else if (segMove(el, e.key)) {
    e.preventDefault();
    return;
  }

  const matrix = slotMatrix();
  const at = locate(matrix, el);
  if (!at) return;
  const row = matrix[at.r + dir[0]];
  if (!row) return;
  const cell = row[Math.min(at.c + dir[1], row.length - 1)]; // 末行只有一格，落回第 0 列
  const next = cell?.querySelector(FOCUSABLE);
  if (!next) return;

  e.preventDefault();
  scenePop.value = audiencePop.value = stylePop.value = false;
  next.focus();
  if (next.setSelectionRange) {
    try {
      next.setSelectionRange(next.value.length, next.value.length); // 落到末尾，方便继续贴边出格
    } catch {
      /* number/date 等类型不支持选区，忽略 */
    }
  }
}

// ── 补充选项：补充说明 / 模型选择 循环切换（点右侧箭头）。
// 参考图已移到「开始锻造」之后的选图页 —— 在那里上传才能和搜到的图一起排序。 ──
const EXTRA_PANES = [
  { key: "description", label: "补充说明（可选）", icon: PhNotePencil },
  { key: "video_model", label: "模型选择", icon: PhGear },
];
const extraIndex = ref(0);
const extra = computed(() => EXTRA_PANES[extraIndex.value]);
const extraFilled = computed(() => {
  if (extra.value.key === "video_model") return true; // 有默认值，恒为已填
  return !!form.description.trim();
});

const submitting = ref(false);
const created = ref(null);
const submitError = ref("");

// ── 配方完成度：分母动态 = 9 宫格必选 + 模型默认选上（恒 10），填了补充说明再 +1 ──
const descFilled = computed(() => !!form.description.trim());
const slotsFilled = computed(() => {
  let n = 0;
  if (form.city.trim()) n++;
  if (form.location.trim()) n++;
  if (form.theme.trim()) n++;
  if (form.scene_type) n++;
  if (form.audience.trim()) n++;
  if (form.style.trim()) n++;
  n += 4; // 时长/画幅/分辨率 + 模型选择（默认值恒为已填）
  if (descFilled.value) n++;
  return n;
});
const totalSlots = computed(() => 10 + (descFilled.value ? 1 : 0));
const completion = computed(() =>
  Math.round((slotsFilled.value / totalSlots.value) * 100),
);

// 必需材料：城市 / 地点 / 主题 / 场景类型
const requiredOk = computed(
  () =>
    form.city.trim() &&
    form.location.trim() &&
    form.theme.trim() &&
    form.scene_type,
);
const sceneLabel = computed(() =>
  SCENE_TYPES.find((s) => s.value === form.scene_type),
);

const durationMarks = { 15: "15s", 60: "60s", 120: "120s" };

function applyCustom(key) {
  const v =
    key === "audience" ? customAudience.value.trim() : customStyle.value.trim();
  if (v) form[key] = v;
  if (key === "audience") audiencePop.value = false;
  else stylePop.value = false;
}

async function onSubmit() {
  if (!requiredOk.value) {
    message.warning("工作台上还缺材料：城市 / 地点 / 主题 / 场景类型");
    return;
  }
  submitting.value = true;
  submitError.value = "";
  created.value = null;
  try {
    const payload = {
      city: form.city.trim(),
      location: form.location.trim(),
      theme: form.theme.trim(),
      scene_type: form.scene_type,
      audience: form.audience.trim() || DEFAULT_AUDIENCE,
      style: form.style.trim() || DEFAULT_STYLE,
      duration_s: form.duration_s,
      aspect_ratio: form.aspect_ratio,
      resolution: form.resolution,
      description: form.description.trim(),
      video_model: form.video_model,
      // 参考图不在这里传：改到创建之后的选图页上传，好和搜到的图一起排序
    };
    const data = await createProject(payload);
    created.value = data;
    sessionStorage.setItem("travelgen_project_id", data.project_id);
    message.success("项目已创建，正在搜索景点实景图片…");
    router.push(`/project/${data.project_id}/references`);
  } catch (e) {
    // 401 是登录态失效（token 过期 / 后端重启后内存会话丢失），不是后端没开 ——
    // 别把它套进「后端未连接」里，那会让人去查一个根本没坏的东西。
    if (e.status === 401) {
      clearSession();
      submitError.value = "登录已失效（后端重启会清空登录态），请重新登录后再试";
      message.error(submitError.value);
      router.push("/login");
      return;
    }
    submitError.value =
      e.code === "invalid_param"
        ? e.message
        : `后端未连接：${e.message}（请先运行 python backend/app.py，无 key 也能走 demo 模式）`;
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="page">
    <!-- 顶部导航 -->
    <header class="nav fade-up">
      <div class="nav-inner">
        <div class="logo">
          <img :src="logoUrl" class="logo-mark" alt="TravelGen" />
          <span class="logo-text gradient-text">TravelGen</span>
        </div>
        <nav class="nav-links">
          <a href="#bench">工作台</a>
          <a href="#compliance">版权合规</a>
          <template v-if="loggedIn">
            <router-link to="/history">我的创作</router-link>
            <span class="nav-user" title="已登录"
              ><PhUser :size="14" />{{ username }}</span
            >
            <a href="#" class="nav-auth" @click.prevent="onLogout">退出</a>
          </template>
          <router-link v-else to="/login" class="nav-auth"
            >登录 / 注册</router-link
          >
          <ThemeToggle />
        </nav>
      </div>
    </header>

    <!-- 主区 -->
    <main class="workshop">
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>

      <!-- 文案区 -->
      <section class="hero-text">
        <span class="eyebrow fade-up">浙江文旅 · AIGC 创意工作台</span>
        <h1 class="title fade-up-1">
          把你的灵感，<span class="gradient-text">摆上工作台</span>
        </h1>
        <!-- <p class="subtitle fade-up-2">
          像拼装配方一样创作：放入内容素材、选定创作方向、核对输出规格 ——
          一键锻造一部属于浙江的文旅宣传片。
        </p> -->
        <div class="ability-row fade-up-3">
          <span class="ability">✍️ 文案</span>
          <span class="ability">🎬 分镜</span>
          <span class="ability">🎙️ 配音</span>
          <span class="ability">🎵 音乐</span>
          <span class="ability">📹 视频</span>
        </div>
      </section>

      <!-- 工作台 -->
      <div
        id="bench"
        ref="benchRef"
        class="bench-area fade-up-2"
        @keydown="onGridKey"
      >
        <div class="bench-left">
          <div class="craft-panel" :class="{ ready: requiredOk }">
            <!-- ① 内容素材 -->
            <div class="craft-row">
              <div class="row-tag">① 配方原料</div>
              <CraftSlot
                label="城市"
                :icon="PhBuildings"
                :filled="!!form.city.trim()"
                required
              >
                <NInput v-model:value="form.city" placeholder="如：杭州" />
              </CraftSlot>
              <CraftSlot
                label="景点地点"
                :icon="PhMapPin"
                :filled="!!form.location.trim()"
                required
              >
                <NInput v-model:value="form.location" placeholder="如：西湖" />
              </CraftSlot>
              <CraftSlot
                label="传播主题"
                :icon="PhLightbulb"
                :filled="!!form.theme.trim()"
                required
              >
                <NInput
                  v-model:value="form.theme"
                  placeholder="如：西湖十景新玩法"
                />
              </CraftSlot>
            </div>

            <!-- ② 创作方向 -->
            <div class="craft-row">
              <div class="row-tag">② 定制偏好</div>
              <CraftSlot
                label="场景类型"
                :icon="PhPuzzlePiece"
                :filled="!!form.scene_type"
                required
              >
                <NPopover
                  v-model:show="scenePop"
                  trigger="click"
                  placement="bottom"
                  :width="320"
                  style="width: 100%"
                >
                  <template #trigger>
                    <button
                      type="button"
                      class="pick-box"
                      :class="{ empty: !form.scene_type }"
                    >
                      <template v-if="sceneLabel">
                        <component :is="sceneLabel.icon" class="ico-inline" />
                        {{ sceneLabel.value }}
                      </template>
                      <template v-else>点击放入「场景块」</template>
                    </button>
                  </template>
                  <div class="scene-picker">
                    <button
                      v-for="s in SCENE_TYPES"
                      :key="s.value"
                      type="button"
                      class="scene-opt"
                      @click="
                        form.scene_type = s.value;
                        scenePop = false;
                      "
                    >
                      <span class="opt-icon"><component :is="s.icon" /></span>
                      <span class="opt-text"
                        ><b>{{ s.value }}</b
                        ><i>{{ s.desc }}</i></span
                      >
                    </button>
                  </div>
                </NPopover>
              </CraftSlot>

              <CraftSlot
                label="目标人群"
                :icon="PhUsersThree"
                :filled="!!form.audience.trim()"
              >
                <NPopover
                  v-model:show="audiencePop"
                  trigger="click"
                  placement="bottom"
                  :width="280"
                  style="width: 100%"
                >
                  <template #trigger>
                    <button type="button" class="pick-box">
                      {{ form.audience }}
                    </button>
                  </template>
                  <div class="chip-picker">
                    <button
                      v-for="p in AUDIENCE_PRESETS"
                      :key="p"
                      type="button"
                      class="chip"
                      :class="{ on: form.audience === p }"
                      @click="
                        form.audience = p;
                        audiencePop = false;
                      "
                    >
                      {{ p }}
                    </button>
                    <div class="custom-row">
                      <NInput
                        v-model:value="customAudience"
                        size="small"
                        placeholder="自定义人群…"
                        @keyup.enter="applyCustom('audience')"
                      />
                      <NButton size="small" @click="applyCustom('audience')"
                        >放入</NButton
                      >
                    </div>
                  </div>
                </NPopover>
              </CraftSlot>

              <CraftSlot
                label="视频风格"
                :icon="PhPalette"
                :filled="!!form.style.trim()"
              >
                <NPopover
                  v-model:show="stylePop"
                  trigger="click"
                  placement="bottom"
                  :width="280"
                  style="width: 100%"
                >
                  <template #trigger>
                    <button type="button" class="pick-box">
                      {{ form.style }}
                    </button>
                  </template>
                  <div class="chip-picker">
                    <button
                      v-for="p in STYLE_PRESETS"
                      :key="p"
                      type="button"
                      class="chip"
                      :class="{ on: form.style === p }"
                      @click="
                        form.style = p;
                        stylePop = false;
                      "
                    >
                      {{ p }}
                    </button>
                    <div class="custom-row">
                      <NInput
                        v-model:value="customStyle"
                        size="small"
                        placeholder="自定义风格…"
                        @keyup.enter="applyCustom('style')"
                      />
                      <NButton size="small" @click="applyCustom('style')"
                        >放入</NButton
                      >
                    </div>
                  </div>
                </NPopover>
              </CraftSlot>
            </div>

            <!-- ③ 输出规格 -->
            <div class="craft-row">
              <div class="row-tag">③ 输出规格</div>
              <CraftSlot label="视频时长" :icon="PhTimer" :filled="true">
                <NSlider
                  v-model:value="form.duration_s"
                  :min="DURATION_RANGE.min"
                  :max="DURATION_RANGE.max"
                  :marks="durationMarks"
                />
                <div class="slot-note">{{ form.duration_s }} 秒</div>
              </CraftSlot>
              <CraftSlot label="画幅" :icon="PhImage" :filled="true">
                <div class="mini-seg">
                  <button
                    v-for="r in ASPECT_RATIOS"
                    :key="r"
                    type="button"
                    :class="{ on: form.aspect_ratio === r }"
                    @click="form.aspect_ratio = r"
                  >
                    {{ r }}
                  </button>
                </div>
              </CraftSlot>
              <CraftSlot label="分辨率" :icon="PhTelevision" :filled="true">
                <div class="mini-seg">
                  <button
                    v-for="r in RESOLUTIONS"
                    :key="r"
                    type="button"
                    :class="{ on: form.resolution === r }"
                    @click="form.resolution = r"
                  >
                    {{ r }}
                  </button>
                </div>
              </CraftSlot>
            </div>
          </div>
        </div>

        <!-- 合成箭头 -->
        <div class="craft-arrow" aria-hidden="true">
          <span class="arrow-line"></span>
          <span class="arrow-head">▶</span>
        </div>

        <!-- 成品槽 -->
        <aside class="result-slot" :class="{ ready: requiredOk }">
          <div class="result-head">
            <span class="result-icon"><PhFilmSlate /></span> 成品
          </div>
          <div class="result-preview" :class="{ waiting: !requiredOk }">
            <template v-if="requiredOk">
              <p class="r-title">{{ form.theme }}</p>
              <p class="r-line">
                <PhMapPin class="r-ico" /> {{ form.city }} · {{ form.location }}
              </p>
              <p class="r-line">
                <PhPuzzlePiece class="r-ico" /> {{ form.scene_type }}
              </p>
              <p class="r-line">
                <PhPalette class="r-ico" /> {{ form.style }}｜{{ form.audience }}
              </p>
              <p class="r-line">
                <PhTimer class="r-ico" /> {{ form.duration_s }}s｜{{
                  form.aspect_ratio
                }}｜{{ form.resolution }}
              </p>
            </template>
            <template v-else>
              <div class="waiting-hint">
                <span class="waiting-icon"><PhCircleDashed /></span>
                <p>还缺材料…<br />放入 城市 / 地点 / 主题 / 场景类型</p>
              </div>
            </template>
          </div>
          <NButton
            class="craft-btn"
            block
            size="large"
            :loading="submitting"
            :disabled="!requiredOk"
            @click="onSubmit"
          >
            <template v-if="submitting">锻造中…</template>
            <template v-else>
              <PhHammer :size="16" class="btn-ico" /> 开始锻造
            </template>
          </NButton>
          <NAlert
            v-if="created"
            type="success"
            class="result-alert"
            :bordered="false"
          >
            项目已创建：<b>{{ created.project_id }}</b
            >（{{ created.status }}）。正在跳转实景选图页…
          </NAlert>
          <NAlert
            v-if="submitError"
            type="error"
            class="result-alert"
            :bordered="false"
          >
            {{ submitError }}
          </NAlert>
        </aside>

        <!-- 可选补充槽：补充说明 / 模型选择 / 参考图片 循环切换（独立网格行，与九宫格左对齐） -->
        <div class="extra-row">
          <CraftSlot
            :label="extra.label"
            :icon="extra.icon"
            :filled="extraFilled"
          >
            <NInput
              v-if="extra.key === 'description'"
              v-model:value="form.description"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 3 }"
              placeholder="想要突出的元素、风格要求等（会注入 AI 的创作提示词）"
            />
            <template v-else-if="extra.key === 'video_model'">
              <div class="mini-seg">
                <button
                  v-for="m in VIDEO_MODELS"
                  :key="m"
                  type="button"
                  :class="{ on: form.video_model === m }"
                  @click="form.video_model = m"
                >
                  {{ m }}
                </button>
              </div>
              <div class="slot-note">Pro 版画质更高、生成更慢</div>
            </template>
          </CraftSlot>
          <div class="extra-side">
            <button
              type="button"
              class="extra-arrow"
              title="切换补充选项"
              @click="extraIndex = (extraIndex + 1) % EXTRA_PANES.length"
            >
              <PhCaretRight :size="14" />
            </button>
            <div class="extra-dots">
              <span
                v-for="(p, i) in EXTRA_PANES"
                :key="p.key"
                :class="{ on: i === extraIndex }"
              />
            </div>
          </div>
        </div>

        <!-- 配方完成度 -->
        <div class="recipe-bar">
          <span class="recipe-label">配方完成度</span>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: completion + '%' }"></div>
          </div>
          <span class="recipe-count">{{ slotsFilled }}/{{ totalSlots }}</span>
          <span v-if="requiredOk" class="recipe-ready">
            <PhSparkle :size="12" weight="fill" /> 配方就绪
          </span>
        </div>
      </div>
    </main>

    <!-- 页脚 -->
    <footer id="compliance" class="footer"></footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--color-bg);
  font-family: var(--font-sans);
  color: var(--color-ink);
  position: relative;
  overflow-x: hidden;
}

/* ---------- 导航 ---------- */
.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--surface-nav); /* 与 logo 图底色一致，消除色差 */
  border-bottom: 1px solid var(--color-border);
  box-shadow: var(--shadow-soft);
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
}
.logo-mark {
  width: 76px;
  height: 76px;
  border-radius: 12px;
  object-fit: cover;
  display: block;
  flex-shrink: 0;
  box-shadow: 0 0 0 1px var(--logo-ring);
}
.logo-text {
  font-family: var(--font-serif);
  font-size: 25px;
  font-weight: 700;
  letter-spacing: 1px;
}
.nav-links {
  display: flex;
  align-items: center;
  gap: 32px;
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
.nav-user {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  color: var(--color-primary);
  white-space: nowrap;
}
.nav-auth {
  padding: 5px 16px;
  border-radius: 999px;
  border: 1.5px solid var(--color-primary);
  font-size: 13.5px;
  color: var(--color-primary) !important;
  white-space: nowrap;
  transition: all 0.15s;
}
.nav-auth:hover {
  background: var(--color-primary);
  color: var(--color-on-primary) !important;
}

/* ---------- 主区 ---------- */
.workshop {
  position: relative;
  padding: 48px 24px 40px;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.3;
  pointer-events: none;
}
.glow-1 {
  width: 420px;
  height: 420px;
  background: var(--glow-primary);
  top: -60px;
  right: -60px;
}
.glow-2 {
  width: 320px;
  height: 320px;
  background: var(--glow-gold);
  bottom: 80px;
  left: -100px;
  opacity: 0.18;
}

.hero-text {
  max-width: 1200px;
  margin: 0 auto 40px;
}
.eyebrow {
  display: inline-block;
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--color-primary-fade);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-light);
  letter-spacing: 0.5px;
}
.title {
  font-family: var(--font-serif);
  font-size: 42px;
  line-height: 1.3;
  margin: 18px 0 12px;
  font-weight: 800;
  letter-spacing: 1px;
}
.subtitle {
  font-size: 15px;
  line-height: 1.9;
  color: var(--color-ink-sub);
  max-width: 560px;
}
.ability-row {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}
.ability {
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  font-size: 13px;
  box-shadow: var(--shadow-card);
}

/* ---------- 工作台 ---------- */
.bench-area {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 72px 290px;
  gap: 20px;
  align-items: start;
}

.craft-panel {
  position: relative;
  border: 3px solid var(--color-primary-deep);
  border-radius: 14px;
  padding: 18px;
  /* 工作台面板：极淡的网格底纹（拼装感，不抢戏） */
  background:
    repeating-linear-gradient(
      0deg,
      var(--grid-line) 0 1px,
      transparent 1px 24px
    ),
    repeating-linear-gradient(
      90deg,
      var(--grid-line) 0 1px,
      transparent 1px 24px
    ),
    var(--color-card);
  box-shadow:
    var(--shadow-card),
    inset 0 0 0 5px var(--panel-inset);
  transition: box-shadow 0.3s;
}
.craft-panel.ready {
  box-shadow:
    0 0 26px 2px var(--glow-gold-soft),
    var(--shadow-card),
    inset 0 0 0 5px var(--panel-inset);
}

.craft-row {
  display: grid;
  grid-template-columns: 46px repeat(3, 1fr);
  gap: 12px;
  align-items: stretch;
}
.craft-row + .craft-row {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--divider-primary);
}

.row-tag {
  writing-mode: vertical-rl;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  letter-spacing: 3px;
  color: var(--color-primary);
  background: var(--color-primary-fade);
  border: 1px solid var(--color-primary-light);
  border-radius: 8px;
  user-select: none;
}

/* 选择类槽位（真实 button：Tab 可达 + Enter/Space 开弹层） */
.pick-box {
  width: 100%;
  border: 1.5px dashed var(--slot-border);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  font-family: var(--font-sans);
  text-align: left;
  color: var(--color-ink);
  background: var(--input-bg);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: border-color 0.15s;
}
.pick-box:hover {
  border-color: var(--color-primary);
}
.pick-box.empty {
  color: var(--slot-empty);
}

/* 键盘焦点环：九宫格里 Tab / 方向键走到哪一眼看得见 */
.pick-box:focus-visible,
.chip:focus-visible,
.scene-opt:focus-visible,
.mini-seg button:focus-visible,
.extra-arrow:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.slot-note {
  font-size: 11px;
  color: var(--color-ink-sub);
  text-align: right;
  margin-top: 2px;
}

/* 场景选择弹层 */
.scene-picker {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 4px;
}
.scene-opt {
  display: flex;
  gap: 8px;
  align-items: center;
  text-align: left;
  padding: 9px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-card);
  cursor: pointer;
  transition: all 0.15s;
}
.scene-opt:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-fade);
  transform: translateY(-1px);
}
.opt-icon {
  font-size: 20px;
  color: var(--color-primary);
}
.opt-text {
  display: flex;
  flex-direction: column;
}
.opt-text b {
  font-size: 13px;
  color: var(--color-ink);
}
.opt-text i {
  font-style: normal;
  font-size: 11px;
  color: var(--color-ink-sub);
}

/* 预设块选择弹层 */
.chip-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px;
}
.chip {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1.5px solid var(--color-border);
  background: var(--color-card);
  font-size: 12.5px;
  color: var(--color-ink);
  cursor: pointer;
  transition: all 0.15s;
}
.chip:hover {
  border-color: var(--color-primary);
}
.chip.on {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-weight: 600;
}
.custom-row {
  display: flex;
  gap: 6px;
  width: 100%;
  margin-top: 4px;
}

/* 迷你分段按钮（画幅/分辨率） */
.mini-seg {
  display: flex;
  gap: 6px;
}
.mini-seg button {
  flex: 1;
  padding: 8px 4px;
  font-size: 12.5px;
  border: 1.5px solid var(--slot-border);
  background: var(--color-card);
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-ink-sub);
  transition: all 0.15s;
  font-family: var(--font-sans);
}
.mini-seg button.on {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-weight: 600;
}

/* 可选补充槽（补充说明 / 模型选择 / 参考图片 循环切换） */
.extra-row {
  grid-row: 2;
  grid-column: 1;
  margin-top: 14px;
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.extra-row :deep(.craft-slot) {
  flex: 1;
  min-height: 64px;
}

.extra-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 4px 2px;
}
.extra-arrow {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1.5px solid var(--color-border);
  background: var(--color-card);
  color: var(--color-primary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font-sans);
}
.extra-arrow:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-fade);
}
.extra-dots {
  display: flex;
  gap: 4px;
}
.extra-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border);
  transition: background 0.15s;
}
.extra-dots span.on {
  background: var(--color-primary);
}

/* 配方完成度 */
.recipe-bar {
  grid-row: 3;
  grid-column: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  padding: 0 6px;
}
.recipe-label {
  font-size: 12px;
  color: var(--color-ink-sub);
  white-space: nowrap;
}
.bar-track {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: var(--color-border);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--gradient-bar);
  transition: width 0.3s ease;
}
.recipe-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
}
.recipe-ready {
  font-size: 12px;
  color: var(--color-gold-text);
  font-weight: 600;
}

/* ---------- 合成箭头 ---------- */
.craft-arrow {
  display: flex;
  align-items: center;
  gap: 8px;
  align-self: center;
}
.arrow-line {
  flex: 1;
  border-top: 2px dashed var(--color-gold);
  opacity: 0.7;
}
.arrow-head {
  color: var(--color-gold);
  font-size: 22px;
  animation: arrow-nudge 1.6s ease-in-out infinite;
}

/* ---------- 成品槽 ---------- */
.result-slot {
  position: sticky;
  top: 112px; /* 与导航高度（~108px）对齐，滚动时不被盖住 */
  align-self: center;
  background: var(--color-card);
  border: 2px dashed var(--color-border);
  border-radius: 14px;
  padding: 20px 18px;
  box-shadow: var(--shadow-card);
  transition:
    border-color 0.3s,
    box-shadow 0.3s;
}
.result-slot.ready {
  border: 2px solid var(--color-gold);
  animation: breathe 2.4s ease-in-out infinite;
}
.result-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--color-border);
}
.result-icon {
  font-size: 18px;
}

.result-preview {
  min-height: 150px;
  padding: 14px 0;
}
.result-preview.waiting {
  display: flex;
  align-items: center;
  justify-content: center;
}
.r-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--color-primary-deep);
  margin: 0 0 10px;
}
.r-line {
  font-size: 12.5px;
  color: var(--color-ink-sub);
  margin: 5px 0;
  line-height: 1.5;
}

.waiting-hint {
  text-align: center;
  color: var(--slot-empty);
}
.waiting-icon {
  font-size: 26px;
  display: block;
  margin-bottom: 8px;
}
.waiting-hint p {
  font-size: 12.5px;
  line-height: 1.8;
  margin: 0;
}

.craft-btn {
  font-size: 16px;
  letter-spacing: 3px;
  background: var(--color-card) !important;
  color: var(--color-primary) !important;
  border: 1px solid var(--color-gold) !important;
  transition: all 0.25s ease;
}
.craft-btn:hover {
  background: var(--color-gold) !important;
  color: var(--color-on-gold) !important;
  border-color: var(--color-gold) !important;
  box-shadow: var(--shadow-gold); /* 金辉，呼应卡片 ready 金边 */
}

.result-alert {
  margin-top: 12px;
}

/* ---------- 页脚 ---------- */
.footer {
  max-width: 1200px;
  margin: 0 auto;
  padding: 22px 24px 30px;
  border-top: 1px solid var(--color-border);
  font-size: 12.5px;
  color: var(--color-ink-sub);
  line-height: 1.8;
  text-align: center;
}

/* ---------- 响应式 ---------- */
@media (max-width: 980px) {
  .bench-area {
    grid-template-columns: 1fr;
  }
  .craft-arrow {
    padding-top: 0;
    transform: rotate(90deg);
    width: 60px;
    margin: 6px auto;
  }
  .result-slot {
    position: static;
  }
  .title {
    font-size: 32px;
  }
}
@media (max-width: 720px) {
  .craft-row {
    grid-template-columns: 1fr;
  }
  .row-tag {
    writing-mode: horizontal-tb;
    letter-spacing: 2px;
    padding: 4px 0;
    font-size: 12px;
  }
}
</style>
