// 路由表：工作台 → 实景选图/VLM → 方案确认 → 分镜编辑 → 后续成片页
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ReferenceSelectView from '../views/ReferenceSelectView.vue'
import PlanConfirmView from '../views/PlanConfirmView.vue'
import StoryboardView from '../views/StoryboardView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import LibraryView from '../views/LibraryView.vue'
import LoginView from '../views/LoginView.vue'
import { isLoggedIn } from '../auth'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, top: 24 }
    if (to.path === from.path) return
    return { top: 0 }
  },
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/history', redirect: '/projects' },
    { path: '/projects', name: 'projects', component: ProjectsView },
    { path: '/library', name: 'library', component: LibraryView },
    { path: '/project/:pid/references', name: 'reference-select', component: ReferenceSelectView },
    { path: '/plan/:pid', name: 'plan-confirm', component: PlanConfirmView },
    { path: '/plan/:pid/storyboard', name: 'storyboard', component: StoryboardView },
    // 兜底：未匹配路径回工作台
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to, from) => {
  const privatePage = path => /^\/(projects|library|history|project\/|plan\/)/.test(path)
  if(privatePage(to.path) && !isLoggedIn()) return {path:'/login',query:{redirect:to.fullPath}}
  if(to.path==='/login' && !to.query.redirect && privatePage(from.path)) return {path:'/login',query:{redirect:from.fullPath}}
})

export default router
