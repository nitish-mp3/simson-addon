import{a as f,c as w,g as _}from"./chunk-QQ3R3DIZ.js";import"./chunk-KRDI2XUQ.js";import{a as $}from"./chunk-JLXVDRQC.js";import"./chunk-XSKVCSHS.js";import{b as k,c as h,g as y,j as m}from"./chunk-RP7N3B43.js";import{e as d}from"./chunk-6R6CGC23.js";import{a as g,b as e,d as u}from"./chunk-OPL7LVHU.js";function x(){return d.sip.length?`
    <div class="data-table">
      ${d.sip.map(C).join("")}
    </div>
  `:'<div class="empty">No SIP endpoints returned yet.</div>'}function C(t){let a=h(t)||{},s=a.enabled!==!1,i=a.id||a.extension||a.username,n=m(a),l=!!a.registered,c=a.contact_address?`${a.contact_address}${a.contact_latency_ms?` \xB7 ${a.contact_latency_ms}ms`:""}`:a.contact_status||"no live contact",o=a.auto_answer?a.auto_answer_callers?`auto-answer from ${a.auto_answer_callers}`:"auto-answer from anyone":"manual answer",v=a.auto_speaker?a.auto_speaker_callers?`speaker from ${a.auto_speaker_callers}`:"speaker follows auto-answer":"speaker off",S=a.callback_bridge?`caller callback from ${a.callback_bridge_callers||"no allowlist"}${a.callback_caller_auto_speaker?" with caller speaker":a.callback_caller_auto_answer?" with caller auto-answer":""}`:"caller callback off",p=a.gateway_inbound_mode||"inherit",P=a.gateway_direct_target||"",T=a.gateway_ivr_enabled?`IVR ${a.gateway_ivr_sound||"built-in wait prompt"}`:"IVR off",I=a.answer_announcement_text?`private prompt "${a.answer_announcement_text}"`:"no private answer prompt",A=a.pre_ring_announcement_text?`caller waiting announcement "${a.pre_ring_announcement_text}"`:"no caller waiting announcement",b=Object.keys(a.call_duration_rules||{}).length,r=k(a.supervision),R=[r.listen?"monitor":"",r.whisper?"whisper":"",r.barge?"barge":""].filter(Boolean);return`
    <div class="sip-manage-row ${n?"protected":""}">
      <div class="sip-main">
        <div style="min-width:0;">
          <div class="row-title">${e(a.extension||"-")} ${a.description?`<span>${e(a.description)}</span>`:""}</div>
          <div class="row-sub">User ${e(a.username||"-")} \xB7 ${e(a.route_to||"any available node")} \xB7 ${a.video_enabled?"Audio + H.264":"Audio only"} \xB7 ${e(o)} \xB7 ${e(v)} \xB7 ${e(S)} \xB7 ${e(A)} \xB7 ${e(I)} \xB7 ${b?`${b} timed route${b===1?"":"s"}`:"no call time limit"}</div>
          <div class="row-sub">Live contact: ${e(c)}</div>
          ${!n&&r.enabled?`<div class="row-sub supervision-summary">Supervisor access: ${e(R.join(", ")||"not configured")} \xB7 ${r.targets.length} permitted target${r.targets.length===1?"":"s"}</div>`:""}
        </div>
        <div class="row-actions">
          <span class="pill ${s?"ok":"bad"}">${s?"enabled":"disabled"}</span>
          <span class="pill ${l?"ok":"warn"}">${l?"registered":"offline"}</span>
          ${a.default_outbound?'<span class="pill ok">default outside gateway</span>':""}
          ${n?'<span class="pill warn">gateway protected</span>':""}
          ${n?`<span class="pill">${e(p==="direct_target"?"direct inbound":p==="haos_then_fallback"?"card then fallback":"inherits inbound")}</span>`:""}
        </div>
      </div>
      <div class="sip-edit-grid">
        <div class="field">
          <label>Label</label>
          <input data-sip-id="${e(i)}" data-sip-key="description" value="${e(a.description||"")}" placeholder="Kitchen monitor">
        </div>
        <div class="field">
          <label>Route to HAOS node</label>
          <input data-sip-id="${e(i)}" data-sip-key="route_to" list="node-list" value="${e(a.route_to||"")}" placeholder="any available node">
        </div>
        <div class="field">
          <label>Rotate password</label>
          <input data-sip-id="${e(i)}" data-sip-key="password" type="password" placeholder="new password only">
        </div>
        <div class="sip-checks">
          <label><input data-sip-id="${e(i)}" data-sip-key="enabled" type="checkbox" ${s?"checked":""}> Enabled</label>
          <label><input data-sip-id="${e(i)}" data-sip-key="video_enabled" type="checkbox" ${a.video_enabled?"checked":""}> H.264 video</label>
          ${n?`<label><input data-sip-id="${e(i)}" data-sip-key="default_outbound" type="checkbox" ${a.default_outbound?"checked":""}> Default outside gateway</label>`:""}
          <label><input data-sip-id="${e(i)}" data-sip-key="auto_answer" type="checkbox" ${a.auto_answer?"checked":""}> Auto-answer</label>
          <label><input data-sip-id="${e(i)}" data-sip-key="auto_speaker" type="checkbox" ${a.auto_speaker?"checked":""}> Speaker on auto-answer</label>
        </div>
        ${n?`
        <div class="field full gateway-policy">
          <div class="gateway-policy-head">
            <div>
              <label>Inbound behavior for gateway ${e(a.extension)}</label>
              <div class="hint">This applies only to calls arriving through this gateway. It will not affect other gateways.</div>
            </div>
            <span class="pill">${e(T)}</span>
          </div>
          <div class="form-grid compact">
            <div class="field">
              <label>Incoming call path</label>
              <select data-sip-id="${e(i)}" data-sip-key="gateway_inbound_mode">
                ${u("","Use global routing policy",p==="inherit"?"":p)}
                ${u("haos_then_fallback","Ring HAOS card, then this fallback",p)}
                ${u("direct_target","Send directly to this target",p)}
              </select>
            </div>
            <div class="field">
              <label>Gateway target / fallback</label>
              <select data-sip-id="${e(i)}" data-sip-key="gateway_direct_target">
                ${y(P)}
              </select>
              <div class="hint">For direct mode this starts immediately. Select a <b>Route plan</b> to run its full multi-stage escalation. For card mode this is tried after the HAOS ring delay.</div>
            </div>
            <div class="field">
              <label><input data-sip-id="${e(i)}" data-sip-key="gateway_ivr_enabled" type="checkbox" ${a.gateway_ivr_enabled?"checked":""}> Play IVR before routing</label>
              <div class="hint">Optional. Leave off for fastest gateway handoff.</div>
            </div>
            <div class="field">
              <label>IVR sound name</label>
              <input data-sip-id="${e(i)}" data-sip-key="gateway_ivr_sound" value="${e(a.gateway_ivr_sound||"")}" placeholder="custom/site_welcome">
              <div class="hint">Per account/gateway Asterisk sound. Blank uses the built-in wait prompt if IVR is enabled.</div>
            </div>
          </div>
        </div>`:""}
        <div class="field full call-stage-box caller-stage">
          <div class="call-stage-label"><span>1</span><div><b>Caller waiting announcement</b><small>Before ${e(a.extension||"the destination")} starts ringing \xB7 caller hears this</small></div></div>
          <textarea data-sip-id="${e(i)}" data-sip-key="pre_ring_announcement_text" maxlength="300" rows="2" placeholder="Please wait while I call the kitchen monitor.">${e(a.pre_ring_announcement_text||"")}</textarea>
          <div class="prompt-audience caller"><b>Audience: caller only.</b> Asterisk plays early media first, then starts ringing ${e(a.extension||"this phone")}. The receiving phone cannot hear this stage.</div>
        </div>
        <div class="field full call-stage-box receiver-stage">
          <div class="call-stage-label"><span>2</span><div><b>Receiving-phone private prompt</b><small>Immediately after manual/auto-answer \xB7 receiver hears this</small></div></div>
          <textarea data-sip-id="${e(i)}" data-sip-key="answer_announcement_text" maxlength="300" rows="2" placeholder="Call for Amit. Please wait while I connect you.">${e(a.answer_announcement_text||"")}</textarea>
          <div class="prompt-audience receiver"><b>Audience: receiving phone only.</b> The phone must answer before SIP media can be delivered; Simson plays this privately before bridging the caller. Blank disables it.</div>
          <div class="sip-standard-note">Standard SIP does not support sending arbitrary audio to an unanswered receiving handset. This is the earliest standards-compliant receiver-side prompt and does not alter normal ringing behavior.</div>
        </div>
        <div class="field full route-duration-box">
          <div class="duration-head">
            <div>
              <label>Route-specific connected call limits</label>
              <div class="hint">Optional. The timer starts only after ${e(a.extension||"this phone")} answers. Ring time is never deducted.</div>
            </div>
            <button class="btn small secondary" data-action="add-duration-rule" data-id="${e(i)}" data-target-ext="${e(a.extension||"")}">+ Add limit</button>
          </div>
          <div class="duration-rule-list" data-duration-list="${e(i)}">
            ${_(i,a.extension,a.call_duration_rules)}
          </div>
          <div class="hint">Example: source 1027 with 15 seconds means only 1027 \u2192 ${e(a.extension||"this phone")} ends after 15 connected seconds. All other callers remain unlimited.</div>
        </div>
        <div class="field full">
          <label>Only auto-answer from caller extension(s)</label>
          <input data-sip-id="${e(i)}" data-sip-key="auto_answer_callers" value="${e(a.auto_answer_callers||"")}" placeholder="1025, 1602">
          <div class="hint">Blank means any caller. For precise behavior like <b>1025 \u2192 ${e(a.extension||"this phone")}</b>, put <b>1025</b> here.</div>
        </div>
        <div class="field full">
          <label>Only request speaker/intercom from caller extension(s)</label>
          <input data-sip-id="${e(i)}" data-sip-key="auto_speaker_callers" value="${e(a.auto_speaker_callers||"")}" placeholder="${e(a.auto_answer_callers||"1025, 1602")}">
          <div class="hint">Blank reuses the auto-answer caller list. This sends intercom/speaker hints to the <b>called</b> phone; Asterisk cannot force the original caller handset into speaker after it has already placed a call.</div>
        </div>
        <div class="field full feature-box">
          <label><input data-sip-id="${e(i)}" data-sip-key="callback_bridge" type="checkbox" ${a.callback_bridge?"checked":""}> Caller callback bridge</label>
          <div class="hint">Use when the <b>caller</b> phone also needs auto-answer/speaker. Simson replaces the original dial attempt with a fresh callback to the caller, then bridges to this target.</div>
        </div>
        <div class="field full">
          <label>Only callback-bridge these caller extension(s)</label>
          <input data-sip-id="${e(i)}" data-sip-key="callback_bridge_callers" value="${e(a.callback_bridge_callers||"")}" placeholder="1025, 1026">
          <div class="hint">Required allowlist. Example: set this on target <b>${e(a.extension||"1603")}</b> to <b>1025</b> for only 1025 \u2192 ${e(a.extension||"1603")}.</div>
        </div>
        <div class="sip-checks full">
          <label><input data-sip-id="${e(i)}" data-sip-key="callback_caller_auto_answer" type="checkbox" ${a.callback_caller_auto_answer?"checked":""}> Caller callback auto-answer</label>
          <label><input data-sip-id="${e(i)}" data-sip-key="callback_caller_auto_speaker" type="checkbox" ${a.callback_caller_auto_speaker?"checked":""}> Caller callback speaker/intercom</label>
        </div>
        ${n?"":H(i,a.extension,r)}
      </div>
      <div class="sip-actions">
        <button class="btn small secondary" data-action="save-sip" data-id="${e(i)}">Save Device</button>
        ${n?`<button class="btn small secondary ghost" data-action="clear-stuck-sip" data-id="${e(i)}" data-ext="${e(a.extension||i)}" title="Release orphaned calls on this gateway">Clear stuck call</button>`:""}
        ${n?`<button class="btn small red ghost" data-action="delete-sip" data-id="${e(i)}" data-ext="${e(a.extension||i)}" title="Gateway trunks require typed confirmation">Delete Gateway</button>`:`<button class="btn small red" data-action="delete-sip" data-id="${e(i)}" data-ext="${e(a.extension||i)}">Delete</button>`}
      </div>
    </div>
  `}function O(t,a,s){let i=new Set((s||[]).map(String)),n=d.sip.map(h).filter(l=>l&&l.enabled!==!1&&!m(l)&&l.extension&&l.extension!==a);return n.length?n.map(l=>{let c=l.id||l.extension||l.username;return`
      <label class="supervision-target">
        <input type="checkbox" data-supervision-owner="${e(t)}" data-supervision-target="${e(l.extension)}" ${i.has(String(l.extension))?"checked":""}>
        <span><b>${e(l.extension)}</b>${l.description?`<small>${e(l.description)}</small>`:""}</span>
        <i class="${l.registered?"online":"offline"}">${l.registered?"online":"offline"}</i>
      </label>`}).join(""):'<div class="empty compact">No other enabled SIP phones are available on this site.</div>'}function H(t,a,s){let i=s.enabled?"open":"",n=(l,c="target")=>{let o=String(l||""),v=o.startsWith("*")?o.slice(1):o;return v&&v!==o?`Dial ${o} + ${c}. If the handset reserves *, dial ${v} + ${c}.`:`Dial ${o} + ${c}.`};return`
    <details class="field full supervision-panel" ${i}>
      <summary>
        <span><b>Supervisor access</b><small>Secure monitor, whisper, and barge permissions for ${e(a||"this extension")}</small></span>
        <span class="pill ${s.enabled?"ok":""}">${s.enabled?"enabled":"off"}</span>
      </summary>
      <div class="supervision-body">
        <label class="supervision-enable"><input data-sip-id="${e(t)}" data-sip-key="supervision_enabled" type="checkbox" ${s.enabled?"checked":""}> Allow this authenticated SIP phone to supervise selected calls</label>
        <div class="supervision-security">Authorization uses the registered SIP endpoint, not caller ID. The phone can supervise only the target extensions selected below.</div>
        <div class="supervision-modes">
          <div class="supervision-mode">
            <label><input data-sip-id="${e(t)}" data-sip-key="supervision_listen" type="checkbox" ${s.listen?"checked":""}> Silent monitor</label>
            <input data-sip-id="${e(t)}" data-sip-key="supervision_listen_key" value="${e(s.listen_key)}" maxlength="7" aria-label="Silent monitor key">
            <small>${e(n(s.listen_key))} Neither party hears the supervisor.</small>
          </div>
          <div class="supervision-mode">
            <label><input data-sip-id="${e(t)}" data-sip-key="supervision_whisper" type="checkbox" ${s.whisper?"checked":""}> Whisper</label>
            <input data-sip-id="${e(t)}" data-sip-key="supervision_whisper_key" value="${e(s.whisper_key)}" maxlength="7" aria-label="Whisper key">
            <small>${e(n(s.whisper_key))} Supervisor coaches the target privately.</small>
          </div>
          <div class="supervision-mode">
            <label><input data-sip-id="${e(t)}" data-sip-key="supervision_barge" type="checkbox" ${s.barge?"checked":""}> Full barge</label>
            <input data-sip-id="${e(t)}" data-sip-key="supervision_barge_key" value="${e(s.barge_key)}" maxlength="7" aria-label="Full barge key">
            <small>${e(n(s.barge_key))} Everyone can hear the supervisor.</small>
          </div>
        </div>
        <div class="supervision-targets-head"><b>Permitted target phones</b><span>Select one or more active SIP extensions</span></div>
        <div class="supervision-targets">${O(t,a,s.targets)}</div>
      </div>
    </details>`}function B(){g("content").innerHTML=`
    <div class="inline-notice info" style="margin-bottom:16px">
      <div><b>Need multi-level or parallel ringing?</b><span>Advanced plans are configured under Routing. Choose a gateway or SIP phone as the exact incoming source, then add ordered stages and parallel SIP/HAOS destinations.</span></div>
      <button class="btn small secondary" data-page="routing">Open Routing</button>
    </div>
    <div class="grid cols-2 dense-grid">
      <div class="card glow">
        <div class="card-title">Create SIP phone</div>
        <div class="card-sub">Use for desk phones, indoor video monitors, door stations, or ATA boxes.</div>
        <div class="form-grid" style="margin-top:14px">
          <div class="field">
            <label>Extension</label>
            <input id="sip-ext" placeholder="1602">
          </div>
          <div class="field">
            <label>Username</label>
            <input id="sip-user" placeholder="same as extension">
          </div>
          <div class="field">
            <label>Password</label>
            <input id="sip-pass" type="password" placeholder="strong SIP password">
          </div>
          <div class="field">
            <label>Label</label>
            <input id="sip-desc" placeholder="Kitchen monitor">
          </div>
          <div class="field full">
            <label>Route to HAOS node optional</label>
            <input id="sip-route" list="node-list" placeholder="office2">
          </div>
          <div class="field full">
            <label><input id="sip-video" type="checkbox"> Video capable H.264 device</label>
          </div>
          <div class="field full">
            <label>Caller announcement before this phone starts ringing optional</label>
            <textarea id="sip-pre-ring-announcement-text" maxlength="300" rows="2" placeholder="Please wait while I call the kitchen monitor."></textarea>
            <div class="hint">The caller hears this first using early media; this phone starts ringing immediately after the sentence finishes. Leave blank for normal immediate ringing.</div>
          </div>
          <div class="field full">
            <label>Prompt spoken to this phone after answer optional</label>
            <textarea id="sip-answer-announcement-text" maxlength="300" rows="2" placeholder="Call for Amit. Please wait while I connect you."></textarea>
            <div class="hint">Just type the sentence. Simson privately generates and caches the audio for this site and phone. The caller joins after the receiving phone hears it.</div>
          </div>
          <div class="field full">
            <label><input id="sip-default-outbound" type="checkbox"> Make this the default outside gateway</label>
            <div class="hint">Only use this for FXO/GSM/PSTN gateway accounts. Normal SIP phones should leave it off.</div>
          </div>
          <div class="field full">
            <label><input id="sip-auto-answer" type="checkbox"> Auto-answer incoming SIP calls</label>
            <div class="hint">Use only for door stations or monitors that should pick up instantly. Normal desk phones should stay off.</div>
          </div>
          <div class="field full">
            <label><input id="sip-auto-speaker" type="checkbox"> Request speaker/intercom mode when auto-answering</label>
            <div class="hint">Phone support varies; Simson sends standard SIP auto-answer/intercom headers to the called phone.</div>
          </div>
          <div class="field full">
            <label>Only auto-answer calls from optional</label>
            <input id="sip-auto-answer-callers" placeholder="1025, 1602">
            <div class="hint">Leave blank for any caller. For route-specific pickup, put the caller extension here, e.g. <b>1025</b>.</div>
          </div>
          <div class="field full">
            <label>Only request speaker from optional</label>
            <input id="sip-auto-speaker-callers" placeholder="1025, 1602">
            <div class="hint">Leave blank to reuse the auto-answer caller list. This controls the called phone only; caller-side speaker must be configured on that phone itself.</div>
          </div>
          <div class="field full feature-box">
            <label><input id="sip-callback-bridge" type="checkbox"> Caller callback bridge for speaker/intercom</label>
            <div class="hint">For cases like <b>1025 \u2192 ${e("this phone")}</b>: Simson briefly releases the original caller leg, calls the caller phone back with auto-answer/speaker hints, then bridges to this target.</div>
          </div>
          <div class="field full">
            <label>Only use caller callback bridge from</label>
            <input id="sip-callback-callers" placeholder="1025, 1026">
            <div class="hint">Required allowlist. Leave blank to keep callback bridge disabled even if checked.</div>
          </div>
          <div class="field full">
            <label><input id="sip-callback-caller-auto-answer" type="checkbox"> Caller phone auto-answers the callback</label>
          </div>
          <div class="field full">
            <label><input id="sip-callback-caller-auto-speaker" type="checkbox"> Caller phone requests speaker/intercom on callback</label>
          </div>
          <div class="field full phone-provision-wrap">
            <label class="provision-toggle"><input id="sip-phone-provision-enabled" type="checkbox" ${d.phoneProvisioning.enabled?"checked":""}> Configure a supported phone automatically</label>
            <div class="hint">Optional. Simson can configure a free SIP account on a supported LAN phone after testing its management login. Existing phone accounts are never overwritten.</div>
            <div id="sip-phone-provision-panel" class="phone-provision-panel ${d.phoneProvisioning.enabled?"":"hidden"}">
              <div class="provision-head">
                <div>
                  <b>Phone management connection</b>
                  <span>Credentials are held in memory for 5 minutes and are never saved in addon settings.</span>
                </div>
                <span class="pill">Optional</span>
              </div>
              <div class="form-grid compact">
                <div class="field full">
                  <label>Device profile</label>
                  <select id="sip-phone-profile" data-phone-connection>
                    ${f().map(t=>u(t.id,`${t.name}${t.automatic_write===!1?" \xB7 provisioning server":""}`,"grandstrweam_gsc36xx")).join("")}
                  </select>
                  <div id="sip-phone-profile-help" class="hint">${e(f()[0]?.help||"Select the exact device family.")}</div>
                </div>
                <div class="field">
                  <label>Phone private IP</label>
                  <input id="sip-phone-ip" data-phone-connection inputmode="decimal" placeholder="192.168.1.80" autocomplete="off">
                </div>
                <div class="field split-field">
                  <div>
                    <label>Management protocol</label>
                    <select id="sip-phone-scheme" data-phone-connection>
                      <option value="https">HTTPS</option>
                      <option value="http">HTTP</option>
                    </select>
                  </div>
                  <div>
                    <label>Port</label>
                    <input id="sip-phone-port" data-phone-connection type="number" min="1" max="65535" value="443">
                  </div>
                </div>
                <div class="field">
                  <label>Phone administrator username</label>
                  <input id="sip-phone-admin-user" data-phone-connection autocomplete="username" placeholder="admin">
                </div>
                <div class="field">
                  <label>Phone administrator password</label>
                  <input id="sip-phone-admin-pass" data-phone-connection type="password" autocomplete="current-password" placeholder="device web password">
                </div>
                <div class="field">
                  <label>SIP transport</label>
                  <select id="sip-phone-transport">
                    <option value="tcp" selected>TCP (recommended default)</option>
                    <option value="udp">UDP</option>
                    <option value="tls">TLS/TCP</option>
                  </select>
                </div>
                <div class="field checkbox-bottom">
                  <label><input id="sip-phone-verify-tls" data-phone-connection type="checkbox"> Verify HTTPS certificate</label>
                  <div class="hint">Leave off for a phone's self-signed certificate.</div>
                </div>
              </div>
              <div class="provision-actions">
                <button class="btn secondary" type="button" data-action="discover-phone">Test connection & find accounts</button>
              </div>
              <div id="sip-phone-test-result" class="provision-result">${w()}</div>
            </div>
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn" data-action="create-sip">Create SIP Phone</button></div>
      </div>
      <div class="card">
        <div class="card-title">Phone setup reminder</div>
        <div class="card-sub">Server/domain: <b>simson-vps.vipsy.in</b>, port <b>5060</b>, transport UDP or TCP. Use PCMU/G.711u and PCMA/G.711a for audio; enable H.264 on video phones.</div>
      </div>
    </div>
    <datalist id="node-list">${d.nodes.map(t=>`<option value="${e(t.id)}">${e(t.label||t.id)}</option>`).join("")}</datalist>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Registered SIP devices</div>
          <div class="card-sub">These are scoped to this VPS account/site.</div>
        </div>
      </div>
      ${x()}
    </div>
  `,$("sip")}export{B as renderSip};
