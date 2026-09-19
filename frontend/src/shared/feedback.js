import { state } from '../state/store.js';
import { $ } from './dom.js';

export function setDirty(message = "Unsaved changes") {
  state.dirty = true;
  setSaveState(message);
}

export function setSaveState(text, tone = "") {
  const el = $("save-state");
  if (!el) return;
  el.textContent = text || "Everything saved";
  el.style.color = tone === "bad" ? "var(--danger)" : tone === "ok" ? "var(--success)" : "var(--text-secondary)";
}

export function toast(text) {
  const el = $("toast");
  if (!el) return;
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2800);
}

