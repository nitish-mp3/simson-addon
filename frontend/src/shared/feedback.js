import { state } from '../state/store.js';
import { $ } from './dom.js';

export function setDirty(message = "Unsaved changes") {
  state.dirty = true;
  setSaveState(message);
}

export function setSaveState(text, tone = "") {
  const el = $("save-state");
  const top = $("top-save-state");
  for (const target of [el, top]) {
    if (!target) continue;
    target.textContent = text || "Everything saved";
    target.dataset.tone = tone;
  }
}

export function toast(text) {
  const el = $("toast");
  if (!el) return;
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2800);
}
