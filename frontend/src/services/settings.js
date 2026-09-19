import { $ } from '../shared/dom.js';
import { api } from './api.js';
import { toast, setSaveState } from '../shared/feedback.js';
import { refresh } from './sync.js';
import { saveRenderedSipEdits } from '../features/sip/actions.js';
import { getSettings } from '../state/settings.js';
import { effectiveDoorCooldown } from '../features/automation/helpers.js';
import { state } from '../state/store.js';

export async function provision() {
  const form = $("setup-form");
  const payload = Object.fromEntries(new FormData(form).entries());
  await api("api/provision", { method: "POST", body: JSON.stringify(payload) });
  toast("Provisioned. Reloading…");
  setTimeout(() => location.reload(), 900);
}

export async function saveIdentity() {
  const payload = {
    account_id: $("identity-account")?.value.trim() || "",
    node_id: $("identity-node")?.value.trim() || "",
    install_token: $("identity-token")?.value.trim() || "",
    node_label: $("identity-label")?.value.trim() || "",
  };
  if (!payload.account_id || !payload.node_id) {
    toast("Account ID and Node ID are required.");
    return;
  }
  const result = await api("api/identity", { method: "POST", body: JSON.stringify(payload) });
  const verb = result.action === "provisioned" ? "created and saved" : "validated and saved";
  toast(`Identity ${verb}. Restart the addon to reconnect with the new account.`);
  await refresh();
}

export async function saveSettings() {
  setSaveState("Saving…");
  const sipSaved = await saveRenderedSipEdits();
  const payload = getSettings();
  payload.automation.cooldown_seconds = effectiveDoorCooldown(payload.automation.cooldown_seconds);
  payload.automation.triggers = (payload.automation.triggers || []).map((trigger) => {
    if (trigger?.mode !== "door_station") return trigger;
    return {
      ...trigger,
      cooldown_seconds: effectiveDoorCooldown(trigger.cooldown_seconds || payload.automation.cooldown_seconds),
      target_ids: Array.isArray(trigger.target_ids) && trigger.target_ids.length
        ? trigger.target_ids
        : [trigger.target_id].filter(Boolean),
    };
  });
  const saved = await api("api/settings", { method: "POST", body: JSON.stringify(payload) });
  state.dirty = false;
  setSaveState("Saved", "ok");
  const gatewaySync = saved?.gateway_default_sync;
  if (gatewaySync && gatewaySync.ok === false && !gatewaySync.skipped) {
    toast(`Settings saved, but VPS default gateway did not sync: ${gatewaySync.reason || "unknown error"}`);
  } else {
    toast(sipSaved ? `Settings saved. ${sipSaved} SIP device(s) updated.` : "Settings saved.");
  }
  await refresh();
}

