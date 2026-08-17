<script setup>
import { SCENE_TYPES } from '../constants'

defineProps({ modelValue: String })
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="scene-grid">
    <button
      v-for="s in SCENE_TYPES"
      :key="s.value"
      type="button"
      class="scene-card"
      :class="{ active: modelValue === s.value }"
      @click="$emit('update:modelValue', s.value)"
    >
      <span class="emoji">{{ s.emoji }}</span>
      <span class="label">{{ s.value }}</span>
      <span class="desc">{{ s.desc }}</span>
      <span v-if="modelValue === s.value" class="check">✓</span>
    </button>
  </div>
</template>

<style scoped>
.scene-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.scene-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  text-align: left;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-card);
  cursor: pointer;
  transition: all 0.18s ease;
  font-family: var(--font-sans);
}

.scene-card:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-card);
}

.scene-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-fade);
  box-shadow: 0 4px 14px rgba(15, 118, 110, 0.12);
}

.emoji { font-size: 20px; line-height: 1.2; }
.label { font-size: 14px; font-weight: 600; color: var(--color-ink); }
.desc  { font-size: 11px; color: var(--color-ink-sub); }

.check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-gold);
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
