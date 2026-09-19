import { state } from '../state/store.js';
import { getSettings } from '../state/settings.js';
import { option } from './dom.js';

export function normalizeCallDurationRules(value) {
  if (typeof value === "string") {
    try { value = JSON.parse(value || "{}"); } catch (_) { value = {}; }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const result = {};
  Object.entries(value).forEach(([source, seconds]) => {
    const sourceExt = String(source || "").trim();
    const duration = Number(seconds);
    if (sourceExt && Number.isInteger(duration) && duration >= 1 && duration <= 86400) {
      result[sourceExt] = duration;
    }
  });
  return result;
}

export function normalizeSupervision(value) {
  if (typeof value === "string") {
    try { value = JSON.parse(value || "{}"); } catch (_) { value = {}; }
  }
  const config = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  return {
    enabled: Boolean(config.enabled ?? config.Enabled ?? false),
    listen: Boolean(config.listen ?? config.Listen ?? false),
    listen_key: String(config.listen_key ?? config.ListenKey ?? "*81").trim() || "*81",
    whisper: Boolean(config.whisper ?? config.Whisper ?? false),
    whisper_key: String(config.whisper_key ?? config.WhisperKey ?? "*82").trim() || "*82",
    barge: Boolean(config.barge ?? config.Barge ?? false),
    barge_key: String(config.barge_key ?? config.BargeKey ?? "*83").trim() || "*83",
    targets: Array.isArray(config.targets ?? config.Targets)
      ? (config.targets ?? config.Targets).map((item) => String(item || "").trim()).filter(Boolean)
      : [],
  };
}

export function normalizeSipEndpoint(ep) {
  if (!ep || typeof ep !== "object") return null;
  return {
    id: ep.id ?? ep.ID ?? "",
    account_id: ep.account_id ?? ep.AccountID ?? "",
    extension: ep.extension ?? ep.Extension ?? "",
    username: ep.username ?? ep.Username ?? "",
    description: ep.description ?? ep.Description ?? "",
    route_to: ep.route_to ?? ep.RouteTo ?? "",
    default_outbound: Boolean(ep.default_outbound ?? ep.DefaultOutbound ?? false),
    video_enabled: Boolean(ep.video_enabled ?? ep.VideoEnabled ?? ep.video ?? false),
    auto_answer: Boolean(ep.auto_answer ?? ep.AutoAnswer ?? false),
    auto_answer_callers: ep.auto_answer_callers ?? ep.AutoAnswerCallers ?? "",
    auto_speaker: Boolean(ep.auto_speaker ?? ep.AutoSpeaker ?? false),
    auto_speaker_callers: ep.auto_speaker_callers ?? ep.AutoSpeakerCallers ?? "",
    callback_bridge: Boolean(ep.callback_bridge ?? ep.CallbackBridge ?? false),
    callback_bridge_callers: ep.callback_bridge_callers ?? ep.CallbackBridgeCallers ?? "",
    callback_caller_auto_answer: Boolean(ep.callback_caller_auto_answer ?? ep.CallbackCallerAutoAnswer ?? false),
    callback_caller_auto_speaker: Boolean(ep.callback_caller_auto_speaker ?? ep.CallbackCallerAutoSpeaker ?? false),
    gateway_inbound_mode: ep.gateway_inbound_mode ?? ep.GatewayInboundMode ?? "",
    gateway_direct_target: ep.gateway_direct_target ?? ep.GatewayDirectTarget ?? "",
    gateway_ivr_enabled: Boolean(ep.gateway_ivr_enabled ?? ep.GatewayIVREnabled ?? false),
    gateway_ivr_sound: ep.gateway_ivr_sound ?? ep.GatewayIVRSound ?? "",
    answer_announcement: ep.answer_announcement ?? ep.AnswerAnnouncement ?? "",
    answer_announcement_text: ep.answer_announcement_text ?? ep.AnswerAnnouncementText ?? "",
    pre_ring_announcement: ep.pre_ring_announcement ?? ep.PreRingAnnouncement ?? "",
    pre_ring_announcement_text: ep.pre_ring_announcement_text ?? ep.PreRingAnnouncementText ?? "",
    call_duration_rules: normalizeCallDurationRules(ep.call_duration_rules ?? ep.CallDurationRules ?? {}),
    supervision: normalizeSupervision(ep.supervision ?? ep.Supervision ?? ep.supervision_config ?? ep.SupervisionConfig ?? {}),
    enabled: ep.enabled ?? ep.Enabled ?? true,
    registered: Boolean(ep.registered ?? ep.Registered ?? false),
    contact_status: ep.contact_status ?? ep.ContactStatus ?? "",
    contact_uri: ep.contact_uri ?? ep.ContactURI ?? "",
    contact_address: ep.contact_address ?? ep.ContactAddress ?? "",
    contact_latency_ms: ep.contact_latency_ms ?? ep.ContactLatencyMS ?? "",
  };
}

export function gatewayEndpoints() {
  return state.sip.map(normalizeSipEndpoint).filter((ep) => ep && isGatewaySip(ep));
}

export function defaultGatewayTrunk() {
  const settings = getSettings();
  const configured = String(settings.routing.default_gateway_trunk || "").trim();
  if (configured) return configured;
  const marked = gatewayEndpoints().find((ep) => ep.default_outbound);
  if (marked?.extension) return marked.extension;
  return gatewayEndpoints()[0]?.extension || "";
}

export function targetSelectOptions(selected = "", includeBlank = true) {
  const values = [];
  const add = (value, label) => {
    const text = String(value || "").trim();
    if (!text || values.some((item) => item.value === text)) return;
    values.push({ value: text, label: label || text });
  };
  if (includeBlank) values.push({ value: "", label: "None" });
  getSettings().call_targets.forEach((target) => add(target.id, `${target.label || target.id} (${target.type || "target"})`));
  state.sip.map(normalizeSipEndpoint).filter(Boolean).forEach((ep) => add(ep.extension, `${ep.extension} · ${ep.description || ep.username || "SIP"}`));
  state.nodes.forEach((node) => add(node.id, `${node.label || node.id} · HAOS node`));
  return values.map((item) => option(item.value, item.label, selected)).join("");
}

export function gatewayInboundTargetOptions(selected = "") {
  const values = [];
  const add = (value, label) => {
    const text = String(value || "").trim();
    if (!text || values.some((item) => item.value === text)) return;
    values.push({ value: text, label: label || text });
  };
  values.push({ value: "", label: "None (use HAOS fallback policy)" });
  (state.advancedRoutes || []).forEach((route) => {
    if (route?.enabled !== false) add(route.id, `Route plan · ${route.name || route.id}`);
  });
  getSettings().call_targets.forEach((target) => add(target.id, `${target.label || target.id} (${target.type || "target"})`));
  state.sip.map(normalizeSipEndpoint).filter(Boolean).forEach((ep) => add(ep.extension, `${ep.extension} · ${ep.description || ep.username || "SIP"}`));
  state.nodes.forEach((node) => add(node.id, `${node.label || node.id} · HAOS node`));
  const current = String(selected || "").trim();
  if (current && !values.some((item) => item.value === current)) {
    values.push({ value: current, label: `${current} · unavailable (choose a valid target)` });
  }
  return values.map((item) => option(item.value, item.label, current)).join("");
}

export function gatewayRoutePlan(target) {
  const id = String(target || "").trim();
  return (state.advancedRoutes || []).find((route) => String(route?.id || "") === id) || null;
}

export function gatewaySelectOptions(selected = "") {
  const gateways = gatewayEndpoints();
  const current = String(selected || "").trim();
  const rows = gateways.length ? gateways : state.sip.map(normalizeSipEndpoint).filter(Boolean);
  const opts = [`<option value="">Auto-select best registered gateway</option>`];
  rows.forEach((ep) => {
    const label = `${ep.extension} · ${ep.description || ep.username || "gateway"}${ep.default_outbound ? " · current default" : ""}`;
    opts.push(option(ep.extension, label, current));
  });
  return opts.join("");
}

export function isGatewaySip(ep) {
  const text = `${ep.extension || ""} ${ep.username || ""} ${ep.description || ""}`.toLowerCase();
  return /^70[0-9]{2}$/.test(String(ep.extension || "")) || text.includes("gateway") || text.includes("gsm") || text.includes("fxo") || text.includes("landline");
}

