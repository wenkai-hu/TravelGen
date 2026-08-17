<script setup>
import { NConfigProvider, NMessageProvider, NDialogProvider, zhCN, dateZhCN } from 'naive-ui'
import HomeView from './views/HomeView.vue'

// Naive UI 主题定制：把组件库主色对齐「宋韵青绿」设计 token
const themeOverrides = {
  common: {
    primaryColor: '#0F766E',
    primaryColorHover: '#138A80',
    primaryColorPressed: '#115E59',
    primaryColorSuppl: '#138A80',
    borderRadius: '8px',
    fontFamily:
      "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
  },
}
</script>

<template>
  <NConfigProvider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <HomeView />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
