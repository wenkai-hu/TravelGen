<script setup>
defineProps({ state: String });
defineEmits(["retry"]);
</script>
<template>
  <span v-if="state && state !== 'saved'" class="draft-status" role="status"
    >{{
      {
        saving: "正在保存…",
        pending: "等待保存…",
        error: "暂未同步，已在本机保留",
      }[state]
    }}<button v-if="state === 'error'" @click="$emit('retry')">
      重试保存
    </button></span
  >
</template>
<style scoped>
.draft-status {
  color: var(--color-ink-muted);
  font-size: 12px;
  display: inline-flex;
  gap: 8px;
  align-items: center;
}
.draft-status button {
  border: 0;
  background: none;
  color: var(--color-primary);
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
}
</style>
