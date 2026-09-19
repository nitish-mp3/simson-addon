import { $, esc, option } from '../shared/dom.js';
import { state } from '../state/store.js';
import { phoneProvisioningProfiles, phoneProvisioningResultHtml } from '../features/sip/provisioning.js';
import { sipTable } from '../features/sip/endpoint-view.js';

export function renderSip() {
  $("content").innerHTML = `
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
            <div class="hint">For cases like <b>1025 → ${esc("this phone")}</b>: Simson briefly releases the original caller leg, calls the caller phone back with auto-answer/speaker hints, then bridges to this target.</div>
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
            <label class="provision-toggle"><input id="sip-phone-provision-enabled" type="checkbox" ${state.phoneProvisioning.enabled ? "checked" : ""}> Configure a supported phone automatically</label>
            <div class="hint">Optional. Simson can configure a free SIP account on a supported LAN phone after testing its management login. Existing phone accounts are never overwritten.</div>
            <div id="sip-phone-provision-panel" class="phone-provision-panel ${state.phoneProvisioning.enabled ? "" : "hidden"}">
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
                    ${phoneProvisioningProfiles().map((profile) => option(
                      profile.id,
                      `${profile.name}${profile.automatic_write === false ? " · provisioning server" : ""}`,
                      "grandstrweam_gsc36xx",
                    )).join("")}
                  </select>
                  <div id="sip-phone-profile-help" class="hint">${esc(phoneProvisioningProfiles()[0]?.help || "Select the exact device family.")}</div>
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
              <div id="sip-phone-test-result" class="provision-result">${phoneProvisioningResultHtml()}</div>
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
    <datalist id="node-list">${state.nodes.map((n) => `<option value="${esc(n.id)}">${esc(n.label || n.id)}</option>`).join("")}</datalist>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Registered SIP devices</div>
          <div class="card-sub">These are scoped to this VPS account/site.</div>
        </div>
      </div>
      ${sipTable()}
    </div>
  `;
}

