import { getSettings } from '../state/settings.js';
import { defaultGatewayTrunk, gatewaySelectOptions, targetSelectOptions } from '../shared/endpoints.js';
import { $, option, esc } from '../shared/dom.js';
import { state } from '../state/store.js';
import { targetRow } from '../features/routing/target-view.js';
import { renderAdvancedRoutes } from '../features/routing/route-editor.js';

export function renderRouting() {
  const settings = getSettings();
  const defaultTrunk = defaultGatewayTrunk();
  const inboundMode = settings.routing.gateway_inbound_mode || "haos_then_fallback";
  const directTarget = settings.routing.gateway_direct_target || "";
  $("content").innerHTML = `
    <div class="grid cols-2">
      <div class="card glow">
        <div class="card-head">
          <div>
            <div class="card-title">Routing policy</div>
            <div class="card-sub">Controls incoming gateway/PSTN calls after the HAOS card has rung. This does not edit door-camera flows.</div>
          </div>
        </div>
        <div class="form-grid">
          <div class="field full">
            <label>Default outside gateway for SIP phones</label>
            <select data-path="routing.default_gateway_trunk">
              ${gatewaySelectOptions(settings.routing.default_gateway_trunk || "")}
            </select>
            <div class="hint">SIP phones can dial outside numbers directly. Use a gateway prefix only when forcing a specific line.</div>
          </div>
          <div class="field">
            <label>Inbound gateway behavior</label>
            <select data-path="routing.gateway_inbound_mode">
              ${option("haos_then_fallback", "Ring HAOS first, then fallback", inboundMode)}
              ${option("direct_target", "Send directly to selected target", inboundMode)}
            </select>
            <div class="hint">Use direct mode for landline/GSM gateways that should always ring a SIP phone or route immediately.</div>
          </div>
          <div class="field">
            <label>Direct inbound target</label>
            <select data-path="routing.gateway_direct_target">
              ${targetSelectOptions(directTarget, true)}
            </select>
            <div class="hint">Only used when inbound behavior is direct. Pick a SIP phone, route target, or HAOS node.</div>
          </div>
          <div class="field">
            <label>Strategy</label>
            <select data-path="routing.strategy">
              ${option("priority", "Try saved fallback order", settings.routing.strategy)}
              ${option("round_robin", "Round robin", settings.routing.strategy)}
            </select>
          </div>
          <div class="field">
            <label>Ring HAOS before fallback</label>
            <input type="number" min="5" max="300" data-path="routing.ring_seconds" value="${esc(settings.routing.ring_seconds)}">
            <div class="hint">Gateway calls ring this dashboard first for this many seconds.</div>
          </div>
          <div class="field">
            <label>Max attempts</label>
            <input type="number" min="1" max="20" data-path="routing.max_attempts" value="${esc(settings.routing.max_attempts)}">
          </div>
          <div class="field">
            <label>Gateway fallback target</label>
            <input data-path="routing.final_fallback_target" value="${esc(settings.routing.final_fallback_target)}" placeholder="1025 or security_desk">
            <div class="hint">Only this explicit target, or a gateway route's fallback list, receives missed gateway calls.</div>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="routing.skip_unavailable" ${settings.routing.skip_unavailable ? "checked" : ""}> Skip busy/offline targets</label>
          </div>
        </div>
        <div class="flow-preview route-preview" style="margin-top:14px;">
          <strong>Gateway call path</strong>
          <span>PSTN/GSM gateway call</span>
          <b>→</b>
          ${inboundMode === "direct_target"
            ? `<span>direct transfer</span><b>→</b><span>${esc(directTarget || "no target selected")}</span>`
            : `<span>HAOS card for ${esc(settings.routing.ring_seconds)}s</span><b>→</b><span>${esc(settings.routing.final_fallback_target || "no automatic SIP fallback")}</span>`}
        </div>
        <div class="flow-preview route-preview" style="margin-top:10px;">
          <strong>Outside dial path</strong>
          <span>SIP phone dials number</span>
          <b>→</b>
          <span>${esc(defaultTrunk || "auto gateway")}</span>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Quick add route</div>
        <div class="card-sub">Create named destinations. SIP/HAOS routes can receive calls; gateway routes are for outside outbound dialing.</div>
        <div class="form-grid" style="margin-top:14px">
          <div class="field">
            <label>Kind</label>
            <select id="quick-kind">
              <option value="node">HAOS node</option>
              <option value="sip">SIP phone</option>
              <option value="gateway">Outside-number route</option>
              <option value="intercom">Building/intercom extension via gateway</option>
            </select>
          </div>
          <div class="field">
            <label>Name</label>
            <input id="quick-label" placeholder="Dining phone">
          </div>
          <div class="field">
            <label>Destination</label>
            <input id="quick-value" list="node-list" placeholder="1025, office2, outside number, or apartment code">
          </div>
          <div class="field">
            <label>Fallback IDs for this route</label>
            <input id="quick-fallbacks" placeholder="1025, security, office2">
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn orange" data-action="add-route">Add Route</button></div>
      </div>
    </div>
    <datalist id="node-list">${state.nodes.map((n) => `<option value="${esc(n.id)}">${esc(n.label || n.id)}</option>`).join("")}</datalist>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Routing targets</div>
          <div class="card-sub">Each row shows exactly what it is: HAOS node, SIP extension, or outbound gateway route.</div>
        </div>
      </div>
      <div class="list" id="target-list">
        ${settings.call_targets.map(targetRow).join("") || `<div class="empty">No route targets yet.</div>`}
      </div>
    </div>
    ${renderAdvancedRoutes()}
  `;
  compactWorkspace('routing');
}
import { compactWorkspace } from '../shared/workspace.js';
