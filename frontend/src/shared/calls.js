import { state } from '../state/store.js';
import { normalizeSipEndpoint } from './endpoints.js';

export function activeCallDisplay(active) {
  if (!active) return "Call";
  const extension = String(
    active.direction === "incoming"
      ? (active.source_extension || active.caller_number || active.caller_id || "")
      : (active.target_extension || active.callee_number || active.remote_number || ""),
  ).trim();
  const endpoint = state.sip
    .map(normalizeSipEndpoint)
    .find((item) => item && String(item.extension) === extension);
  return active.display_name
    || active.remote_name
    || active.caller_name
    || active.callee_name
    || endpoint?.description
    || extension
    || active.remote_label
    || active.remote_node_id
    || "Active call";
}

export function activeCallSubtitle(active) {
  const direction = active?.direction === "incoming" ? "Incoming" : "Outgoing";
  const route = active?.routing?.target_label
    || active?.routing?.target_id
    || active?.target_label
    || active?.target_type
    || active?.call_type
    || "voice";
  const elapsed = Number(active?.active_for || active?.duration_seconds || 0);
  return `${direction} · ${route}${elapsed > 0 ? ` · ${Math.floor(elapsed)}s` : ""}`;
}

