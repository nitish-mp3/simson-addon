import { $, option, esc } from '../../shared/dom.js';
import { state } from '../../state/store.js';
import { api } from '../../services/api.js';
import { toast, setDirty } from '../../shared/feedback.js';
import { refresh } from '../../services/sync.js';
import { selectedPhoneProvisioningProfile, renderPhoneProvisioningResult } from './provisioning.js';
import { normalizeSipEndpoint, isGatewaySip, normalizeCallDurationRules, gatewayRoutePlan } from '../../shared/endpoints.js';

export async function createSip() {
  const payload = {
    extension: $("sip-ext").value.trim(),
    username: $("sip-user").value.trim() || $("sip-ext").value.trim(),
    password: $("sip-pass").value.trim(),
    description: $("sip-desc").value.trim(),
    route_to: $("sip-route").value.trim(),
    default_outbound: $("sip-default-outbound").checked,
    video_enabled: $("sip-video").checked,
    pre_ring_announcement_text: $("sip-pre-ring-announcement-text").value.trim(),
    answer_announcement_text: $("sip-answer-announcement-text").value.trim(),
    call_duration_rules: {},
    auto_answer: $("sip-auto-answer").checked,
    auto_answer_callers: $("sip-auto-answer-callers").value.trim(),
    auto_speaker: $("sip-auto-speaker").checked,
    auto_speaker_callers: $("sip-auto-speaker-callers").value.trim(),
    callback_bridge: $("sip-callback-bridge").checked,
    callback_bridge_callers: $("sip-callback-callers").value.trim(),
    callback_caller_auto_answer: $("sip-callback-caller-auto-answer").checked,
    callback_caller_auto_speaker: $("sip-callback-caller-auto-speaker").checked,
    enabled: true,
  };
  if (state.phoneProvisioning.enabled) {
    const slot = $("sip-phone-slot")?.value || state.phoneProvisioning.selectedSlot;
    if (!state.phoneProvisioning.sessionId) {
      throw new Error("Test the phone management connection before creating the SIP account.");
    }
    if (!slot) throw new Error("Select an available phone account slot.");
    payload.phone_provisioning = {
      session_id: state.phoneProvisioning.sessionId,
      slot: Number(slot),
      transport: $("sip-phone-transport")?.value || "tcp",
    };
  }
  const result = await api("api/sip-endpoints", { method: "POST", body: JSON.stringify(payload) });
  const configured = result.phone_provisioning;
  state.phoneProvisioning = {
    enabled: false,
    sessionId: "",
    slots: [],
    selectedSlot: "",
    deviceName: "",
    phoneIp: "",
  };
  toast(configured ? `SIP phone created and Account ${configured.slot} configured.` : "SIP phone created.");
  await refresh();
}

export async function discoverPhone() {
  const profile = selectedPhoneProvisioningProfile();
  if (profile?.automatic_write === false) {
    throw new Error(profile.help || "This phone family requires its vendor provisioning-server workflow.");
  }
  const required = {
    ip: $("sip-phone-ip")?.value.trim(),
    admin_username: $("sip-phone-admin-user")?.value.trim(),
    admin_password: $("sip-phone-admin-pass")?.value || "",
  };
  if (!required.ip || !required.admin_username || !required.admin_password) {
    throw new Error("Phone IP, administrator username, and administrator password are all required for automatic setup.");
  }
  const result = await api("api/phone-provision/discover", {
    method: "POST",
    body: JSON.stringify({
      profile: $("sip-phone-profile")?.value || "grandstream_gsc36xx",
      ip: required.ip,
      scheme: $("sip-phone-scheme")?.value || "https",
      port: Number($("sip-phone-port")?.value || 443),
      admin_username: required.admin_username,
      admin_password: required.admin_password,
      verify_tls: Boolean($("sip-phone-verify-tls")?.checked),
    }),
  });
  state.phoneProvisioning.sessionId = result.session_id;
  state.phoneProvisioning.slots = Array.isArray(result.slots) ? result.slots : [];
  state.phoneProvisioning.selectedSlot = "";
  state.phoneProvisioning.deviceName = result.device_name || result.profile || "Supported phone";
  state.phoneProvisioning.phoneIp = result.phone_ip || required.ip;
  renderPhoneProvisioningResult();
  toast("Phone verified. Select an available account slot.");
}

export function sipFieldValue(endpointId, key) {
  const el = document.querySelector(`[data-sip-id="${CSS.escape(endpointId)}"][data-sip-key="${key}"]`);
  if (!el) return "";
  return el.type === "checkbox" ? el.checked : el.value.trim();
}

export function durationSourceOptions(targetExtension, selected = "") {
  const sources = state.sip
    .map(normalizeSipEndpoint)
    .filter((ep) => ep && ep.enabled !== false && ep.extension && ep.extension !== targetExtension && !isGatewaySip(ep));
  const options = [`<option value="">Select caller phone</option>`];
  if (selected && !sources.some((ep) => ep.extension === selected)) {
    options.push(option(selected, `${selected} (unavailable; remove or replace)`, selected));
  }
  sources.forEach((ep) => options.push(option(ep.extension, `${ep.extension}${ep.description ? ` · ${ep.description}` : ""}`, selected)));
  return options.join("");
}

export function durationRuleRow(endpointId, targetExtension, source = "", seconds = "") {
  return `
    <div class="duration-rule-row" data-duration-target="${esc(endpointId)}">
      <div class="route-pair">
        <select data-duration-key="source">${durationSourceOptions(targetExtension, source)}</select>
        <span class="route-arrow">→</span>
        <span class="route-target">${esc(targetExtension || "target")}</span>
      </div>
      <label class="duration-seconds"><input type="number" min="1" max="86400" step="1" data-duration-key="seconds" value="${esc(seconds)}" placeholder="15"><span>seconds connected</span></label>
      <button class="icon-btn danger" type="button" data-action="remove-duration-rule" aria-label="Remove call limit">×</button>
    </div>`;
}

export function durationRuleRows(endpointId, targetExtension, rules) {
  return Object.entries(normalizeCallDurationRules(rules))
    .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
    .map(([source, seconds]) => durationRuleRow(endpointId, targetExtension, source, seconds))
    .join("");
}

export function addDurationRule(endpointId, targetExtension) {
  const list = document.querySelector(`[data-duration-list="${CSS.escape(endpointId)}"]`);
  if (!list) return;
  list.insertAdjacentHTML("beforeend", durationRuleRow(endpointId, targetExtension));
  setDirty("Call duration rule added. Choose a caller and save the SIP device.");
}

export function removeDurationRule(button) {
  button.closest(".duration-rule-row")?.remove();
  setDirty("Call duration rule removed. Save the SIP device to apply it.");
}

export function collectDurationRules(endpointId, targetExtension) {
  const rules = {};
  const rows = document.querySelectorAll(`[data-duration-target="${CSS.escape(endpointId)}"]`);
  rows.forEach((row) => {
    const source = row.querySelector('[data-duration-key="source"]')?.value.trim() || "";
    const rawSeconds = row.querySelector('[data-duration-key="seconds"]')?.value.trim() || "";
    if (!source && !rawSeconds) return;
    const seconds = Number(rawSeconds);
    if (!/^\d{2,12}$/.test(source)) throw new Error("Choose a valid source SIP extension for every call limit.");
    if (source === String(targetExtension || "")) throw new Error("A call limit source and target cannot be the same phone.");
    if (!Number.isInteger(seconds) || seconds < 1 || seconds > 86400) throw new Error("Connected call duration must be between 1 and 86400 seconds.");
    if (Object.prototype.hasOwnProperty.call(rules, source)) throw new Error(`Only one call limit is allowed for source ${source}.`);
    rules[source] = seconds;
  });
  return rules;
}

export function collectSupervisionTargets(endpointId) {
  return Array.from(document.querySelectorAll(`[data-supervision-owner="${CSS.escape(endpointId)}"][data-supervision-target]:checked`))
    .map((item) => String(item.dataset.supervisionTarget || "").trim())
    .filter(Boolean);
}

export function renderedSipEndpointIds() {
  return Array.from(document.querySelectorAll("[data-sip-id][data-sip-key]"))
    .map((el) => el.dataset.sipId)
    .filter(Boolean)
    .filter((id, index, all) => all.indexOf(id) === index);
}

export function sipUpdatePayload(endpointId) {
  const endpoint = state.sip.map(normalizeSipEndpoint).find((ep) => String(ep?.id || ep?.extension || ep?.username) === String(endpointId));
  const payload = {
    description: sipFieldValue(endpointId, "description"),
    route_to: sipFieldValue(endpointId, "route_to"),
    default_outbound: Boolean(sipFieldValue(endpointId, "default_outbound")),
    video_enabled: Boolean(sipFieldValue(endpointId, "video_enabled")),
    auto_answer: Boolean(sipFieldValue(endpointId, "auto_answer")),
    auto_answer_callers: sipFieldValue(endpointId, "auto_answer_callers"),
    auto_speaker: Boolean(sipFieldValue(endpointId, "auto_speaker")),
    auto_speaker_callers: sipFieldValue(endpointId, "auto_speaker_callers"),
    callback_bridge: Boolean(sipFieldValue(endpointId, "callback_bridge")),
    callback_bridge_callers: sipFieldValue(endpointId, "callback_bridge_callers"),
    callback_caller_auto_answer: Boolean(sipFieldValue(endpointId, "callback_caller_auto_answer")),
    callback_caller_auto_speaker: Boolean(sipFieldValue(endpointId, "callback_caller_auto_speaker")),
    gateway_inbound_mode: sipFieldValue(endpointId, "gateway_inbound_mode"),
    gateway_direct_target: sipFieldValue(endpointId, "gateway_direct_target"),
    gateway_ivr_enabled: Boolean(sipFieldValue(endpointId, "gateway_ivr_enabled")),
    gateway_ivr_sound: sipFieldValue(endpointId, "gateway_ivr_sound"),
    pre_ring_announcement_text: sipFieldValue(endpointId, "pre_ring_announcement_text"),
    answer_announcement_text: sipFieldValue(endpointId, "answer_announcement_text"),
    call_duration_rules: collectDurationRules(endpointId, endpoint?.extension || ""),
    supervision: {
      enabled: Boolean(sipFieldValue(endpointId, "supervision_enabled")),
      listen: Boolean(sipFieldValue(endpointId, "supervision_listen")),
      listen_key: sipFieldValue(endpointId, "supervision_listen_key") || "*81",
      whisper: Boolean(sipFieldValue(endpointId, "supervision_whisper")),
      whisper_key: sipFieldValue(endpointId, "supervision_whisper_key") || "*82",
      barge: Boolean(sipFieldValue(endpointId, "supervision_barge")),
      barge_key: sipFieldValue(endpointId, "supervision_barge_key") || "*83",
      targets: collectSupervisionTargets(endpointId),
    },
    enabled: Boolean(sipFieldValue(endpointId, "enabled")),
  };
  const password = sipFieldValue(endpointId, "password");
  if (password) payload.password = password;
  return payload;
}

export function validateGatewayInboundPayload(payload) {
  const mode = String(payload?.gateway_inbound_mode || "").trim();
  const target = String(payload?.gateway_direct_target || "").trim();
  if (mode === "direct_target" && !target) {
    throw new Error("Choose an immediate gateway target, or use the HAOS fallback mode.");
  }
  if (!target.startsWith("route_")) return;
  const plan = gatewayRoutePlan(target);
  if (!plan || plan.enabled === false) {
    throw new Error("The selected gateway route plan is unavailable. Choose an enabled plan before saving.");
  }
  if (mode !== "direct_target") {
    throw new Error("A multi-stage route plan requires “Send directly to this target” for gateway inbound calls.");
  }
}

export async function saveRenderedSipEdits() {
  const ids = renderedSipEndpointIds();
  if (!ids.length) return 0;
  for (const endpointId of ids) {
    const payload = sipUpdatePayload(endpointId);
    validateGatewayInboundPayload(payload);
    await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }
  return ids.length;
}

export async function saveSip(endpointId) {
  if (!endpointId) {
    toast("Missing SIP endpoint ID.");
    return;
  }
  const payload = sipUpdatePayload(endpointId);
  validateGatewayInboundPayload(payload);
  const password = Boolean(payload.password);
  const saved = await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  if (saved.save_verified !== true) {
    throw new Error("SIP device response was not verified; settings were not reported as saved.");
  }
  toast(password ? "SIP device saved, verified, and password rotated." : "SIP device saved and verified.");
  await refresh();
}

export async function deleteSip(endpointId, extension) {
  if (!endpointId) {
    toast("Missing SIP endpoint ID.");
    return;
  }
  const label = extension || endpointId;
  const endpoint = state.sip
    .map(normalizeSipEndpoint)
    .find((ep) => String(ep.id || ep.extension || ep.username) === String(endpointId));
  const gateway = endpoint ? isGatewaySip(endpoint) : /^70[0-9]{2}$/.test(String(label || ""));
  if (gateway) {
    const typed = prompt(`Gateway ${label} is protected because deleting it can break live PSTN/GSM/FXO calling.\n\nType ${label} to confirm deletion.`);
    if (typed !== String(label)) {
      toast("Gateway deletion cancelled.");
      return;
    }
  }
  if (!confirm(`Delete SIP device ${label}? The phone will stop registering until you create it again.`)) {
    return;
  }
  await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}`, { method: "DELETE" });
  toast(`SIP device ${label} deleted.`);
  await refresh();
}

export async function clearStuckSip(endpointId, extension) {
  if (!endpointId) return;
  const label = extension || endpointId;
  if (!confirm(`Clear live channels for ${label}? This only releases calls currently using this endpoint.`)) return;
  const result = await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}/clear-stuck`, { method: "POST" });
  if (result.cleared) {
    toast(`Released ${result.cleared} linked Asterisk channel${result.cleared === 1 ? "" : "s"} on ${label}.`);
  } else if (result.hardware_action_required) {
    toast(`Asterisk is clear, but gateway ${label} still owns the analog line. Enable CPC/busy-tone/polarity disconnect on that gateway or release its FXO port.`);
  } else {
    toast(`Asterisk has no live channel for ${label}.`);
  }
  await refresh();
}

