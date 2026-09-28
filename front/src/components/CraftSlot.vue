<script setup>
import { PhCheck } from '@phosphor-icons/vue'

// 工作台槽位：所有输入都放进统一的"凹槽"里，拼装感由此而来。
// filled 控制高亮，required 未填时显示虚线边框（提示这是必需材料）。
defineProps({
  label: String,   // 槽位名，如「城市」
  icon: Object,    // 槽位图标：Phosphor 组件（全站统一图标家族）
  filled: Boolean, // 是否已放入内容
  required: Boolean,
})
</script>

<template>
  <div class="craft-slot" :class="{ filled, required }">
    <div class="slot-badge">
      <span class="slot-icon"><component :is="icon" /></span>
      <span class="slot-label">{{ label }}</span>
      <span v-if="required" class="req">*</span>
    </div>
    <div class="slot-body">
      <slot />
    </div>
    <span v-if="filled" class="slot-check">
      <PhCheck :size="11" weight="bold" />
    </span>
  </div>
</template>

<style scoped>
.craft-slot {
  position: relative;
  background: var(--slot-bg);
  border: 2px solid var(--slot-border);
  border-radius: 8px;
  padding: 12px 12px 14px;
  min-height: 92px;
  display: flex;
  flex-direction: column;
  /* 凹槽质感：顶部高光 + 底部暗边（克制的 Minecraft 斜面） */
  box-shadow:
    inset 0 2px 0 var(--inset-highlight),
    inset 0 -2px 0 var(--inset-shadow),
    0 2px 6px var(--shadow-color);
  transition: border-color 0.2s, background 0.2s, transform 0.15s, box-shadow 0.2s;
}

.craft-slot:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow:
    inset 0 2px 0 var(--inset-highlight),
    inset 0 -2px 0 var(--inset-shadow),
    0 6px 14px var(--shadow-primary);
}

/* 已填：青绿高亮 */
.craft-slot.filled {
  border-color: var(--color-primary);
  background: var(--color-primary-fade);
}

/* 必填未填：虚线邀请 */
.craft-slot.required:not(.filled) {
  border-style: dashed;
}

.slot-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--color-ink-sub);
  margin-bottom: 8px;
  user-select: none;
}
.slot-icon { font-size: 14px; }
.slot-label { letter-spacing: 1px; }
.req { color: var(--color-error); font-size: 12px; }

.slot-body { flex: 1; display: flex; flex-direction: column; justify-content: center; }

.slot-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  background: var(--color-gold);
  color: var(--color-on-gold);
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
</style>
