import { getSettings } from '../../state/settings.js';
import { defaults, state } from '../../state/store.js';
import { $ } from '../../shared/dom.js';
import { renderAutomation, targetDisplayName } from '../../pages/automation.js';
import { normalizeSipEndpoint } from '../../shared/endpoints.js';

export function externalBaseUrl() {
  const settings = getSettings();
  const port = String(settings.local_api_port || defaults.local_api_port || 8799);
  const host = window.location.hostname || "homeassistant.local";
  const direct = window.location.port === port;
  const protocol = direct ? window.location.protocol : "http:";
  return `${protocol}//${host}:${port}`;
}

export function deviceCallbackPath(triggerId = "TRIGGER_ID") {
  const auto = getSettings().automation;
  return `/api/automation/device/${auto.webhook_id || "WEBHOOK_ID"}/${triggerId}`;
}

export function deviceCallbackUrl(triggerId = "TRIGGER_ID") {
  return `${externalBaseUrl()}${deviceCallbackPath(triggerId)}`;
}

export function stableDoorCallbackPath() {
  const auto = getSettings().automation;
  return `/api/automation/webhook/${auto.webhook_id || "WEBHOOK_ID"}`;
}

export function stableDoorCallbackUrl() {
  return `${externalBaseUrl()}${stableDoorCallbackPath()}`;
}

export function randomHex(bytes = 24) {
  const values = new Uint8Array(bytes);
  if (window.crypto && typeof window.crypto.getRandomValues === "function") {
    window.crypto.getRandomValues(values);
  } else {
    for (let i = 0; i < values.length; i += 1) {
      values[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(values, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function syncDoorFlowForm() {
  const selected = $("door-trigger-select")?.value || "";
  const selectedDoor = selected ? (getSettings().automation.triggers || []).find((t) => t.id === selected) : null;
  const currentSource = $("door-source")?.value || "";
  const previousId = state.selectedDoorTriggerId;

  if (selectedDoor && selectedDoor.source_extension && selectedDoor.source_extension !== currentSource) {
    state.selectedDoorTriggerId = "";
  } else {
    state.selectedDoorTriggerId = selected;
  }

  // Only re-render if the selection actually changed — prevents choppy DOM thrash
  if (state.selectedDoorTriggerId !== previousId) {
    renderAutomation();
  }
}

export function effectiveDoorCooldown(value) {
  const parsed = Number(value);
  const safe = Number.isFinite(parsed) && parsed > 0 ? parsed : 90;
  return Math.max(20, Math.min(3600, Math.round(safe)));
}

export function sourceSipLabel(extension) {
  const ext = String(extension || "").trim();
  if (!ext) return "No outdoor source selected";
  const ep = state.sip.map(normalizeSipEndpoint).find((item) => item && String(item.extension) === ext);
  const label = ep?.description || ep?.username || ext;
  return `${label} (${ext})`;
}

export function targetListText(ids) {
  const list = Array.isArray(ids) ? ids.filter(Boolean) : [];
  if (!list.length) return "No destinations selected";
  return list.map(targetDisplayName).join(" + ");
}

