<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NInput,
  NModal,
  NPopconfirm,
  NSelect,
  NSkeleton,
  useMessage,
} from "naive-ui";
import {
  PhFilmStrip,
  PhWaveform,
  PhMagnifyingGlass,
  PhArrowUpRight,
  PhDownloadSimple,
  PhPencilSimple,
  PhTrash,
  PhFolderOpen,
} from "@phosphor-icons/vue";
import CollectionShell from "../components/CollectionShell.vue";
import {
  getLibraryVideos,
  getLibraryVoices,
  renameLibraryVoice,
  deleteLibraryVoice,
  downloadLibraryAsset,
  listProjects,
  selectVoice,
} from "../api";
import { logout } from "../auth";

const router = useRouter(),
  route = useRoute(),
  message = useMessage();
const tab = ref(route.query.tab === "voices" ? "voices" : "videos"),
  groups = ref([]),
  voices = ref([]),
  loading = ref(true),
  error = ref(""),
  search = ref(""),
  history = ref(false);
const renaming = ref(null),
  name = ref(""),
  busy = ref(false),
  using = ref(null),
  projectId = ref(null),
  projectOptions = ref([]);
let timer;
const filteredGroups = computed(() =>
  groups.value.filter((g) =>
    g.name.toLowerCase().includes(search.value.toLowerCase()),
  ),
);
const filteredVoices = computed(() =>
  voices.value.filter((v) =>
    `${v.name} ${v.description}`
      .toLowerCase()
      .includes(search.value.toLowerCase()),
  ),
);
const videoCount = computed(() =>
  groups.value.reduce((sum, g) => sum + g.assets.length, 0),
);
function date(v) {
  return new Date(v).toLocaleDateString("zh-CN");
}
function items(group) {
  const seen = new Set();
  const selected = history.value
    ? [...group.assets]
    : group.assets.filter((a) => {
        const key = `${a.kind}:${a.output_key}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  return selected.sort(
    (a, b) =>
      Number(a.kind === "final_video") - Number(b.kind === "final_video") ||
      (a.metadata.shot_ids?.[0] || 0) - (b.metadata.shot_ids?.[0] || 0) ||
      (a.metadata.continuation_index || 1) -
        (b.metadata.continuation_index || 1) ||
      new Date(b.created_at) - new Date(a.created_at),
  );
}
function changeTab(value) {
  tab.value = value;
  search.value = "";
  router.replace({ query: { tab: value } });
}
async function load(silent = false) {
  if (!silent) loading.value = true;
  try {
    const [v, a] = await Promise.all([getLibraryVideos(), getLibraryVoices()]);
    groups.value = v.groups;
    voices.value = a.voices;
    error.value = "";
  } catch (e) {
    if (e.status === 401) {
      logout();
      router.replace("/login?redirect=/library");
    } else error.value = e.message;
  } finally {
    loading.value = false;
  }
}
async function openProject(group) {
  try {
    const p = (await listProjects()).projects.find(
      (p) => p.project_id === group.project_id,
    );
    if (p) router.push(p.resume_url);
    else message.warning("来源项目已删除，素材仍可使用");
  } catch (e) {
    message.error(e.message);
  }
}
async function download(asset, extension) {
  try {
    await downloadLibraryAsset(
      asset.id || asset.asset_id,
      `${asset.name}.${extension}`,
    );
  } catch (e) {
    message.error(e.message);
  }
}
function edit(v) {
  renaming.value = v;
  name.value = v.name;
}
async function saveName() {
  busy.value = true;
  try {
    await renameLibraryVoice(renaming.value.voice_id, name.value.trim());
    renaming.value = null;
    await load(true);
  } catch (e) {
    message.error(e.message);
  } finally {
    busy.value = false;
  }
}
async function remove(v) {
  try {
    await deleteLibraryVoice(v.voice_id);
    message.success("已从音色库移除，已有项目仍保留其参考音频");
    await load(true);
  } catch (e) {
    message.error(e.message);
  }
}
async function useVoice(v) {
  using.value = v;
  projectId.value = null;
  try {
    projectOptions.value = (await listProjects()).projects
      .filter(
        (p) =>
          p.shot_count > 0 && !["generating", "composing"].includes(p.status),
      )
      .map((p) => ({ label: p.name, value: p.project_id }));
  } catch (e) {
    message.error(e.message);
  }
}
async function applyVoice() {
  busy.value = true;
  try {
    await selectVoice(projectId.value, { voice_id: using.value.voice_id });
    using.value = null;
    message.success("音色已应用，可以继续创作");
    router.push(`/plan/${projectId.value}/storyboard`);
  } catch (e) {
    message.error(e.message);
  } finally {
    busy.value = false;
  }
}
function play(event) {
  document.querySelectorAll("audio,video").forEach((el) => {
    if (el !== event.target) el.pause();
  });
}
onMounted(() => {
  load();
  timer = setInterval(() => {
    if (!document.hidden) load(true);
  }, 12000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>

<template>
  <CollectionShell active="library">
    <div class="collection-heading">
      <div>
        <span class="collection-eyebrow">MADE BY YOU, KEPT FOR YOU</span>
        <h1>我的素材</h1>
        <p>镜头与声音，在这里留存，也为下一次创作带来灵感。</p>
      </div>
      <div class="library-summary">
        <strong>{{ videoCount + voices.length }}</strong
        ><span>份创作成果</span>
      </div>
    </div>
    <div class="library-tabs" role="tablist" aria-label="素材类型">
      <button
        role="tab"
        :aria-selected="tab === 'videos'"
        :class="{ active: tab === 'videos' }"
        @click="changeTab('videos')"
      >
        <PhFilmStrip :size="20" />视频<span>{{ videoCount }}</span></button
      ><button
        role="tab"
        :aria-selected="tab === 'voices'"
        :class="{ active: tab === 'voices' }"
        @click="changeTab('voices')"
      >
        <PhWaveform :size="20" />音色<span>{{ voices.length }}</span>
      </button>
    </div>
    <div class="collection-toolbar">
      <div class="collection-muted">
        {{
          tab === "videos"
            ? "按项目分类整理 · 自动收录成品"
            : "你的专属声音收藏 · 可在所有项目中复用"
        }}<label v-if="tab === 'videos'" class="library-history"
          ><input v-model="history" type="checkbox" />显示历史版本</label
        >
      </div>
      <NInput
        v-model:value="search"
        class="collection-search"
        clearable
        :placeholder="tab === 'videos' ? '搜索来源项目' : '搜索音色名称或描述'"
        ><template #prefix><PhMagnifyingGlass /></template
      ></NInput>
    </div>
    <div v-if="loading" class="collection-grid">
      <NSkeleton
        v-for="i in 3"
        :key="i"
        height="260px"
        style="border-radius: 14px"
      />
    </div>
    <div v-else-if="error" class="collection-empty">
      <h2>暂时没有读取到素材</h2>
      <p>{{ error }}</p>
      <NButton @click="load()">重新加载</NButton>
    </div>
    <template v-else-if="tab === 'videos'">
      <div v-if="!filteredGroups.length" class="collection-empty">
        <PhFilmStrip :size="48" weight="duotone" />
        <h2>{{ search ? "没有找到相关视频" : "第一个镜头，值得被收藏" }}</h2>
        <p>项目中成功生成的每个镜头和完整视频，都会自动出现在这里。</p>
        <NButton type="primary" @click="router.push('/projects')"
          >前往项目</NButton
        >
      </div>
      <section
        v-for="group in filteredGroups"
        :key="group.project_id"
        class="library-group"
      >
        <div class="library-group-heading">
          <div>
            <PhFolderOpen :size="21" />
            <h2>{{ group.name }}</h2>
            <span>{{ group.assets.length }} 个视频</span>
          </div>
          <NButton
            v-if="!group.project_deleted"
            text
            type="primary"
            @click="openProject(group)"
            >进入项目<template #icon><PhArrowUpRight /></template></NButton
          ><span v-else class="collection-muted">来源项目已删除</span>
        </div>
        <div class="collection-grid">
          <article
            v-for="asset in items(group)"
            :key="asset.id"
            class="collection-card"
          >
            <div class="library-video">
              <video
                v-if="asset.available"
                :src="asset.url"
                controls
                preload="metadata"
                playsinline
                @play="play"
              ></video>
              <div v-else class="library-missing">
                <PhFilmStrip :size="32" /><span>源文件暂不可用</span>
              </div>
              <span class="library-kind">{{
                asset.kind === "final_video" ? "成片" : "镜头"
              }}</span>
            </div>
            <div class="collection-card-body">
              <h3>{{ asset.name }}</h3>
              <p>
                <template v-if="asset.metadata.duration_s"
                  >{{ Number(asset.metadata.duration_s).toFixed(1) }}s · </template
                >{{ date(asset.created_at)
                }}<template v-if="asset.metadata.version">
                  · v{{ asset.metadata.version
                  }}<template v-if="asset.metadata.mix_version"
                    >.{{ asset.metadata.mix_version }}</template
                  ></template
                >
              </p>
              <div class="collection-card-actions">
                <span class="collection-muted">{{
                  asset.kind === "final_video"
                    ? "完整旅途，已成片"
                    : "已保存到素材库"
                }}</span
                ><NButton
                  size="small"
                  quaternary
                  :disabled="!asset.available"
                  @click="download(asset, 'mp4')"
                  ><template #icon><PhDownloadSimple /></template>下载</NButton
                >
              </div>
            </div>
          </article>
        </div>
      </section>
    </template>
    <template v-else>
      <div v-if="!filteredVoices.length" class="collection-empty">
        <PhWaveform :size="48" />
        <h2>{{ search ? "没有找到这个声音" : "为故事，收藏一个好声音" }}</h2>
        <p>
          在项目中生成自定义音色后，会自动保存到这里。以后创作可以直接选择使用。
        </p>
        <NButton type="primary" @click="router.push('/projects')"
          >前往项目生成音色</NButton
        >
      </div>
      <div v-else class="collection-grid">
        <article
          v-for="voice in filteredVoices"
          :key="voice.voice_id"
          class="collection-card voice-card"
        >
          <div class="voice-visual" aria-hidden="true">
            <PhWaveform :size="42" weight="light" /><span>VOICE</span>
          </div>
          <div class="collection-card-body">
            <h3 :title="voice.name">{{ voice.name }}</h3>
            <p class="voice-description">{{ voice.description }}</p>
            <audio
              v-if="voice.available"
              :src="voice.preview_url"
              controls
              preload="none"
              @play="play"
            ></audio>
            <p v-else class="collection-error">音频文件暂不可用</p>
            <div class="collection-muted">
              收藏于 {{ date(voice.created_at) }}
            </div>
            <div class="collection-card-actions">
              <NButton
                size="small"
                type="primary"
                secondary
                :disabled="!voice.available"
                @click="useVoice(voice)"
                >用于项目</NButton
              >
              <div class="voice-tools">
                <NButton
                  quaternary
                  circle
                  size="small"
                  aria-label="下载音色"
                  :disabled="!voice.available"
                  @click="download(voice, 'wav')"
                  ><template #icon><PhDownloadSimple /></template></NButton
                ><NButton
                  quaternary
                  circle
                  size="small"
                  aria-label="重命名音色"
                  @click="edit(voice)"
                  ><template #icon><PhPencilSimple /></template></NButton
                ><NPopconfirm @positive-click="remove(voice)"
                  ><template #trigger
                    ><NButton
                      quaternary
                      circle
                      size="small"
                      aria-label="删除音色"
                      ><template #icon
                        ><PhTrash /></template></NButton></template
                  >从音色库移除？已经使用它的项目不受影响。</NPopconfirm
                >
              </div>
            </div>
          </div>
        </article>
      </div>
    </template>
    <NModal
      :show="!!renaming"
      preset="card"
      title="给音色起个名字"
      style="width: 420px; max-width: 90vw"
      @update:show="
        (v) => {
          if (!v) renaming = null;
        }
      "
      ><NInput v-model:value="name" maxlength="100" @keyup.enter="saveName" />
      <div class="collection-modal-actions">
        <NButton @click="renaming = null">取消</NButton
        ><NButton
          type="primary"
          :loading="busy"
          :disabled="!name.trim()"
          @click="saveName"
          >保存</NButton
        >
      </div></NModal
    >
    <NModal
      :show="!!using"
      preset="card"
      title="将音色用于项目"
      style="width: 440px; max-width: 90vw"
      @update:show="
        (v) => {
          if (!v) using = null;
        }
      "
      ><p>
        选择已经准备好分镜的项目。更换音色后，已有镜头需要重新生成才能使用新声音。
      </p>
      <NSelect
        v-model:value="projectId"
        :options="projectOptions"
        placeholder="选择项目"
      />
      <p v-if="!projectOptions.length" class="collection-muted">
        暂无可选项目，请先创建项目并完成分镜。
      </p>
      <div class="collection-modal-actions">
        <NButton @click="using = null">取消</NButton
        ><NButton
          type="primary"
          :disabled="!projectId"
          :loading="busy"
          @click="applyVoice"
          >使用并进入项目</NButton
        >
      </div></NModal
    >
  </CollectionShell>
</template>

<style scoped>
.library-summary {
  flex-shrink: 0;
  white-space: nowrap;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  color: var(--color-ink-muted);
  font-size: 12px;
}
.library-summary strong {
  font-size: 30px;
  font-weight: 500;
  color: var(--color-primary);
}
.library-tabs {
  display: flex;
  gap: 32px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 24px;
}
.library-tabs button {
  display: flex;
  gap: 9px;
  align-items: center;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 0 2px 17px;
  margin-bottom: -1px;
  background: none;
  font: inherit;
  font-size: 15px;
  cursor: pointer;
  color: var(--color-ink-sub);
}
.library-tabs button.active {
  color: var(--color-primary);
  border-color: var(--color-primary);
  font-weight: 650;
}
.library-tabs button span {
  background: var(--color-primary-light);
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 5px;
}
.library-history {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 18px;
  cursor: pointer;
}
.library-history input {
  accent-color: var(--color-primary);
}
.library-group {
  margin-bottom: 38px;
}
.library-group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 16px;
}
.library-group-heading > div {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
  color: var(--color-primary);
}
.library-group-heading h2 {
  font-size: 17px;
  color: var(--color-ink);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.library-group-heading span {
  font-size: 12px;
  color: var(--color-ink-muted);
  white-space: nowrap;
}
.library-video {
  position: relative;
  aspect-ratio: 16/10;
  background: var(--media-placeholder);
}
.library-video video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.library-kind {
  position: absolute;
  top: 12px;
  left: 12px;
  pointer-events: none;
  font-size: 11px;
  background: var(--color-card);
  color: var(--color-primary);
  padding: 3px 8px;
  border-radius: 4px;
}
.library-missing {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: var(--color-ink-muted);
}
.voice-visual {
  height: 88px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: linear-gradient(
    110deg,
    var(--color-primary-light),
    var(--color-gold-fade)
  );
  color: var(--color-primary);
}
.voice-visual span {
  letter-spacing: 4px;
  font-size: 10px;
}
.voice-description {
  min-height: 44px;
  line-height: 1.8;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.voice-card audio {
  display: block;
  width: 100%;
  height: 36px;
  margin: 18px 0 16px;
}
.voice-tools {
  display: flex;
  gap: 3px;
}
@media (max-width: 600px) {
  .library-history {
    margin: 10px 0 0;
    display: flex;
  }
  .library-group-heading h2 {
    max-width: 140px;
  }
  .library-group-heading span {
    display: none;
  }
}
</style>
