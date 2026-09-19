import { getSettings } from '../state/settings.js';
import { effectiveDoorCooldown, sourceSipLabel, targetListText, stableDoorCallbackUrl, stableDoorCallbackPath, deviceCallbackPath, deviceCallbackUrl } from '../features/automation/helpers.js';
import { state, boot } from '../state/store.js';
import { normalizeSipEndpoint, targetSelectOptions } from '../shared/endpoints.js';
import { splitList, $, esc, option } from '../shared/dom.js';

export function renderAutomation() {
  const settings = getSettings();
  const auto = settings.automation;
  const globalCooldown = effectiveDoorCooldown(auto.cooldown_seconds);
  const videoSip = state.sip.map(normalizeSipEndpoint).filter((ep) => ep && ep.enabled !== false && ep.video_enabled);
  const doorTargets = settings.call_targets.filter((t) => ["sip", "asterisk", "node", "device"].includes(t.type));
  const doorTriggers = (auto.triggers || []).filter((item) => item.mode === "door_station");
  const selectedDoorTriggerId = state.selectedDoorTriggerId || "";
  const selectedDoor = doorTriggers.find((item) => item.id === selectedDoorTriggerId) || {};
  const existingTargetIds = Array.isArray(selectedDoor.target_ids) && selectedDoor.target_ids.length
    ? selectedDoor.target_ids
    : [selectedDoor.target_id].filter(Boolean);
  const selectedDoorTargets = new Set(existingTargetIds.map(String));
  const selectedSource = selectedDoor.source_extension || videoSip[0]?.extension || "";
  const selectedFanout = selectedDoor.fanout_mode || "parallel";
  const configuredNotifyTargets = new Set(splitList(auto.notify_services));
  const discoveredNotifyRefs = new Set(state.notificationTargets.map((item) => String(item.ref || "")));
  const companionRefs = new Set(state.notificationTargets.filter((item) => item.rich_actions).map((item) => String(item.ref || "")));
  const notifyTargets = state.notificationTargets.filter((item) => {
    if (item.kind !== "entity") return true;
    const suffix = String(item.ref || "").replace(/^notify\./, "");
    return !companionRefs.has(`notify.mobile_app_${suffix}`) || configuredNotifyTargets.has(String(item.ref));
  }).filter((item) => item.rich_actions || configuredNotifyTargets.has(String(item.ref)))
    .sort((a, b) => {
      const selectedDelta = Number(configuredNotifyTargets.has(String(b.ref))) - Number(configuredNotifyTargets.has(String(a.ref)));
      if (selectedDelta) return selectedDelta;
      return String(a.label || a.ref).localeCompare(String(b.label || b.ref));
    });
  const selectedNotifyTargets = notifyTargets.filter((item) => configuredNotifyTargets.has(String(item.ref)));
  const missingNotifyTargets = [...configuredNotifyTargets].filter((ref) => !discoveredNotifyRefs.has(ref));

  $("content").innerHTML = `
    <div class="automation-grid">
      <div class="card glow">
        <div class="card-head">
          <div>
            <div class="card-title">Anti-spam guard</div>
            <div class="card-sub">Stops unknown-face devices from immediately retriggering after a call ends.</div>
          </div>
          <span class="pill ok">${esc(globalCooldown)}s cooldown</span>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Default cooldown seconds</label>
            <input type="number" min="20" max="3600" data-path="automation.cooldown_seconds" value="${esc(globalCooldown)}">
            <div class="hint">Minimum 20s. Recommended for face detection: 90-180 seconds.</div>
          </div>
          <div class="field">
            <label>Webhook ID</label>
            <input data-path="automation.webhook_id" value="${esc(auto.webhook_id)}" placeholder="site_unknown_face">
          </div>
          <div class="field full">
            <label>Webhook secret</label>
            <input type="password" data-path="automation.webhook_secret" value="${esc(auto.webhook_secret)}" placeholder="generate a long private secret">
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.webhook_enabled" ${auto.webhook_enabled ? "checked" : ""}> Enable webhook callbacks</label>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.block_while_call_active" ${auto.block_while_call_active !== false ? "checked" : ""}> Suppress triggers while a call is already active</label>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.persistent_notifications" ${auto.persistent_notifications !== false ? "checked" : ""}> Create Home Assistant notifications for door events</label>
          </div>
          <div class="field full">
            <div class="notify-recipient-head">
              <div>
                <label>Phones receiving incoming-call alerts</label>
                <div class="hint">Only Companion-app devices that support Answer, Decline, and dashboard deep links are shown.</div>
              </div>
              <button type="button" class="btn small secondary" data-action="toggle-notify-picker">${state.notificationPickerOpen ? "Done" : `Manage phones (${selectedNotifyTargets.length})`}</button>
            </div>
            <div class="notify-selected-list">
              ${selectedNotifyTargets.map((target) => `
                <span class="notify-selected-chip" title="${esc(target.ref)}">
                  <b>${esc(target.label || target.ref)}</b>
                  <button type="button" data-action="remove-notify-target" data-ref="${esc(target.ref)}" aria-label="Remove ${esc(target.label || target.ref)}">×</button>
                </span>`).join("") || `<div class="inline-notice error compact"><div><b>No call-alert phone selected</b><span>Select at least one Companion device to receive incoming-call controls.</span></div></div>`}
            </div>
            ${state.notificationPickerOpen ? `
              <div class="notify-picker-panel">
                <input id="notify-target-search" type="search" placeholder="Search phone name or notify service">
                <div class="notify-target-picker">
                  ${notifyTargets.map((target) => `
                    <label class="notify-target ${configuredNotifyTargets.has(String(target.ref)) ? "selected" : ""}" data-notify-search="${esc(`${target.label || ""} ${target.ref}`.toLowerCase())}">
                      <input type="checkbox" data-notify-target="${esc(target.ref)}" ${configuredNotifyTargets.has(String(target.ref)) ? "checked" : ""}>
                      <span><strong>${esc(target.label || target.ref)}</strong><small>${esc(target.ref)}</small></span>
                      <em class="rich">Call controls ready</em>
                    </label>`).join("") || `<div class="empty compact-empty">${esc(state.notificationTargetsError || "No compatible Companion phones were discovered. Open the Companion app once, then refresh.")}</div>`}
                </div>
              </div>` : ""}
            ${missingNotifyTargets.length ? `<div class="inline-notice error compact"><div><b>Unavailable saved target</b><span>${esc(missingNotifyTargets.join(", "))}</span></div></div>` : ""}
            <details class="manual-notify"><summary>Manual or legacy target</summary><input data-path="automation.notify_services" value="${esc(auto.notify_services || "")}" placeholder="notify.mobile_app_phone"></details>
          </div>
          <div class="field full">
            <label>Notification opens this HA dashboard path</label>
            <input data-path="automation.dashboard_path" value="${esc(auto.dashboard_path || "/lovelace/default_view")}" placeholder="/lovelace/sip_webrtc">
            <div class="hint">Tapping the alert opens this dashboard. Answer &amp; Open controls the exact call first, then redirects here.</div>
          </div>
        </div>
        <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
          <button class="btn secondary" data-action="generate-webhook">Generate credentials</button>
          <button class="btn secondary" data-action="test-notification">Send Test Notification</button>
        </div>
        ${webhookPreview(auto)}
      </div>
      <div class="card">
        <div class="card-title">Door camera flow</div>
        <div class="card-sub">Door flows are separate from gateway fallback. Choose one outdoor source, then choose every SIP monitor or HAOS card that should be notified/ring.</div>
        <div class="door-flow multi" style="margin-top:14px">
          <div class="door-step">
            <label>1 · Outdoor source</label>
            <select id="door-source">${videoSip.map((ep) => option(ep.extension, `${ep.extension} · ${ep.description || ep.username}`, selectedSource)).join("")}</select>
            <div class="hint">This SIP device is called first so it can publish live audio + H.264 video.</div>
          </div>
          <div class="door-arrow">→</div>
          <div class="door-step destination">
            <label>2 · Destinations</label>
            <div class="check-list">
              ${doorTargets.map((t) => `
                <label class="check-row">
                  <input type="checkbox" class="door-target-check" value="${esc(t.id)}" ${selectedDoorTargets.has(String(t.id)) ? "checked" : ""}>
                  <span>
                    <strong>${esc(t.label || t.id)}</strong>
                    <small>${esc(targetDescriptor(t))}</small>
                  </span>
                </label>
              `).join("") || `<div class="empty">Add SIP phones or HAOS node routes first.</div>`}
            </div>
          </div>
        </div>
        <div class="form-grid" style="margin-top:14px">
          <div class="field full">
            <label>Saved door flow</label>
            <select id="door-trigger-select">
              <option value="">Create new door flow</option>
              ${doorTriggers.length ? doorTriggers.map((t) => option(
                t.id,
                `${t.label || t.id} — ${sourceSipLabel(t.source_extension || selectedSource)} → ${targetListText(Array.isArray(t.target_ids) ? t.target_ids : [t.target_id].filter(Boolean))}`,
                t.id === selectedDoorTriggerId
              )).join("") : ``}
            </select>
          </div>
          <div class="field">
            <label>Flow name</label>
            <input id="door-label" value="${esc(selectedDoor.label || "Unknown visitor at front door")}">
          </div>
          <div class="field">
            <label>Ring time seconds</label>
            <input id="door-timeout" type="number" min="5" max="120" value="${esc(selectedDoor.timeout || 30)}">
          </div>
          <div class="field">
            <label>Trigger cooldown seconds</label>
            <input id="door-cooldown" type="number" min="20" max="3600" value="${esc(effectiveDoorCooldown(selectedDoor.cooldown_seconds || globalCooldown))}">
            <div class="hint">Minimum 20s to prevent repeated face-detection calls.</div>
          </div>
          <div class="field">
            <label>Caller ID</label>
            <input id="door-caller" value="${esc(selectedDoor.caller_id || "")}" placeholder="Unknown visitor">
          </div>
          <div class="field full">
            <label>Fan-out mode</label>
            <select id="door-fanout">
              ${option("parallel", "Ring selected destinations at the same time", selectedFanout)}
              ${option("priority", "Try destinations in priority order", selectedFanout)}
            </select>
            <div class="hint">Native H.264 video is safest with one SIP monitor. If you select SIP + HAOS together, Simson uses shared bridge fanout so HAOS rings too; video remains native only in SIP-only monitor flows.</div>
          </div>
          <div class="field full">
            <div class="flow-preview">
              <strong>Current selected flow</strong>
              <span>Source: ${esc(sourceSipLabel(selectedSource))}</span>
              <b>→</b>
              <span>Destinations: ${esc(targetListText(existingTargetIds) || "none")}</span>
            </div>
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn orange" data-action="create-door-flow">${selectedDoorTriggerId ? "Update Door Flow" : "Create Door Flow"}</button></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">HTTP intercom URL builder</div>
          <div class="card-sub">Generate a full URL for a phone shortcut, wall panel, or automation. It calls one SIP/source phone and bridges it to another SIP phone or HAOS node with optional auto-answer/speaker hints.</div>
        </div>
      </div>
      <div class="form-grid">
        <div class="field">
          <label>Source SIP extension</label>
          <select id="intercom-source">${state.sip.map(normalizeSipEndpoint).filter(Boolean).map((ep) => option(ep.extension, `${ep.extension} · ${ep.description || ep.username}`, "")).join("")}</select>
        </div>
        <div class="field">
          <label>Target SIP/node</label>
          <select id="intercom-target">${targetSelectOptions("", false)}</select>
        </div>
        <div class="field">
          <label>Source mode</label>
          <select id="intercom-source-mode">
            ${option("speaker", "Auto-answer + speaker/intercom", "speaker")}
            ${option("answer", "Auto-answer only", "")}
            ${option("manual", "Manual answer", "")}
          </select>
        </div>
        <div class="field">
          <label>Target mode</label>
          <select id="intercom-target-mode">
            ${option("speaker", "Auto-answer + speaker/intercom", "speaker")}
            ${option("answer", "Auto-answer only", "")}
            ${option("manual", "Manual answer", "")}
          </select>
        </div>
        <div class="field full">
          <label>Generated full URL</label>
          <input id="intercom-url" class="mono" readonly value="${esc(intercomUrlPreview())}">
          <div class="hint">If this is empty, provision the addon first so account ID, node ID, and install token are available.</div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Automation triggers</div>
          <div class="card-sub">Each trigger can call one or more saved targets. Door triggers show the exact device callback URL.</div>
        </div>
      </div>
      <div class="list">
        ${auto.triggers.map(triggerRow).join("") || `<div class="empty">No automation triggers yet.</div>`}
      </div>
    </div>
  `;
}

export function vpsHttpBase() {
  const raw = String(state.status?.server_url || boot.server_url || "").trim();
  if (!raw) return "";
  if (raw.startsWith("wss://")) return `https://${raw.slice(6).replace(/\/ws\/?$/, "")}`;
  if (raw.startsWith("ws://")) return `http://${raw.slice(5).replace(/\/ws\/?$/, "")}`;
  return raw.replace(/\/ws\/?$/, "").replace(/\/$/, "");
}

export function intercomUrlPreview() {
  const source = $("intercom-source")?.value || state.sip.map(normalizeSipEndpoint).filter(Boolean)[0]?.extension || "";
  const firstTarget = getSettings().call_targets[0]?.id
    || state.sip.map(normalizeSipEndpoint).filter(Boolean).find((ep) => ep.extension !== source)?.extension
    || "";
  const target = $("intercom-target")?.value || firstTarget;
  const sourceMode = $("intercom-source-mode")?.value || "speaker";
  const targetMode = $("intercom-target-mode")?.value || "speaker";
  const base = vpsHttpBase();
  const accountID = state.status?.account_id || "";
  const nodeID = state.status?.node_id || "";
  const token = state.status?.install_token || "";
  if (!base || !accountID || !nodeID || !token || !source || !target) return "";
  const url = new URL("/node/sip-intercom", base);
  url.searchParams.set("account_id", accountID);
  url.searchParams.set("node_id", nodeID);
  url.searchParams.set("install_token", token);
  url.searchParams.set("source", source);
  url.searchParams.set("target", target);
  url.searchParams.set("source_auto_mode", sourceMode);
  url.searchParams.set("target_auto_mode", targetMode);
  url.searchParams.set("timeout_sec", "30");
  return url.toString();
}

export function refreshIntercomUrl() {
  const el = $("intercom-url");
  if (el) el.value = intercomUrlPreview();
}

export function targetDescriptor(target) {
  if (!target) return "";
  if (["sip", "asterisk"].includes(target.type)) return `SIP/video extension ${target.extension || target.id}`;
  if (["node", "device"].includes(target.type)) return `HAOS node ${target.node_id || target.id}`;
  return `${target.type || "target"} ${target.extension || target.node_id || target.id}`;
}

export function targetDisplayName(id) {
  const target = getSettings().call_targets.find((item) => String(item.id) === String(id));
  if (!target) return String(id || "");
  const label = target.label || target.id;
  const suffix = target.extension ? ` (${target.extension})` : target.node_id ? ` (${target.node_id})` : "";
  return `${label}${suffix}`;
}

export function webhookPreview(auto) {
  if (!auto.webhook_id) {
    return `<div class="empty" style="margin-top:14px">Generate credentials to get device callback URLs.</div>`;
  }
  const doorTriggers = (getSettings().automation.triggers || []).filter(
    (item) => item.mode === "door_station" && String(item.id || "").trim()
  );
  if (doorTriggers.length === 1) {
    return `
      <div class="row" style="margin-top:14px">
        <div class="row-title">Door panel callback URL</div>
        <div class="row-sub">Paste this single full URL into the outdoor device. Change destinations below without changing the device URL.</div>
        <input class="mono" readonly value="${esc(stableDoorCallbackUrl())}" style="margin-top:8px;">
        <div class="row-sub" style="margin-top:6px;">POST with secret also works: ${esc(stableDoorCallbackPath())}. Advanced per-trigger URL: ${esc(deviceCallbackPath("TRIGGER_ID"))}</div>
      </div>
    `;
  }
  return `
    <div class="field-hint" style="margin-top:14px"><strong>${doorTriggers.length} saved door flow(s)</strong></div>
    <div class="field-hint" style="margin-top:7px">Use a per-trigger callback URL for each outdoor device. Legacy stable callback requires exactly one enabled door flow.</div>
    ${doorTriggers.map((trigger) => `
      <div class="row" style="margin-top:12px">
        <div class="row-title">${esc(trigger.label || trigger.id)}</div>
        <div class="row-sub">Trigger ID: ${esc(trigger.id)}</div>
        <input class="mono" readonly value="${esc(deviceCallbackUrl(trigger.id))}" style="margin-top:6px;">
      </div>
    `).join("")}
  `;
}

export function triggerRow(t) {
  const targetIds = Array.isArray(t.target_ids) && t.target_ids.length ? t.target_ids : [t.target_id].filter(Boolean);
  const targetText = targetIds.map(targetDisplayName).join(" + ");
  const cooldown = t.mode === "door_station"
    ? effectiveDoorCooldown(t.cooldown_seconds || getSettings().automation.cooldown_seconds)
    : (t.cooldown_seconds || getSettings().automation.cooldown_seconds || 90);
  const isDoor = t.mode === "door_station";
  const fanout = t.fanout_mode === "priority" ? "priority order" : "same time";
  return `
    <div class="row ${isDoor ? "door-trigger-row" : ""}">
      <div class="row-main">
        <div style="min-width:0;">
          <div class="row-title">${esc(t.label || t.id)}</div>
          ${isDoor ? `
            <div class="route-line">
              <span class="route-chip source">Outdoor ${esc(sourceSipLabel(t.source_extension))}</span>
              <span class="route-arrow">→</span>
              <span class="route-chip destination">${esc(targetText || "no destination")}</span>
            </div>
            <div class="row-sub">Door camera bridge · ${esc(targetIds.length)} destination(s) · fan-out ${esc(fanout)} · cooldown ${esc(cooldown)}s · ring ${esc(t.timeout || 30)}s</div>
          ` : `
            <div class="row-sub">${esc(t.mode || "standard")} · targets ${esc(targetText || "none")} · cooldown ${esc(cooldown)}s</div>
          `}
        </div>
        <div class="row-actions">
          <span class="pill ${t.enabled !== false ? "ok" : "bad"}">${t.enabled !== false ? "enabled" : "disabled"}</span>
          <button class="btn small red" data-action="delete-trigger" data-id="${esc(t.id)}">Delete</button>
        </div>
      </div>
      ${isDoor && getSettings().automation.webhook_id ? `
        <div class="callback-box">
          <label>Single device callback URL for this full flow</label>
          <input class="mono" readonly value="${esc(deviceCallbackUrl(t.id))}">
          <div class="row-sub">Paste this one URL into the outdoor panel. It runs the saved source and every selected destination above.</div>
        </div>
      ` : ""}
    </div>
  `;
}

