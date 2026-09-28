<script setup>
import { computed } from 'vue'
import { PhSun, PhMoonStars } from '@phosphor-icons/vue'
import { theme, toggleTheme } from '../theme'

const isDark = computed(() => theme.value === 'dark')
const label = computed(() => (isDark.value ? '切换到日间模式' : '切换到夜间模式'))
</script>

<template>
  <button
    class="theme-toggle"
    type="button"
    aria-label="夜间模式"
    :aria-pressed="isDark"
    :title="label"
    @click="toggleTheme"
  >
    <!-- 图标显示的是"点下去会切到哪一边" -->
    <PhSun v-if="isDark" :size="18" />
    <PhMoonStars v-else :size="18" />
  </button>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  /* 图标 color 默认 currentColor，跟着这里走 */
  color: var(--color-ink-sub);
  cursor: pointer;
  transition: color 0.15s, background 0.15s, border-color 0.15s;
}
.theme-toggle:hover {
  color: var(--color-primary);
  background: var(--color-primary-fade);
  border-color: var(--color-border);
}
.theme-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
</style>
