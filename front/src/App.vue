<script setup>
import { computed } from 'vue'
import { NConfigProvider, NMessageProvider, NDialogProvider, darkTheme, zhCN, dateZhCN } from 'naive-ui'
import { theme } from './theme'
import AppShell from './components/AppShell.vue'

// Naive UI 主题定制：把组件库配色对齐设计 token（浅：宋韵青绿 / 深：墨韵暖调）。
// 浅色只补状态色——原先没设，NAlert type="info" 会漏出 naive 默认蓝 #2080f0、
// 报错文案漏出玫红 #d03050，是全项目仅有的两个体系外颜色。
// 深色必须把基础表面色一并覆盖：naive 自带的冷灰会跟暖墨底明显撞色。
const lightOverrides = {
  common: {
    primaryColor: '#0F766E',
    primaryColorHover: '#138A80',
    primaryColorPressed: '#115E59',
    primaryColorSuppl: '#138A80',
    infoColor: '#0F766E',
    infoColorHover: '#138A80',
    infoColorPressed: '#115E59',
    successColor: '#2F855A',
    warningColor: '#B7791F',
    errorColor: '#B03A2E',
    borderRadius: '8px',
    fontFamily: 'var(--font-sans)',
  },
}

const darkOverrides = {
  common: {
    primaryColor: '#5ECAB8',
    primaryColorHover: '#7DD8C8',
    primaryColorPressed: '#45B8A5',
    primaryColorSuppl: '#45B8A5',
    infoColor: '#5ECAB8',
    infoColorHover: '#7DD8C8',
    infoColorPressed: '#45B8A5',
    successColor: '#5CC08A',
    warningColor: '#D9A441',
    errorColor: '#E0796A',
    // 表面：与 tokens.css 的深色值一一对应
    bodyColor: '#17150F',
    cardColor: '#211E17',
    modalColor: '#211E17',
    popoverColor: '#262218',
    tableColor: '#211E17',
    inputColor: '#1C1A14',
    actionColor: '#1C1A14',
    borderColor: '#3D382C',
    dividerColor: '#3D382C',
    textColorBase: '#EAE5DA',
    textColor1: '#EAE5DA',
    textColor2: '#D5CFC2',
    textColor3: '#8D8474',
    placeholderColor: '#8D8474',
    hoverColor: 'rgba(255, 255, 255, 0.06)',
    scrollbarColor: 'rgba(255, 255, 255, 0.16)',
    scrollbarColorHover: 'rgba(255, 255, 255, 0.26)',
    borderRadius: '8px',
    fontFamily: 'var(--font-sans)',
  },
}

const isDark = computed(() => theme.value === 'dark')
const naiveTheme = computed(() => (isDark.value ? darkTheme : null))
const themeOverrides = computed(() => (isDark.value ? darkOverrides : lightOverrides))
</script>

<template>
  <NConfigProvider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
  >
    <NMessageProvider>
      <NDialogProvider>
        <AppShell><router-view /></AppShell>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
