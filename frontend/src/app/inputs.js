import { mediaStudio, state } from '../state/store.js';
import { $, splitList } from '../shared/dom.js';
import { saveMediaPreferences, startMediaPreview, renderMediaStudio } from '../features/media/studio.js';
import { getSettings, setByPath } from '../state/settings.js';
import { setDirty } from '../shared/feedback.js';
import { renderAutomation, refreshIntercomUrl } from '../pages/automation.js';
import { advancedDefaultIngressValue } from './clicks.js';
import { renderRouting } from '../pages/routing.js';
import { advancedDefaultTargetValue } from '../features/routing/actions.js';
import { defaultGatewayTrunk } from '../shared/endpoints.js';
import { invalidatePhoneProvisioningTest, updatePhoneProfileHelp } from '../features/sip/provisioning.js';
import { syncDoorFlowForm, effectiveDoorCooldown } from '../features/automation/helpers.js';

export function onInput(event) {
  const el = event.target;

  if (["media-audio-input", "media-video-input", "media-audio-output", "media-video-enabled"].includes(el.id)) {
    mediaStudio.selectedAudioInput = $("media-audio-input")?.value || mediaStudio.selectedAudioInput;
    mediaStudio.selectedVideoInput = $("media-video-input")?.value || mediaStudio.selectedVideoInput;
    mediaStudio.selectedAudioOutput = $("media-audio-output")?.value || mediaStudio.selectedAudioOutput;
    mediaStudio.videoEnabled = $("media-video-enabled")?.checked !== false;
    saveMediaPreferences();
    if (mediaStudio.previewStream) startMediaPreview();
    else if (el.id === "media-video-enabled") renderMediaStudio();
    return;
  }

  if (el.id === "notify-target-search") {
    const query = String(el.value || "").trim().toLowerCase();
    document.querySelectorAll("[data-notify-search]").forEach((row) => {
      row.hidden = Boolean(query) && !String(row.dataset.notifySearch || "").includes(query);
    });
    return;
  }

  if (el.matches("[data-notify-target]")) {
    const selected = new Set(splitList(getSettings().automation.notify_services));
    if (el.checked) selected.add(el.dataset.notifyTarget);
    else selected.delete(el.dataset.notifyTarget);
    getSettings().automation.notify_services = [...selected].join(", ");
    state.notificationPickerOpen = true;
    setDirty("Notification recipients changed. Save Settings to apply.");
    renderAutomation();
    return;
  }

  if (el.matches("[data-advanced-route-key]")) {
    if (!state.advancedDraft) return;
    const key = el.dataset.advancedRouteKey;
    state.advancedDraft[key] = el.type === "checkbox" ? el.checked : el.value;
    if (key === "ingress_kind") {
      state.advancedDraft.ingress_value = advancedDefaultIngressValue(el.value);
      renderRouting();
    }
    return;
  }

  if (el.matches("[data-call-feature-key]")) {
    const key = el.dataset.callFeatureKey;
    state.callFeatures[key] = el.type === "checkbox" ? el.checked : el.value;
    return;
  }

  if (el.matches("[data-active-invite-key]")) {
    state.activeInvite[el.dataset.activeInviteKey] = el.value;
    return;
  }

  if (el.matches("[data-advanced-stage-index][data-advanced-stage-key]")) {
    const stage = state.advancedDraft?.stages?.[Number(el.dataset.advancedStageIndex)];
    if (!stage) return;
    const key = el.dataset.advancedStageKey;
    const previousValue = stage[key];
    stage[key] = el.type === "number" ? Number(el.value) : el.value;
    if (key === "answer_mode") {
      stage.max_answered = el.value === "first_answer" ? 1 : Math.max(2, Number(stage.max_answered) || 2);
      if (el.value === "private_hub") {
        state.advancedDraft.enabled = false;
        state.advancedDraft._disabled_for_private_hub = true;
      } else if (
        previousValue === "private_hub"
        && state.advancedDraft._disabled_for_private_hub
        && !state.advancedDraft.stages.some((item) => item.answer_mode === "private_hub")
      ) {
        state.advancedDraft.enabled = true;
        delete state.advancedDraft._disabled_for_private_hub;
      }
      renderRouting();
    }
    return;
  }

  if (el.matches("[data-advanced-target-stage][data-advanced-target-index][data-advanced-target-key]")) {
    const target = state.advancedDraft?.stages?.[Number(el.dataset.advancedTargetStage)]?.targets?.[Number(el.dataset.advancedTargetIndex)];
    if (!target) return;
    const key = el.dataset.advancedTargetKey;
    target[key] = el.type === "checkbox" ? el.checked : el.value;
    if (key === "kind") {
      target.value = advancedDefaultTargetValue(el.value);
      target.trunk = el.value === "external" ? defaultGatewayTrunk() : "";
      renderRouting();
    }
    return;
  }

  if (el.id === "sip-phone-provision-enabled") {
    state.phoneProvisioning.enabled = el.checked;
    $("sip-phone-provision-panel")?.classList.toggle("hidden", !el.checked);
    if (!el.checked) invalidatePhoneProvisioningTest();
    return;
  }

  if (el.id === "sip-phone-slot") {
    state.phoneProvisioning.selectedSlot = el.value;
    return;
  }

  if (el.matches("[data-phone-connection]")) {
    if (el.id === "sip-phone-scheme") {
      const port = $("sip-phone-port");
      if (port && ["80", "443", ""].includes(port.value)) port.value = el.value === "https" ? "443" : "80";
    }
    invalidatePhoneProvisioningTest();
    if (el.id === "sip-phone-profile") updatePhoneProfileHelp();
    return;
  }

  // Handle door flow selects via delegation instead of inline onchange
  if (el.id === "door-source" || el.id === "door-trigger-select") {
    syncDoorFlowForm();
    return;
  }

  if (el.id && el.id.startsWith("intercom-")) {
    refreshIntercomUrl();
    return;
  }

  if (el.matches("[data-sip-id][data-sip-key]")) {
    setDirty("SIP device edited. Save Settings or Save Device to apply it.");
    return;
  }
  if (el.matches("[data-path]")) {
    let value = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
    if (el.dataset.path === "automation.cooldown_seconds") {
      value = effectiveDoorCooldown(value);
      if (el.type === "number" && Number(el.value) < value) el.value = value;
    }
    setByPath(el.dataset.path, value);
    setDirty();
  }
  if (el.matches("[data-target]")) {
    const target = getSettings().call_targets[Number(el.dataset.target)];
    if (!target) return;
    if (el.dataset.key === "fallback_targets_text") {
      target.fallback_targets = splitList(el.value);
    } else {
      target[el.dataset.key] = el.value;
    }
    setDirty();
  }
}

