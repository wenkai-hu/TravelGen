<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NInput,
  NModal,
  NPopconfirm,
  NSkeleton,
  useMessage,
} from "naive-ui";
import {
  PhPlus,
  PhMagnifyingGlass,
  PhArrowRight,
  PhFolderOpen,
  PhFilmSlate,
  PhPencilSimple,
  PhTrash,
  PhClock,
} from "@phosphor-icons/vue";
import CollectionShell from "../components/CollectionShell.vue";
import { listProjects, renameProject, deleteProject } from "../api";
import { logout } from "../auth";

const router = useRouter(),
  message = useMessage();
const projects = ref([]),
  loading = ref(true),
  error = ref(""),
  search = ref(""),
  filter = ref("all");
const renaming = ref(null),
  newName = ref(""),
  saving = ref(false);
const labels = {
  draft: "需求草稿",
  created: "准备开始",
  searching_references: "实景搜索中",
  waiting_reference_confirm: "待选择参考图",
  analyzing_references: "图片分析中",
  planning: "方案生成中",
  waiting_confirm: "待确认方案",
  plan_confirmed: "待生成分镜",
  storyboarding: "分镜生成中",
  waiting_storyboard_confirm: "分镜创作中",
  generating: "镜头生成中",
  video_ready: "待合成成片",
  composing: "成片合成中",
  completed: "已完成",
  failed: "需要处理",
};
const filters = [
  { id: "all", label: "全部项目" },
  { id: "active", label: "进行中" },
  { id: "completed", label: "已完成" },
  { id: "draft", label: "草稿" },
];
const visible = computed(() =>
  projects.value.filter(
    (p) =>
      (!search.value ||
        `${p.name} ${p.theme}`
          .toLowerCase()
          .includes(search.value.toLowerCase())) &&
      (filter.value === "all" ||
        (filter.value === "active"
          ? !["draft", "completed"].includes(p.status)
          : p.status === filter.value)),
  ),
);
let timer;
function date(value) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
async function load(silent = false) {
  if (!silent) loading.value = true;
  try {
    projects.value = (await listProjects()).projects;
    error.value = "";
  } catch (e) {
    if (e.status === 401) {
      logout();
      router.replace("/login?redirect=/projects");
    } else error.value = e.message;
  } finally {
    loading.value = false;
  }
}
function open(p) {
  router.push(p.resume_url);
}
function edit(p) {
  renaming.value = p;
  newName.value = p.name;
}
async function saveName() {
  if (!newName.value.trim()) return;
  saving.value = true;
  try {
    await renameProject(renaming.value.project_id, newName.value.trim());
    renaming.value = null;
    await load(true);
  } catch (e) {
    message.error(e.message);
  } finally {
    saving.value = false;
  }
}
async function remove(p) {
  try {
    await deleteProject(p.project_id);
    message.success("项目已删除，已生成的素材仍然保留");
    await load(true);
  } catch (e) {
    message.error(e.message);
  }
}
onMounted(() => {
  load();
  timer = setInterval(() => {
    if (!document.hidden) load(true);
  }, 10000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>

<template>
  <CollectionShell active="projects">
    <div class="collection-heading">
      <div>
        <span class="collection-eyebrow">YOUR CREATIVE SPACE</span>
        <h1>
          我的项目 <span class="project-count">{{ projects.length }}</span>
        </h1>
        <p>继续您的创作</p>
      </div>
      <NButton type="primary" size="large" @click="router.push('/')"
        ><template #icon><PhPlus /></template>新建项目</NButton
      >
    </div>
    <div class="collection-toolbar">
      <div class="collection-filters">
        <button
          v-for="item in filters"
          :key="item.id"
          :class="{ active: filter === item.id }"
          :aria-pressed="filter === item.id"
          @click="filter = item.id"
        >
          {{ item.label }}
        </button>
      </div>
      <NInput
        v-model:value="search"
        class="collection-search"
        placeholder="搜索项目名称"
        clearable
        aria-label="搜索项目"
        ><template #prefix><PhMagnifyingGlass /></template
      ></NInput>
    </div>
    <div v-if="loading" class="collection-grid">
      <NSkeleton
        v-for="i in 3"
        :key="i"
        height="310px"
        style="border-radius: 14px"
      />
    </div>
    <div v-else-if="error" class="collection-empty">
      <h2>暂时没有读取到项目</h2>
      <p>{{ error }}</p>
      <NButton @click="load()">重新加载</NButton>
    </div>
    <div v-else-if="!visible.length" class="collection-empty">
      <PhFolderOpen :size="48" weight="duotone" />
      <h2>
        {{ projects.length ? "没有匹配的项目" : "你的第一个故事，从这里开始" }}
      </h2>
      <p>
        {{
          projects.length
            ? "试试其他名称，或切换项目分类。"
            : "填写创作需求后会自动保存为草稿。随时离开，随时回来继续。"
        }}
      </p>
      <NButton v-if="!projects.length" type="primary" @click="router.push('/')"
        >开始创作</NButton
      >
    </div>
    <div v-else class="collection-grid">
      <article v-for="p in visible" :key="p.project_id" class="collection-card">
        <button
          class="project-cover"
          :aria-label="`打开项目：${p.name}`"
          @click="open(p)"
        >
          <img
            v-if="p.cover_url"
            :src="p.cover_url"
            :alt="p.name"
            loading="lazy"
            @error="p.cover_url = null"
          />
          <div v-else class="project-cover-empty">
            <PhFilmSlate :size="46" weight="duotone" /><span>{{
              p.scene_type || "一个新的旅行故事"
            }}</span>
          </div>
          <span
            class="project-status"
            :class="{
              done: p.status === 'completed',
              failed: p.status === 'failed',
            }"
            ><i></i>{{ labels[p.status] || p.status }}</span
          >
          <span v-if="p.duration_s" class="project-duration"
            >{{ p.duration_s }}s</span
          >
        </button>
        <div class="collection-card-body">
          <h3 :title="p.name">{{ p.name }}</h3>
          <p>
            {{ p.scene_type || "需求填写中"
            }}<template v-if="p.shot_count">
              · {{ p.completed_shots }} /
              {{ p.shot_count }} 个镜头已生成</template
            >
          </p>
          <div class="project-progress" aria-hidden="true">
            <span
              :style="{
                width: `${p.status === 'completed' ? 100 : p.shot_count ? (p.completed_shots / p.shot_count) * 100 : p.progress || 0}%`,
              }"
            ></span>
          </div>
          <div class="project-time">
            <PhClock :size="13" />{{ date(p.updated_at) }}
          </div>
          <div class="collection-card-actions">
            <NButton text type="primary" @click="open(p)"
              >{{ p.status === "completed" ? "查看成片" : "继续创作"
              }}<template #icon><PhArrowRight /></template
            ></NButton>
            <div class="project-tools">
              <NButton
                quaternary
                circle
                size="small"
                aria-label="重命名项目"
                @click="edit(p)"
                ><template #icon><PhPencilSimple /></template></NButton
              ><NPopconfirm @positive-click="remove(p)"
                ><template #trigger
                  ><NButton quaternary circle size="small" aria-label="删除项目"
                    ><template #icon><PhTrash /></template></NButton></template
                >删除这个项目？已生成的视频和音色会保留在素材库。</NPopconfirm
              >
            </div>
          </div>
        </div>
      </article>
    </div>
    <NModal
      :show="!!renaming"
      preset="card"
      title="重命名项目"
      style="width: 420px; max-width: 90vw"
      @update:show="
        (v) => {
          if (!v) renaming = null;
        }
      "
      ><NInput
        v-model:value="newName"
        maxlength="100"
        placeholder="项目名称"
        @keyup.enter="saveName"
      />
      <div class="collection-modal-actions">
        <NButton @click="renaming = null">取消</NButton
        ><NButton
          type="primary"
          :loading="saving"
          :disabled="!newName.trim()"
          @click="saveName"
          >保存</NButton
        >
      </div></NModal
    >
  </CollectionShell>
</template>

<style scoped>
.project-count {
  display: inline-flex;
  vertical-align: middle;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0;
  background: var(--color-primary-light);
  color: var(--color-primary);
  padding: 4px 10px;
  border-radius: 8px;
  margin-left: 8px;
}
.project-cover {
  position: relative;
  display: block;
  padding: 0;
  width: 100%;
  aspect-ratio: 16/10;
  border: 0;
  cursor: pointer;
  background: var(--media-placeholder);
  overflow: hidden;
}
.project-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.35s;
}
.project-cover:hover img {
  transform: scale(1.03);
}
.project-cover-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  background:
    radial-gradient(
      ellipse at 75% 20%,
      var(--color-gold-fade),
      transparent 65%
    ),
    linear-gradient(145deg, var(--color-primary-light), var(--surface-sunken));
  color: var(--color-primary);
}
.project-cover-empty span {
  font-size: 12px;
  letter-spacing: 2px;
}
.project-status {
  position: absolute;
  top: 14px;
  left: 14px;
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 11px;
  color: var(--color-ink);
  background: var(--color-card);
  padding: 5px 9px;
  border-radius: 5px;
  box-shadow: var(--shadow-soft);
}
.project-status i {
  width: 5px;
  height: 5px;
  background: var(--color-gold);
  border-radius: 50%;
}
.project-status.done i {
  background: var(--color-success);
}
.project-status.failed i {
  background: var(--color-error);
}
.project-duration {
  position: absolute;
  right: 13px;
  bottom: 12px;
  background: var(--color-card);
  color: var(--color-ink);
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
}
.project-progress {
  height: 3px;
  background: var(--color-primary-light);
  border-radius: 2px;
  margin: 17px 0 11px;
  overflow: hidden;
}
.project-progress span {
  display: block;
  height: 100%;
  background: var(--color-primary);
}
.project-time {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--color-ink-muted);
  font-size: 11px;
}
.project-tools {
  display: flex;
  gap: 3px;
}
</style>
