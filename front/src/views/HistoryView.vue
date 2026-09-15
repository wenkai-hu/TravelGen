<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton } from "naive-ui";
import logoUrl from "../images/logo.png";
import { listProjects } from "../api";
import { isLoggedIn, logout as clearSession } from "../auth";

const router = useRouter();
const projects = ref([]);
const loading = ref(true);
const error = ref("");

// 状态 → 徽标文案/配色（与后端 project.status 状态机对齐）
const STATUS = {
  created: { label: "已创建", cls: "info" },
  searching_references: { label: "实景搜索中", cls: "info" },
  waiting_reference_confirm: { label: "实景待选择", cls: "warn" },
  analyzing_references: { label: "图片理解中", cls: "info" },
  planning: { label: "方案生成中", cls: "info" },
  waiting_confirm: { label: "方案待确认", cls: "warn" },
  plan_confirmed: { label: "方案已确认", cls: "warn" },
  storyboarding: { label: "分镜生成中", cls: "info" },
  waiting_storyboard_confirm: { label: "分镜待确认", cls: "warn" },
  generating: { label: "视频生成中", cls: "info" },
  completed: { label: "已完成", cls: "ok" },
  failed: { label: "失败", cls: "bad" },
};
const statusOf = (s) => STATUS[s] || { label: s, cls: "info" };

function projectRoute(project) {
  if (
    [
      "searching_references",
      "waiting_reference_confirm",
      "analyzing_references",
    ].includes(project.status) ||
    (project.status === "failed" && project.progress < 8)
  ) {
    return `/project/${project.project_id}/references`;
  }
  if (
    ["plan_confirmed", "storyboarding", "waiting_storyboard_confirm", "generating", "completed"].includes(
      project.status,
    )
  ) {
    return `/plan/${project.project_id}/storyboard`;
  }
  return `/plan/${project.project_id}`;
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await listProjects();
    projects.value = data.projects || [];
  } catch (e) {
    if (e.status === 401) {
      // 登录失效：清会话回登录页（token 过期 / 服务重启后内存会话丢失）
      clearSession();
      router.replace("/login");
      return;
    }
    error.value = e.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (!isLoggedIn()) {
    router.replace("/login");
    return;
  }
  load();
});
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
          <router-link to="/">工作台</router-link>
          <router-link to="/history" class="active">我的创作</router-link>
        </nav>
      </div>
    </header>

    <main class="stage">
      <h1 class="page-title">我的创作</h1>
      <p class="page-sub">过往作品留档，点击卡片从上次进度继续</p>

      <!-- 加载中 -->
      <div v-if="loading" class="card center">
        <div class="spin-ring"></div>
        <p class="center-text">正在读取作品…</p>
      </div>

      <!-- 加载失败 -->
      <div v-else-if="error" class="card center">
        <p class="center-text">{{ error }}</p>
        <NButton size="small" style="margin-top: 12px" @click="load">重试</NButton>
      </div>

      <!-- 空态 -->
      <div v-else-if="!projects.length" class="card center">
        <p class="center-text">还没有作品，去工作台开始第一支吧 ✨</p>
        <NButton
          size="small"
          type="primary"
          style="margin-top: 12px"
          @click="router.push('/')"
          >去创作</NButton
        >
      </div>

      <!-- 作品卡片 -->
      <div v-else class="grid">
        <article
          v-for="p in projects"
          :key="p.project_id"
          class="card project-card"
          @click="router.push(projectRoute(p))"
        >
          <div class="cover">
            <img v-if="p.cover_url" :src="p.cover_url" :alt="p.theme" />
            <span v-else class="cover-fallback">🎬</span>
            <span class="badge" :class="statusOf(p.status).cls">
              {{ statusOf(p.status).label }}
            </span>
          </div>
          <div class="body">
            <h3 class="p-title">{{ p.theme }}</h3>
            <p class="p-meta">
              <span v-if="p.scene_type">🧩 {{ p.scene_type }}</span>
              <span v-if="p.duration_s">⏱ {{ p.duration_s }}s</span>
              <span v-if="p.shot_count">🎞 {{ p.shot_count }} 镜头</span>
            </p>
            <p class="p-time">更新于 {{ fmtTime(p.updated_at) }}</p>
          </div>
        </article>
      </div>
    </main>
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
  flex-shrink: 0;
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
.nav-links a.active {
  color: var(--color-primary);
  font-weight: 600;
}

/* ---------- 主区 ---------- */
.stage {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px 60px;
}
.page-title {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 800;
  margin: 0;
  color: var(--color-primary-deep);
}
.page-sub {
  font-size: 13px;
  color: var(--color-ink-sub);
  margin: 8px 0 24px;
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

/* ---------- 作品卡片 ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
}
.project-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition:
    transform 0.15s,
    box-shadow 0.2s;
}
.project-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.18);
}
.cover {
  position: relative;
  aspect-ratio: 16 / 10;
  background: var(--color-primary-fade);
  display: flex;
  align-items: center;
  justify-content: center;
}
.cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cover-fallback {
  font-size: 42px;
  opacity: 0.55;
}
.badge {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #fff;
  backdrop-filter: blur(2px);
}
.badge.info {
  background: rgba(15, 118, 110, 0.85);
}
.badge.warn {
  background: rgba(201, 162, 39, 0.9);
}
.badge.ok {
  background: rgba(21, 128, 61, 0.9);
}
.badge.bad {
  background: rgba(190, 18, 60, 0.88);
}
.body {
  padding: 14px 16px 16px;
}
.p-title {
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 8px;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.p-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--color-ink-sub);
  margin: 0 0 6px;
}
.p-time {
  font-size: 11px;
  color: var(--color-ink-sub);
  opacity: 0.75;
  margin: 0;
}

@media (max-width: 720px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
