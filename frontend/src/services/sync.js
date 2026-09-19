import { setSaveState } from '../shared/feedback.js';
import { api } from './api.js';
import { state, defaults } from '../state/store.js';
import { deepMerge, $ } from '../shared/dom.js';
import { getSettings } from '../state/settings.js';
import { normalizeSipEndpoint } from '../shared/endpoints.js';
import { render } from '../app/shell.js';

export let liveStatusPollBusy = false;

export let liveStatusSignature = "";

export async function refresh() {
  setSaveState("Refreshing…");
  const [health, status, settings, nodes, sip, routing, advancedRouteResult, callFeatureResult, notificationTargetResult] = await Promise.all([
    api("api/health").catch(() => null),
    api("api/status").catch(() => null),
    api("api/settings").catch(() => null),
    api("api/nodes").catch(() => ({ nodes: [] })),
    api("api/sip-endpoints").catch(() => []),
    api("api/routing").catch(() => null),
    api("api/advanced-routes")
      .then((data) => ({ data, error: "" }))
      .catch((error) => ({ data: [], error: error?.message || "Request failed" })),
    api("api/call-features")
      .then((data) => ({ data, error: "" }))
      .catch((error) => ({ data: null, error: error?.message || "Phone controls could not be loaded" })),
    api("api/notification-targets")
      .then((data) => ({ data, error: "" }))
      .catch((error) => ({ data: { targets: [] }, error: error?.message || "Notification discovery failed" })),
  ]);
  state.health = health;
  state.status = status;
  liveStatusSignature = statusSignature(status);
  state.settings = settings ? deepMerge(defaults, settings) : getSettings();
  state.nodes = Array.isArray(nodes?.nodes) ? nodes.nodes : [];
  const sipItems = Array.isArray(sip) ? sip : Array.isArray(sip?.endpoints) ? sip.endpoints : [];
  state.sip = sipItems.map(normalizeSipEndpoint).filter(Boolean);
  state.routing = routing;
  state.advancedRoutes = Array.isArray(advancedRouteResult.data) ? advancedRouteResult.data : [];
  state.advancedRoutesError = advancedRouteResult.error || "";
  if (callFeatureResult.data) state.callFeatures = callFeatureResult.data;
  state.callFeaturesError = callFeatureResult.error || "";
  state.notificationTargets = Array.isArray(notificationTargetResult.data?.targets) ? notificationTargetResult.data.targets : [];
  state.notificationTargetsError = notificationTargetResult.error || "";
  if (state.advancedDraft?.id) {
    const freshDraft = state.advancedRoutes.find((route) => route.id === state.advancedDraft.id);
    state.advancedDraft = freshDraft ? structuredClone(freshDraft) : null;
  }
  state.loaded = true;
  if (!state.dirty) setSaveState("Everything saved", "ok");
  render();
}

export function statusSignature(status) {
  const active = status?.active_call || null;
  return JSON.stringify({
    connected: Boolean(status?.vps_connected),
    asterisk: Boolean(status?.asterisk_connected),
    active: active ? {
      call_id: active.call_id || "",
      state: active.state || "",
      direction: active.direction || "",
      caller: active.caller || active.from || active.source || "",
      callee: active.callee || active.to || active.target || "",
      started_at: active.started_at || active.created_at || "",
      active_for: Number(active.active_for || active.duration_seconds || 0),
    } : null,
  });
}

export async function refreshLiveStatus() {
  if (!state.loaded || liveStatusPollBusy || document.hidden) return;
  liveStatusPollBusy = true;
  try {
    const status = await api("api/status");
    const signature = statusSignature(status);
    if (signature === liveStatusSignature) return;
    state.status = status;
    liveStatusSignature = signature;
    if (state.page === "overview") await render();
    const connection = $("side-conn");
    if (connection) {
      connection.innerHTML = status?.vps_connected
        ? '<span style="color:var(--success)">Online</span>'
        : '<span style="color:var(--danger)">Offline</span>';
    }
  } catch (_) {
    // The regular refresh path reports persistent failures; a transient poll must not disrupt editing.
  } finally {
    liveStatusPollBusy = false;
  }
}
