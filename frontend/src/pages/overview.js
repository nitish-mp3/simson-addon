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
  const online = Boolean(s.vps_connected);
  const endpoints = state.sip.length;
  const targets = settings.call_targets.length;
  $("content").innerHTML = `
    <section class="overview-hero ${online ? 'connected' : 'disconnected'}">
      <div class="overview-orbit" aria-hidden="true"><span></span><i></i></div>
      <div class="overview-copy"><span class="eyebrow">SITE CONTROL CENTER</span><h2>${esc(s.node_id || 'Your Simson node')}</h2><p>${online ? 'Your call services are connected and ready.' : 'The addon cannot reach the call service. Check the node and network connection.'}</p><div class="overview-health"><i></i>${online ? 'Node online' : 'Connection needs attention'} <span>·</span> ${s.asterisk_connected ? 'Asterisk connected' : 'Asterisk not confirmed'}</div></div>
      <button class="btn secondary overview-refresh" data-action="refresh">Refresh status <span aria-hidden="true">↻</span></button>
    </section>
    <section class="overview-metrics" aria-label="System summary">
      <article class="metric-card"><span class="metric-icon" aria-hidden="true">☎</span><div><small>SIP devices</small><b>${endpoints}</b><span>${state.sip.filter(endpoint => endpoint.registered).length} registered</span></div><button data-page="sip" aria-label="Manage SIP devices">↗</button></article>
      <article class="metric-card"><span class="metric-icon" aria-hidden="true">⇄</span><div><small>Destinations</small><b>${targets}</b><span>${settings.automation.triggers.length} automations</span></div><button data-page="routing" aria-label="Manage routes">↗</button></article>
      <article class="metric-card"><span class="metric-icon" aria-hidden="true">◷</span><div><small>Repeat call guard</small><b>${effectiveDoorCooldown(settings.automation.cooldown_seconds)}<small>s</small></b><span>${settings.automation.block_while_call_active ? 'Blocks while a call is active' : 'Cooldown enabled'}</span></div><button data-page="automation" aria-label="Manage automation">↗</button></article>
    </section>
    <div class="grid cols-2 overview-details">
      <div class="card overview-call-card">
        <div class="card-head">
          <div>
            <div class="card-title">${active ? 'Call in progress' : 'Call activity'}</div>
            <div class="card-sub">${active ? 'A call is currently using this site.' : 'No active call. New calls will appear here.'}</div>
          </div>
          <span class="live-dot ${active ? 'busy' : ''}">${active ? 'LIVE' : 'READY'}</span>
        </div>
        ${active ? `
          <div class="overview-active-call"><span class="call-wave" aria-hidden="true">〰</span><div><b>${esc(activeCallDisplay(active))}</b><p>${esc(activeCallSubtitle(active))}</p></div></div>
        ` : `<div class="overview-idle"><span aria-hidden="true">◌</span><div><b>All clear</b><p>There are no active calls on this addon.</p></div></div>`}
      </div>
      <div class="card overview-routes-card">
        <div class="card-head">
          <div>
            <div class="card-title">Your destinations</div>
            <div class="card-sub">The places calls can reach from this site.</div>
          </div>
          <button class="btn small secondary" data-page="routing">Manage</button>
        </div>
        <div class="list">
          ${settings.call_targets.slice(0, 4).map(targetRowReadonly).join("") || `<div class="overview-empty"><span aria-hidden="true">＋</span><b>No destinations configured</b><p>Add a SIP phone, gateway, or Home Assistant node to get started.</p><button class="btn small" data-page="routing">Set up routing</button></div>`}
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
