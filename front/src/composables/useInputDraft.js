import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { createProjectDraft, getProject, saveProjectDraft } from "../api";
import { getUsername, isLoggedIn } from "../auth";

export function useInputDraft(form, message) {
  const route = useRoute(),
    router = useRouter();
  const pid = ref(String(route.query.draft || "")),
    state = ref("saved");
  const owner = getUsername(),
    cacheKey = `travelgen:input:${owner}`;
  let ready = false,
    timer,
    creating,
    chain = Promise.resolve(),
    submitted = false;
  const snapshot = () => JSON.parse(JSON.stringify(form));
  function cache() {
    try {
      localStorage.setItem(
        cacheKey,
        JSON.stringify({ pid: pid.value, data: snapshot() }),
      );
    } catch {
      /* keep DB persistence */
    }
  }
  async function ensure() {
    if (pid.value) return pid.value;
    if (!creating)
      creating = createProjectDraft(snapshot())
        .then((result) => {
          pid.value = result.project_id;
          cache();
          router.replace({ path: "/", query: { draft: pid.value } });
          return pid.value;
        })
        .finally(() => {
          creating = null;
        });
    return creating;
  }
  function flush() {
    clearTimeout(timer);
    if (
      !ready ||
      submitted ||
      state.value === "saved" ||
      !isLoggedIn() ||
      !(
        form.city ||
        form.location ||
        form.theme ||
        form.description ||
        form.scene_type
      )
    )
      return chain;
    const data = snapshot();
    chain = chain
      .catch(() => {})
      .then(async () => {
        state.value = "saving";
        try {
          const id = await ensure();
          await saveProjectDraft(id, "input", data, { keepalive: true });
          if (JSON.stringify(data) === JSON.stringify(snapshot()))
            localStorage.removeItem(cacheKey);
          state.value = "saved";
        } catch (e) {
          state.value = "error";
          throw e;
        }
      });
    return chain;
  }
  watch(
    form,
    () => {
      if (!ready || submitted || !isLoggedIn()) return;
      cache();
      state.value = "pending";
      clearTimeout(timer);
      timer = setTimeout(() => flush().catch(() => {}), 700);
    },
    { deep: true },
  );
  onMounted(async () => {
    let needsSync = false;
    try {
      const cached = JSON.parse(localStorage.getItem(cacheKey) || "null");
      if (pid.value) {
        const project = await getProject(pid.value);
        if (project.status !== "draft") {
          message.info("该项目已经开始，请从项目页继续");
          router.replace("/projects");
          return;
        }
        Object.assign(
          form,
          project.request,
          cached?.pid === pid.value ? cached.data : {},
        );
        needsSync = cached?.pid === pid.value;
      } else if (cached) {
        pid.value = cached.pid || "";
        Object.assign(form, cached.data);
        needsSync = true;
        if (pid.value)
          await router.replace({ path: "/", query: { draft: pid.value } });
      }
    } catch (e) {
      message.error(e.message || "草稿读取失败");
      if (pid.value) {
        router.replace("/projects");
        return;
      }
    }
    ready = true;
    if (needsSync) {
      state.value = "pending";
      timer = setTimeout(() => flush().catch(() => {}), 700);
    }
  });
  function finish() {
    submitted = true;
    clearTimeout(timer);
    localStorage.removeItem(cacheKey);
  }
  const unload = () => {
    if (ready && !submitted) {
      if (state.value !== "saved") cache();
      flush().catch(() => {});
    }
  };
  window.addEventListener("pagehide", unload);
  onBeforeRouteLeave(async () => {
    try {
      await flush();
    } catch (e) {
      message.warning("草稿尚未同步，已保留在本机");
    }
  });
  onBeforeUnmount(() => {
    window.removeEventListener("pagehide", unload);
    clearTimeout(timer);
  });
  return { pid, state, flush, ensure, finish };
}
