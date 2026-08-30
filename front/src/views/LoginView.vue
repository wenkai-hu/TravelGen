<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { NAlert, NButton, NInput, useMessage } from "naive-ui";
import { login, register } from "../api";
import { setSession } from "../auth";
import logoUrl from "../images/logo.png";

const router = useRouter();
const message = useMessage();

const mode = ref("login"); // login | register
const username = ref("");
const password = ref("");
const confirm = ref("");
const loading = ref(false);
const error = ref("");

async function onSubmit() {
  error.value = "";
  const name = username.value.trim();
  if (!name) return message.warning("请输入用户名");
  if (password.value.length < 6) return message.warning("密码至少 6 位");
  if (mode.value === "register" && password.value !== confirm.value)
    return message.warning("两次输入的密码不一致");
  loading.value = true;
  try {
    if (mode.value === "register") {
      await register({ username: name, password: password.value });
      message.success("注册成功，请登录");
      mode.value = "login";
      password.value = confirm.value = "";
    } else {
      const data = await login({ username: name, password: password.value });
      setSession(data.token, data.username);
      message.success(`欢迎回来，${data.username}！`);
      router.push("/");
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <header class="nav">
      <div class="nav-inner">
        <div class="logo" @click="router.push('/')">
          <img :src="logoUrl" class="logo-mark" alt="TravelGen" />
          <span class="logo-text gradient-text">TravelGen</span>
        </div>
        <router-link to="/" class="back-link">
          <i class="iconfont icon-fanhui"></i> 返回工作台
        </router-link>
      </div>
    </header>

    <main class="auth-wrap">
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>

      <div class="auth-card fade-up">
        <div class="card-logo">
          <img :src="logoUrl" class="logo-mark" alt="TravelGen" />
          <span class="logo-text gradient-text">TravelGen</span>
        </div>

        <div class="tab-row">
          <button
            type="button"
            class="tab"
            :class="{ on: mode === 'login' }"
            @click="mode = 'login'"
          >
            登录
          </button>
          <button
            type="button"
            class="tab"
            :class="{ on: mode === 'register' }"
            @click="mode = 'register'"
          >
            注册
          </button>
        </div>

        <div class="field">
          <div class="field-top">
            <label>用户名</label>
            <span class="rule">2-50 位，可用中文</span>
          </div>
          <NInput
            v-model:value="username"
            size="large"
            placeholder="请输入用户名"
            @keyup.enter="onSubmit"
          />
        </div>
        <div class="field">
          <div class="field-top">
            <label>密码</label>
            <span class="rule">至少 6 位</span>
          </div>
          <NInput
            v-model:value="password"
            type="password"
            size="large"
            show-password-on="click"
            placeholder="请输入密码"
            @keyup.enter="onSubmit"
          />
        </div>
        <div v-if="mode === 'register'" class="field">
          <div class="field-top">
            <label>确认密码</label>
          </div>
          <NInput
            v-model:value="confirm"
            type="password"
            size="large"
            show-password-on="click"
            placeholder="请再次输入密码"
            @keyup.enter="onSubmit"
          />
        </div>

        <NAlert v-if="error" type="error" class="auth-alert" :bordered="false">
          {{ error }}
        </NAlert>

        <NButton
          class="auth-btn"
          block
          size="large"
          :loading="loading"
          @click="onSubmit"
        >
          {{ mode === "login" ? "登 录" : "注 册" }}
        </NButton>
      </div>
    </main>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: var(--color-bg);
  font-family: var(--font-sans);
  color: var(--color-ink);
  position: relative;
  overflow: hidden;
}

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
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-ink-sub);
  text-decoration: none;
  font-size: 15px;
  transition: color 0.15s;
}
.back-link .iconfont {
  font-size: 14px;
}
.back-link:hover {
  color: var(--color-primary);
}

.auth-wrap {
  position: relative;
  min-height: calc(100vh - 110px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.3;
  pointer-events: none;
}
.glow-1 {
  width: 420px;
  height: 420px;
  background: #17a398;
  top: -60px;
  right: -60px;
}
.glow-2 {
  width: 320px;
  height: 320px;
  background: #c9a227;
  bottom: 80px;
  left: -100px;
  opacity: 0.18;
}

.auth-card {
  position: relative;
  width: 100%;
  max-width: 420px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 18px;
  padding: 36px 36px 32px;
  box-shadow: var(--shadow-card-hover);
}

/* 卡片顶部 logo（同首页导航视觉，尺寸略收） */
.card-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-bottom: 26px;
}
.card-logo .logo-mark {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  object-fit: cover;
  box-shadow: 0 6px 16px rgba(15, 118, 110, 0.18);
}
.card-logo .logo-text {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 2px;
}

/* 登录 / 注册切换 */
.tab-row {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  background: var(--color-primary-fade);
  border-radius: 10px;
  padding: 4px;
}
.tab {
  flex: 1;
  padding: 9px 0;
  font-size: 14px;
  border: none;
  background: transparent;
  border-radius: 8px;
  color: var(--color-ink-sub);
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all 0.2s;
}
.tab.on {
  background: var(--color-card);
  color: var(--color-primary);
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(15, 118, 110, 0.12);
}

/* 输入字段 */
.field {
  margin-bottom: 18px;
}
.field-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 6px;
}
.field-top label {
  font-size: 13px;
  color: var(--color-ink);
  font-weight: 600;
}
.field-top .rule {
  font-size: 11px;
  color: var(--color-ink-sub);
}
.field :deep(.n-input) {
  --n-border-radius: 8px;
}

.auth-alert {
  margin-bottom: 16px;
}

/* 主按钮：白字 + 青绿渐变，hover 泛金 */
.auth-btn {
  --n-text-color: #fff !important;
  --n-text-color-hover: #fff !important;
  --n-text-color-pressed: #fff !important;
  --n-text-color-focus: #fff !important;
  --n-color: #0f766e !important;
  --n-color-hover: #115e59 !important;
  --n-color-pressed: #0d5f58 !important;
  --n-color-focus: #115e59 !important;
  --n-border: none;
  --n-border-hover: none;
  --n-border-pressed: none;
  --n-border-focus: none;
  --n-border-radius: 10px;
  font-size: 16px;
  letter-spacing: 4px;
  background: linear-gradient(120deg, #0f766e, #115e59);
  box-shadow: 0 4px 14px rgba(15, 118, 110, 0.25);
  transition: all 0.2s ease;
}
.auth-btn:hover {
  background: linear-gradient(120deg, #138a80, #0f766e);
  box-shadow: 0 6px 20px rgba(15, 118, 110, 0.35);
  transform: translateY(-1px);
}
.auth-btn:active {
  transform: translateY(0);
}
</style>
