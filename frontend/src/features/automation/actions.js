import { setSaveState, toast, setDirty } from '../../shared/feedback.js';
import { api } from '../../services/api.js';
import { getSettings } from '../../state/settings.js';
import { randomHex, effectiveDoorCooldown, sourceSipLabel } from './helpers.js';
import { renderAutomation } from '../../pages/automation.js';
import { $ } from '../../shared/dom.js';
import { state } from '../../state/store.js';

export async function testNotification() {
  setSaveState("Testing notification…");
  const result = await api("api/notification/test", {
    method: "POST",
    body: JSON.stringify({
      notify_services: getSettings().automation.notify_services || "",
    }),
  });
  const sent = Number(result.sent || 0);
  const total = Number(result.total || 0);
  if (sent > 0) {
    toast(`Notification test sent to ${sent}/${total} target(s).`);
    setSaveState("Notification test sent", "ok");
    return;
  }
  throw new Error("No notification target accepted the test message.");
}

export function generateWebhook() {
  const auto = getSettings().automation;
  auto.webhook_enabled = true;
  auto.webhook_id = auto.webhook_id || `site_${randomHex(16)}`;
  auto.webhook_secret = randomHex(24) + randomHex(24);
  setDirty("Webhook credentials generated. Save to activate.");
  renderAutomation();
}

export function createDoorFlow() {
  const source = $("door-source").value;
  const targets = Array.from(document.querySelectorAll(".door-target-check:checked")).map((el) => el.value);
  const label = $("door-label").value.trim() || "Unknown visitor";
  const triggerSelect = $("door-trigger-select");
  const selectedTriggerId = triggerSelect ? triggerSelect.value : "";
  const rawCooldown = Number($("door-cooldown").value);
  const cooldown = effectiveDoorCooldown(rawCooldown || getSettings().automation.cooldown_seconds);
  if (!source || !targets.length) {
    toast("Pick the outdoor source and at least one destination.");
    return;
  }
  const sourceAsTarget = targets.some((targetId) => {
    const target = getSettings().call_targets.find((item) => String(item.id) === String(targetId));
    return ["sip", "asterisk"].includes(target?.type) && String(target.extension || "").trim() === String(source);
  });
  if (sourceAsTarget) {
    toast("Outdoor source cannot also be a SIP destination.");
    return;
  }
  const selectedTargets = targets
    .map((targetId) => getSettings().call_targets.find((item) => String(item.id) === String(targetId)))
    .filter(Boolean);
  const sipCount = selectedTargets.filter((target) => ["sip", "asterisk"].includes(target.type)).length;
  const haosCount = selectedTargets.filter((target) => ["node", "device"].includes(target.type)).length;
  if (sipCount > 1 && haosCount === 0 && $("door-fanout").value !== "priority") {
    toast("Native SIP video supports one monitor at a time. Add a HAOS target for shared fanout, or choose priority order.");
    return;
  }
  if (rawCooldown && rawCooldown < cooldown) {
    $("door-cooldown").value = cooldown;
    toast(`Door cooldown raised to ${cooldown}s minimum to prevent spam.`);
  }
  const automation = getSettings().automation;
  let existingDoor = null;
  if (selectedTriggerId) {
    existingDoor = (automation.triggers || []).find((item) => String(item.id || "") === String(selectedTriggerId));
    if (existingDoor && existingDoor.source_extension !== source) {
      existingDoor = null;
    }
  }
  const triggerId = String(existingDoor?.id || "").trim() || `door_${randomHex(10)}`;
  const trigger = {
    id: triggerId,
    label,
    enabled: true,
    mode: "door_station",
    target_id: targets[0],
    target_ids: targets,
    fanout_mode: $("door-fanout").value || "parallel",
    source_extension: source,
    caller_id: $("door-caller").value.trim() || label,
    timeout: Number($("door-timeout").value) || 30,
    cooldown_seconds: cooldown,
  };
  automation.triggers = automation.triggers || [];
  if (existingDoor) {
    const existingIndex = automation.triggers.indexOf(existingDoor);
    if (existingIndex >= 0) {
      automation.triggers[existingIndex] = trigger;
    } else {
      automation.triggers.push(trigger);
    }
  } else {
    automation.triggers.push(trigger);
  }
  state.selectedDoorTriggerId = triggerId;
  if (!automation.webhook_id || !automation.webhook_secret || automation.webhook_secret.length < 24) {
    automation.webhook_enabled = true;
    automation.webhook_id = automation.webhook_id || `site_${randomHex(16)}`;
    automation.webhook_secret = automation.webhook_secret && automation.webhook_secret.length >= 24
      ? automation.webhook_secret
      : randomHex(24) + randomHex(24);
  }
  const modeText = sipCount && haosCount
    ? "shared bridge fanout"
    : sipCount
      ? "native SIP video"
      : "HAOS browser bridge";
  setDirty(`Door flow ready: ${sourceSipLabel(source)} to ${targets.length} destination(s) using ${modeText}. Save once; the outdoor device URL stays the same.`);
  renderAutomation();
}

export function deleteTrigger(id) {
  const auto = getSettings().automation;
  auto.triggers = auto.triggers.filter((item) => item.id !== id);
  setDirty("Trigger deleted. Save to keep it.");
  renderAutomation();
}

