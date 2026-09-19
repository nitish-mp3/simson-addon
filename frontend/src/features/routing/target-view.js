import { esc } from '../../shared/dom.js';
import { getSettings } from '../../state/settings.js';
import { gatewaySelectOptions, defaultGatewayTrunk } from '../../shared/endpoints.js';

export function targetRowReadonly(t) {
  return `
    <div class="row" style="padding:10px 14px;">
      <div class="row-main">
        <div>
          <div class="row-title">${esc(t.label || t.id)}</div>
          <div class="row-sub">${esc(t.type)} · ${esc(t.node_id || t.extension || t.trunk || "site")}</div>
        </div>
        <span class="pill">${esc(t.id)}</span>
      </div>
    </div>
  `;
}

export function targetRow(t) {
  const idx = getSettings().call_targets.indexOf(t);
  const mode = getSettings().route_overrides?.[t.id]?.mode || "available";
  const descriptor = targetFlowDescription(t);
  const isGateway = t.type === "gateway";
  return `
    <div class="row" data-target-index="${idx}">
      <div class="row-main">
        <div style="min-width:0;">
          <div class="row-title">${esc(t.label || t.id)}</div>
          <div class="row-sub">${esc(descriptor)}</div>
        </div>
        <div class="row-actions">
          <span class="pill ${mode === "available" ? "ok" : mode === "busy" ? "warn" : "bad"}">${esc(mode)}</span>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="available">Available</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="busy">Busy</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="offline">Offline</button>
          <button class="btn small red" data-action="delete-target" data-index="${idx}">Delete</button>
        </div>
      </div>
      <div class="form-grid" style="margin-top:10px;">
        <div class="field">
          <label>Route ID</label>
          <input data-target="${idx}" data-key="id" value="${esc(t.id)}">
        </div>
        <div class="field">
          <label>Label</label>
          <input data-target="${idx}" data-key="label" value="${esc(t.label)}">
        </div>
        <div class="field">
          <label>HAOS node ID</label>
          <input data-target="${idx}" data-key="node_id" list="node-list" value="${esc(t.node_id)}">
        </div>
        <div class="field">
          <label>SIP extension / outside number</label>
          <input data-target="${idx}" data-key="extension" value="${esc(t.extension)}">
        </div>
        ${isGateway ? `
          <div class="field">
            <label>Gateway trunk</label>
            <select data-target="${idx}" data-key="trunk">
              ${gatewaySelectOptions(t.trunk || defaultGatewayTrunk())}
            </select>
            <div class="hint">Short residence/intercom codes are dialed through this gateway; they do not need to be registered.</div>
          </div>
        ` : ""}
        <div class="field full">
          <label>Fallback target IDs</label>
          <input data-target="${idx}" data-key="fallback_targets_text" value="${esc((t.fallback_targets || []).join(", "))}">
        </div>
      </div>
    </div>
  `;
}

export function targetFlowDescription(t) {
  if (!t) return "";
  if (["sip", "asterisk"].includes(t.type)) return `Incoming target: SIP extension ${t.extension || t.id}`;
  if (["node", "device"].includes(t.type)) return `Incoming target: HAOS node ${t.node_id || t.id}`;
  if (t.type === "gateway") {
    const digits = String(t.extension || "").replace(/\D/g, "");
    const kind = digits && digits.length < 7 ? "Building/intercom extension" : "Outside number";
    return `${kind}: dial ${t.extension || "number"} via gateway ${t.trunk || defaultGatewayTrunk() || "auto"}`;
  }
  return `${t.type || "target"} · ${t.node_id || t.extension || t.trunk || ""}`;
}

