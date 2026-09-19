import { state } from '../state/store.js';
import { getSettings } from '../state/settings.js';
import { $, esc } from '../shared/dom.js';
import { effectiveDoorCooldown } from '../features/automation/helpers.js';
import { activeCallDisplay, activeCallSubtitle } from '../shared/calls.js';
import { targetRowReadonly } from '../features/routing/target-view.js';

export function renderOverview() {
  const s = state.status || {};
  const settings = getSettings();
  const active = s.active_call;
  $("content").innerHTML = `
    <div class="grid cols-3">
      ${stat("VPS", s.vps_connected ? "Online" : "Offline", s.server_url || "not configured", s.vps_connected ? "ok" : "bad")}
      ${stat("Asterisk", s.asterisk_connected ? "Connected" : "Unknown", "AMI and SIP bridge state", s.asterisk_connected ? "ok" : "warn")}
      ${stat("Automation guard", `${effectiveDoorCooldown(settings.automation.cooldown_seconds)}s`, settings.automation.block_while_call_active ? "Blocks repeats while calls are active" : "Cooldown only", "ok")}
    </div>
    <div class="grid cols-2" style="margin-top:16px">
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">Live Call</div>
            <div class="card-sub">Current site call state</div>
          </div>
          <span class="pill ${active ? "warn" : "ok"}">${active ? active.state : "idle"}</span>
        </div>
        ${active ? `
          <div class="row" style="background:transparent;border:0;padding:8px 0;">
            <div class="row-title">${esc(activeCallDisplay(active))}</div>
            <div class="row-sub">${esc(activeCallSubtitle(active))}</div>
          </div>
        ` : `<div class="empty">No active call on this addon.</div>`}
      </div>
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">Routes at a glance</div>
            <div class="card-sub">${settings.call_targets.length} saved route targets · ${settings.automation.triggers.length} automation trigger(s)</div>
          </div>
        </div>
        <div class="list">
          ${settings.call_targets.slice(0, 5).map(targetRowReadonly).join("") || `<div class="empty">No routes yet. Add routes from Routing.</div>`}
        </div>
      </div>
    </div>
  `;
}

export function stat(title, value, sub, tone) {
  return `
    <div class="stat">
      <span>${esc(title)}</span>
      <b>${esc(value)}</b>
      <span class="pill ${tone === "bad" ? "bad" : tone === "warn" ? "warn" : "ok"}">${esc(sub)}</span>
    </div>
  `;
}

