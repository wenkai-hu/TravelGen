<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  PhSparkle, PhFolderOpen, PhSquaresFour,
  PhSidebarSimple, PhUser, PhSignOut, PhSignIn,
} from '@phosphor-icons/vue'
import ThemeToggle from './ThemeToggle.vue'
import logoUrl from '../images/logo.png'
import { getUsername, isLoggedIn, logout } from '../auth'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const collapsed = ref(false)
const loggedIn = ref(isLoggedIn())
const username = ref(getUsername() || '')
const isLogin = computed(() => route.name === 'login')
const activePage = computed(() => {
  if (route.name === 'projects' || route.name === 'library') return route.name
  return 'home'
})
const links = [
  { id: 'home', to: '/', label: '工作台', icon: PhSparkle },
  { id: 'projects', to: '/projects', label: '项目', icon: PhFolderOpen },
  { id: 'library', to: '/library', label: '素材', icon: PhSquaresFour },
]

watch(() => route.fullPath, () => {
  loggedIn.value = isLoggedIn()
  username.value = getUsername() || ''
})

function onLogout() {
  logout()
  loggedIn.value = false
  username.value = ''
  message.success('已退出登录')
  router.push('/login')
}
</script>

<template>
  <div class="app-shell" :class="{ 'is-collapsed': collapsed, 'is-login': isLogin }">
    <aside v-if="!isLogin" class="app-sidebar" aria-label="侧边栏">
      <div class="sidebar-heading">
        <router-link to="/" class="sidebar-brand" aria-label="TravelGen 工作台" title="TravelGen 工作台">
          <img :src="logoUrl" alt="" />
          <span class="sidebar-label gradient-text">TravelGen</span>
        </router-link>
        <button class="sidebar-collapse" type="button" :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
          :title="collapsed ? '展开侧边栏' : '收起侧边栏'" :aria-expanded="!collapsed" aria-controls="sidebar-nav" @click="collapsed = !collapsed">
          <PhSidebarSimple :size="18" />
        </button>
      </div>

      <nav id="sidebar-nav" class="sidebar-nav" aria-label="主导航">
        <router-link v-for="link in links" :key="link.id" :to="link.to" class="sidebar-link"
          :class="{ 'is-active': activePage === link.id }" :aria-current="activePage === link.id ? 'page' : undefined"
          :aria-label="link.label" :title="link.label">
          <component :is="link.icon" :size="21" :weight="activePage === link.id ? 'fill' : 'regular'" />
          <span class="sidebar-label">{{ link.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-bottom">
        <div class="sidebar-preferences">
          <span class="sidebar-label">外观模式</span>
          <ThemeToggle />
        </div>
        <div v-if="loggedIn" class="sidebar-account">
          <div class="sidebar-profile" :title="username">
            <span class="sidebar-avatar"><PhUser :size="18" /></span>
            <span class="sidebar-label sidebar-username">{{ username }}</span>
          </div>
          <button type="button" class="sidebar-logout" aria-label="退出登录" title="退出登录" @click="onLogout">
            <PhSignOut :size="19" />
          </button>
        </div>
        <router-link v-else to="/login" class="sidebar-link sidebar-login" title="登录 / 注册" aria-label="登录 / 注册">
          <PhSignIn :size="21" /><span class="sidebar-label">登录 / 注册</span>
        </router-link>
      </div>
    </aside>
    <div class="app-content"><slot /></div>
  </div>
</template>

<style scoped>
.app-shell {
  --sidebar-width: 232px;
  --sidebar-motion: 280ms cubic-bezier(.22, 1, .36, 1);
  min-height: 100vh;
  color: var(--color-ink);
  background: var(--color-bg);
  font-family: var(--font-sans);
}
.app-shell.is-collapsed { --sidebar-width: 76px; }
.app-content {
  min-width: 0;
  margin-left: var(--sidebar-width);
  transition: margin-left var(--sidebar-motion);
}
.app-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  width: var(--sidebar-width);
  height: 100dvh;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 24px 14px 18px;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--surface-nav);
  border-right: 1px solid var(--color-border);
  transition: width var(--sidebar-motion);
}
.sidebar-heading { position: relative; flex-shrink: 0; height: 72px; margin-bottom: 10px; }
.sidebar-brand { display: flex; align-items: center; gap: 8px; min-width: 0; width: fit-content; padding-left: 4px; text-decoration: none; transition: gap var(--sidebar-motion); }
.sidebar-label {
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  opacity: 1;
  transition: max-width var(--sidebar-motion), opacity 160ms ease, transform var(--sidebar-motion), visibility 160ms;
}
.sidebar-brand img { width: 40px; height: 40px; object-fit: contain; flex-shrink: 0; }
.sidebar-brand span { font-family: var(--font-serif); font-size: 21px; font-weight: 700; }
.sidebar-collapse, .sidebar-logout {
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0; width: 30px; height: 32px; padding: 0;
  border: 0; border-radius: 8px; background: transparent; color: var(--color-ink-muted); cursor: pointer;
}
.sidebar-collapse { position: absolute; top: 4px; right: 0; transition: top var(--sidebar-motion), right var(--sidebar-motion); }
.sidebar-nav { display: flex; flex-direction: column; gap: 8px; }
.sidebar-link {
  display: flex; align-items: center; gap: 12px; min-height: 46px; padding: 0 14px;
  border-radius: 10px; color: var(--color-ink-sub); text-decoration: none; font-size: 14px;
  transition: background .15s, color .15s, padding var(--sidebar-motion), gap var(--sidebar-motion);
}
.sidebar-link svg { flex-shrink: 0; }
.sidebar-link:hover, .sidebar-collapse:hover, .sidebar-logout:hover { background: var(--color-primary-fade); color: var(--color-primary); }
.sidebar-link.is-active { color: var(--color-primary-deep); background: var(--color-primary-light); font-weight: 650; }
.sidebar-link:focus-visible, .sidebar-collapse:focus-visible, .sidebar-logout:focus-visible, .sidebar-brand:focus-visible {
  outline: 2px solid var(--color-primary); outline-offset: 3px;
}
.sidebar-bottom { margin-top: auto; padding-top: 40px; }
.sidebar-preferences { display: flex; align-items: center; justify-content: flex-end; padding: 10px 8px; color: var(--color-ink-sub); font-size: 12px; }
.sidebar-preferences > .sidebar-label { margin-right: auto; }
.sidebar-account { position: relative; height: 88px; box-sizing: border-box; padding: 16px 8px 0; border-top: 1px solid var(--color-border); }
.sidebar-profile { display: flex; min-width: 0; align-items: center; gap: 10px; padding-right: 30px; transition: gap var(--sidebar-motion), padding var(--sidebar-motion); }
.sidebar-logout { position: absolute; right: 8px; top: 16px; transition: top var(--sidebar-motion); }
.sidebar-avatar { display: flex; align-items: center; justify-content: center; flex-shrink: 0; width: 32px; height: 32px; border-radius: 50%; background: var(--color-primary-light); color: var(--color-primary); }
.sidebar-username { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.sidebar-login { border-top: 1px solid var(--color-border); border-radius: 0; }
.is-collapsed .sidebar-label { max-width: 0; opacity: 0; transform: translateX(-6px); visibility: hidden; }
.is-collapsed .sidebar-brand { gap: 0; }
.is-collapsed .sidebar-collapse { top: 46px; right: 9px; }
.is-collapsed .sidebar-link { padding-inline: 13px; gap: 0; }
.is-collapsed .sidebar-profile { gap: 0; padding-right: 0; }
.is-collapsed .sidebar-logout { top: 56px; }
@media (max-width: 900px) {
  .app-shell { --sidebar-width: 68px; }
  .app-shell.is-collapsed { --sidebar-width: 68px; }
  .app-sidebar { padding: 18px 10px 14px; }
  .sidebar-label, .sidebar-collapse { display: none; }
  .sidebar-heading, .is-collapsed .sidebar-heading { height: 40px; margin-bottom: 32px; }
  .sidebar-brand { gap: 0; }
  .sidebar-link, .is-collapsed .sidebar-link { padding: 0; gap: 0; justify-content: center; }
  .sidebar-preferences { padding: 10px 0; justify-content: center; }
  .sidebar-profile { gap: 0; padding-right: 0; }
  .sidebar-logout { top: 56px; }
}
.app-shell.is-login { --sidebar-width: 0px; }
.is-login .app-content { transition: none; }
</style>
