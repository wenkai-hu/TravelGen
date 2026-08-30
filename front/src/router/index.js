// 路由表：/ 工作台（输入页）→ /plan/:pid 方案确认页 → /plan/:pid/storyboard 分镜编辑页 → 后续成片页
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import PlanConfirmView from '../views/PlanConfirmView.vue'
import StoryboardView from '../views/StoryboardView.vue'
import HistoryView from '../views/HistoryView.vue'
import LoginView from '../views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/history', name: 'history', component: HistoryView },
    { path: '/plan/:pid', name: 'plan-confirm', component: PlanConfirmView },
    { path: '/plan/:pid/storyboard', name: 'storyboard', component: StoryboardView },
    // 兜底：未匹配路径回工作台
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
