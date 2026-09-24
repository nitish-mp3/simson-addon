import{b as G}from"./chunk-VUYAJJE6.js";import{i as $}from"./chunk-SKZ5RTBX.js";import{a as P,c as g,d as _}from"./chunk-XNCLTULO.js";import{a as H}from"./chunk-MH4MHY7U.js";import{c as p,d as f,e as A,f as N,i as R,j as h}from"./chunk-RP7N3B43.js";import{e as n,h as w}from"./chunk-6R6CGC23.js";import{a as b,b as d,d as c,e as F,f as E}from"./chunk-OPL7LVHU.js";function le(){n.advancedDraft=q(),u(),requestAnimationFrame(()=>b("advanced-route-form")?.scrollIntoView({behavior:"smooth",block:"start"}))}function ce(){let e=f();if(e.length<2)throw new Error("Direct outside forwarding needs separate inbound and outbound gateways. Add or enable a second gateway first.");n.advancedDraft={id:"",name:"Direct outside forward",ingress_kind:"gateway",ingress_value:e[0].extension,enabled:!0,stages:[{id:`stage_${$(4)}`,name:"Forward immediately",ring_seconds:60,max_call_seconds:0,answer_mode:"first_answer",max_answered:1,targets:[{id:`target_${$(4)}`,kind:"external",value:"",trunk:e[1].extension,label:"Outside destination",enabled:!0}]}]},u(),requestAnimationFrame(()=>b("advanced-route-form")?.scrollIntoView({behavior:"smooth",block:"start"}))}async function ue(){let e={transfer_code:String(n.callFeatures?.transfer_code||"").trim(),conference_code:String(n.callFeatures?.conference_code||"").trim(),invite_listen_code:String(n.callFeatures?.invite_listen_code||"*86").trim(),invite_whisper_code:String(n.callFeatures?.invite_whisper_code||"*87").trim(),invite_barge_code:String(n.callFeatures?.invite_barge_code||"*88").trim(),enabled:n.callFeatures?.enabled!==!1},a=await _("api/call-features",{method:"PUT",body:JSON.stringify(e)});n.callFeatures=a,n.callFeaturesError="",g("Site phone codes saved and applied."),u()}async function ve(){let e=String(n.activeInvite.source_extension||"").trim(),a=String(n.activeInvite.target||"").trim();if(!e||!a)throw new Error("Choose the active participant and enter who should be invited.");let t=await _("api/active-call-invite",{method:"POST",body:JSON.stringify({source_extension:e,target:a,mode:n.activeInvite.mode||"barge",timeout_sec:30})});return g(`${n.activeInvite.mode==="barge"?"Participant":n.activeInvite.mode==="whisper"?"Coach":"Listener"} invitation sent to ${a}.`),t}function pe(e){let a=n.advancedRoutes.find(t=>String(t.id)===String(e));a&&(n.advancedDraft=structuredClone(a),!n.advancedDraft.enabled&&(n.advancedDraft.stages||[]).some(t=>t.answer_mode==="private_hub")&&(n.advancedDraft._disabled_for_private_hub=!0),u(),requestAnimationFrame(()=>b("advanced-route-form")?.scrollIntoView({behavior:"smooth",block:"start"})))}function ge(){n.advancedDraft=null,u()}function be(){if(n.advancedDraft){if(n.advancedDraft.stages.length>=10){g("A route can contain at most 10 stages.");return}n.advancedDraft.stages.push({id:`stage_${$(4)}`,name:`Stage ${n.advancedDraft.stages.length+1}`,ring_seconds:20,max_call_seconds:0,answer_mode:"first_answer",max_answered:1,targets:[]}),u()}}function me(e){if(n.advancedDraft){if(n.advancedDraft.stages.length<=1){g("A route needs at least one stage.");return}n.advancedDraft.stages.splice(Number(e),1),u()}}function T(e){return e==="haos"?n.nodes[0]?.id||"":e==="gateway"?f()[0]?.extension||"":e==="sip"&&n.sip.map(p).filter(a=>a&&!h(a))[0]?.extension||""}function fe(e){let a=n.advancedDraft?.stages?.[Number(e)];if(!a)return;if(a.targets.length>=20){g("A stage can contain at most 20 destinations.");return}let t=T("sip")?"sip":T("haos")?"haos":"gateway",s=a.targets.some(i=>i.role==="hub");a.targets.push({id:`target_${$(4)}`,kind:t,value:T(t),trunk:"",label:"",role:a.answer_mode==="private_hub"&&!s?"hub":"spoke",enabled:!0}),u()}function he(e,a){let t=n.advancedDraft?.stages?.[Number(e)];t&&(t.targets.splice(Number(a),1),u())}function M(e){let a=structuredClone(e);return delete a._disabled_for_private_hub,a.name=String(a.name||"").trim(),a.ingress_value=String(a.ingress_value||"").trim(),a.stages=(a.stages||[]).map((t,s)=>({...t,id:t.id||`stage_${s+1}`,name:String(t.name||`Stage ${s+1}`).trim(),ring_seconds:Number(t.ring_seconds)||20,max_call_seconds:Math.max(0,Number(t.max_call_seconds)||0),max_answered:t.answer_mode==="first_answer"?1:Number(t.max_answered)||2,targets:(t.targets||[]).map((i,o)=>({...i,id:i.id||`target_${s+1}_${o+1}`,value:String(i.value||"").trim(),trunk:String(i.trunk||"").trim(),label:String(i.label||"").trim(),enabled:i.enabled!==!1}))})),a}function D(e){if(!String(e?.name||"").trim())return"Enter a plan name.";if(!["gateway","sip"].includes(String(e?.ingress_kind||"")))return"Choose whether calls enter from a gateway or SIP phone.";if(!String(e?.ingress_value||"").trim())return"Choose the exact incoming gateway or SIP phone.";if(!Array.isArray(e?.stages)||!e.stages.length)return"Add at least one routing stage.";let a=new Map,t=String(e?.ingress_kind||"").trim().toLowerCase(),s=String(e?.ingress_value||"").trim();for(let[i,o]of(e?.stages||[]).entries()){let r=(o?.targets||[]).filter(v=>v?.enabled!==!1),l=t==="sip"&&i===0,x=r.length+(l&&!r.some(v=>String(v?.kind||"").trim().toLowerCase()==="sip"&&String(v?.value||"").trim()===s)?1:0),k=Number(o?.ring_seconds),S=Number(o?.max_call_seconds||0);if(!x)return`Stage ${i+1} needs at least one active destination.`;if(!Number.isFinite(k)||k<3||k>300)return`Stage ${i+1} ring time must be between 3 and 300 seconds.`;if(!Number.isFinite(S)||S<0||S>86400||S>0&&S<10)return`Stage ${i+1} connected-call limit must be 0 (unlimited) or between 10 and 86400 seconds.`;if(o?.answer_mode==="conference"&&r.some(v=>v.kind!=="sip"))return`Stage ${i+1} conference mode supports SIP phones only.`;let C=r.filter(v=>String(v?.kind||"").trim().toLowerCase()==="external");if(C.length){if(x!==1)return`Stage ${i+1} outside forwarding must be the only destination in its stage. This prevents an analog gateway from answering and cancelling parallel phones.`;if(o?.answer_mode!=="first_answer")return`Stage ${i+1} outside forwarding must use First answer wins.`;if(t==="gateway"&&String(C[0]?.trunk||"").trim()===s)return`Stage ${i+1} cannot send the call back out through incoming gateway ${s}. Choose a separate outbound gateway.`}for(let v of r){if(v?.enabled===!1)continue;let y=String(v?.kind||"").trim().toLowerCase(),m=String(v?.value||"").trim(),O=String(v?.trunk||"").trim();if(!m)return`Stage ${i+1} has a destination with no value selected.`;if(y==="external"&&!O)return`Stage ${i+1} outside number ${m} needs an outbound gateway.`;if(t!=="manual"&&(y==="sip"||y==="gateway")&&m===s&&!(t==="sip"&&y==="sip"&&m===s&&i===0))return`Stage ${i+1} routes ${m} back to its own incoming source.`;let I=y==="sip"||y==="gateway"?`endpoint:${m}`:`${y}:${m}:${O}`;if(a.has(I))return`${m} is already used in stage ${a.get(I)}. A destination can appear only once in a route plan.`;a.set(I,i+1)}}return""}async function ye(){if(!n.advancedDraft)return;let e=M(n.advancedDraft),a=D(e);if(a){g(a),u();return}let t=e.id?`api/advanced-routes/${encodeURIComponent(e.id)}`:"api/advanced-routes",s=await _(t,{method:e.id?"PUT":"POST",body:JSON.stringify(e)}),i=n.advancedRoutes.findIndex(o=>o.id===s.id);i>=0?n.advancedRoutes[i]=s:n.advancedRoutes.push(s),n.advancedDraft=structuredClone(s),g(e.id?"Route plan updated.":"Route plan created."),u()}async function we(e){let a=n.advancedRoutes.find(t=>t.id===e);!a||!window.confirm(`Delete route plan \u201C${a.name}\u201D? Existing legacy routes are not affected.`)||(await _(`api/advanced-routes/${encodeURIComponent(e)}`,{method:"DELETE"}),n.advancedRoutes=n.advancedRoutes.filter(t=>t.id!==e),n.advancedDraft?.id===e&&(n.advancedDraft=null),g("Route plan deleted."),u())}async function $e(e,a){let t=n.advancedRoutes.find(r=>String(r.id)===String(e));if(!t)return;if(a&&(t.stages||[]).some(r=>r.answer_mode==="private_hub"))throw new Error("Private hub plans require the isolated-media worker and cannot be activated as a shared conference.");let s=M({...t,enabled:a}),i=await _(`api/advanced-routes/${encodeURIComponent(e)}`,{method:"PUT",body:JSON.stringify(s)}),o=n.advancedRoutes.findIndex(r=>String(r.id)===String(e));o>=0&&(n.advancedRoutes[o]=i),n.advancedDraft?.id===e&&(n.advancedDraft=structuredClone(i)),g(a?"Route plan is live.":"Route plan saved as draft."),u()}function _e(){let e=b("quick-kind").value,a=b("quick-label").value.trim(),t=b("quick-value").value.trim();if(!a||!t){g("Route needs a name and destination.");return}let s=E(a||t),i=e==="intercom"?"gateway":e,o={id:s,label:a,type:i,node_id:i==="node"?t:"",extension:i!=="node"?t:"",trunk:i==="gateway"?A():"",timeout:w().routing.ring_seconds||25,fallback_targets:F(b("quick-fallbacks").value)};w().call_targets.push(o),P("Route added. Save to keep it."),u()}function ke(e){w().call_targets.splice(Number(e),1),P("Route deleted. Save to keep it."),u()}function Se(e,a){let t=w();t.route_overrides[e]={mode:a,reason:""},P("Availability changed. Save to keep it."),u()}function q(){let e=f()[0]?.extension||"",a=n.sip.map(p).filter(Boolean).find(t=>!h(t));return{id:"",name:"",ingress_kind:e?"gateway":"sip",ingress_value:e||a?.extension||"",enabled:!0,stages:[{id:`stage_${$(4)}`,name:"First response",ring_seconds:20,answer_mode:"first_answer",max_answered:1,targets:[]}]}}function j(){let e=n.advancedRoutes||[],a=n.advancedDraft;return`
    <section class="advanced-routing" aria-labelledby="advanced-routing-title">
      ${U()}
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
        ${n.advancedRoutesError?`<div class="inline-notice error"><div><b>Advanced routing could not be loaded</b><span>${d(n.advancedRoutesError)}</span></div><button class="btn small secondary" data-action="refresh">Retry</button></div>`:""}
        ${e.map(V).join("")||'<div class="empty compact-empty">No advanced plans. Existing gateway and SIP routing remains unchanged.</div>'}
      </div>
      ${a?J(a):""}
    </section>`}function U(){let e=n.callFeatures||{},a=n.sip.map(p).filter(l=>l&&l.enabled!==!1&&!h(l)),t=n.sip.map(p).filter(l=>l&&l.enabled!==!1&&h(l)),s=n.activeInvite.source_extension||a[0]?.extension||"",i=a.map(l=>`<option value="${d(l.extension)}">${d(l.extension)} \xB7 ${d(l.description||l.username||"SIP phone")}</option>`).join(""),o=a.map(l=>`<option value="${d(l.extension)}">${d(l.description||l.username||l.extension)}</option>`).join(""),r=t.length?`Outside format: *${d(t[0].extension)}*number`:"Add an enabled gateway before inviting an outside number.";return`<div class="site-feature-card">
    <div class="site-feature-copy">
      <div class="kicker">Account-wide phone controls</div>
      <h3>Transfer, conference and active-call invitations</h3>
      <p>These codes apply only to SIP phones in this site/account. A person already on a call can invite another phone as a private listener, coach, or full participant.</p>
    </div>
    <label class="toggle-line feature-enabled"><input type="checkbox" data-call-feature-key="enabled" ${e.enabled!==!1?"checked":""}> Enabled</label>
    <div class="feature-code-grid">
      <div class="field">
        <label>Blind transfer prefix</label>
        <input data-call-feature-key="transfer_code" value="${d(e.transfer_code||"*84")}" inputmode="tel" placeholder="*84">
        <small>While connected, send <b>${d(e.transfer_code||"*84")}1028#</b>. For an outside transfer through a chosen gateway, send <b>${d(e.transfer_code||"*84")}*7014*9123208334#</b>.</small>
      </div>
      <div class="field">
        <label>Conference launch prefix</label>
        <input data-call-feature-key="conference_code" value="${d(e.conference_code||"*85")}" inputmode="tel" placeholder="*85">
        <small>While connected, send <b>${d(e.conference_code||"*85")}1028#</b> to invite SIP 1028. Send <b>${d(e.conference_code||"*85")}*7014*9123208334#</b> to invite an outside number through gateway 7014.</small>
      </div>
      <div class="field">
        <label>Invite as listener</label>
        <input data-call-feature-key="invite_listen_code" value="${d(e.invite_listen_code||"*86")}" inputmode="tel" placeholder="*86">
        <small>The current participant sends <b>${d(e.invite_listen_code||"*86")}1026#</b>. SIP 1026 hears the active call but cannot speak into it.</small>
      </div>
      <div class="field">
        <label>Invite as private coach</label>
        <input data-call-feature-key="invite_whisper_code" value="${d(e.invite_whisper_code||"*87")}" inputmode="tel" placeholder="*87">
        <small>The current participant sends this prefix plus an extension and <b>#</b>. The invited phone can privately coach that participant.</small>
      </div>
      <div class="field">
        <label>Invite with full barge</label>
        <input data-call-feature-key="invite_barge_code" value="${d(e.invite_barge_code||"*88")}" inputmode="tel" placeholder="*88">
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
        <label><span>Active participant</span><select data-active-invite-key="source_extension">${i.replace(`value="${d(s)}"`,`value="${d(s)}" selected`)}</select></label>
        <label><span>Invite as</span><select data-active-invite-key="mode">
          <option value="listen" ${n.activeInvite.mode==="listen"?"selected":""}>Listener \xB7 cannot speak</option>
          <option value="whisper" ${n.activeInvite.mode==="whisper"?"selected":""}>Private coach \xB7 source hears them</option>
          <option value="barge" ${n.activeInvite.mode==="barge"?"selected":""}>Full participant \xB7 everyone hears</option>
        </select></label>
        <label><span>SIP extension or outside route</span><input data-active-invite-key="target" list="active-invite-targets" value="${d(n.activeInvite.target)}" placeholder="1026 or *7014*9123208334"><datalist id="active-invite-targets">${o}</datalist><small>${r}</small></label>
        <button class="btn active-invite-button" data-action="active-call-invite" ${a.length<2?"disabled":""}>Invite now</button>
      </div>
    </div>
    ${n.callFeaturesError?`<div class="inline-notice error compact-feature-error"><div><b>Phone controls unavailable</b><span>${d(n.callFeaturesError)}</span></div></div>`:""}
  </div>`}function V(e){let a=Array.isArray(e.stages)?e.stages:[],t=f().filter(i=>String(i.gateway_inbound_mode||"")==="direct_target"&&String(i.gateway_direct_target||"")===String(e.id||"")),s=a.map((i,o)=>{let l=(i.targets||[]).filter(k=>k.enabled!==!1).map(B);o===0&&e.ingress_kind==="sip"&&l.unshift(`${L(e)} (primary)`);let x=l.join(" + ")||"no destination";return`<span class="route-stage-pill"><b>${o+1}</b><span>${d(i.name||`Stage ${o+1}`)}<small>${d(x)} \xB7 ${d(i.ring_seconds||0)}s</small></span></span>`}).join('<span class="route-arrow">\u2192</span>');return`<article class="route-plan-summary ${e.enabled?"":"disabled"}">
    <div class="route-plan-main">
      <div class="route-plan-title"><span class="pill ${e.enabled?"ok":"warn"}">${e.enabled?"live":"draft"}</span>${d(e.name)}</div>
      <div class="route-plan-ingress"><span>${e.ingress_kind==="sip"?"Calls landing on":"Calls entering from"}</span><b>${d(L(e))}</b></div>
      ${e.ingress_kind==="gateway"?`<div class="route-plan-assignment ${t.length?"ok":"warn"}"><b>${t.length?`Assigned gateway${t.length===1?"":"s"}: ${t.map(i=>i.extension).join(", ")}`:"Not assigned to a gateway"}</b><span>${t.length?"Calls use this full staged plan as soon as they arrive.":"If the physical gateway sends calls to a different extension, open that gateway below and select this route plan."}</span></div>`:""}
      <div class="route-stage-path">${s||"No escalation stages"}</div>
      ${e.ingress_kind==="sip"?'<div class="route-plan-trigger">Calls to this SIP extension use this plan, whether they come from another SIP phone, a gateway, or a HAOS node. Normal extension-to-extension calls remain direct when no plan is enabled.</div>':""}
    </div>
    <div class="row-actions">
      ${!e.enabled&&!a.some(i=>i.answer_mode==="private_hub")?`<button class="btn small" data-action="advanced-activate" data-id="${d(e.id)}">Activate</button>`:""}
      <button class="btn small secondary" data-action="advanced-edit" data-id="${d(e.id)}">Edit</button>
      <button class="btn small red" data-action="advanced-delete" data-id="${d(e.id)}">Delete</button>
    </div>
  </article>`}function L(e){let a=String(e?.ingress_value||""),t=n.sip.map(p).filter(Boolean).find(i=>String(i.extension)===a),s=t?.description||t?.username||a||"not selected";return`${e?.ingress_kind==="gateway"?"Gateway":"SIP phone"} ${a}${s&&s!==a?` \xB7 ${s}`:""}`}function B(e){let a=String(e?.value||"");if(e?.kind==="external")return`Gateway ${e.trunk||"not selected"} dials ${a||"no number selected"}`;if(e?.kind==="haos")return`HAOS ${n.nodes.find(o=>String(o.id)===a)?.label||a}`;let t=n.sip.map(p).filter(Boolean).find(i=>String(i.extension)===a);return`${e?.kind==="gateway"?"Gateway/FXO":"SIP"} ${a}${t?.description?` \xB7 ${t.description}`:""}`}function J(e){let a=Array.isArray(e.stages)?e.stages:[],t=a.some(i=>i.answer_mode==="private_hub"),s=D(e);return`<form class="advanced-editor" id="advanced-route-form">
    <div class="advanced-editor-head">
      <div>
        <div class="kicker">${e.id?"Edit route plan":"New route plan"}</div>
        <h3>${d(e.name||"Untitled route")}</h3>
      </div>
      <button type="button" class="icon-btn" data-action="advanced-close" aria-label="Close editor">\xD7</button>
    </div>
    <div class="advanced-route-basics">
      <div class="field wide"><label>Plan name</label><input data-advanced-route-key="name" value="${d(e.name)}" placeholder="Main line escalation"></div>
      <div class="field"><label>Match incoming call by</label><select data-advanced-route-key="ingress_kind">
        ${c("gateway","Gateway / FXO / GSM",e.ingress_kind)}
        ${c("sip","SIP phone",e.ingress_kind)}
      </select></div>
      <div class="field"><label>${e.ingress_kind==="sip"?"Called SIP phone":"Incoming gateway"}</label>${W(e)}</div>
      <label class="toggle-line"><input type="checkbox" data-advanced-route-key="enabled" ${e.enabled?"checked":""}> Enable this exact landing route</label>
    </div>
    <div class="advanced-route-note">${e.ingress_kind==="sip"?`Calls landing on SIP phone <b>${d(e.ingress_value||"not selected")}</b> automatically ring that phone in <b>Stage 1</b>. Any other Stage 1 destinations ring in parallel; later stages are fallbacks. The caller hears waiting audio instead of silence. No special <b>100</b> dial is required.`:`Only calls arriving through gateway <b>${d(e.ingress_value||"not selected")}</b> use this plan. Other calls keep their current routing.`}</div>
    ${s?`<div class="inline-notice error"><div><b>Fix this route before saving</b><span>${d(s)}</span></div></div>`:""}
    <div class="stage-stack">
      ${a.map(z).join("")}
    </div>
    <div class="advanced-editor-actions">
      <button type="button" class="btn secondary" data-action="advanced-add-stage">+ Add next stage</button>
      <span class="capability-note ${t?"warn":""}">${t?"Private hub is saved disabled until isolated-media support is assigned; this prevents spoke audio leakage.":"Stages run in order. Targets inside a stage ring at the same time."}</span>
      <button type="button" class="btn" data-action="advanced-save">${e.id?"Save plan":"Create plan"}</button>
    </div>
  </form>`}function W(e){let a=e.ingress_kind==="gateway"?f():n.sip.map(p).filter(s=>s&&!h(s));return`<select data-advanced-route-key="ingress_value">
    ${!a.some(s=>String(s.extension)===String(e.ingress_value))&&e.ingress_value?c(e.ingress_value,`${e.ingress_value} \xB7 current`,e.ingress_value):""}
    ${a.map(s=>c(s.extension,`${s.extension} \xB7 ${s.description||s.username||e.ingress_kind}`,e.ingress_value)).join("")}
  </select>`}function z(e,a){let t=Array.isArray(e.targets)?e.targets:[],s=e.answer_mode==="conference",i=e.answer_mode==="private_hub";return`<article class="advanced-stage ${i?"unsupported":""}">
    <div class="stage-number">${String(a+1).padStart(2,"0")}</div>
    <div class="stage-body">
      <div class="stage-controls">
        <div class="field wide"><label>Stage name</label><input data-advanced-stage-index="${a}" data-advanced-stage-key="name" value="${d(e.name)}"></div>
        <div class="field small"><label>Ring for</label><div class="input-suffix"><input type="number" min="3" max="300" data-advanced-stage-index="${a}" data-advanced-stage-key="ring_seconds" value="${d(e.ring_seconds)}"><span>s</span></div></div>
        <div class="field small"><label>End connected call after</label><div class="input-suffix"><input type="number" min="0" max="86400" data-advanced-stage-index="${a}" data-advanced-stage-key="max_call_seconds" value="${d(e.max_call_seconds||0)}"><span>s</span></div></div>
        <div class="field"><label>When answered</label><select data-advanced-stage-index="${a}" data-advanced-stage-key="answer_mode">
          ${c("first_answer","First answer wins",e.answer_mode)}
          ${c("conference","Conference answered SIP phones",e.answer_mode)}
          ${c("private_hub","Private hub / whisper (requires media worker)",e.answer_mode)}
        </select></div>
        ${s||i?`<div class="field small"><label>Participant limit</label><input type="number" min="1" max="10" data-advanced-stage-index="${a}" data-advanced-stage-key="max_answered" value="${d(e.max_answered||2)}"></div>`:""}
        <button type="button" class="icon-btn danger" data-action="advanced-remove-stage" data-stage="${a}" aria-label="Remove stage">\xD7</button>
      </div>
      <div class="stage-policy">${X(e)}</div>
      ${a===0&&n.advancedDraft?.ingress_kind==="sip"?`<div class="landing-target-lock"><span class="landing-target-icon">IN</span><span><b>${d(n.advancedDraft.ingress_value||"Choose a landing SIP phone")}</b><small>Primary landing phone \xB7 added automatically to this stage</small></span><span class="pill ok">always rings</span></div>`:""}
      <div class="advanced-targets">
        ${t.map((o,r)=>K(o,a,r,e.answer_mode)).join("")||'<div class="empty compact-empty">Add one or more destinations for this stage.</div>'}
      </div>
      <button type="button" class="text-button" data-action="advanced-add-target" data-stage="${a}">+ Add parallel destination</button>
    </div>
  </article>`}function X(e){let a=e?.answer_mode;if(a==="conference"){let t=(e?.targets||[]).filter(i=>i?.enabled!==!1).length,s=Math.max(1,Number(e?.max_answered)||1);return`All ${t} active SIP destination${t===1?"":"s"} ring together. Up to ${s} answered destination${s===1?"":"s"} stay in the conference; the original caller is additional and is not counted in this limit.`}return a==="private_hub"?"Isolation contract: the hub may talk to every spoke while spokes remain private. This plan stays draft until the ARI isolated-media worker is installed; Simson will never substitute a shared conference that leaks spoke audio.":"The first destination to answer owns the call; all other ringing destinations are cancelled immediately."}function K(e,a,t,s){let i=e.kind==="external"?"Number or intercom extension to dial":e.kind==="haos"?"HAOS node/card":e.kind==="gateway"?"Gateway or wired port":"SIP phone",o=Q(e);return`<div class="advanced-target ${e.enabled===!1?"disabled":""}">
    <div class="advanced-target-field kind"><label>Destination type</label><select aria-label="Destination type" data-advanced-target-stage="${a}" data-advanced-target-index="${t}" data-advanced-target-key="kind">
      ${c("sip","SIP phone",e.kind)}
      ${c("haos","HAOS card / node",e.kind)}
      ${c("gateway","Gateway / FXO port",e.kind)}
      ${c("external","Number/extension through gateway",e.kind)}
    </select></div>
    <div class="advanced-target-field destination"><label>${d(i)}</label>${Y(e,a,t)}</div>
    ${e.kind==="external"?`<div class="advanced-target-field trunk"><label>Gateway that places the call</label><select aria-label="Outbound gateway" data-advanced-target-stage="${a}" data-advanced-target-index="${t}" data-advanced-target-key="trunk">${R(e.trunk||"")}</select></div>`:""}
    ${s==="private_hub"?`<select aria-label="Private hub role" data-advanced-target-stage="${a}" data-advanced-target-index="${t}" data-advanced-target-key="role">${c("spoke","Spoke (private)",e.role||"spoke")}${c("hub","Main hub",e.role||"spoke")}</select>`:""}
    <input aria-label="Destination label" data-advanced-target-stage="${a}" data-advanced-target-index="${t}" data-advanced-target-key="label" value="${d(e.label||"")}" placeholder="Label (optional)">
    ${o?`<span class="pill ${o.ok?"ok":"warn"}" title="${d(o.detail)}">${d(o.label)}</span>`:""}
    <label class="target-enabled"><input type="checkbox" data-advanced-target-stage="${a}" data-advanced-target-index="${t}" data-advanced-target-key="enabled" ${e.enabled!==!1?"checked":""}> Active</label>
    <button type="button" class="icon-btn danger" data-action="advanced-remove-target" data-stage="${a}" data-target="${t}" aria-label="Remove destination">\xD7</button>
  </div>`}function Q(e){let a=String(e?.value||"").trim();if(!a)return null;if(e?.kind==="sip"||e?.kind==="gateway"){let t=n.sip.map(p).filter(Boolean).find(s=>String(s.extension)===a);return t?t.registered?{ok:!0,label:"registered",detail:t.contact_address||t.contact_uri||"Asterisk has a live contact."}:{ok:!1,label:"offline",detail:t.contact_status||"Asterisk has no live SIP contact, so this destination cannot ring."}:{ok:!1,label:"unknown",detail:"This endpoint is not present in the current site endpoint list."}}if(e?.kind==="haos"){let t=n.nodes.find(i=>String(i.id)===a);return!!(t?.online??t?.connected??t?.is_online)?{ok:!0,label:"online",detail:"The HAOS node is connected."}:{ok:!1,label:"offline",detail:"The HAOS node is not currently connected."}}return null}function Y(e,a,t){let s=`data-advanced-target-stage="${a}" data-advanced-target-index="${t}" data-advanced-target-key="value"`;if(e.kind==="external")return`<input ${s} value="${d(e.value)}" placeholder="Exact phone or intercom number"><small>The selected gateway dials this exact value.</small>`;let i=[];e.kind==="haos"&&(i=n.nodes.map(r=>({value:r.id,label:`${r.label||r.id} \xB7 HAOS`}))),e.kind==="gateway"&&(i=f().map(r=>({value:r.extension,label:`${r.extension} \xB7 ${r.description||"gateway"}`}))),e.kind==="sip"&&(i=n.sip.map(p).filter(r=>r&&!h(r)).map(r=>({value:r.extension,label:`${r.extension} \xB7 ${r.description||r.username||"SIP"}`})));let o=i.some(r=>String(r.value)===String(e.value));return`<select ${s}>${!o&&e.value?c(e.value,`${e.value} \xB7 current`,e.value):""}${i.map(r=>c(r.value,r.label,e.value)).join("")}</select>`}function u(){let e=w(),a=A(),t=e.routing.gateway_inbound_mode||"haos_then_fallback",s=e.routing.gateway_direct_target||"";b("content").innerHTML=`
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
              ${R(e.routing.default_gateway_trunk||"")}
            </select>
            <div class="hint">SIP phones can dial outside numbers directly. Use a gateway prefix only when forcing a specific line.</div>
          </div>
          <div class="field">
            <label>Inbound gateway behavior</label>
            <select data-path="routing.gateway_inbound_mode">
              ${c("haos_then_fallback","Ring HAOS first, then fallback",t)}
              ${c("direct_target","Send directly to selected target",t)}
            </select>
            <div class="hint">Use direct mode for landline/GSM gateways that should always ring a SIP phone or route immediately.</div>
          </div>
          <div class="field">
            <label>Direct inbound target</label>
            <select data-path="routing.gateway_direct_target">
              ${N(s,!0)}
            </select>
            <div class="hint">Only used when inbound behavior is direct. Pick a SIP phone, route target, or HAOS node.</div>
          </div>
          <div class="field">
            <label>Strategy</label>
            <select data-path="routing.strategy">
              ${c("priority","Try saved fallback order",e.routing.strategy)}
              ${c("round_robin","Round robin",e.routing.strategy)}
            </select>
          </div>
          <div class="field">
            <label>Ring HAOS before fallback</label>
            <input type="number" min="5" max="300" data-path="routing.ring_seconds" value="${d(e.routing.ring_seconds)}">
            <div class="hint">Gateway calls ring this dashboard first for this many seconds.</div>
          </div>
          <div class="field">
            <label>Max attempts</label>
            <input type="number" min="1" max="20" data-path="routing.max_attempts" value="${d(e.routing.max_attempts)}">
          </div>
          <div class="field">
            <label>Gateway fallback target</label>
            <input data-path="routing.final_fallback_target" value="${d(e.routing.final_fallback_target)}" placeholder="1025 or security_desk">
            <div class="hint">Only this explicit target, or a gateway route's fallback list, receives missed gateway calls.</div>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="routing.skip_unavailable" ${e.routing.skip_unavailable?"checked":""}> Skip busy/offline targets</label>
          </div>
        </div>
        <div class="flow-preview route-preview" style="margin-top:14px;">
          <strong>Gateway call path</strong>
          <span>PSTN/GSM gateway call</span>
          <b>\u2192</b>
          ${t==="direct_target"?`<span>direct transfer</span><b>\u2192</b><span>${d(s||"no target selected")}</span>`:`<span>HAOS card for ${d(e.routing.ring_seconds)}s</span><b>\u2192</b><span>${d(e.routing.final_fallback_target||"no automatic SIP fallback")}</span>`}
        </div>
        <div class="flow-preview route-preview" style="margin-top:10px;">
          <strong>Outside dial path</strong>
          <span>SIP phone dials number</span>
          <b>\u2192</b>
          <span>${d(a||"auto gateway")}</span>
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
    <datalist id="node-list">${n.nodes.map(i=>`<option value="${d(i.id)}">${d(i.label||i.id)}</option>`).join("")}</datalist>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Routing targets</div>
          <div class="card-sub">Each row shows exactly what it is: HAOS node, SIP extension, or outbound gateway route.</div>
        </div>
      </div>
      <div class="list" id="target-list">
        ${e.call_targets.map(G).join("")||'<div class="empty">No route targets yet.</div>'}
      </div>
    </div>
    ${j()}
  `,H("routing")}export{le as a,ce as b,ue as c,ve as d,pe as e,ge as f,be as g,me as h,T as i,fe as j,he as k,ye as l,we as m,$e as n,_e as o,ke as p,Se as q,u as r};
