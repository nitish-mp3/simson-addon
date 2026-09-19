import { gatewayEndpoints, normalizeSipEndpoint, isGatewaySip } from '../shared/endpoints.js';
import { state } from '../state/store.js';
import { stopMediaPreview, detectMediaDevices, startMediaPreview } from '../features/media/studio.js';
import { render, renderNav } from './shell.js';
import { refresh } from '../services/sync.js';
import { saveSettings, saveIdentity, provision } from '../services/settings.js';
import { addRoute, deleteTarget, setTargetMode, saveCallFeatures, inviteActiveCall, openDirectForwardRoute, openNewAdvancedRoute, editAdvancedRoute, closeAdvancedRoute, addAdvancedStage, removeAdvancedStage, addAdvancedTarget, removeAdvancedTarget, saveAdvancedRoute, setAdvancedRouteEnabled, deleteAdvancedRoute } from '../features/routing/actions.js';
import { discoverPhone, createSip, saveSip, clearStuckSip, deleteSip, addDurationRule, removeDurationRule } from '../features/sip/actions.js';
import { generateWebhook, testNotification, createDoorFlow, deleteTrigger } from '../features/automation/actions.js';
import { renderAutomation } from '../pages/automation.js';
import { splitList } from '../shared/dom.js';
import { getSettings } from '../state/settings.js';
import { setDirty, toast, setSaveState } from '../shared/feedback.js';

export function advancedDefaultIngressValue(kind) {
  if (kind === "gateway") return gatewayEndpoints()[0]?.extension || "";
  if (kind === "sip") {
    return state.sip
      .map(normalizeSipEndpoint)
      .filter(Boolean)
      .find((endpoint) => !isGatewaySip(endpoint))?.extension || "";
  }
  return "";
}

export async function onClick(event) {
  const btn = event.target.closest("button");
  if (!btn) return;

  if (btn.dataset.page) {
    if (state.page === "media" && btn.dataset.page !== "media") stopMediaPreview(false);
    state.page = btn.dataset.page;
    state.navOpen = false;
    render();
    return;
  }

  const action = btn.dataset.action;
  if (!action) return;
  event.preventDefault();

  if (action === "toggle-nav") {
    state.navOpen = !state.navOpen;
    renderNav();
    return;
  }

  // Prevent double-clicks
  if (btn.dataset.loading === "true") return;
  const setLoading = (v) => { btn.dataset.loading = v ? "true" : ""; btn.disabled = v; };

  try {
    setLoading(true);
    if (action === "refresh") await refresh();
    if (action === "save") await saveSettings();
    if (action === "save-identity") await saveIdentity();
    if (action === "provision") await provision();
    if (action === "add-route") addRoute();
    if (action === "delete-target") deleteTarget(btn.dataset.index);
    if (action === "target-mode") setTargetMode(btn.dataset.id, btn.dataset.mode);
    if (action === "call-features-save") await saveCallFeatures();
    if (action === "active-call-invite") await inviteActiveCall();
    if (action === "advanced-direct-forward") openDirectForwardRoute();
    if (action === "advanced-new") openNewAdvancedRoute();
    if (action === "advanced-edit") editAdvancedRoute(btn.dataset.id);
    if (action === "advanced-close") closeAdvancedRoute();
    if (action === "advanced-add-stage") addAdvancedStage();
    if (action === "advanced-remove-stage") removeAdvancedStage(btn.dataset.stage);
    if (action === "advanced-add-target") addAdvancedTarget(btn.dataset.stage);
    if (action === "advanced-remove-target") removeAdvancedTarget(btn.dataset.stage, btn.dataset.target);
    if (action === "advanced-save") await saveAdvancedRoute();
    if (action === "advanced-activate") await setAdvancedRouteEnabled(btn.dataset.id, true);
    if (action === "advanced-delete") await deleteAdvancedRoute(btn.dataset.id);
    if (action === "discover-phone") await discoverPhone();
    if (action === "media-detect") await detectMediaDevices();
    if (action === "media-preview") await startMediaPreview();
    if (action === "media-stop") stopMediaPreview();
    if (action === "media-open-sip") {
      stopMediaPreview(false);
      state.page = "sip";
      render();
    }
    if (action === "create-sip") await createSip();
    if (action === "save-sip") await saveSip(btn.dataset.id);
    if (action === "clear-stuck-sip") await clearStuckSip(btn.dataset.id, btn.dataset.ext);
    if (action === "delete-sip") await deleteSip(btn.dataset.id, btn.dataset.ext);
    if (action === "add-duration-rule") addDurationRule(btn.dataset.id, btn.dataset.targetExt);
    if (action === "remove-duration-rule") removeDurationRule(btn);
    if (action === "generate-webhook") generateWebhook();
    if (action === "test-notification") await testNotification();
    if (action === "toggle-notify-picker") {
      state.notificationPickerOpen = !state.notificationPickerOpen;
      renderAutomation();
    }
    if (action === "remove-notify-target") {
      const selected = new Set(splitList(getSettings().automation.notify_services));
      selected.delete(String(btn.dataset.ref || ""));
      getSettings().automation.notify_services = [...selected].join(", ");
      setDirty("Notification recipients changed. Save Settings to apply.");
      renderAutomation();
    }
    if (action === "create-door-flow") createDoorFlow();
    if (action === "delete-trigger") deleteTrigger(btn.dataset.id);
  } catch (err) {
    const detail = Array.isArray(err.data?.errors) && err.data.errors.length
      ? err.data.errors.join("; ")
      : err.data?.error || err.message || "Action failed";
    toast(detail);
    setSaveState(detail, "bad");
  } finally {
    setLoading(false);
  }
}

