import{a as m}from"./chunk-VUYAJJE6.js";import{k as c}from"./chunk-NYPYZHXP.js";import{c as d}from"./chunk-RP7N3B43.js";import{e as s,h as l}from"./chunk-6R6CGC23.js";import{a,b as n}from"./chunk-OPL7LVHU.js";function p(t){if(!t)return"Call";let e=String(t.direction==="incoming"?t.source_extension||t.caller_number||t.caller_id||"":t.target_extension||t.callee_number||t.remote_number||"").trim(),o=s.sip.map(d).find(i=>i&&String(i.extension)===e);return t.display_name||t.remote_name||t.caller_name||t.callee_name||o?.description||e||t.remote_label||t.remote_node_id||"Active call"}function u(t){let e=t?.direction==="incoming"?"Incoming":"Outgoing",o=t?.routing?.target_label||t?.routing?.target_id||t?.target_label||t?.target_type||t?.call_type||"voice",i=Number(t?.active_for||t?.duration_seconds||0);return`${e} \xB7 ${o}${i>0?` \xB7 ${Math.floor(i)}s`:""}`}function x(){let t=s.status||{},e=l(),o=t.active_call;a("content").innerHTML=`
    <div class="grid cols-3">
      ${r("VPS",t.vps_connected?"Online":"Offline",t.server_url||"not configured",t.vps_connected?"ok":"bad")}
      ${r("Asterisk",t.asterisk_connected?"Connected":"Unknown","AMI and SIP bridge state",t.asterisk_connected?"ok":"warn")}
      ${r("Automation guard",`${c(e.automation.cooldown_seconds)}s`,e.automation.block_while_call_active?"Blocks repeats while calls are active":"Cooldown only","ok")}
    </div>
    <div class="grid cols-2" style="margin-top:16px">
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">Live Call</div>
            <div class="card-sub">Current site call state</div>
          </div>
          <span class="pill ${o?"warn":"ok"}">${o?o.state:"idle"}</span>
        </div>
        ${o?`
          <div class="row" style="background:transparent;border:0;padding:8px 0;">
            <div class="row-title">${n(p(o))}</div>
            <div class="row-sub">${n(u(o))}</div>
          </div>
        `:'<div class="empty">No active call on this addon.</div>'}
      </div>
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">Routes at a glance</div>
            <div class="card-sub">${e.call_targets.length} saved route targets \xB7 ${e.automation.triggers.length} automation trigger(s)</div>
          </div>
        </div>
        <div class="list">
          ${e.call_targets.slice(0,5).map(m).join("")||'<div class="empty">No routes yet. Add routes from Routing.</div>'}
        </div>
      </div>
    </div>
  `}function r(t,e,o,i){return`
    <div class="stat">
      <span>${n(t)}</span>
      <b>${n(e)}</b>
      <span class="pill ${i==="bad"?"bad":i==="warn"?"warn":"ok"}">${n(o)}</span>
    </div>
  `}export{x as renderOverview,r as stat};
