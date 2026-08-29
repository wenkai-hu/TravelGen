import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端开发配置：/api 代理到后端 FastAPI（避免跨域，也方便部署时改环境变量）
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1', // 明确绑 IPv4，避免 Vite 默认只监听 IPv6 ::1 导致浏览器连不上
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 视频转存 assets/videos/ 由后端静态挂载（backend/app.py），前端经 /assets 代理直接播放
      '/assets': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
