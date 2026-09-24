import{a as N}from"./chunk-MH4MHY7U.js";import{c as m,f as O}from"./chunk-RP7N3B43.js";import{a as U,e as s,f as C,h as d}from"./chunk-6R6CGC23.js";import{a as u,b as i,d as c,e as L}from"./chunk-OPL7LVHU.js";function M(){let e=d(),t=String(e.local_api_port||C.local_api_port||8799),a=window.location.hostname||"homeassistant.local";return`${window.location.port===t?window.location.protocol:"http:"}//${a}:${t}`}function k(e="TRIGGER_ID"){return`/api/automation/device/${d().automation.webhook_id||"WEBHOOK_ID"}/${e}`}function x(e="TRIGGER_ID"){return`${M()}${k(e)}`}function S(){return`/api/automation/webhook/${d().automation.webhook_id||"WEBHOOK_ID"}`}function j(){return`${M()}${S()}`}function Y(e=24){let t=new Uint8Array(e);if(window.crypto&&typeof window.crypto.getRandomValues=="function")window.crypto.getRandomValues(t);else for(let a=0;a<t.length;a+=1)t[a]=Math.floor(Math.random()*256);return Array.from(t,a=>a.toString(16).padStart(2,"0")).join("")}function Z(){let e=u("door-trigger-select")?.value||"",t=e?(d().automation.triggers||[]).find(n=>n.id===e):null,a=u("door-source")?.value||"",r=s.selectedDoorTriggerId;t&&t.source_extension&&t.source_extension!==a?s.selectedDoorTriggerId="":s.selectedDoorTriggerId=e,s.selectedDoorTriggerId!==r&&H()}function $(e){let t=Number(e),a=Number.isFinite(t)&&t>0?t:90;return Math.max(20,Math.min(3600,Math.round(a)))}function y(e){let t=String(e||"").trim();if(!t)return"No outdoor source selected";let a=s.sip.map(m).find(n=>n&&String(n.extension)===t);return`${a?.description||a?.username||t} (${t})`}function D(e){let t=Array.isArray(e)?e.filter(Boolean):[];return t.length?t.map(_).join(" + "):"No destinations selected"}function H(){let e=d(),t=e.automation,a=$(t.cooldown_seconds),r=s.sip.map(m).filter(o=>o&&o.enabled!==!1&&o.video_enabled),n=e.call_targets.filter(o=>["sip","asterisk","node","device"].includes(o.type)),v=(t.triggers||[]).filter(o=>o.mode==="door_station"),b=s.selectedDoorTriggerId||"",l=v.find(o=>o.id===b)||{},g=Array.isArray(l.target_ids)&&l.target_ids.length?l.target_ids:[l.target_id].filter(Boolean),p=new Set(g.map(String)),h=l.source_extension||r[0]?.extension||"",I=l.fanout_mode||"parallel",f=new Set(L(t.notify_services)),E=new Set(s.notificationTargets.map(o=>String(o.ref||""))),G=new Set(s.notificationTargets.filter(o=>o.rich_actions).map(o=>String(o.ref||""))),T=s.notificationTargets.filter(o=>{if(o.kind!=="entity")return!0;let w=String(o.ref||"").replace(/^notify\./,"");return!G.has(`notify.mobile_app_${w}`)||f.has(String(o.ref))}).filter(o=>o.rich_actions||f.has(String(o.ref))).sort((o,w)=>{let R=Number(f.has(String(w.ref)))-Number(f.has(String(o.ref)));return R||String(o.label||o.ref).localeCompare(String(w.label||w.ref))}),P=T.filter(o=>f.has(String(o.ref))),A=[...f].filter(o=>!E.has(o));u("content").innerHTML=`
    <div class="automation-grid">
      <div class="card glow">
        <div class="card-head">
          <div>
            <div class="card-title">Anti-spam guard</div>
            <div class="card-sub">Stops unknown-face devices from immediately retriggering after a call ends.</div>
          </div>
          <span class="pill ok">${i(a)}s cooldown</span>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Default cooldown seconds</label>
            <input type="number" min="20" max="3600" data-path="automation.cooldown_seconds" value="${i(a)}">
            <div class="hint">Minimum 20s. Recommended for face detection: 90-180 seconds.</div>
          </div>
          <div class="field">
            <label>Webhook ID</label>
            <input data-path="automation.webhook_id" value="${i(t.webhook_id)}" placeholder="site_unknown_face">
          </div>
          <div class="field full">
            <label>Webhook secret</label>
            <input type="password" data-path="automation.webhook_secret" value="${i(t.webhook_secret)}" placeholder="generate a long private secret">
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.webhook_enabled" ${t.webhook_enabled?"checked":""}> Enable webhook callbacks</label>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.block_while_call_active" ${t.block_while_call_active!==!1?"checked":""}> Suppress triggers while a call is already active</label>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.persistent_notifications" ${t.persistent_notifications!==!1?"checked":""}> Create Home Assistant notifications for door events</label>
          </div>
          <div class="field full">
            <div class="notify-recipient-head">
              <div>
                <label>Phones receiving incoming-call alerts</label>
                <div class="hint">Only Companion-app devices that support Answer, Decline, and dashboard deep links are shown.</div>
              </div>
              <button type="button" class="btn small secondary" data-action="toggle-notify-picker">${s.notificationPickerOpen?"Done":`Manage phones (${P.length})`}</button>
            </div>
            <div class="notify-selected-list">
              ${P.map(o=>`
                <span class="notify-selected-chip" title="${i(o.ref)}">
                  <b>${i(o.label||o.ref)}</b>
                  <button type="button" data-action="remove-notify-target" data-ref="${i(o.ref)}" aria-label="Remove ${i(o.label||o.ref)}">\xD7</button>
                </span>`).join("")||'<div class="inline-notice error compact"><div><b>No call-alert phone selected</b><span>Select at least one Companion device to receive incoming-call controls.</span></div></div>'}
            </div>
            ${s.notificationPickerOpen?`
              <div class="notify-picker-panel">
                <input id="notify-target-search" type="search" placeholder="Search phone name or notify service">
                <div class="notify-target-picker">
                  ${T.map(o=>`
                    <label class="notify-target ${f.has(String(o.ref))?"selected":""}" data-notify-search="${i(`${o.label||""} ${o.ref}`.toLowerCase())}">
                      <input type="checkbox" data-notify-target="${i(o.ref)}" ${f.has(String(o.ref))?"checked":""}>
                      <span><strong>${i(o.label||o.ref)}</strong><small>${i(o.ref)}</small></span>
                      <em class="rich">Call controls ready</em>
                    </label>`).join("")||`<div class="empty compact-empty">${i(s.notificationTargetsError||"No compatible Companion phones were discovered. Open the Companion app once, then refresh.")}</div>`}
                </div>
              </div>`:""}
            ${A.length?`<div class="inline-notice error compact"><div><b>Unavailable saved target</b><span>${i(A.join(", "))}</span></div></div>`:""}
            <details class="manual-notify"><summary>Manual or legacy target</summary><input data-path="automation.notify_services" value="${i(t.notify_services||"")}" placeholder="notify.mobile_app_phone"></details>
          </div>
          <div class="field full">
            <label>Notification opens this HA dashboard path</label>
            <input data-path="automation.dashboard_path" value="${i(t.dashboard_path||"/lovelace/default_view")}" placeholder="/lovelace/sip_webrtc">
            <div class="hint">Tapping the alert opens this dashboard. Answer &amp; Open controls the exact call first, then redirects here.</div>
          </div>
        </div>
        <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
          <button class="btn secondary" data-action="generate-webhook">Generate credentials</button>
          <button class="btn secondary" data-action="test-notification">Send Test Notification</button>
        </div>
        ${z(t)}
      </div>
      <div class="card">
        <div class="card-title">Door camera flow</div>
        <div class="card-sub">Door flows are separate from gateway fallback. Choose one outdoor source, then choose every SIP monitor or HAOS card that should be notified/ring.</div>
        <div class="door-flow multi" style="margin-top:14px">
          <div class="door-step">
            <label>1 \xB7 Outdoor source</label>
            <select id="door-source">${r.map(o=>c(o.extension,`${o.extension} \xB7 ${o.description||o.username}`,h)).join("")}</select>
            <div class="hint">This SIP device is called first so it can publish live audio + H.264 video.</div>
          </div>
          <div class="door-arrow">\u2192</div>
          <div class="door-step destination">
            <label>2 \xB7 Destinations</label>
            <div class="check-list">
              ${n.map(o=>`
                <label class="check-row">
                  <input type="checkbox" class="door-target-check" value="${i(o.id)}" ${p.has(String(o.id))?"checked":""}>
                  <span>
                    <strong>${i(o.label||o.id)}</strong>
                    <small>${i(W(o))}</small>
                  </span>
                </label>
              `).join("")||'<div class="empty">Add SIP phones or HAOS node routes first.</div>'}
            </div>
          </div>
        </div>
        <div class="form-grid" style="margin-top:14px">
          <div class="field full">
            <label>Saved door flow</label>
            <select id="door-trigger-select">
              <option value="">Create new door flow</option>
              ${v.length?v.map(o=>c(o.id,`${o.label||o.id} \u2014 ${y(o.source_extension||h)} \u2192 ${D(Array.isArray(o.target_ids)?o.target_ids:[o.target_id].filter(Boolean))}`,o.id===b)).join(""):""}
            </select>
          </div>
          <div class="field">
            <label>Flow name</label>
            <input id="door-label" value="${i(l.label||"Unknown visitor at front door")}">
          </div>
          <div class="field">
            <label>Ring time seconds</label>
            <input id="door-timeout" type="number" min="5" max="120" value="${i(l.timeout||30)}">
          </div>
          <div class="field">
            <label>Trigger cooldown seconds</label>
            <input id="door-cooldown" type="number" min="20" max="3600" value="${i($(l.cooldown_seconds||a))}">
            <div class="hint">Minimum 20s to prevent repeated face-detection calls.</div>
          </div>
          <div class="field">
            <label>Caller ID</label>
            <input id="door-caller" value="${i(l.caller_id||"")}" placeholder="Unknown visitor">
          </div>
          <div class="field full">
            <label>Fan-out mode</label>
            <select id="door-fanout">
              ${c("parallel","Ring selected destinations at the same time",I)}
              ${c("priority","Try destinations in priority order",I)}
            </select>
            <div class="hint">Native H.264 video is safest with one SIP monitor. If you select SIP + HAOS together, Simson uses shared bridge fanout so HAOS rings too; video remains native only in SIP-only monitor flows.</div>
          </div>
          <div class="field full">
            <div class="flow-preview">
              <strong>Current selected flow</strong>
              <span>Source: ${i(y(h))}</span>
              <b>\u2192</b>
              <span>Destinations: ${i(D(g)||"none")}</span>
            </div>
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn orange" data-action="create-door-flow">${b?"Update Door Flow":"Create Door Flow"}</button></div>
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
          <select id="intercom-source">${s.sip.map(m).filter(Boolean).map(o=>c(o.extension,`${o.extension} \xB7 ${o.description||o.username}`,"")).join("")}</select>
        </div>
        <div class="field">
          <label>Target SIP/node</label>
          <select id="intercom-target">${O("",!1)}</select>
        </div>
        <div class="field">
          <label>Source mode</label>
          <select id="intercom-source-mode">
            ${c("speaker","Auto-answer + speaker/intercom","speaker")}
            ${c("answer","Auto-answer only","")}
            ${c("manual","Manual answer","")}
          </select>
        </div>
        <div class="field">
          <label>Target mode</label>
          <select id="intercom-target-mode">
            ${c("speaker","Auto-answer + speaker/intercom","speaker")}
            ${c("answer","Auto-answer only","")}
            ${c("manual","Manual answer","")}
          </select>
        </div>
        <div class="field full">
          <label>Generated full URL</label>
          <input id="intercom-url" class="mono" readonly value="${i(B())}">
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
        ${t.triggers.map(K).join("")||'<div class="empty">No automation triggers yet.</div>'}
      </div>
    </div>
  `,N("automation")}function F(){let e=String(s.status?.server_url||U.server_url||"").trim();return e?e.startsWith("wss://")?`https://${e.slice(6).replace(/\/ws\/?$/,"")}`:e.startsWith("ws://")?`http://${e.slice(5).replace(/\/ws\/?$/,"")}`:e.replace(/\/ws\/?$/,"").replace(/\/$/,""):""}function B(){let e=u("intercom-source")?.value||s.sip.map(m).filter(Boolean)[0]?.extension||"",t=d().call_targets[0]?.id||s.sip.map(m).filter(Boolean).find(h=>h.extension!==e)?.extension||"",a=u("intercom-target")?.value||t,r=u("intercom-source-mode")?.value||"speaker",n=u("intercom-target-mode")?.value||"speaker",v=F(),b=s.status?.account_id||"",l=s.status?.node_id||"",g=s.status?.install_token||"";if(!v||!b||!l||!g||!e||!a)return"";let p=new URL("/node/sip-intercom",v);return p.searchParams.set("account_id",b),p.searchParams.set("node_id",l),p.searchParams.set("install_token",g),p.searchParams.set("source",e),p.searchParams.set("target",a),p.searchParams.set("source_auto_mode",r),p.searchParams.set("target_auto_mode",n),p.searchParams.set("timeout_sec","30"),p.toString()}function re(){let e=u("intercom-url");e&&(e.value=B())}function W(e){return e?["sip","asterisk"].includes(e.type)?`SIP/video extension ${e.extension||e.id}`:["node","device"].includes(e.type)?`HAOS node ${e.node_id||e.id}`:`${e.type||"target"} ${e.extension||e.node_id||e.id}`:""}function _(e){let t=d().call_targets.find(n=>String(n.id)===String(e));if(!t)return String(e||"");let a=t.label||t.id,r=t.extension?` (${t.extension})`:t.node_id?` (${t.node_id})`:"";return`${a}${r}`}function z(e){if(!e.webhook_id)return'<div class="empty" style="margin-top:14px">Generate credentials to get device callback URLs.</div>';let t=(d().automation.triggers||[]).filter(a=>a.mode==="door_station"&&String(a.id||"").trim());return t.length===1?`
      <div class="row" style="margin-top:14px">
        <div class="row-title">Door panel callback URL</div>
        <div class="row-sub">Paste this single full URL into the outdoor device. Change destinations below without changing the device URL.</div>
        <input class="mono" readonly value="${i(j())}" style="margin-top:8px;">
        <div class="row-sub" style="margin-top:6px;">POST with secret also works: ${i(S())}. Advanced per-trigger URL: ${i(k("TRIGGER_ID"))}</div>
      </div>
    `:`
    <div class="field-hint" style="margin-top:14px"><strong>${t.length} saved door flow(s)</strong></div>
    <div class="field-hint" style="margin-top:7px">Use a per-trigger callback URL for each outdoor device. Legacy stable callback requires exactly one enabled door flow.</div>
    ${t.map(a=>`
      <div class="row" style="margin-top:12px">
        <div class="row-title">${i(a.label||a.id)}</div>
        <div class="row-sub">Trigger ID: ${i(a.id)}</div>
        <input class="mono" readonly value="${i(x(a.id))}" style="margin-top:6px;">
      </div>
    `).join("")}
  `}function K(e){let t=Array.isArray(e.target_ids)&&e.target_ids.length?e.target_ids:[e.target_id].filter(Boolean),a=t.map(_).join(" + "),r=e.mode==="door_station"?$(e.cooldown_seconds||d().automation.cooldown_seconds):e.cooldown_seconds||d().automation.cooldown_seconds||90,n=e.mode==="door_station",v=e.fanout_mode==="priority"?"priority order":"same time";return`
    <div class="row ${n?"door-trigger-row":""}">
      <div class="row-main">
        <div style="min-width:0;">
          <div class="row-title">${i(e.label||e.id)}</div>
          ${n?`
            <div class="route-line">
              <span class="route-chip source">Outdoor ${i(y(e.source_extension))}</span>
              <span class="route-arrow">\u2192</span>
              <span class="route-chip destination">${i(a||"no destination")}</span>
            </div>
            <div class="row-sub">Door camera bridge \xB7 ${i(t.length)} destination(s) \xB7 fan-out ${i(v)} \xB7 cooldown ${i(r)}s \xB7 ring ${i(e.timeout||30)}s</div>
          `:`
            <div class="row-sub">${i(e.mode||"standard")} \xB7 targets ${i(a||"none")} \xB7 cooldown ${i(r)}s</div>
          `}
        </div>
        <div class="row-actions">
          <span class="pill ${e.enabled!==!1?"ok":"bad"}">${e.enabled!==!1?"enabled":"disabled"}</span>
          <button class="btn small red" data-action="delete-trigger" data-id="${i(e.id)}">Delete</button>
        </div>
      </div>
      ${n&&d().automation.webhook_id?`
        <div class="callback-box">
          <label>Single device callback URL for this full flow</label>
          <input class="mono" readonly value="${i(x(e.id))}">
          <div class="row-sub">Paste this one URL into the outdoor panel. It runs the saved source and every selected destination above.</div>
        </div>
      `:""}
    </div>
  `}export{H as a,F as b,B as c,re as d,W as e,_ as f,z as g,K as h,Y as i,Z as j,$ as k,y as l};
