// 路由表：/ 工作台（输入页）→ /plan/:pid 方案确认页 → 后续分镜/视频页
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import PlanConfirmView from '../views/PlanConfirmView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/plan/:pid', name: 'plan-confirm', component: PlanConfirmView },
    // 兜底：未匹配路径回工作台
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
