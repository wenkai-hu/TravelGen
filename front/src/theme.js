// 主题：light / dark 存 localStorage，切换时写 <html data-theme>，CSS 变量跟着换值
// 默认浅色、不跟随系统。首屏防闪逻辑在 index.html 的内联脚本里，判定规则与这里保持一致。
import { ref } from 'vue'

const THEME_KEY = 'travelgen_theme'
const DARK = 'dark'

function readStored() {
  // 模块加载即读，storage 被禁（隐私模式等）时不能让整个应用起不来
  try {
    return localStorage.getItem(THEME_KEY) === DARK ? DARK : 'light'
  } catch {
    return 'light'
  }
}

export const theme = ref(readStored())

export function getTheme() {
  return theme.value
}

export function applyTheme(t) {
  theme.value = t === DARK ? DARK : 'light'
  document.documentElement.dataset.theme = theme.value
  // 移动端地址栏/状态栏配色跟着走（index.html 里那个 meta）
  const meta = document.getElementById('theme-color')
  if (meta) meta.setAttribute('content', theme.value === DARK ? '#17150f' : '#f7f5f0')
  try {
    localStorage.setItem(THEME_KEY, theme.value)
  } catch {
    // 存不下就只影响"下次打开还记不记得"，本次会话照常
  }
}

export function toggleTheme() {
  applyTheme(theme.value === DARK ? 'light' : DARK)
}
