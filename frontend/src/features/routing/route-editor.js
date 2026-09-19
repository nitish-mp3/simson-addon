import { gatewayEndpoints, normalizeSipEndpoint, isGatewaySip, gatewaySelectOptions } from '../../shared/endpoints.js';
import { state } from '../../state/store.js';
import { randomHex } from '../automation/helpers.js';
import { esc, option } from '../../shared/dom.js';
import { advancedRouteValidationError } from './actions.js';

export function newAdvancedRoute() {
  const gateway = gatewayEndpoints()[0]?.extension || "";
  const sip = state.sip.map(normalizeSipEndpoint).filter(Boolean).find((ep) => !isGatewaySip(ep));
  return {
    id: "",
    name: "",
    ingress_kind: gateway ? "gateway" : "sip",
    ingress_value: gateway || sip?.extension || "",
    enabled: true,
    stages: [{
      id: `stage_${randomHex(4)}`,
      name: "First response",
      ring_seconds: 20,
      answer_mode: "first_answer",
      max_answered: 1,
      targets: [],
    }],
  };
}

export function renderAdvancedRoutes() {
  const routes = state.advancedRoutes || [];
  const draft = state.advancedDraft;
  return `
    <section class="advanced-routing" aria-labelledby="advanced-routing-title">
      ${renderCallFeaturePolicy()}
      <div class="advanced-heading">
        <div>
          <div class="kicker">Per-line orchestration</div>
          <h2 id="advanced-routing-title">Multi-level call routes</h2>
      <p>Match a called gateway or SIP phone, ring targets in parallel, then move to the next stage only when nobody answers.</p>
        </div>
        <div class="advanced-heading-actions">
          <button class="btn secondary" data-action="advanced-direct-forward">+ Direct outside forward</button>
          <button class="btn" data-action="advanced-new">+ New plan</button>
        </div>
      </div>
      <div class="route-plan-list">
        ${state.advancedRoutesError ? `<div class="inline-notice error"><div><b>Advanced routing could not be loaded</b><span>${esc(state.advancedRoutesError)}</span></div><button class="btn small secondary" data-action="refresh">Retry</button></div>` : ""}
        ${routes.map(advancedRouteSummary).join("") || `<div class="empty compact-empty">No advanced plans. Existing gateway and SIP routing remains unchanged.</div>`}
      </div>
      ${draft ? advancedRouteEditor(draft) : ""}
    </section>`;
}

export function renderCallFeaturePolicy() {
  const features = state.callFeatures || {};
  const phones = state.sip.map(normalizeSipEndpoint).filter((ep) => ep && ep.enabled !== false && !isGatewaySip(ep));
  const gateways = state.sip.map(normalizeSipEndpoint).filter((ep) => ep && ep.enabled !== false && isGatewaySip(ep));
  const source = state.activeInvite.source_extension || phones[0]?.extension || "";
  const phoneOptions = phones.map((ep) => `<option value="${esc(ep.extension)}">${esc(ep.extension)} · ${esc(ep.description || ep.username || "SIP phone")}</option>`).join("");
  const targetOptions = phones.map((ep) => `<option value="${esc(ep.extension)}">${esc(ep.description || ep.username || ep.extension)}</option>`).join("");
  const gatewayHelp = gateways.length ? `Outside format: *${esc(gateways[0].extension)}*number` : "Add an enabled gateway before inviting an outside number.";
  return `<div class="site-feature-card">
    <div class="site-feature-copy">
      <div class="kicker">Account-wide phone controls</div>
      <h3>Transfer, conference and active-call invitations</h3>
      <p>These codes apply only to SIP phones in this site/account. A person already on a call can invite another phone as a private listener, coach, or full participant.</p>
    </div>
    <label class="toggle-line feature-enabled"><input type="checkbox" data-call-feature-key="enabled" ${features.enabled !== false ? "checked" : ""}> Enabled</label>
    <div class="feature-code-grid">
      <div class="field">
        <label>Blind transfer prefix</label>
        <input data-call-feature-key="transfer_code" value="${esc(features.transfer_code || "*84")}" inputmode="tel" placeholder="*84">
        <small>While connected, send <b>${esc(features.transfer_code || "*84")}1028#</b>. For an outside transfer through a chosen gateway, send <b>${esc(features.transfer_code || "*84")}*7014*9123208334#</b>.</small>
      </div>
      <div class="field">
        <label>Conference launch prefix</label>
        <input data-call-feature-key="conference_code" value="${esc(features.conference_code || "*85")}" inputmode="tel" placeholder="*85">
        <small>While connected, send <b>${esc(features.conference_code || "*85")}1028#</b> to invite SIP 1028. Send <b>${esc(features.conference_code || "*85")}*7014*9123208334#</b> to invite an outside number through gateway 7014.</small>
      </div>
      <div class="field">
        <label>Invite as listener</label>
        <input data-call-feature-key="invite_listen_code" value="${esc(features.invite_listen_code || "*86")}" inputmode="tel" placeholder="*86">
        <small>The current participant sends <b>${esc(features.invite_listen_code || "*86")}1026#</b>. SIP 1026 hears the active call but cannot speak into it.</small>
      </div>
      <div class="field">
        <label>Invite as private coach</label>
        <input data-call-feature-key="invite_whisper_code" value="${esc(features.invite_whisper_code || "*87")}" inputmode="tel" placeholder="*87">
        <small>The current participant sends this prefix plus an extension and <b>#</b>. The invited phone can privately coach that participant.</small>
      </div>
      <div class="field">
        <label>Invite with full barge</label>
        <input data-call-feature-key="invite_barge_code" value="${esc(features.invite_barge_code || "*88")}" inputmode="tel" placeholder="*88">
        <small>The current participant sends this prefix plus a destination and <b>#</b>. Everyone can hear and speak after the invited destination answers.</small>
      </div>
      <div class="feature-code-help"><b>Handset codes:</b> enter them during an established call and finish with <b>#</b>. The phone must send DTMF as RFC2833/RFC4733 RTP events. SIP INFO or in-band tones may never reach Simson.</div>
      <button class="btn feature-save" data-action="call-features-save">Save phone codes</button>
    </div>
    <div class="active-invite-panel">
      <div class="active-invite-heading">
        <div><span class="kicker">Reliable active-call control</span><h4>Invite someone into a live SIP call</h4></div>
        <small>Use this when a handset does not transmit feature-code DTMF. The selected source must already be answered and active.</small>
      </div>
      <div class="active-invite-grid">
        <label><span>Active participant</span><select data-active-invite-key="source_extension">${phoneOptions.replace(`value="${esc(source)}"`, `value="${esc(source)}" selected`)}</select></label>
        <label><span>Invite as</span><select data-active-invite-key="mode">
          <option value="listen" ${state.activeInvite.mode === "listen" ? "selected" : ""}>Listener · cannot speak</option>
          <option value="whisper" ${state.activeInvite.mode === "whisper" ? "selected" : ""}>Private coach · source hears them</option>
          <option value="barge" ${state.activeInvite.mode === "barge" ? "selected" : ""}>Full participant · everyone hears</option>
        </select></label>
        <label><span>SIP extension or outside route</span><input data-active-invite-key="target" list="active-invite-targets" value="${esc(state.activeInvite.target)}" placeholder="1026 or *7014*9123208334"><datalist id="active-invite-targets">${targetOptions}</datalist><small>${gatewayHelp}</small></label>
        <button class="btn active-invite-button" data-action="active-call-invite" ${phones.length < 2 ? "disabled" : ""}>Invite now</button>
      </div>
    </div>
    ${state.callFeaturesError ? `<div class="inline-notice error compact-feature-error"><div><b>Phone controls unavailable</b><span>${esc(state.callFeaturesError)}</span></div></div>` : ""}
  </div>`;
}

export function advancedRouteSummary(route) {
  const stages = Array.isArray(route.stages) ? route.stages : [];
  const assignedGateways = gatewayEndpoints().filter((gateway) =>
    String(gateway.gateway_inbound_mode || "") === "direct_target"
    && String(gateway.gateway_direct_target || "") === String(route.id || "")
  );
  const path = stages.map((stage, index) => {
    const targets = (stage.targets || []).filter((target) => target.enabled !== false);
    const destinations = targets.map(advancedTargetLabel);
    if (index === 0 && route.ingress_kind === "sip") {
      destinations.unshift(`${advancedIngressLabel(route)} (primary)`);
    }
    const destinationSummary = destinations.join(" + ") || "no destination";
    return `<span class="route-stage-pill"><b>${index + 1}</b><span>${esc(stage.name || `Stage ${index + 1}`)}<small>${esc(destinationSummary)} · ${esc(stage.ring_seconds || 0)}s</small></span></span>`;
  }).join(`<span class="route-arrow">→</span>`);
  return `<article class="route-plan-summary ${route.enabled ? "" : "disabled"}">
    <div class="route-plan-main">
      <div class="route-plan-title"><span class="pill ${route.enabled ? "ok" : "warn"}">${route.enabled ? "live" : "draft"}</span>${esc(route.name)}</div>
      <div class="route-plan-ingress"><span>${route.ingress_kind === "sip" ? "Calls landing on" : "Calls entering from"}</span><b>${esc(advancedIngressLabel(route))}</b></div>
      ${route.ingress_kind === "gateway" ? `<div class="route-plan-assignment ${assignedGateways.length ? "ok" : "warn"}"><b>${assignedGateways.length ? `Assigned gateway${assignedGateways.length === 1 ? "" : "s"}: ${assignedGateways.map((gateway) => gateway.extension).join(", ")}` : "Not assigned to a gateway"}</b><span>${assignedGateways.length ? "Calls use this full staged plan as soon as they arrive." : "If the physical gateway sends calls to a different extension, open that gateway below and select this route plan."}</span></div>` : ""}
      <div class="route-stage-path">${path || "No escalation stages"}</div>
      ${route.ingress_kind === "sip" ? `<div class="route-plan-trigger">Calls to this SIP extension use this plan, whether they come from another SIP phone, a gateway, or a HAOS node. Normal extension-to-extension calls remain direct when no plan is enabled.</div>` : ""}
    </div>
    <div class="row-actions">
      ${!route.enabled && !stages.some((stage) => stage.answer_mode === "private_hub")
        ? `<button class="btn small" data-action="advanced-activate" data-id="${esc(route.id)}">Activate</button>`
        : ""}
      <button class="btn small secondary" data-action="advanced-edit" data-id="${esc(route.id)}">Edit</button>
      <button class="btn small red" data-action="advanced-delete" data-id="${esc(route.id)}">Delete</button>
    </div>
  </article>`;
}

export function advancedIngressLabel(route) {
  const value = String(route?.ingress_value || "");
  const endpoint = state.sip.map(normalizeSipEndpoint).filter(Boolean).find((item) => String(item.extension) === value);
  const label = endpoint?.description || endpoint?.username || value || "not selected";
  return `${route?.ingress_kind === "gateway" ? "Gateway" : "SIP phone"} ${value}${label && label !== value ? ` · ${label}` : ""}`;
}

export function advancedTargetLabel(target) {
  const value = String(target?.value || "");
  if (target?.kind === "external") return `Gateway ${target.trunk || "not selected"} dials ${value || "no number selected"}`;
  if (target?.kind === "haos") {
    const node = state.nodes.find((item) => String(item.id) === value);
    return `HAOS ${node?.label || value}`;
  }
  const endpoint = state.sip.map(normalizeSipEndpoint).filter(Boolean).find((item) => String(item.extension) === value);
  const prefix = target?.kind === "gateway" ? "Gateway/FXO" : "SIP";
  return `${prefix} ${value}${endpoint?.description ? ` · ${endpoint.description}` : ""}`;
}

export function advancedRouteEditor(route) {
  const stages = Array.isArray(route.stages) ? route.stages : [];
  const privateHub = stages.some((stage) => stage.answer_mode === "private_hub");
  const validationError = advancedRouteValidationError(route);
  return `<form class="advanced-editor" id="advanced-route-form">
    <div class="advanced-editor-head">
      <div>
        <div class="kicker">${route.id ? "Edit route plan" : "New route plan"}</div>
        <h3>${esc(route.name || "Untitled route")}</h3>
      </div>
      <button type="button" class="icon-btn" data-action="advanced-close" aria-label="Close editor">×</button>
    </div>
    <div class="advanced-route-basics">
      <div class="field wide"><label>Plan name</label><input data-advanced-route-key="name" value="${esc(route.name)}" placeholder="Main line escalation"></div>
      <div class="field"><label>Match incoming call by</label><select data-advanced-route-key="ingress_kind">
        ${option("gateway", "Gateway / FXO / GSM", route.ingress_kind)}
        ${option("sip", "SIP phone", route.ingress_kind)}
      </select></div>
      <div class="field"><label>${route.ingress_kind === "sip" ? "Called SIP phone" : "Incoming gateway"}</label>${advancedIngressField(route)}</div>
      <label class="toggle-line"><input type="checkbox" data-advanced-route-key="enabled" ${route.enabled ? "checked" : ""}> Enable this exact landing route</label>
    </div>
    <div class="advanced-route-note">${route.ingress_kind === "sip"
      ? `Calls landing on SIP phone <b>${esc(route.ingress_value || "not selected")}</b> automatically ring that phone in <b>Stage 1</b>. Any other Stage 1 destinations ring in parallel; later stages are fallbacks. The caller hears waiting audio instead of silence. No special <b>100</b> dial is required.`
      : `Only calls arriving through gateway <b>${esc(route.ingress_value || "not selected")}</b> use this plan. Other calls keep their current routing.`}</div>
    ${validationError ? `<div class="inline-notice error"><div><b>Fix this route before saving</b><span>${esc(validationError)}</span></div></div>` : ""}
    <div class="stage-stack">
      ${stages.map(advancedStageEditor).join("")}
    </div>
    <div class="advanced-editor-actions">
      <button type="button" class="btn secondary" data-action="advanced-add-stage">+ Add next stage</button>
      <span class="capability-note ${privateHub ? "warn" : ""}">${privateHub ? "Private hub is saved disabled until isolated-media support is assigned; this prevents spoke audio leakage." : "Stages run in order. Targets inside a stage ring at the same time."}</span>
      <button type="button" class="btn" data-action="advanced-save">${route.id ? "Save plan" : "Create plan"}</button>
    </div>
  </form>`;
}

export function advancedIngressField(route) {
  const endpoints = route.ingress_kind === "gateway"
    ? gatewayEndpoints()
    : state.sip.map(normalizeSipEndpoint).filter((ep) => ep && !isGatewaySip(ep));
  const hasCurrent = endpoints.some((ep) => String(ep.extension) === String(route.ingress_value));
  return `<select data-advanced-route-key="ingress_value">
    ${!hasCurrent && route.ingress_value ? option(route.ingress_value, `${route.ingress_value} · current`, route.ingress_value) : ""}
    ${endpoints.map((ep) => option(ep.extension, `${ep.extension} · ${ep.description || ep.username || route.ingress_kind}`, route.ingress_value)).join("")}
  </select>`;
}

export function advancedStageEditor(stage, stageIndex) {
  const targets = Array.isArray(stage.targets) ? stage.targets : [];
  const conference = stage.answer_mode === "conference";
  const privateHub = stage.answer_mode === "private_hub";
  return `<article class="advanced-stage ${privateHub ? "unsupported" : ""}">
    <div class="stage-number">${String(stageIndex + 1).padStart(2, "0")}</div>
    <div class="stage-body">
      <div class="stage-controls">
        <div class="field wide"><label>Stage name</label><input data-advanced-stage-index="${stageIndex}" data-advanced-stage-key="name" value="${esc(stage.name)}"></div>
        <div class="field small"><label>Ring for</label><div class="input-suffix"><input type="number" min="3" max="300" data-advanced-stage-index="${stageIndex}" data-advanced-stage-key="ring_seconds" value="${esc(stage.ring_seconds)}"><span>s</span></div></div>
        <div class="field small"><label>End connected call after</label><div class="input-suffix"><input type="number" min="0" max="86400" data-advanced-stage-index="${stageIndex}" data-advanced-stage-key="max_call_seconds" value="${esc(stage.max_call_seconds || 0)}"><span>s</span></div></div>
        <div class="field"><label>When answered</label><select data-advanced-stage-index="${stageIndex}" data-advanced-stage-key="answer_mode">
          ${option("first_answer", "First answer wins", stage.answer_mode)}
          ${option("conference", "Conference answered SIP phones", stage.answer_mode)}
          ${option("private_hub", "Private hub / whisper (requires media worker)", stage.answer_mode)}
        </select></div>
        ${(conference || privateHub) ? `<div class="field small"><label>Participant limit</label><input type="number" min="1" max="10" data-advanced-stage-index="${stageIndex}" data-advanced-stage-key="max_answered" value="${esc(stage.max_answered || 2)}"></div>` : ""}
        <button type="button" class="icon-btn danger" data-action="advanced-remove-stage" data-stage="${stageIndex}" aria-label="Remove stage">×</button>
      </div>
      <div class="stage-policy">${advancedModeHelp(stage)}</div>
      ${stageIndex === 0 && state.advancedDraft?.ingress_kind === "sip" ? `<div class="landing-target-lock"><span class="landing-target-icon">IN</span><span><b>${esc(state.advancedDraft.ingress_value || "Choose a landing SIP phone")}</b><small>Primary landing phone · added automatically to this stage</small></span><span class="pill ok">always rings</span></div>` : ""}
      <div class="advanced-targets">
        ${targets.map((target, targetIndex) => advancedTargetEditor(target, stageIndex, targetIndex, stage.answer_mode)).join("") || `<div class="empty compact-empty">Add one or more destinations for this stage.</div>`}
      </div>
      <button type="button" class="text-button" data-action="advanced-add-target" data-stage="${stageIndex}">+ Add parallel destination</button>
    </div>
  </article>`;
}

export function advancedModeHelp(stage) {
  const mode = stage?.answer_mode;
  if (mode === "conference") {
    const active = (stage?.targets || []).filter((target) => target?.enabled !== false).length;
    const limit = Math.max(1, Number(stage?.max_answered) || 1);
    return `All ${active} active SIP destination${active === 1 ? "" : "s"} ring together. Up to ${limit} answered destination${limit === 1 ? "" : "s"} stay in the conference; the original caller is additional and is not counted in this limit.`;
  }
  if (mode === "private_hub") return "Isolation contract: the hub may talk to every spoke while spokes remain private. This plan stays draft until the ARI isolated-media worker is installed; Simson will never substitute a shared conference that leaks spoke audio.";
  return "The first destination to answer owns the call; all other ringing destinations are cancelled immediately.";
}

export function advancedTargetEditor(target, stageIndex, targetIndex, answerMode) {
  const kindLabel = target.kind === "external" ? "Number or intercom extension to dial" : target.kind === "haos" ? "HAOS node/card" : target.kind === "gateway" ? "Gateway or wired port" : "SIP phone";
  const availability = advancedTargetAvailability(target);
  return `<div class="advanced-target ${target.enabled === false ? "disabled" : ""}">
    <div class="advanced-target-field kind"><label>Destination type</label><select aria-label="Destination type" data-advanced-target-stage="${stageIndex}" data-advanced-target-index="${targetIndex}" data-advanced-target-key="kind">
      ${option("sip", "SIP phone", target.kind)}
      ${option("haos", "HAOS card / node", target.kind)}
      ${option("gateway", "Gateway / FXO port", target.kind)}
      ${option("external", "Number/extension through gateway", target.kind)}
    </select></div>
    <div class="advanced-target-field destination"><label>${esc(kindLabel)}</label>${advancedTargetValueField(target, stageIndex, targetIndex)}</div>
    ${target.kind === "external" ? `<div class="advanced-target-field trunk"><label>Gateway that places the call</label><select aria-label="Outbound gateway" data-advanced-target-stage="${stageIndex}" data-advanced-target-index="${targetIndex}" data-advanced-target-key="trunk">${gatewaySelectOptions(target.trunk || "")}</select></div>` : ""}
    ${answerMode === "private_hub" ? `<select aria-label="Private hub role" data-advanced-target-stage="${stageIndex}" data-advanced-target-index="${targetIndex}" data-advanced-target-key="role">${option("spoke", "Spoke (private)", target.role || "spoke")}${option("hub", "Main hub", target.role || "spoke")}</select>` : ""}
    <input aria-label="Destination label" data-advanced-target-stage="${stageIndex}" data-advanced-target-index="${targetIndex}" data-advanced-target-key="label" value="${esc(target.label || "")}" placeholder="Label (optional)">
    ${availability ? `<span class="pill ${availability.ok ? "ok" : "warn"}" title="${esc(availability.detail)}">${esc(availability.label)}</span>` : ""}
    <label class="target-enabled"><input type="checkbox" data-advanced-target-stage="${stageIndex}" data-advanced-target-index="${targetIndex}" data-advanced-target-key="enabled" ${target.enabled !== false ? "checked" : ""}> Active</label>
    <button type="button" class="icon-btn danger" data-action="advanced-remove-target" data-stage="${stageIndex}" data-target="${targetIndex}" aria-label="Remove destination">×</button>
  </div>`;
}

export function advancedTargetAvailability(target) {
  const value = String(target?.value || "").trim();
  if (!value) return null;
  if (target?.kind === "sip" || target?.kind === "gateway") {
    const endpoint = state.sip.map(normalizeSipEndpoint).filter(Boolean).find((item) => String(item.extension) === value);
    if (!endpoint) return { ok: false, label: "unknown", detail: "This endpoint is not present in the current site endpoint list." };
    return endpoint.registered
      ? { ok: true, label: "registered", detail: endpoint.contact_address || endpoint.contact_uri || "Asterisk has a live contact." }
      : { ok: false, label: "offline", detail: endpoint.contact_status || "Asterisk has no live SIP contact, so this destination cannot ring." };
  }
  if (target?.kind === "haos") {
    const node = state.nodes.find((item) => String(item.id) === value);
    const online = Boolean(node?.online ?? node?.connected ?? node?.is_online);
    return online
      ? { ok: true, label: "online", detail: "The HAOS node is connected." }
      : { ok: false, label: "offline", detail: "The HAOS node is not currently connected." };
  }
  return null;
}

export function advancedTargetValueField(target, stageIndex, targetIndex) {
  const attrs = `data-advanced-target-stage="${stageIndex}" data-advanced-target-index="${targetIndex}" data-advanced-target-key="value"`;
  if (target.kind === "external") return `<input ${attrs} value="${esc(target.value)}" placeholder="Exact phone or intercom number"><small>The selected gateway dials this exact value.</small>`;
  let options = [];
  if (target.kind === "haos") options = state.nodes.map((node) => ({ value: node.id, label: `${node.label || node.id} · HAOS` }));
  if (target.kind === "gateway") options = gatewayEndpoints().map((ep) => ({ value: ep.extension, label: `${ep.extension} · ${ep.description || "gateway"}` }));
  if (target.kind === "sip") options = state.sip.map(normalizeSipEndpoint).filter((ep) => ep && !isGatewaySip(ep)).map((ep) => ({ value: ep.extension, label: `${ep.extension} · ${ep.description || ep.username || "SIP"}` }));
  const hasCurrent = options.some((item) => String(item.value) === String(target.value));
  return `<select ${attrs}>${!hasCurrent && target.value ? option(target.value, `${target.value} · current`, target.value) : ""}${options.map((item) => option(item.value, item.label, target.value)).join("")}</select>`;
}

