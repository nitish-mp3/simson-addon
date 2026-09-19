import { state } from '../../state/store.js';
import { newAdvancedRoute } from './route-editor.js';
import { renderRouting } from '../../pages/routing.js';
import { $, slug, splitList } from '../../shared/dom.js';
import { gatewayEndpoints, normalizeSipEndpoint, isGatewaySip, defaultGatewayTrunk } from '../../shared/endpoints.js';
import { randomHex } from '../automation/helpers.js';
import { api } from '../../services/api.js';
import { toast, setDirty } from '../../shared/feedback.js';
import { getSettings } from '../../state/settings.js';

export function openNewAdvancedRoute() {
  state.advancedDraft = newAdvancedRoute();
  renderRouting();
  requestAnimationFrame(() => $("advanced-route-form")?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

export function openDirectForwardRoute() {
  const gateways = gatewayEndpoints();
  if (gateways.length < 2) {
    throw new Error("Direct outside forwarding needs separate inbound and outbound gateways. Add or enable a second gateway first.");
  }
  state.advancedDraft = {
    id: "",
    name: "Direct outside forward",
    ingress_kind: "gateway",
    ingress_value: gateways[0].extension,
    enabled: true,
    stages: [{
      id: `stage_${randomHex(4)}`,
      name: "Forward immediately",
      ring_seconds: 60,
      max_call_seconds: 0,
      answer_mode: "first_answer",
      max_answered: 1,
      targets: [{
        id: `target_${randomHex(4)}`,
        kind: "external",
        value: "",
        trunk: gateways[1].extension,
        label: "Outside destination",
        enabled: true,
      }],
    }],
  };
  renderRouting();
  requestAnimationFrame(() => $("advanced-route-form")?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

export async function saveCallFeatures() {
  const payload = {
    transfer_code: String(state.callFeatures?.transfer_code || "").trim(),
    conference_code: String(state.callFeatures?.conference_code || "").trim(),
    invite_listen_code: String(state.callFeatures?.invite_listen_code || "*86").trim(),
    invite_whisper_code: String(state.callFeatures?.invite_whisper_code || "*87").trim(),
    invite_barge_code: String(state.callFeatures?.invite_barge_code || "*88").trim(),
    enabled: state.callFeatures?.enabled !== false,
  };
  const saved = await api("api/call-features", { method: "PUT", body: JSON.stringify(payload) });
  state.callFeatures = saved;
  state.callFeaturesError = "";
  toast("Site phone codes saved and applied.");
  renderRouting();
}

export async function inviteActiveCall() {
  const source = String(state.activeInvite.source_extension || "").trim();
  const target = String(state.activeInvite.target || "").trim();
  if (!source || !target) throw new Error("Choose the active participant and enter who should be invited.");
  const result = await api("api/active-call-invite", {
    method: "POST",
    body: JSON.stringify({
      source_extension: source,
      target,
      mode: state.activeInvite.mode || "barge",
      timeout_sec: 30,
    }),
  });
  toast(`${state.activeInvite.mode === "barge" ? "Participant" : state.activeInvite.mode === "whisper" ? "Coach" : "Listener"} invitation sent to ${target}.`);
  return result;
}

export function editAdvancedRoute(id) {
  const route = state.advancedRoutes.find((item) => String(item.id) === String(id));
  if (!route) return;
  state.advancedDraft = structuredClone(route);
  if (
    !state.advancedDraft.enabled
    && (state.advancedDraft.stages || []).some((stage) => stage.answer_mode === "private_hub")
  ) {
    state.advancedDraft._disabled_for_private_hub = true;
  }
  renderRouting();
  requestAnimationFrame(() => $("advanced-route-form")?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

export function closeAdvancedRoute() {
  state.advancedDraft = null;
  renderRouting();
}

export function addAdvancedStage() {
  if (!state.advancedDraft) return;
  if (state.advancedDraft.stages.length >= 10) {
    toast("A route can contain at most 10 stages.");
    return;
  }
  state.advancedDraft.stages.push({
    id: `stage_${randomHex(4)}`,
    name: `Stage ${state.advancedDraft.stages.length + 1}`,
    ring_seconds: 20,
    max_call_seconds: 0,
    answer_mode: "first_answer",
    max_answered: 1,
    targets: [],
  });
  renderRouting();
}

export function removeAdvancedStage(index) {
  if (!state.advancedDraft) return;
  if (state.advancedDraft.stages.length <= 1) {
    toast("A route needs at least one stage.");
    return;
  }
  state.advancedDraft.stages.splice(Number(index), 1);
  renderRouting();
}

export function advancedDefaultTargetValue(kind) {
  if (kind === "haos") return state.nodes[0]?.id || "";
  if (kind === "gateway") return gatewayEndpoints()[0]?.extension || "";
  if (kind === "sip") return state.sip.map(normalizeSipEndpoint).filter((ep) => ep && !isGatewaySip(ep))[0]?.extension || "";
  return "";
}

export function addAdvancedTarget(stageIndex) {
  const stage = state.advancedDraft?.stages?.[Number(stageIndex)];
  if (!stage) return;
  if (stage.targets.length >= 20) {
    toast("A stage can contain at most 20 destinations.");
    return;
  }
  const kind = advancedDefaultTargetValue("sip") ? "sip" : advancedDefaultTargetValue("haos") ? "haos" : "gateway";
  const hubExists = stage.targets.some((target) => target.role === "hub");
  stage.targets.push({
    id: `target_${randomHex(4)}`,
    kind,
    value: advancedDefaultTargetValue(kind),
    trunk: "",
    label: "",
    role: stage.answer_mode === "private_hub" && !hubExists ? "hub" : "spoke",
    enabled: true,
  });
  renderRouting();
}

export function removeAdvancedTarget(stageIndex, targetIndex) {
  const stage = state.advancedDraft?.stages?.[Number(stageIndex)];
  if (!stage) return;
  stage.targets.splice(Number(targetIndex), 1);
  renderRouting();
}

export function normalizeAdvancedRouteForSave(route) {
  const payload = structuredClone(route);
  delete payload._disabled_for_private_hub;
  payload.name = String(payload.name || "").trim();
  payload.ingress_value = String(payload.ingress_value || "").trim();
  payload.stages = (payload.stages || []).map((stage, stageIndex) => ({
    ...stage,
    id: stage.id || `stage_${stageIndex + 1}`,
    name: String(stage.name || `Stage ${stageIndex + 1}`).trim(),
    ring_seconds: Number(stage.ring_seconds) || 20,
    max_call_seconds: Math.max(0, Number(stage.max_call_seconds) || 0),
    max_answered: stage.answer_mode === "first_answer" ? 1 : Number(stage.max_answered) || 2,
    targets: (stage.targets || []).map((target, targetIndex) => ({
      ...target,
      id: target.id || `target_${stageIndex + 1}_${targetIndex + 1}`,
      value: String(target.value || "").trim(),
      trunk: String(target.trunk || "").trim(),
      label: String(target.label || "").trim(),
      enabled: target.enabled !== false,
    })),
  }));
  return payload;
}

export function advancedRouteValidationError(route) {
  if (!String(route?.name || "").trim()) return "Enter a plan name.";
  if (!["gateway", "sip"].includes(String(route?.ingress_kind || ""))) return "Choose whether calls enter from a gateway or SIP phone.";
  if (!String(route?.ingress_value || "").trim()) return "Choose the exact incoming gateway or SIP phone.";
  if (!Array.isArray(route?.stages) || !route.stages.length) return "Add at least one routing stage.";
  const seen = new Map();
  const ingressKind = String(route?.ingress_kind || "").trim().toLowerCase();
  const ingressValue = String(route?.ingress_value || "").trim();
  for (const [stageIndex, stage] of (route?.stages || []).entries()) {
    const enabledTargets = (stage?.targets || []).filter((target) => target?.enabled !== false);
    const hasImplicitLanding = ingressKind === "sip" && stageIndex === 0;
    const effectiveTargetCount = enabledTargets.length + (hasImplicitLanding && !enabledTargets.some((target) =>
      String(target?.kind || "").trim().toLowerCase() === "sip"
      && String(target?.value || "").trim() === ingressValue
    ) ? 1 : 0);
    const ringSeconds = Number(stage?.ring_seconds);
    const maxCallSeconds = Number(stage?.max_call_seconds || 0);
    if (!effectiveTargetCount) return `Stage ${stageIndex + 1} needs at least one active destination.`;
    if (!Number.isFinite(ringSeconds) || ringSeconds < 3 || ringSeconds > 300) return `Stage ${stageIndex + 1} ring time must be between 3 and 300 seconds.`;
    if (!Number.isFinite(maxCallSeconds) || maxCallSeconds < 0 || maxCallSeconds > 86400 || (maxCallSeconds > 0 && maxCallSeconds < 10)) {
      return `Stage ${stageIndex + 1} connected-call limit must be 0 (unlimited) or between 10 and 86400 seconds.`;
    }
    if (stage?.answer_mode === "conference" && enabledTargets.some((target) => target.kind !== "sip")) {
      return `Stage ${stageIndex + 1} conference mode supports SIP phones only.`;
    }
    const externalTargets = enabledTargets.filter((target) => String(target?.kind || "").trim().toLowerCase() === "external");
    if (externalTargets.length) {
      if (effectiveTargetCount !== 1) {
        return `Stage ${stageIndex + 1} outside forwarding must be the only destination in its stage. This prevents an analog gateway from answering and cancelling parallel phones.`;
      }
      if (stage?.answer_mode !== "first_answer") {
        return `Stage ${stageIndex + 1} outside forwarding must use First answer wins.`;
      }
      if (ingressKind === "gateway" && String(externalTargets[0]?.trunk || "").trim() === ingressValue) {
        return `Stage ${stageIndex + 1} cannot send the call back out through incoming gateway ${ingressValue}. Choose a separate outbound gateway.`;
      }
    }
    for (const target of enabledTargets) {
      if (target?.enabled === false) continue;
      const kind = String(target?.kind || "").trim().toLowerCase();
      const value = String(target?.value || "").trim();
      const trunk = String(target?.trunk || "").trim();
      if (!value) return `Stage ${stageIndex + 1} has a destination with no value selected.`;
      if (kind === "external" && !trunk) return `Stage ${stageIndex + 1} outside number ${value} needs an outbound gateway.`;
      const landingSIPTarget = ingressKind === "sip" && kind === "sip" && value === ingressValue && stageIndex === 0;
      if (ingressKind !== "manual" && (kind === "sip" || kind === "gateway") && value === ingressValue && !landingSIPTarget) {
        return `Stage ${stageIndex + 1} routes ${value} back to its own incoming source.`;
      }
      const key = (kind === "sip" || kind === "gateway")
        ? `endpoint:${value}`
        : `${kind}:${value}:${trunk}`;
      if (seen.has(key)) {
        return `${value} is already used in stage ${seen.get(key)}. A destination can appear only once in a route plan.`;
      }
      seen.set(key, stageIndex + 1);
    }
  }
  return "";
}

export async function saveAdvancedRoute() {
  if (!state.advancedDraft) return;
  const payload = normalizeAdvancedRouteForSave(state.advancedDraft);
  const validationError = advancedRouteValidationError(payload);
  if (validationError) {
    toast(validationError);
    renderRouting();
    return;
  }
  const path = payload.id ? `api/advanced-routes/${encodeURIComponent(payload.id)}` : "api/advanced-routes";
  const saved = await api(path, { method: payload.id ? "PUT" : "POST", body: JSON.stringify(payload) });
  const index = state.advancedRoutes.findIndex((item) => item.id === saved.id);
  if (index >= 0) state.advancedRoutes[index] = saved;
  else state.advancedRoutes.push(saved);
  state.advancedDraft = structuredClone(saved);
  toast(payload.id ? "Route plan updated." : "Route plan created.");
  renderRouting();
}

export async function deleteAdvancedRoute(id) {
  const route = state.advancedRoutes.find((item) => item.id === id);
  if (!route || !window.confirm(`Delete route plan “${route.name}”? Existing legacy routes are not affected.`)) return;
  await api(`api/advanced-routes/${encodeURIComponent(id)}`, { method: "DELETE" });
  state.advancedRoutes = state.advancedRoutes.filter((item) => item.id !== id);
  if (state.advancedDraft?.id === id) state.advancedDraft = null;
  toast("Route plan deleted.");
  renderRouting();
}

export async function setAdvancedRouteEnabled(id, enabled) {
  const route = state.advancedRoutes.find((item) => String(item.id) === String(id));
  if (!route) return;
  if (enabled && (route.stages || []).some((stage) => stage.answer_mode === "private_hub")) {
    throw new Error("Private hub plans require the isolated-media worker and cannot be activated as a shared conference.");
  }
  const payload = normalizeAdvancedRouteForSave({ ...route, enabled });
  const saved = await api(`api/advanced-routes/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  const index = state.advancedRoutes.findIndex((item) => String(item.id) === String(id));
  if (index >= 0) state.advancedRoutes[index] = saved;
  if (state.advancedDraft?.id === id) state.advancedDraft = structuredClone(saved);
  toast(enabled ? "Route plan is live." : "Route plan saved as draft.");
  renderRouting();
}

export function addRoute() {
  const kind = $("quick-kind").value;
  const label = $("quick-label").value.trim();
  const value = $("quick-value").value.trim();
  if (!label || !value) {
    toast("Route needs a name and destination.");
    return;
  }
  const id = slug(label || value);
  const targetType = kind === "intercom" ? "gateway" : kind;
  const target = {
    id,
    label,
    type: targetType,
    node_id: targetType === "node" ? value : "",
    extension: targetType !== "node" ? value : "",
    trunk: targetType === "gateway" ? defaultGatewayTrunk() : "",
    timeout: getSettings().routing.ring_seconds || 25,
    fallback_targets: splitList($("quick-fallbacks").value),
  };
  getSettings().call_targets.push(target);
  setDirty("Route added. Save to keep it.");
  renderRouting();
}

export function deleteTarget(index) {
  getSettings().call_targets.splice(Number(index), 1);
  setDirty("Route deleted. Save to keep it.");
  renderRouting();
}

export function setTargetMode(id, mode) {
  const settings = getSettings();
  settings.route_overrides[id] = { mode, reason: "" };
  setDirty("Availability changed. Save to keep it.");
  renderRouting();
}

