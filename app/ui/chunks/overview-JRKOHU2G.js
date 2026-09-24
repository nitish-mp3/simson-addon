import{a as d}from"./chunk-VUYAJJE6.js";import{k as c}from"./chunk-U6KNJANJ.js";import"./chunk-HCD6FVME.js";import{c as l}from"./chunk-RP7N3B43.js";import{e as n,h as r}from"./chunk-6R6CGC23.js";import{a as o,b as s}from"./chunk-OPL7LVHU.js";function p(e){if(!e)return"Call";let t=String(e.direction==="incoming"?e.source_extension||e.caller_number||e.caller_id||"":e.target_extension||e.callee_number||e.remote_number||"").trim(),a=n.sip.map(l).find(i=>i&&String(i.extension)===t);return e.display_name||e.remote_name||e.caller_name||e.callee_name||a?.description||t||e.remote_label||e.remote_node_id||"Active call"}function v(e){let t=e?.direction==="incoming"?"Incoming":"Outgoing",a=e?.routing?.target_label||e?.routing?.target_id||e?.target_label||e?.target_type||e?.call_type||"voice",i=Number(e?.active_for||e?.duration_seconds||0);return`${t} \xB7 ${a}${i>0?` \xB7 ${Math.floor(i)}s`:""}`}function k(){let e=n.status||{},t=r(),a=e.active_call,i=!!e.vps_connected,u=n.sip.length,m=t.call_targets.length;o("content").innerHTML=`
    <section class="overview-hero ${i?"connected":"disconnected"}">
      <div class="overview-orbit" aria-hidden="true"><span></span><i></i></div>
      <div class="overview-copy"><span class="eyebrow">SITE CONTROL CENTER</span><h2>${s(e.node_id||"Your Simson node")}</h2><p>${i?"Your call services are connected and ready.":"The addon cannot reach the call service. Check the node and network connection."}</p><div class="overview-health"><i></i>${i?"Node online":"Connection needs attention"} <span>\xB7</span> ${e.asterisk_connected?"Asterisk connected":"Asterisk not confirmed"}</div></div>
      <button class="btn secondary overview-refresh" data-action="refresh">Refresh status <span aria-hidden="true">\u21BB</span></button>
    </section>
    <section class="overview-metrics" aria-label="System summary">
      <article class="metric-card"><span class="metric-icon" aria-hidden="true">\u260E</span><div><small>SIP devices</small><b>${u}</b><span>${n.sip.filter(b=>b.registered).length} registered</span></div><button data-page="sip" aria-label="Manage SIP devices">\u2197</button></article>
      <article class="metric-card"><span class="metric-icon" aria-hidden="true">\u21C4</span><div><small>Destinations</small><b>${m}</b><span>${t.automation.triggers.length} automations</span></div><button data-page="routing" aria-label="Manage routes">\u2197</button></article>
      <article class="metric-card"><span class="metric-icon" aria-hidden="true">\u25F7</span><div><small>Repeat call guard</small><b>${c(t.automation.cooldown_seconds)}<small>s</small></b><span>${t.automation.block_while_call_active?"Blocks while a call is active":"Cooldown enabled"}</span></div><button data-page="automation" aria-label="Manage automation">\u2197</button></article>
    </section>
    <div class="grid cols-2 overview-details">
      <div class="card overview-call-card">
        <div class="card-head">
          <div>
            <div class="card-title">${a?"Call in progress":"Call activity"}</div>
            <div class="card-sub">${a?"A call is currently using this site.":"No active call. New calls will appear here."}</div>
          </div>
          <span class="live-dot ${a?"busy":""}">${a?"LIVE":"READY"}</span>
        </div>
        ${a?`
          <div class="overview-active-call"><span class="call-wave" aria-hidden="true">\u3030</span><div><b>${s(p(a))}</b><p>${s(v(a))}</p></div></div>
        `:'<div class="overview-idle"><span aria-hidden="true">\u25CC</span><div><b>All clear</b><p>There are no active calls on this addon.</p></div></div>'}
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
          ${t.call_targets.slice(0,4).map(d).join("")||'<div class="overview-empty"><span aria-hidden="true">\uFF0B</span><b>No destinations configured</b><p>Add a SIP phone, gateway, or Home Assistant node to get started.</p><button class="btn small" data-page="routing">Set up routing</button></div>'}
        </div>
      </div>
    </div>
  `}function x(e,t,a,i){return`
    <div class="stat">
      <span>${s(e)}</span>
      <b>${s(t)}</b>
      <span class="pill ${i==="bad"?"bad":i==="warn"?"warn":"ok"}">${s(a)}</span>
    </div>
  `}export{k as renderOverview,x as stat};
