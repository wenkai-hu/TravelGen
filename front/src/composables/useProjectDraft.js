import { onBeforeUnmount, ref, unref } from "vue";
import { saveProjectDraft } from "../api";
import { getUsername } from "../auth";

// Local backup is written immediately; DB writes are debounced and ordered.
// A pending local draft survives an abrupt browser close or network failure.
export function useProjectDraft(pid, section) {
  const state = ref("saved");
  let timer,
    pending,
    chain = Promise.resolve(),
    lastValue;
  const key = () => `travelgen:draft:${getUsername()}:${unref(pid)}:${section}`;
  function restore(remote) {
    let local;
    try {
      local = JSON.parse(localStorage.getItem(key()) || "null");
    } catch {
      /* corrupt cache */
    }
    const value = local ? local.data : remote;
    lastValue = JSON.stringify(value ?? null);
    if (local) {
      pending = { pid: unref(pid), key: key(), data: value };
      state.value = "pending";
      timer = setTimeout(() => flush().catch(() => {}), 650);
    }
    return value;
  }
  function queue(data) {
    const value = JSON.stringify(data);
    if (value === lastValue || !unref(pid)) return;
    lastValue = value;
    pending = { pid: unref(pid), key: key(), data: JSON.parse(value) };
    try {
      localStorage.setItem(pending.key, JSON.stringify({ data: pending.data }));
    } catch {
      /* DB save still available */
    }
    state.value = "pending";
    clearTimeout(timer);
    timer = setTimeout(() => flush().catch(() => {}), 650);
  }
  function flush() {
    clearTimeout(timer);
    const item = pending;
    if (!item) return chain;
    pending = null;
    chain = chain
      .catch(() => {})
      .then(async () => {
        state.value = "saving";
        try {
          await saveProjectDraft(item.pid, section, item.data, {
            keepalive: true,
          });
          const cache = JSON.parse(localStorage.getItem(item.key) || "null");
          if (JSON.stringify(cache?.data) === JSON.stringify(item.data))
            localStorage.removeItem(item.key);
          state.value = pending ? "pending" : "saved";
        } catch (e) {
          if (!pending) pending = item;
          state.value = "error";
          throw e;
        }
      });
    return chain;
  }
  function unload() {
    flush().catch(() => {});
  }
  window.addEventListener("pagehide", unload);
  onBeforeUnmount(() => {
    window.removeEventListener("pagehide", unload);
    unload();
  });
  return { state, restore, queue, flush };
}
