<script setup>
import { PhPlus } from "@phosphor-icons/vue";
</script>

<template>
  <div class="collection-shell">
    <main class="collection-main"><slot /></main>
    <footer class="collection-footer">
      <span>TravelGen</span
      ><router-link to="/"><PhPlus :size="14" /> 开始新的创作</router-link>
    </footer>
  </div>
</template>

<style>
.collection-shell {
  min-height: 100vh;
  background: var(--color-bg);
  color: var(--color-ink);
  font-family: var(--font-sans);
}
.collection-shell * {
  box-sizing: border-box;
}
.collection-main {
  max-width: 1340px;
  margin: auto;
  padding: 54px 48px 80px;
  min-height: calc(100vh - 76px);
}
.collection-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 36px;
}
.collection-eyebrow {
  font-size: 11px;
  letter-spacing: 3px;
  color: var(--color-primary);
  font-weight: 700;
}
.collection-heading h1 {
  font-size: 34px;
  font-weight: 650;
  letter-spacing: -1px;
  margin: 8px 0 10px;
}
.collection-heading p {
  color: var(--color-ink-sub);
  font-size: 14px;
  margin: 0;
}
.collection-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 28px;
}
.collection-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.collection-filters button {
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-ink-sub);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}
.collection-filters button.active {
  background: var(--color-card);
  border-color: var(--color-border);
  color: var(--color-primary);
  box-shadow: var(--shadow-soft);
  font-weight: 600;
}
.collection-search {
  max-width: 280px;
}
.collection-empty {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 12px;
  background: var(--color-card);
  border: 1px dashed var(--border-strong);
  border-radius: 16px;
  color: var(--color-ink-sub);
  padding: 35px;
}
.collection-empty svg {
  color: var(--color-primary);
}
.collection-empty h2 {
  color: var(--color-ink);
  margin: 8px 0 0;
  font-size: 20px;
}
.collection-empty p {
  margin: 0 0 10px;
  font-size: 14px;
  max-width: 440px;
  line-height: 1.8;
}
.collection-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}
.collection-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 14px;
  overflow: hidden;
  transition:
    box-shadow 0.2s,
    transform 0.2s;
}
.collection-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}
.collection-card-body {
  padding: 19px 20px;
}
.collection-card h3 {
  font-size: 16px;
  font-weight: 650;
  margin: 0 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.collection-card p {
  color: var(--color-ink-sub);
  font-size: 12px;
  margin: 0;
}
.collection-card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 18px;
}
.collection-muted {
  color: var(--color-ink-muted);
  font-size: 12px;
}
.collection-footer {
  border-top: 1px solid var(--color-border);
  margin: 0 5%;
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-ink-muted);
}
.collection-footer a {
  color: var(--color-primary);
  display: flex;
  align-items: center;
  gap: 5px;
  text-decoration: none;
}
.collection-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
}
.collection-error {
  color: var(--color-error);
}
@media (min-width: 1700px) {
  .collection-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (max-width: 1200px) {
  .collection-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .collection-main {
    padding: 35px 24px 60px;
  }
}
@media (max-width: 700px) {
  .collection-grid {
    grid-template-columns: 1fr;
  }

  .collection-main {
    padding: 28px 18px 50px;
  }
  .collection-heading h1 {
    font-size: 28px;
  }
  .collection-heading {
    align-items: flex-start;
  }
  .collection-toolbar {
    align-items: stretch;
    flex-direction: column;
    gap: 14px;
  }
  .collection-search {
    max-width: 100%;
  }
  .collection-footer {
    font-size: 11px;
  }
}
</style>
