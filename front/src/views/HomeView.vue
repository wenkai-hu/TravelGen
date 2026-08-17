<script setup>
import { computed, reactive, ref } from 'vue'
import { NAlert, NButton, NInput, NPopover, NSlider, useMessage } from 'naive-ui'
import CraftSlot from '../components/CraftSlot.vue'
import { createProject } from '../api'
import {
  ASPECT_RATIOS,
  DEFAULT_AUDIENCE,
  DEFAULT_STYLE,
  DURATION_RANGE,
  RESOLUTIONS,
  SCENE_TYPES,
} from '../constants'

const message = useMessage()

// ── 配方（表单）—— 与后端 schemas.py GenerateRequest 一一对应 ──
const form = reactive({
  city: '',
  location: '',
  theme: '',
  scene_type: '', // 留空：邀请用户亲手"放入"场景块
  audience: DEFAULT_AUDIENCE,
  style: DEFAULT_STYLE,
  duration_s: DURATION_RANGE.default,
  aspect_ratio: '9:16',
  resolution: '1080p',
  description: '',
})

// 人群 / 风格：预设块 + 可自定义
const AUDIENCE_PRESETS = ['18-35岁年轻游客', '亲子家庭', '银发康养游客', '商务差旅', '学生党']
const STYLE_PRESETS = ['大气唯美', '国风古韵', '青春活力', '文艺清新', '水墨诗意', '赛博未来']

const scenePop = ref(false)
const audiencePop = ref(false)
const stylePop = ref(false)
const customAudience = ref('')
const customStyle = ref('')

const submitting = ref(false)
const created = ref(null)
const submitError = ref('')

// ── 配方完成度：9 个槽位已填数量（时长/画幅/分辨率有默认值，恒为已填） ──
const slotsFilled = computed(() => {
  let n = 0
  if (form.city.trim()) n++
  if (form.location.trim()) n++
  if (form.theme.trim()) n++
  if (form.scene_type) n++
  if (form.audience.trim()) n++
  if (form.style.trim()) n++
  return n + 3
})
const completion = computed(() => Math.round((slotsFilled.value / 9) * 100))

// 必需材料：城市 / 地点 / 主题 / 场景类型
const requiredOk = computed(
  () => form.city.trim() && form.location.trim() && form.theme.trim() && form.scene_type,
)
const sceneLabel = computed(() => SCENE_TYPES.find((s) => s.value === form.scene_type))

const durationMarks = { 15: '15s', 60: '60s', 120: '120s' }

function applyCustom(key) {
  const v = key === 'audience' ? customAudience.value.trim() : customStyle.value.trim()
  if (v) form[key] = v
  if (key === 'audience') audiencePop.value = false
  else stylePop.value = false
}

async function onSubmit() {
  if (!requiredOk.value) {
    message.warning('工作台上还缺材料：城市 / 地点 / 主题 / 场景类型')
    return
  }
  submitting.value = true
  submitError.value = ''
  created.value = null
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
      assets: [],
    }
    const data = await createProject(payload)
    created.value = data
    sessionStorage.setItem('travelgen_project_id', data.project_id)
    message.success('锻造开始！AI 正在生成创作方案…')
  } catch (e) {
    submitError.value =
      e.code === 'invalid_param'
        ? e.message
        : `后端未连接：${e.message}（请先运行 python backend/app.py，无 key 也能走 demo 模式）`
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <!-- 顶部导航 -->
    <header class="nav fade-up">
      <div class="nav-inner">
        <div class="logo">
          <span class="logo-mark">浙</span>
          <span class="logo-text gradient-text">里 · AI 造片</span>
        </div>
        <nav class="nav-links">
          <a href="#bench">工作台</a>
          <a href="#compliance">版权合规</a>
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
        <p class="subtitle fade-up-2">
          像拼装配方一样创作：放入内容素材、选定创作方向、核对输出规格 ——
          一键锻造一部属于浙江的文旅宣传片。
        </p>
        <div class="ability-row fade-up-3">
          <span class="ability">✍️ 文案</span>
          <span class="ability">🎬 分镜</span>
          <span class="ability">🎙️ 配音</span>
          <span class="ability">🎵 音乐</span>
          <span class="ability">📹 视频</span>
        </div>
      </section>

      <!-- 工作台 -->
      <div id="bench" class="bench-area fade-up-2">
        <div class="bench-left">
          <div class="craft-panel" :class="{ ready: requiredOk }">
            <!-- ① 内容素材 -->
            <div class="craft-row">
              <div class="row-tag">① 内容素材</div>
              <CraftSlot label="城市" icon="🏙️" :filled="!!form.city.trim()" required>
                <NInput v-model:value="form.city" placeholder="如：杭州" />
              </CraftSlot>
              <CraftSlot label="景点地点" icon="📍" :filled="!!form.location.trim()" required>
                <NInput v-model:value="form.location" placeholder="如：西湖" />
              </CraftSlot>
              <CraftSlot label="传播主题" icon="💡" :filled="!!form.theme.trim()" required>
                <NInput v-model:value="form.theme" placeholder="如：西湖十景新玩法" />
              </CraftSlot>
            </div>

            <!-- ② 创作方向 -->
            <div class="craft-row">
              <div class="row-tag">② 创作方向</div>
              <CraftSlot label="场景类型" icon="🧩" :filled="!!form.scene_type" required>
                <NPopover
                  v-model:show="scenePop"
                  trigger="click"
                  placement="bottom"
                  :width="320"
                  style="width: 100%"
                >
                  <template #trigger>
                    <div class="pick-box" :class="{ empty: !form.scene_type }">
                      <template v-if="sceneLabel">{{ sceneLabel.emoji }} {{ sceneLabel.value }}</template>
                      <template v-else>点击放入「场景块」</template>
                    </div>
                  </template>
                  <div class="scene-picker">
                    <button
                      v-for="s in SCENE_TYPES"
                      :key="s.value"
                      type="button"
                      class="scene-opt"
                      @click="form.scene_type = s.value; scenePop = false"
                    >
                      <span class="opt-emoji">{{ s.emoji }}</span>
                      <span class="opt-text"><b>{{ s.value }}</b><i>{{ s.desc }}</i></span>
                    </button>
                  </div>
                </NPopover>
              </CraftSlot>

              <CraftSlot label="目标人群" icon="👥" :filled="!!form.audience.trim()">
                <NPopover
                  v-model:show="audiencePop"
                  trigger="click"
                  placement="bottom"
                  :width="280"
                  style="width: 100%"
                >
                  <template #trigger>
                    <div class="pick-box">{{ form.audience }}</div>
                  </template>
                  <div class="chip-picker">
                    <button
                      v-for="p in AUDIENCE_PRESETS"
                      :key="p"
                      type="button"
                      class="chip"
                      :class="{ on: form.audience === p }"
                      @click="form.audience = p; audiencePop = false"
                    >
                      {{ p }}
                    </button>
                    <div class="custom-row">
                      <NInput v-model:value="customAudience" size="small" placeholder="自定义人群…" @keyup.enter="applyCustom('audience')" />
                      <NButton size="small" @click="applyCustom('audience')">放入</NButton>
                    </div>
                  </div>
                </NPopover>
              </CraftSlot>

              <CraftSlot label="视频风格" icon="🎨" :filled="!!form.style.trim()">
                <NPopover
                  v-model:show="stylePop"
                  trigger="click"
                  placement="bottom"
                  :width="280"
                  style="width: 100%"
                >
                  <template #trigger>
                    <div class="pick-box">{{ form.style }}</div>
                  </template>
                  <div class="chip-picker">
                    <button
                      v-for="p in STYLE_PRESETS"
                      :key="p"
                      type="button"
                      class="chip"
                      :class="{ on: form.style === p }"
                      @click="form.style = p; stylePop = false"
                    >
                      {{ p }}
                    </button>
                    <div class="custom-row">
                      <NInput v-model:value="customStyle" size="small" placeholder="自定义风格…" @keyup.enter="applyCustom('style')" />
                      <NButton size="small" @click="applyCustom('style')">放入</NButton>
                    </div>
                  </div>
                </NPopover>
              </CraftSlot>
            </div>

            <!-- ③ 输出规格 -->
            <div class="craft-row">
              <div class="row-tag">③ 输出规格</div>
              <CraftSlot label="视频时长" icon="⏱️" :filled="true">
                <NSlider
                  v-model:value="form.duration_s"
                  :min="DURATION_RANGE.min"
                  :max="DURATION_RANGE.max"
                  :marks="durationMarks"
                />
                <div class="slot-note">{{ form.duration_s }} 秒</div>
              </CraftSlot>
              <CraftSlot label="画幅" icon="🖼️" :filled="true">
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
              <CraftSlot label="分辨率" icon="📺" :filled="true">
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

          <!-- 可选补充槽 -->
          <div class="extra-row">
            <CraftSlot label="补充说明（可选）" icon="📝" :filled="!!form.description.trim()">
              <NInput
                v-model:value="form.description"
                type="textarea"
                :autosize="{ minRows: 1, maxRows: 3 }"
                placeholder="想要突出的元素、风格要求等（会注入 AI 的创作提示词）"
              />
            </CraftSlot>
          </div>

          <!-- 配方完成度 -->
          <div class="recipe-bar">
            <span class="recipe-label">配方完成度</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: completion + '%' }"></div>
            </div>
            <span class="recipe-count">{{ slotsFilled }}/9</span>
            <span v-if="requiredOk" class="recipe-ready">✦ 配方就绪</span>
          </div>
        </div>

        <!-- 合成箭头 -->
        <div class="craft-arrow" aria-hidden="true">
          <span class="arrow-line"></span>
          <span class="arrow-head">▶</span>
        </div>

        <!-- 成品槽 -->
        <aside class="result-slot" :class="{ ready: requiredOk }">
          <div class="result-head"><span class="result-icon">🎬</span> 成品</div>
          <div class="result-preview" :class="{ waiting: !requiredOk }">
            <template v-if="requiredOk">
              <p class="r-title">{{ form.theme }}</p>
              <p class="r-line">📍 {{ form.city }} · {{ form.location }}</p>
              <p class="r-line">🧩 {{ form.scene_type }}</p>
              <p class="r-line">🎨 {{ form.style }}｜{{ form.audience }}</p>
              <p class="r-line">⏱ {{ form.duration_s }}s｜{{ form.aspect_ratio }}｜{{ form.resolution }}</p>
            </template>
            <template v-else>
              <div class="waiting-hint">
                <span class="waiting-icon">🕳️</span>
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
            {{ submitting ? '锻造中…' : '⚒ 开始锻造' }}
          </NButton>
          <NAlert v-if="created" type="success" class="result-alert" :bordered="false">
            项目已创建：<b>{{ created.project_id }}</b>（{{ created.status }}）。方案生成中，
            下一步进入「方案确认页」（待开发）。
          </NAlert>
          <NAlert v-if="submitError" type="error" class="result-alert" :bordered="false">
            {{ submitError }}
          </NAlert>
        </aside>
      </div>
    </main>

    <!-- 页脚 -->
    <footer id="compliance" class="footer">
      <p>
        🛡️ 内容安全：生成内容经内容/版权/许可三重检查占位 ·
        🖼️ 素材授权：知识库锚点图来自 Unsplash License，来源可追溯 ·
        ⚙️ 技术栈：Vue 3 · Naive UI · FastAPI · 多模态大模型编排
      </p>
    </footer>
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
  background: rgba(247, 245, 240, 0.86);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--color-border);
}
.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo { display: flex; align-items: center; gap: 10px; }
.logo-mark {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #0f766e, #115e59);
  color: var(--color-gold-light);
  font-family: var(--font-serif);
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-text { font-family: var(--font-serif); font-size: 19px; font-weight: 700; letter-spacing: 1px; }
.nav-links { display: flex; gap: 26px; }
.nav-links a { color: var(--color-ink-sub); text-decoration: none; font-size: 14px; transition: color 0.15s; }
.nav-links a:hover { color: var(--color-primary); }

/* ---------- 主区 ---------- */
.workshop { position: relative; padding: 48px 24px 40px; }
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.3;
  pointer-events: none;
}
.glow-1 { width: 420px; height: 420px; background: #17a398; top: -60px; right: -60px; }
.glow-2 { width: 320px; height: 320px; background: #c9a227; bottom: 80px; left: -100px; opacity: 0.18; }

.hero-text { max-width: 1200px; margin: 0 auto 40px; }
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
.subtitle { font-size: 15px; line-height: 1.9; color: var(--color-ink-sub); max-width: 560px; }
.ability-row { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
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
    repeating-linear-gradient(0deg, var(--grid-line) 0 1px, transparent 1px 24px),
    repeating-linear-gradient(90deg, var(--grid-line) 0 1px, transparent 1px 24px),
    var(--color-card);
  box-shadow:
    var(--shadow-card),
    inset 0 0 0 5px #fbfaf6;
  transition: box-shadow 0.3s;
}
.craft-panel.ready {
  box-shadow:
    0 0 26px 2px rgba(201, 162, 39, 0.28),
    var(--shadow-card),
    inset 0 0 0 5px #fbfaf6;
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
  border-top: 1px dashed rgba(17, 94, 89, 0.18);
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

/* 选择类槽位 */
.pick-box {
  border: 1.5px dashed var(--slot-border);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--color-ink);
  background: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: border-color 0.15s;
}
.pick-box:hover { border-color: var(--color-primary); }
.pick-box.empty { color: var(--slot-empty); }

.slot-note { font-size: 11px; color: var(--color-ink-sub); text-align: right; margin-top: 2px; }

/* 场景选择弹层 */
.scene-picker { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 4px; }
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
.scene-opt:hover { border-color: var(--color-primary); background: var(--color-primary-fade); transform: translateY(-1px); }
.opt-emoji { font-size: 20px; }
.opt-text { display: flex; flex-direction: column; }
.opt-text b { font-size: 13px; color: var(--color-ink); }
.opt-text i { font-style: normal; font-size: 11px; color: var(--color-ink-sub); }

/* 预设块选择弹层 */
.chip-picker { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px; }
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
.chip:hover { border-color: var(--color-primary); }
.chip.on {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
  font-weight: 600;
}
.custom-row { display: flex; gap: 6px; width: 100%; margin-top: 4px; }

/* 迷你分段按钮（画幅/分辨率） */
.mini-seg { display: flex; gap: 6px; }
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
  color: #fff;
  font-weight: 600;
}

/* 可选补充槽 */
.extra-row { margin-top: 14px; }
.extra-row :deep(.craft-slot) { min-height: 64px; }

/* 配方完成度 */
.recipe-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  padding: 0 6px;
}
.recipe-label { font-size: 12px; color: var(--color-ink-sub); white-space: nowrap; }
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
  background: linear-gradient(90deg, #0f766e, #17a398);
  transition: width 0.3s ease;
}
.recipe-count { font-size: 12px; font-weight: 700; color: var(--color-primary); }
.recipe-ready { font-size: 12px; color: var(--color-gold); font-weight: 600; }

/* ---------- 合成箭头 ---------- */
.craft-arrow { display: flex; align-items: center; gap: 8px; padding-top: 40px; }
.arrow-line { flex: 1; border-top: 2px dashed var(--color-gold); opacity: 0.7; }
.arrow-head { color: var(--color-gold); font-size: 22px; animation: arrow-nudge 1.6s ease-in-out infinite; }

/* ---------- 成品槽 ---------- */
.result-slot {
  position: sticky;
  top: 84px;
  background: var(--color-card);
  border: 2px dashed var(--color-border);
  border-radius: 14px;
  padding: 20px 18px;
  box-shadow: var(--shadow-card);
  transition: border-color 0.3s, box-shadow 0.3s;
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
.result-icon { font-size: 18px; }

.result-preview { min-height: 150px; padding: 14px 0; }
.result-preview.waiting { display: flex; align-items: center; justify-content: center; }
.r-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--color-primary-deep);
  margin: 0 0 10px;
}
.r-line { font-size: 12.5px; color: var(--color-ink-sub); margin: 5px 0; line-height: 1.5; }

.waiting-hint { text-align: center; color: var(--slot-empty); }
.waiting-icon { font-size: 26px; display: block; margin-bottom: 8px; }
.waiting-hint p { font-size: 12.5px; line-height: 1.8; margin: 0; }

.craft-btn {
  font-size: 16px;
  letter-spacing: 3px;
  background: linear-gradient(120deg, #0f766e, #115e59) !important;
}
.craft-btn:hover { box-shadow: 0 6px 18px rgba(15, 118, 110, 0.35); }

.result-alert { margin-top: 12px; }

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
  .bench-area { grid-template-columns: 1fr; }
  .craft-arrow {
    padding-top: 0;
    transform: rotate(90deg);
    width: 60px;
    margin: 6px auto;
  }
  .result-slot { position: static; }
  .title { font-size: 32px; }
}
@media (max-width: 720px) {
  .craft-row { grid-template-columns: 1fr; }
  .row-tag {
    writing-mode: horizontal-tb;
    letter-spacing: 2px;
    padding: 4px 0;
    font-size: 12px;
  }
}
</style>
