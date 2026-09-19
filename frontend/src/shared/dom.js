export const $ = (id) => document.getElementById(id);

export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#39;",
}[ch]));

export function deepMerge(base, override) {
  const out = structuredClone(base);
  Object.entries(override || {}).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value) && out[key] && typeof out[key] === "object" && !Array.isArray(out[key])) {
      out[key] = deepMerge(out[key], value);
    } else {
      out[key] = structuredClone(value);
    }
  });
  return out;
}

export function option(value, label, selected) {
  return `<option value="${esc(value)}" ${String(selected) === String(value) ? "selected" : ""}>${esc(label)}</option>`;
}

export function splitList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

export function slug(value) {
  return String(value || "route")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64) || `route_${Date.now()}`;
}

