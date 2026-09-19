import { state } from '../../state/store.js';
import { normalizeSipEndpoint, isGatewaySip, normalizeSupervision, gatewayInboundTargetOptions } from '../../shared/endpoints.js';
import { esc, option } from '../../shared/dom.js';
import { durationRuleRows } from './actions.js';

export function sipTable() {
  if (!state.sip.length) return `<div class="empty">No SIP endpoints returned yet.</div>`;
  return `
    <div class="data-table">
      ${state.sip.map(sipRow).join("")}
    </div>
  `;
}

export function sipRow(raw) {
  const ep = normalizeSipEndpoint(raw) || {};
  const enabled = ep.enabled !== false;
  const endpointId = ep.id || ep.extension || ep.username;
  const isGateway = isGatewaySip(ep);
  const registered = Boolean(ep.registered);
  const contactText = ep.contact_address
    ? `${ep.contact_address}${ep.contact_latency_ms ? ` · ${ep.contact_latency_ms}ms` : ""}`
    : (ep.contact_status || "no live contact");
  const autoAnswerText = ep.auto_answer
    ? (ep.auto_answer_callers ? `auto-answer from ${ep.auto_answer_callers}` : "auto-answer from anyone")
    : "manual answer";
  const speakerText = ep.auto_speaker
    ? (ep.auto_speaker_callers ? `speaker from ${ep.auto_speaker_callers}` : "speaker follows auto-answer")
    : "speaker off";
  const callbackText = ep.callback_bridge
    ? `caller callback from ${ep.callback_bridge_callers || "no allowlist"}${ep.callback_caller_auto_speaker ? " with caller speaker" : ep.callback_caller_auto_answer ? " with caller auto-answer" : ""}`
    : "caller callback off";
  const gatewayMode = ep.gateway_inbound_mode || "inherit";
  const gatewayTarget = ep.gateway_direct_target || "";
  const gatewayIvrText = ep.gateway_ivr_enabled
    ? `IVR ${ep.gateway_ivr_sound || "built-in wait prompt"}`
    : "IVR off";
  const answerPromptText = ep.answer_announcement_text
    ? `private prompt "${ep.answer_announcement_text}"`
    : "no private answer prompt";
  const preRingPromptText = ep.pre_ring_announcement_text
    ? `caller waiting announcement "${ep.pre_ring_announcement_text}"`
    : "no caller waiting announcement";
  const durationRuleCount = Object.keys(ep.call_duration_rules || {}).length;
  const supervision = normalizeSupervision(ep.supervision);
  const supervisionModes = [
    supervision.listen ? "monitor" : "",
    supervision.whisper ? "whisper" : "",
    supervision.barge ? "barge" : "",
  ].filter(Boolean);
  return `
    <div class="sip-manage-row ${isGateway ? "protected" : ""}">
      <div class="sip-main">
        <div style="min-width:0;">
          <div class="row-title">${esc(ep.extension || "-")} ${ep.description ? `<span>${esc(ep.description)}</span>` : ""}</div>
          <div class="row-sub">User ${esc(ep.username || "-")} · ${esc(ep.route_to || "any available node")} · ${ep.video_enabled ? "Audio + H.264" : "Audio only"} · ${esc(autoAnswerText)} · ${esc(speakerText)} · ${esc(callbackText)} · ${esc(preRingPromptText)} · ${esc(answerPromptText)} · ${durationRuleCount ? `${durationRuleCount} timed route${durationRuleCount === 1 ? "" : "s"}` : "no call time limit"}</div>
          <div class="row-sub">Live contact: ${esc(contactText)}</div>
          ${!isGateway && supervision.enabled ? `<div class="row-sub supervision-summary">Supervisor access: ${esc(supervisionModes.join(", ") || "not configured")} · ${supervision.targets.length} permitted target${supervision.targets.length === 1 ? "" : "s"}</div>` : ""}
        </div>
        <div class="row-actions">
          <span class="pill ${enabled ? "ok" : "bad"}">${enabled ? "enabled" : "disabled"}</span>
          <span class="pill ${registered ? "ok" : "warn"}">${registered ? "registered" : "offline"}</span>
          ${ep.default_outbound ? `<span class="pill ok">default outside gateway</span>` : ""}
          ${isGateway ? `<span class="pill warn">gateway protected</span>` : ""}
          ${isGateway ? `<span class="pill">${esc(gatewayMode === "direct_target" ? "direct inbound" : gatewayMode === "haos_then_fallback" ? "card then fallback" : "inherits inbound")}</span>` : ""}
        </div>
      </div>
      <div class="sip-edit-grid">
        <div class="field">
          <label>Label</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="description" value="${esc(ep.description || "")}" placeholder="Kitchen monitor">
        </div>
        <div class="field">
          <label>Route to HAOS node</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="route_to" list="node-list" value="${esc(ep.route_to || "")}" placeholder="any available node">
        </div>
        <div class="field">
          <label>Rotate password</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="password" type="password" placeholder="new password only">
        </div>
        <div class="sip-checks">
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="enabled" type="checkbox" ${enabled ? "checked" : ""}> Enabled</label>
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="video_enabled" type="checkbox" ${ep.video_enabled ? "checked" : ""}> H.264 video</label>
          ${isGateway ? `<label><input data-sip-id="${esc(endpointId)}" data-sip-key="default_outbound" type="checkbox" ${ep.default_outbound ? "checked" : ""}> Default outside gateway</label>` : ""}
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="auto_answer" type="checkbox" ${ep.auto_answer ? "checked" : ""}> Auto-answer</label>
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="auto_speaker" type="checkbox" ${ep.auto_speaker ? "checked" : ""}> Speaker on auto-answer</label>
        </div>
        ${isGateway ? `
        <div class="field full gateway-policy">
          <div class="gateway-policy-head">
            <div>
              <label>Inbound behavior for gateway ${esc(ep.extension)}</label>
              <div class="hint">This applies only to calls arriving through this gateway. It will not affect other gateways.</div>
            </div>
            <span class="pill">${esc(gatewayIvrText)}</span>
          </div>
          <div class="form-grid compact">
            <div class="field">
              <label>Incoming call path</label>
              <select data-sip-id="${esc(endpointId)}" data-sip-key="gateway_inbound_mode">
                ${option("", "Use global routing policy", gatewayMode === "inherit" ? "" : gatewayMode)}
                ${option("haos_then_fallback", "Ring HAOS card, then this fallback", gatewayMode)}
                ${option("direct_target", "Send directly to this target", gatewayMode)}
              </select>
            </div>
            <div class="field">
              <label>Gateway target / fallback</label>
              <select data-sip-id="${esc(endpointId)}" data-sip-key="gateway_direct_target">
                ${gatewayInboundTargetOptions(gatewayTarget)}
              </select>
              <div class="hint">For direct mode this starts immediately. Select a <b>Route plan</b> to run its full multi-stage escalation. For card mode this is tried after the HAOS ring delay.</div>
            </div>
            <div class="field">
              <label><input data-sip-id="${esc(endpointId)}" data-sip-key="gateway_ivr_enabled" type="checkbox" ${ep.gateway_ivr_enabled ? "checked" : ""}> Play IVR before routing</label>
              <div class="hint">Optional. Leave off for fastest gateway handoff.</div>
            </div>
            <div class="field">
              <label>IVR sound name</label>
              <input data-sip-id="${esc(endpointId)}" data-sip-key="gateway_ivr_sound" value="${esc(ep.gateway_ivr_sound || "")}" placeholder="custom/site_welcome">
              <div class="hint">Per account/gateway Asterisk sound. Blank uses the built-in wait prompt if IVR is enabled.</div>
            </div>
          </div>
        </div>` : ""}
        <div class="field full call-stage-box caller-stage">
          <div class="call-stage-label"><span>1</span><div><b>Caller waiting announcement</b><small>Before ${esc(ep.extension || "the destination")} starts ringing · caller hears this</small></div></div>
          <textarea data-sip-id="${esc(endpointId)}" data-sip-key="pre_ring_announcement_text" maxlength="300" rows="2" placeholder="Please wait while I call the kitchen monitor.">${esc(ep.pre_ring_announcement_text || "")}</textarea>
          <div class="prompt-audience caller"><b>Audience: caller only.</b> Asterisk plays early media first, then starts ringing ${esc(ep.extension || "this phone")}. The receiving phone cannot hear this stage.</div>
        </div>
        <div class="field full call-stage-box receiver-stage">
          <div class="call-stage-label"><span>2</span><div><b>Receiving-phone private prompt</b><small>Immediately after manual/auto-answer · receiver hears this</small></div></div>
          <textarea data-sip-id="${esc(endpointId)}" data-sip-key="answer_announcement_text" maxlength="300" rows="2" placeholder="Call for Amit. Please wait while I connect you.">${esc(ep.answer_announcement_text || "")}</textarea>
          <div class="prompt-audience receiver"><b>Audience: receiving phone only.</b> The phone must answer before SIP media can be delivered; Simson plays this privately before bridging the caller. Blank disables it.</div>
          <div class="sip-standard-note">Standard SIP does not support sending arbitrary audio to an unanswered receiving handset. This is the earliest standards-compliant receiver-side prompt and does not alter normal ringing behavior.</div>
        </div>
        <div class="field full route-duration-box">
          <div class="duration-head">
            <div>
              <label>Route-specific connected call limits</label>
              <div class="hint">Optional. The timer starts only after ${esc(ep.extension || "this phone")} answers. Ring time is never deducted.</div>
            </div>
            <button class="btn small secondary" data-action="add-duration-rule" data-id="${esc(endpointId)}" data-target-ext="${esc(ep.extension || "")}">+ Add limit</button>
          </div>
          <div class="duration-rule-list" data-duration-list="${esc(endpointId)}">
            ${durationRuleRows(endpointId, ep.extension, ep.call_duration_rules)}
          </div>
          <div class="hint">Example: source 1027 with 15 seconds means only 1027 → ${esc(ep.extension || "this phone")} ends after 15 connected seconds. All other callers remain unlimited.</div>
        </div>
        <div class="field full">
          <label>Only auto-answer from caller extension(s)</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="auto_answer_callers" value="${esc(ep.auto_answer_callers || "")}" placeholder="1025, 1602">
          <div class="hint">Blank means any caller. For precise behavior like <b>1025 → ${esc(ep.extension || "this phone")}</b>, put <b>1025</b> here.</div>
        </div>
        <div class="field full">
          <label>Only request speaker/intercom from caller extension(s)</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="auto_speaker_callers" value="${esc(ep.auto_speaker_callers || "")}" placeholder="${esc(ep.auto_answer_callers || "1025, 1602")}">
          <div class="hint">Blank reuses the auto-answer caller list. This sends intercom/speaker hints to the <b>called</b> phone; Asterisk cannot force the original caller handset into speaker after it has already placed a call.</div>
        </div>
        <div class="field full feature-box">
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="callback_bridge" type="checkbox" ${ep.callback_bridge ? "checked" : ""}> Caller callback bridge</label>
          <div class="hint">Use when the <b>caller</b> phone also needs auto-answer/speaker. Simson replaces the original dial attempt with a fresh callback to the caller, then bridges to this target.</div>
        </div>
        <div class="field full">
          <label>Only callback-bridge these caller extension(s)</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="callback_bridge_callers" value="${esc(ep.callback_bridge_callers || "")}" placeholder="1025, 1026">
          <div class="hint">Required allowlist. Example: set this on target <b>${esc(ep.extension || "1603")}</b> to <b>1025</b> for only 1025 → ${esc(ep.extension || "1603")}.</div>
        </div>
        <div class="sip-checks full">
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="callback_caller_auto_answer" type="checkbox" ${ep.callback_caller_auto_answer ? "checked" : ""}> Caller callback auto-answer</label>
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="callback_caller_auto_speaker" type="checkbox" ${ep.callback_caller_auto_speaker ? "checked" : ""}> Caller callback speaker/intercom</label>
        </div>
        ${!isGateway ? supervisionEditor(endpointId, ep.extension, supervision) : ""}
      </div>
      <div class="sip-actions">
        <button class="btn small secondary" data-action="save-sip" data-id="${esc(endpointId)}">Save Device</button>
        ${isGateway
          ? `<button class="btn small secondary ghost" data-action="clear-stuck-sip" data-id="${esc(endpointId)}" data-ext="${esc(ep.extension || endpointId)}" title="Release orphaned calls on this gateway">Clear stuck call</button>`
          : ""}
        ${isGateway
          ? `<button class="btn small red ghost" data-action="delete-sip" data-id="${esc(endpointId)}" data-ext="${esc(ep.extension || endpointId)}" title="Gateway trunks require typed confirmation">Delete Gateway</button>`
          : `<button class="btn small red" data-action="delete-sip" data-id="${esc(endpointId)}" data-ext="${esc(ep.extension || endpointId)}">Delete</button>`}
      </div>
    </div>
  `;
}

export function supervisionTargetOptions(endpointId, sourceExtension, selectedTargets) {
  const selected = new Set((selectedTargets || []).map(String));
  const endpoints = state.sip
    .map(normalizeSipEndpoint)
    .filter((item) => item && item.enabled !== false && !isGatewaySip(item) && item.extension && item.extension !== sourceExtension);
  if (!endpoints.length) return `<div class="empty compact">No other enabled SIP phones are available on this site.</div>`;
  return endpoints.map((item) => {
    const itemId = item.id || item.extension || item.username;
    return `
      <label class="supervision-target">
        <input type="checkbox" data-supervision-owner="${esc(endpointId)}" data-supervision-target="${esc(item.extension)}" ${selected.has(String(item.extension)) ? "checked" : ""}>
        <span><b>${esc(item.extension)}</b>${item.description ? `<small>${esc(item.description)}</small>` : ""}</span>
        <i class="${item.registered ? "online" : "offline"}">${item.registered ? "online" : "offline"}</i>
      </label>`;
  }).join("");
}

export function supervisionEditor(endpointId, sourceExtension, supervision) {
  const open = supervision.enabled ? "open" : "";
  const dialHelp = (key, target = "target") => {
    const configured = String(key || "");
    const fallback = configured.startsWith("*") ? configured.slice(1) : configured;
    return fallback && fallback !== configured
      ? `Dial ${configured} + ${target}. If the handset reserves *, dial ${fallback} + ${target}.`
      : `Dial ${configured} + ${target}.`;
  };
  return `
    <details class="field full supervision-panel" ${open}>
      <summary>
        <span><b>Supervisor access</b><small>Secure monitor, whisper, and barge permissions for ${esc(sourceExtension || "this extension")}</small></span>
        <span class="pill ${supervision.enabled ? "ok" : ""}">${supervision.enabled ? "enabled" : "off"}</span>
      </summary>
      <div class="supervision-body">
        <label class="supervision-enable"><input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_enabled" type="checkbox" ${supervision.enabled ? "checked" : ""}> Allow this authenticated SIP phone to supervise selected calls</label>
        <div class="supervision-security">Authorization uses the registered SIP endpoint, not caller ID. The phone can supervise only the target extensions selected below.</div>
        <div class="supervision-modes">
          <div class="supervision-mode">
            <label><input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_listen" type="checkbox" ${supervision.listen ? "checked" : ""}> Silent monitor</label>
            <input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_listen_key" value="${esc(supervision.listen_key)}" maxlength="7" aria-label="Silent monitor key">
            <small>${esc(dialHelp(supervision.listen_key))} Neither party hears the supervisor.</small>
          </div>
          <div class="supervision-mode">
            <label><input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_whisper" type="checkbox" ${supervision.whisper ? "checked" : ""}> Whisper</label>
            <input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_whisper_key" value="${esc(supervision.whisper_key)}" maxlength="7" aria-label="Whisper key">
            <small>${esc(dialHelp(supervision.whisper_key))} Supervisor coaches the target privately.</small>
          </div>
          <div class="supervision-mode">
            <label><input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_barge" type="checkbox" ${supervision.barge ? "checked" : ""}> Full barge</label>
            <input data-sip-id="${esc(endpointId)}" data-sip-key="supervision_barge_key" value="${esc(supervision.barge_key)}" maxlength="7" aria-label="Full barge key">
            <small>${esc(dialHelp(supervision.barge_key))} Everyone can hear the supervisor.</small>
          </div>
        </div>
        <div class="supervision-targets-head"><b>Permitted target phones</b><span>Select one or more active SIP extensions</span></div>
        <div class="supervision-targets">${supervisionTargetOptions(endpointId, sourceExtension, supervision.targets)}</div>
      </div>
    </details>`;
}

