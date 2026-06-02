"""Ingress panel HTML — full single-page app for Simson configuration.

Served at GET / by LocalAPI.  Three server-side placeholders are replaced
before delivery:
    __PROVISIONED__      → true | false
    __HAS_ADMIN_TOKEN__  → true | false
    __VERSION__          → e.g. 3.5.0
Everything else is pure client-side JS fetching /api/status and /api/settings.
"""

INGRESS_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simson&#thinsp;·&#thinsp;Call Relay</title>
<style>
/* ── Reset & tokens ──────────────────────────────────────────────────── */
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0e0e0e;--surface:#1a1a1a;--surface2:#222;--surface3:#2a2a2a;
  --border:#2d2d2d;--border2:#383838;
  --text:#e4e4e4;--text2:#aaa;--text3:#666;
  --accent:#0288d1;--accent-dark:#01579b;--accent-light:#29b6f6;
  --green:#2e7d32;--green-light:#66bb6a;
  --red:#c62828;--red-light:#ef5350;
  --yellow:#e65100;--yellow-light:#ffa726;
  --radius:12px;--radius-sm:8px;--radius-xs:6px;
  --shadow:0 2px 12px rgba(0,0,0,.4);
  --transition:.18s ease;
}
/* ── Layout ─────────────────────────────────────────────────────────── */
body{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif;
     min-height:100vh;padding:0}
#app{max-width:640px;margin:0 auto;padding:20px 16px 48px}
/* ── Header ─────────────────────────────────────────────────────────── */
.header{display:flex;align-items:center;justify-content:space-between;
        margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:10px}
.brand-icon{font-size:22px;line-height:1}
.brand-name{font-size:17px;font-weight:700;letter-spacing:-.3px}
.brand-version{font-size:11px;color:var(--text3);margin-top:1px}
.badge{font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;
       text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.badge-ok{background:#1b5e2033;color:#a5d6a7;border:1px solid #2e7d3244}
.badge-err{background:#b71c1c33;color:#ef9a9a;border:1px solid #c6282844}
.badge-setup{background:#e6510022;color:#ffcc80;border:1px solid #e6510044}
.badge-loading{background:#1a1a1a;color:var(--text3);border:1px solid var(--border)}
/* ── Tabs ───────────────────────────────────────────────────────────── */
.tabs{display:flex;gap:4px;margin-bottom:18px;background:var(--surface);
      border:1px solid var(--border);border-radius:var(--radius);padding:4px}
.tab{flex:1;background:transparent;border:none;border-radius:var(--radius-sm);
     padding:9px 0;font-size:13px;font-weight:600;color:var(--text2);cursor:pointer;
     transition:all var(--transition)}
.tab:hover{color:var(--text);background:var(--surface2)}
.tab.active{background:var(--surface3);color:var(--text);box-shadow:var(--shadow)}
/* ── Cards ──────────────────────────────────────────────────────────── */
.card{background:var(--surface);border:1px solid var(--border);
      border-radius:var(--radius);padding:18px 20px;margin-bottom:14px}
.card-title{font-size:11px;font-weight:700;text-transform:uppercase;
            letter-spacing:.6px;color:var(--text3);margin-bottom:14px}
/* ── Info rows ──────────────────────────────────────────────────────── */
.info-row{display:flex;justify-content:space-between;align-items:center;
          padding:8px 0;border-bottom:1px solid var(--border)}
.info-row:last-child{border-bottom:none}
.info-label{font-size:13px;color:var(--text2)}
.info-value{font-size:13px;font-weight:500;display:flex;align-items:center;gap:6px;
            text-align:right;word-break:break-all;max-width:65%}
/* ── Dot indicators ─────────────────────────────────────────────────── */
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex-shrink:0}
.dot-ok{background:#4caf50} .dot-err{background:#f44336} .dot-warn{background:#ff9800}
/* ── Alerts ─────────────────────────────────────────────────────────── */
.alert{padding:11px 15px;border-radius:var(--radius-sm);font-size:13px;
       line-height:1.5;margin-top:14px}
.alert-success{background:#1b5e2033;border:1px solid #4caf5033;color:#a5d6a7}
.alert-error{background:#b71c1c33;border:1px solid #f4433633;color:#ef9a9a}
.alert-info{background:#01579b22;border:1px solid #0288d133;color:#90caf9}
.alert-warn{background:#e6510022;border:1px solid #ff980044;color:#ffcc80}
/* ── Buttons ────────────────────────────────────────────────────────── */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:none;
     border-radius:var(--radius-sm);padding:10px 20px;font-size:14px;font-weight:600;
     cursor:pointer;transition:all var(--transition);color:#fff}
.btn:active{transform:scale(.97)}
.btn:disabled{opacity:.45;cursor:not-allowed;transform:none}
.btn-primary{background:var(--accent)}
.btn-primary:hover:not(:disabled){background:var(--accent-dark)}
.btn-danger{background:var(--red)}
.btn-danger:hover:not(:disabled){background:#b71c1c}
.btn-secondary{background:var(--surface3);color:var(--text2);
                border:1px solid var(--border2)}
.btn-secondary:hover:not(:disabled){background:var(--border2);color:var(--text)}
.btn-sm{display:inline-flex;align-items:center;gap:5px;border:none;
        border-radius:var(--radius-xs);padding:5px 12px;font-size:12px;
        font-weight:600;cursor:pointer;transition:all var(--transition);
        background:var(--accent);color:#fff}
.btn-sm:hover{background:var(--accent-dark)}
.btn-sm-ghost{background:transparent;color:var(--text3);border:1px solid var(--border2);
              border-radius:var(--radius-xs);padding:4px 10px;font-size:12px;
              font-weight:600;cursor:pointer;transition:all var(--transition)}
.btn-sm-ghost:hover{color:var(--text);border-color:var(--text3)}
.btn-icon{background:transparent;border:1px solid var(--border2);color:var(--text3);
          border-radius:var(--radius-xs);padding:3px 8px;font-size:13px;cursor:pointer;
          transition:all var(--transition)}
.btn-icon:hover{color:var(--text);border-color:var(--text2)}
.btn-icon.del{border-color:var(--red-light)33;color:var(--red-light)99}
.btn-icon.del:hover{color:var(--red-light);border-color:var(--red-light)88;
                    background:var(--red)22}
/* ── Form fields ────────────────────────────────────────────────────── */
.field{display:flex;flex-direction:column;gap:5px;flex:1;min-width:0}
.field label{font-size:12px;font-weight:600;color:var(--text2);
             display:flex;align-items:center;gap:6px}
.field label .hint-tag{font-weight:400;color:var(--text3);font-size:11px}
.field input,.field select{background:var(--surface2);border:1px solid var(--border2);
  border-radius:var(--radius-xs);padding:9px 12px;color:var(--text);font-size:13px;
  outline:none;width:100%;transition:border-color var(--transition)}
.field input:focus,.field select:focus{border-color:var(--accent)}
.field input::placeholder{color:var(--text3)}
.field select option{background:var(--surface2)}
.field-hint{font-size:11px;color:var(--text3);line-height:1.4;margin-top:2px}
.field-row{display:flex;gap:12px;margin-bottom:14px}
.field-row:last-child{margin-bottom:0}
.field-full{flex:none;width:100%}
/* ── Toggle switch ──────────────────────────────────────────────────── */
.switch{position:relative;display:inline-flex;align-items:center;
        width:40px;height:22px;flex-shrink:0;cursor:pointer}
.switch input{opacity:0;width:0;height:0;position:absolute}
.slider{position:absolute;inset:0;background:var(--surface3);
        border-radius:22px;transition:background var(--transition);
        border:1px solid var(--border2)}
.slider::before{content:'';position:absolute;width:16px;height:16px;
  left:2px;top:50%;transform:translateY(-50%);border-radius:50%;
  background:var(--text3);transition:all var(--transition)}
.switch input:checked + .slider{background:var(--accent);border-color:var(--accent-dark)}
.switch input:checked + .slider::before{transform:translateX(18px) translateY(-50%);
  background:#fff}
/* ── Settings sections ──────────────────────────────────────────────── */
.section{background:var(--surface);border:1px solid var(--border);
         border-radius:var(--radius);margin-bottom:14px;overflow:hidden}
.section-head{display:flex;align-items:center;justify-content:space-between;
              padding:15px 18px;cursor:default}
.section-head-left{display:flex;align-items:center;gap:10px}
.section-head h3{font-size:14px;font-weight:600;color:var(--text)}
.section-head .section-badge{font-size:10px;padding:2px 7px;border-radius:10px;
  font-weight:600;letter-spacing:.3px}
.section-badge-on{background:#1b5e2033;color:#a5d6a7;border:1px solid #2e7d3233}
.section-badge-off{background:var(--surface3);color:var(--text3);border:1px solid var(--border)}
.section-body{padding:0 18px 18px;border-top:1px solid var(--border)}
.section-body.collapsed{display:none}
/* ── Checkbox field ─────────────────────────────────────────────────── */
.checkbox-row{display:flex;align-items:center;gap:8px;padding:10px 0}
.checkbox-row input[type=checkbox]{width:16px;height:16px;cursor:pointer;
  accent-color:var(--accent)}
.checkbox-row label{font-size:13px;color:var(--text2);cursor:pointer}
/* ── Call targets ───────────────────────────────────────────────────── */
.target-card{border:1px solid var(--border2);border-radius:var(--radius-sm);
             margin-bottom:10px;overflow:hidden;background:var(--surface2)}
.target-card:last-child{margin-bottom:0}
.target-head{display:flex;align-items:center;gap:10px;padding:11px 14px;
             cursor:pointer;user-select:none}
.target-head:hover{background:var(--surface3)}
.target-emoji{font-size:18px;flex-shrink:0}
.target-name{flex:1;font-size:13px;font-weight:600;min-width:0;overflow:hidden;
             text-overflow:ellipsis;white-space:nowrap}
.target-type-pill{font-size:10px;padding:2px 7px;border-radius:10px;font-weight:700;
  letter-spacing:.3px;background:var(--surface3);color:var(--text3);
  border:1px solid var(--border);flex-shrink:0}
.target-actions{display:flex;gap:6px;flex-shrink:0}
.target-form{padding:14px 14px 16px;border-top:1px solid var(--border)}
.targets-empty{padding:18px;text-align:center;color:var(--text3);font-size:13px}
/* ── Routing board ─────────────────────────────────────────────────── */
.routing-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
.route-board{display:flex;flex-direction:column;gap:10px;margin-top:14px}
.route-row{display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:11px 12px;background:var(--surface2);border:1px solid var(--border2);
  border-radius:var(--radius-sm)}
.route-row-main{min-width:0}
.route-row-title{font-size:13px;font-weight:700;color:var(--text);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.route-row-sub{font-size:11px;color:var(--text3);margin-top:3px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.route-actions{display:flex;gap:5px;flex-shrink:0}
.mode-pill{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.35px;
  padding:3px 8px;border-radius:999px;border:1px solid var(--border2)}
.mode-available{background:#1b5e2033;color:#a5d6a7;border-color:#2e7d3244}
.mode-busy{background:#e6510022;color:#ffcc80;border-color:#ff980044}
.mode-offline{background:#b71c1c33;color:#ef9a9a;border-color:#f4433633}
.live-call{padding:10px 12px;background:#01579b18;border:1px solid #0288d133;
  border-radius:var(--radius-sm);font-size:12px;color:#90caf9;margin-top:10px}
.quick-route{background:linear-gradient(135deg,#01579b20,#1b5e2018);
  border:1px solid #29b6f633;border-radius:var(--radius);padding:14px;margin:14px 0}
.quick-route-title{font-size:13px;font-weight:800;color:var(--text);margin-bottom:4px}
.quick-route-sub{font-size:11px;color:var(--text3);line-height:1.45;margin-bottom:12px}
.quick-route-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:12px;flex-wrap:wrap}
.route-help{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
.route-help-card{padding:10px;background:var(--surface2);border:1px solid var(--border);
  border-radius:var(--radius-sm);font-size:11px;color:var(--text3);line-height:1.45}
.route-help-card b{display:block;color:var(--text2);font-size:12px;margin-bottom:3px}
@media(max-width:560px){.routing-grid{grid-template-columns:1fr}.route-row{align-items:flex-start;flex-direction:column}.route-actions{width:100%;flex-wrap:wrap}}
@media(max-width:560px){.route-help{grid-template-columns:1fr}}
/* ── Automation triggers ───────────────────────────────────────────── */
.automation-card{background:linear-gradient(135deg,#1b5e2018,#01579b20);
  border:1px solid #66bb6a33;border-radius:var(--radius);padding:14px;margin-top:14px}
.automation-list{display:flex;flex-direction:column;gap:10px;margin-top:14px}
.automation-row{padding:12px;background:var(--surface2);border:1px solid var(--border2);
  border-radius:var(--radius-sm)}
.automation-row-head{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.automation-row-title{font-size:13px;font-weight:700;flex:1}
.door-guide{background:linear-gradient(135deg,#004d4029,#e6510018);
  border:1px solid #26a69a55;border-radius:var(--radius);padding:16px;margin-top:14px}
.door-guide-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  margin-bottom:14px;flex-wrap:wrap}
.door-guide-title{font-size:15px;font-weight:800;color:var(--text)}
.door-guide-sub{font-size:11px;color:var(--text3);line-height:1.55;margin-top:4px;max-width:690px}
.door-flow{display:grid;grid-template-columns:minmax(0,1fr) 44px minmax(0,1fr);
  gap:10px;align-items:stretch;margin-top:12px}
.door-device{background:#071b1dcc;border:1px solid #26a69a44;border-radius:var(--radius-sm);padding:12px}
.door-device-target{background:#211407cc;border-color:#ff980044}
.door-device-role{font-size:10px;text-transform:uppercase;letter-spacing:.65px;font-weight:800;
  color:#80cbc4;margin-bottom:5px}
.door-device-target .door-device-role{color:#ffcc80}
.door-device-title{font-size:13px;color:var(--text);font-weight:800;margin-bottom:9px}
.door-arrow{display:flex;align-items:center;justify-content:center;color:#80cbc4;font-size:22px;font-weight:800}
.door-guide-result{margin-top:12px;padding:10px 12px;border-radius:var(--radius-xs);
  background:#0c1818;border:1px solid var(--border);font-size:12px;color:var(--text2);line-height:1.55}
.door-flow-summary{margin-top:9px;padding:9px 10px;border:1px solid #26a69a33;
  border-radius:var(--radius-xs);background:#004d4018;color:#b2dfdb;font-size:11px;line-height:1.55}
@media(max-width:650px){.door-flow{grid-template-columns:1fr}.door-arrow{transform:rotate(90deg);min-height:24px}}
.code-box{background:#111;border:1px solid var(--border2);border-radius:var(--radius-xs);
  color:#a5d6a7;font:11px/1.5 monospace;padding:9px 10px;word-break:break-all;
  white-space:pre-wrap;margin-top:8px}
/* ── Save bar ───────────────────────────────────────────────────────── */
.save-bar{background:var(--surface);border:1px solid var(--border);
          border-radius:var(--radius);padding:16px 18px;
          display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:20px}
.save-status-ok{color:var(--green-light);font-size:13px;font-weight:500}
.save-status-err{color:var(--red-light);font-size:13px;font-weight:500}
.save-errors{background:var(--red)22;border:1px solid var(--red-light)44;
             border-radius:var(--radius-sm);padding:10px 14px;margin-bottom:12px;
             font-size:13px;color:var(--red-light)}
.save-errors ul{padding-left:16px}
.save-errors li{margin-top:4px}
.save-restart-note{background:var(--yellow)22;border:1px solid var(--yellow-light)44;
  border-radius:var(--radius-xs);padding:8px 12px;font-size:12px;
  color:var(--yellow-light);margin-top:10px;line-height:1.5}
/* ── Setup wizard ───────────────────────────────────────────────────── */
.steps{display:flex;flex-direction:column;gap:14px;margin-bottom:18px}
.step-row{display:flex;gap:12px;align-items:flex-start}
.step-num{width:26px;height:26px;background:var(--accent)22;color:var(--accent-light);
          border:1px solid var(--accent)44;border-radius:50%;display:flex;
          align-items:center;justify-content:center;font-size:12px;font-weight:700;
          flex-shrink:0;margin-top:1px}
.step-text{font-size:13px;color:var(--text2);line-height:1.55}
.step-text b{color:var(--text)}
/* ── Danger zone ────────────────────────────────────────────────────── */
.danger-card{border-color:#b71c1c44}
.danger-card .card-title{color:#ef9a9a}
/* ── Copy row ───────────────────────────────────────────────────────── */
.copy-row{display:flex;align-items:center;gap:8px}
.copy-val{background:var(--surface2);border:1px solid var(--border);
          border-radius:var(--radius-xs);padding:4px 10px;
          font-size:12px;font-family:monospace;color:var(--text);
          max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* ── Utility ────────────────────────────────────────────────────────── */
.hidden{display:none!important}
.muted{color:var(--text3);font-size:13px}
p.muted{padding:4px 0}
.divider{height:1px;background:var(--border);margin:16px 0}
</style>
</head>
<body>
<div id="app">

  <!-- ── Header ─────────────────────────────────────────────────── -->
  <div class="header">
    <div class="brand">
      <span class="brand-icon">📞</span>
      <div>
        <div class="brand-name">Simson Call Relay</div>
        <div class="brand-version">v__VERSION__</div>
      </div>
    </div>
    <span id="status-badge" class="badge badge-loading">Loading…</span>
  </div>

  <!-- ── Setup Wizard (not provisioned) ─────────────────────────── -->
  <div id="setup-view" class="hidden">
    <div class="card">
      <div class="card-title">Quick Setup</div>

      <div id="setup-token-section"><!-- injected by JS --></div>

      <div class="steps" id="setup-steps"><!-- injected by JS --></div>

      <div class="divider"></div>

      <div class="field-row" style="flex-direction:column">
        <div class="field" style="width:100%">
          <label>Node Label</label>
          <input type="text" id="f-label" placeholder="e.g. Living Room, Office, Kitchen" autofocus>
          <div class="field-hint">A friendly name for this HA instance. Used to generate the node ID.</div>
        </div>
      </div>
      <div class="field-row" style="flex-direction:column;margin-top:6px">
        <div class="field" style="width:100%">
          <label>Account ID <span class="hint-tag">— for multi-instance calling</span></label>
          <input type="text" id="f-account" placeholder="Leave empty for a brand-new setup">
          <div class="alert alert-warn" style="margin-top:8px">
            ⚠ To call between two HA instances both nodes <b>must share the same Account ID</b>.
            Copy it from the first node's panel and paste it here.
          </div>
        </div>
      </div>

      <button class="btn btn-primary" id="btn-setup" style="margin-top:6px"
              onclick="doSetup()">Set Up Node</button>
      <div id="setup-result"></div>
    </div>
  </div>

  <!-- ── Main App (provisioned) ─────────────────────────────────── -->
  <div id="main-view" class="hidden">

    <!-- Tab bar -->
    <div class="tabs">
      <button class="tab active" data-tab="overview" onclick="switchTab('overview')">Overview</button>
      <button class="tab" data-tab="settings" onclick="switchTab('settings')">⚙ Settings</button>
    </div>

    <!-- ── Overview tab ─────────────────────────────────────────── -->
    <div id="tab-overview">

      <div class="card">
        <div class="card-title">Node</div>
        <div class="info-row">
          <span class="info-label">Node ID</span>
          <span class="info-value" id="node-id-val">—</span>
        </div>
        <div class="info-row">
          <span class="info-label">Account</span>
          <span class="info-value" id="account-id-val">—</span>
        </div>
        <div class="info-row">
          <span class="info-label">Server</span>
          <span class="info-value" id="server-url-val" style="font-size:12px">—</span>
        </div>
        <div class="info-row">
          <span class="info-label">VPS</span>
          <span class="info-value">
            <span class="dot" id="vps-dot"></span>
            <span id="vps-label">—</span>
          </span>
        </div>
        <div class="info-row" id="ast-status-row">
          <span class="info-label">Asterisk</span>
          <span class="info-value">
            <span class="dot" id="ast-dot"></span>
            <span id="ast-label">—</span>
          </span>
        </div>
      </div>

      <div class="card" id="card-call">
        <div class="card-title">Calls</div>
        <p class="muted">No active call</p>
      </div>

      <div class="card">
        <div class="card-title">Add Another HA Instance</div>
        <p style="color:var(--text2);font-size:13px;margin-bottom:14px;line-height:1.6">
          Install Simson on a second Home Assistant, open its panel,
          and paste your <b>Account ID</b> during setup so both nodes share the same account
          and can call each other.
        </p>
        <div class="info-row" style="border-bottom:none">
          <span class="info-label">Your Account ID</span>
          <span class="info-value">
            <div class="copy-row">
              <span class="copy-val" id="copyable-account">—</span>
              <button class="btn-sm-ghost" id="btn-copy-account"
                      onclick="copyAccountId()">Copy</button>
            </div>
          </span>
        </div>
      </div>

    </div><!-- /tab-overview -->

    <!-- ── Settings tab ─────────────────────────────────────────── -->
    <div id="tab-settings" class="hidden">

      <!-- Audio Bridge -------------------------------------------- -->
      <div class="section" id="section-audio-bridge">
        <div class="section-head">
          <div class="section-head-left">
            <h3>☎ SIP Audio Bridge</h3>
            <span class="section-badge section-badge-on">Automatic</span>
          </div>
        </div>
        <div class="section-body">
          <div style="height:14px"></div>
          <p class="field-hint" style="margin-bottom:10px">
            Browser ↔ SIP phone audio is handled by the VPS Asterisk bridge.
            This addon now fetches SIP WebSocket credentials automatically, so
            you do not need to configure local AMI, TURN, or browser SIP secrets here.
          </p>
          <div class="alert alert-info" style="margin-top:8px">
            Keep SIP phones/ATAs on G.711 only: PCMU / G.711u and PCMA / G.711a.
            Do not enable Opus, video, SRTP, or TLS on regular desk phones unless
            the VPS trunk is explicitly configured for it.
          </div>
        </div>
      </div>

      <!-- SIP Phone Endpoints ------------------------------------- -->
      <div class="section" id="section-sip-endpoints">
        <div class="section-head"><h3 class="section-head-left">☎ SIP Phone Endpoints</h3></div>
        <div class="section-body" id="sip-endpoints-body">
          <div style="height:14px"></div>
          <p class="field-hint" style="margin-bottom:12px">
            Create a SIP account for each desk phone, ATA, or SIP landline device.
            Put this node's <b>Node ID</b> in <b>Route To Node ID</b> when calls to
            that extension should ring this HAOS addon directly. Leave it blank only
            when any available node in the account may answer.
          </p>
        </div>
      </div>

      <!-- Routing Policy ------------------------------------------ -->
      <div class="section">
        <div class="section-head" style="cursor:default">
          <div class="section-head-left">
            <h3>🧭 Call Routing Control</h3>
            <span id="routing-mode-badge" class="section-badge section-badge-on">Available</span>
          </div>
          <button class="btn-sm" onclick="loadRoutingBoard()">Refresh</button>
        </div>
        <div class="section-body">
          <div class="route-help">
            <div class="route-help-card"><b>1. Pick who rings first</b>Add one or more targets below. For normal sites, use the quick builder.</div>
            <div class="route-help-card"><b>2. Add fallbacks</b>Each target can try another target if busy, offline, rejected, or not answered.</div>
            <div class="route-help-card"><b>3. Mark availability</b>Busy/offline targets are skipped when the skip option is enabled.</div>
          </div>
          <div class="routing-grid">
            <div class="field">
              <label>Routing Mode</label>
              <select id="routing-strategy" onchange="markSettingsDirty()">
                <option value="priority">Try targets in the fallback order</option>
              </select>
              <div class="field-hint">Calls follow each target's fallback list in order, skipping busy/offline targets when enabled.</div>
            </div>
            <div class="field">
              <label>Ring Before Next Target <span class="hint-tag">seconds</span></label>
              <input id="routing-ring-seconds" type="number" min="5" max="300" value="25" onchange="markSettingsDirty()">
            </div>
            <div class="field">
              <label>Max Attempts <span class="hint-tag">primary included</span></label>
              <input id="routing-max-attempts" type="number" min="1" max="20" value="4" onchange="markSettingsDirty()">
            </div>
            <div class="field">
              <label>Final Fallback Target <span class="hint-tag">optional</span></label>
              <input id="routing-final-fallback" type="text" placeholder="security_desk or sip_backup" oninput="markSettingsDirty()">
            </div>
          </div>
          <label class="checkbox-row">
            <input id="routing-skip-unavailable" type="checkbox" checked onchange="markSettingsDirty()">
            <span>Skip targets marked busy/offline during routing</span>
          </label>
          <div class="routing-grid">
            <div class="field">
              <label>This Site Availability</label>
              <select id="site-availability-mode" onchange="setSiteAvailability(this.value)">
                <option value="available">Available</option>
                <option value="busy">Busy</option>
                <option value="offline">Offline</option>
              </select>
            </div>
            <div class="field">
              <label>Reason <span class="hint-tag">optional</span></label>
              <input id="site-availability-reason" type="text" placeholder="maintenance, lunch, after-hours"
                     oninput="markSettingsDirty()">
            </div>
          </div>
          <div id="live-call-board" class="live-call hidden"></div>
          <div class="route-board" id="route-board"></div>
          <p class="field-hint" style="margin-top:10px">
            These controls are per onsite addon. They do not affect another home/site unless that site admin saves the same settings there.
          </p>
        </div>
      </div>

      <!-- Call Targets -------------------------------------------- -->
      <div class="section">
        <div class="section-head" style="cursor:default">
          <div class="section-head-left">
            <h3>📋 Routing Targets</h3>
            <span id="targets-count-badge" class="section-badge section-badge-off">0</span>
          </div>
          <button class="btn-sm" onclick="addTarget()">+ Add Target</button>
        </div>
        <div class="section-body" id="targets-body" style="padding-bottom:4px">
          <div class="quick-route">
            <div class="quick-route-title">Quick Add Route</div>
            <div class="quick-route-sub">
              Use this for normal setup. It creates the advanced target underneath with safe defaults.
            </div>
            <div class="routing-grid">
              <div class="field">
                <label>What should this route call?</label>
                <select id="quick-kind" onchange="applyQuickRoutePreset(this.value)">
                  <option value="node">HAOS dashboard / addon user</option>
                  <option value="sip">SIP desk phone extension</option>
                  <option value="gateway">Outside number through gateway</option>
                </select>
              </div>
              <div class="field">
                <label>Friendly Name</label>
                <input id="quick-label" type="text" placeholder="Front Desk">
              </div>
              <div class="field">
                <label>Target ID <span class="hint-tag">auto if blank</span></label>
                <input id="quick-id" type="text" placeholder="front_desk">
              </div>
              <div class="field" id="quick-node-wrap">
                <label>HAOS Node ID</label>
                <input id="quick-node" type="text" placeholder="office2">
              </div>
              <div class="field" id="quick-ext-wrap">
                <label id="quick-ext-label">SIP Extension / Number</label>
                <input id="quick-ext" type="text" placeholder="1025">
              </div>
              <div class="field" id="quick-trunk-wrap">
                <label>Gateway / Trunk</label>
                <input id="quick-trunk" type="text" placeholder="7009">
              </div>
              <div class="field">
                <label>Fallback Target IDs <span class="hint-tag">optional</span></label>
                <input id="quick-fallbacks" type="text" placeholder="office2, security_phone">
              </div>
              <div class="field">
                <label>Ring Time</label>
                <input id="quick-timeout" type="number" min="5" max="300" value="25">
              </div>
            </div>
            <div class="quick-route-actions">
              <button class="btn-secondary btn" style="font-size:12px;padding:8px 14px" onclick="clearQuickRoute()">Clear</button>
              <button class="btn btn-primary" style="font-size:12px;padding:8px 14px" onclick="createQuickRoute()">Create Route</button>
            </div>
          </div>
          <div id="targets-list"></div>
          <div id="targets-empty" class="targets-empty">
            No routing targets yet. Use <b>Quick Add Route</b> above for the first one.
          </div>
        </div>
      </div>

      <!-- Automation Triggers ------------------------------------- -->
      <div class="section">
        <div class="section-head" style="cursor:default">
          <div class="section-head-left">
            <h3>⚡ Automation &amp; Webhook Calls</h3>
            <span id="automation-count-badge" class="section-badge section-badge-off">0</span>
          </div>
          <button class="btn-sm" onclick="addAutomationTrigger()">+ Advanced Trigger</button>
        </div>
        <div class="section-body">
          <div class="door-guide">
            <div class="door-guide-head">
              <div>
                <div class="door-guide-title">📹 Door Camera Call Setup</div>
                <div class="door-guide-sub">
                  Configure the real door flow here. When face recognition reports an unknown visitor,
                  Simson calls the outdoor camera station first and then bridges its live SIP audio and
                  H.264 video to the indoor phone you choose.
                </div>
              </div>
              <button class="btn-secondary btn" style="font-size:12px;padding:8px 12px"
                      onclick="scrollToSIPPhones()">Manage SIP Phones</button>
            </div>
            <div class="door-flow">
              <div class="door-device">
                <div class="door-device-role">1 · Video source</div>
                <div class="door-device-title">Outdoor door station with camera</div>
                <div class="field">
                  <label>Call video from this SIP phone</label>
                  <select id="door-guide-source" onchange="renderDoorCameraGuideStatus()"></select>
                  <div class="field-hint">The station must auto-answer callback calls and publish its camera media.</div>
                </div>
              </div>
              <div class="door-arrow">→</div>
              <div class="door-device door-device-target">
                <div class="door-device-role">2 · Video destination</div>
                <div class="door-device-title">Indoor monitor or SIP phone</div>
                <div class="field">
                  <label>Redirect live audio + video to this SIP phone</label>
                  <select id="door-guide-target" onchange="renderDoorCameraGuideStatus()"></select>
                  <div class="field-hint">Choose the indoor video-capable phone that should ring for unknown visitors.</div>
                </div>
              </div>
            </div>
            <div class="routing-grid" style="margin-top:12px">
              <div class="field">
                <label>Flow Name</label>
                <input id="door-guide-label" value="Unknown visitor at front door"
                       placeholder="Unknown visitor at front door">
              </div>
              <div class="field">
                <label>Indoor Phone Ring Time <span class="hint-tag">seconds</span></label>
                <input id="door-guide-timeout" type="number" min="5" max="120" value="30">
              </div>
            </div>
            <div id="door-guide-status" class="door-guide-result"></div>
            <div class="quick-route-actions">
              <button class="btn btn-primary" style="font-size:12px;padding:9px 15px"
                      onclick="createDoorCameraFlow()">Create Door Camera Flow</button>
            </div>
          </div>
          <div class="automation-card">
            <p class="field-hint" style="margin-bottom:12px">
              Webhook credentials are shared by this site's safe automation presets. Generate them
              once, then configure your door station or face-recognition controller to send the
              displayed request when an unknown visitor is detected.
            </p>
            <label class="checkbox-row">
              <input id="automation-webhook-enabled" type="checkbox" onchange="markSettingsDirty();renderAutomationPreview()">
              <span>Enable secret-protected external webhook</span>
            </label>
            <div class="routing-grid">
              <div class="field">
                <label>Webhook ID</label>
                <input id="automation-webhook-id" type="text" placeholder="site_alarm_calls"
                       oninput="markSettingsDirty();renderAutomationPreview()">
              </div>
              <div class="field">
                <label>Webhook Secret <span class="hint-tag">keep private</span></label>
                <input id="automation-webhook-secret" type="password" autocomplete="new-password"
                       placeholder="Generate a secure secret"
                       oninput="markSettingsDirty();renderAutomationPreview()">
              </div>
              <div class="field">
                <label>Repeat Protection <span class="hint-tag">seconds</span></label>
                <input id="automation-cooldown" type="number" min="1" max="3600" value="10"
                       onchange="markSettingsDirty()">
              </div>
            </div>
            <div class="quick-route-actions">
              <button class="btn-secondary btn" style="font-size:12px;padding:8px 14px"
                      onclick="generateWebhookCredentials()">Generate Credentials</button>
            </div>
            <div id="automation-webhook-preview"></div>
          </div>
          <div id="automation-list" class="automation-list"></div>
          <div id="automation-empty" class="targets-empty">
            No automation presets yet. Use <b>Door Camera Call Setup</b> above, or add an advanced trigger.
          </div>
        </div>
      </div>

      <!-- Errors + Save bar --------------------------------------- -->
      <div id="save-errors-box" class="save-errors hidden"></div>
      <div id="save-restart-note" class="save-restart-note hidden">
        ⚠ Some changes may take full effect after restarting the addon.
      </div>

      <div class="save-bar">
        <button class="btn btn-primary" id="btn-save" onclick="saveSettings()">
          Save Settings
        </button>
        <span id="save-status-text"></span>
      </div>

      <!-- Danger zone --------------------------------------------- -->
      <div class="card danger-card" style="margin-top:28px">
        <div class="card-title">Danger Zone</div>
        <p style="color:var(--text2);font-size:13px;margin-bottom:14px">
          Reset credentials to re-run the setup wizard. Use this if this node is
          on the wrong account or you need to re-provision.
        </p>
        <button class="btn btn-danger" id="btn-reset" style="font-size:13px;padding:9px 18px"
                onclick="doReset()">Reset Setup</button>
        <div id="reset-result"></div>
      </div>

    </div><!-- /tab-settings -->

  </div><!-- /main-view -->

</div><!-- /app -->

<script>
// ─── Constants injected server-side ─────────────────────────────────────────
const PROVISIONED = __PROVISIONED__;
const HAS_ADMIN_TOKEN = __HAS_ADMIN_TOKEN__;

// ─── State ──────────────────────────────────────────────────────────────────
let _targets = [];            // working copy of call_targets for the form
let _currentTab = 'overview';
let _settingsDirty = false;   // warn if navigate away with unsaved changes
let _pollingTimer = null;
let _loadedSettings = {};     // preserves hidden infrastructure defaults
let _routing = {};
let _availability = {};
let _routeOverrides = {};
let _liveRouting = {};
let _automation = {};
let _automationTriggers = [];

// ─── Bootstrap ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    if (_currentTab === 'settings' && PROVISIONED) saveSettings();
  }
});

async function init() {
  if (!PROVISIONED) {
    renderSetupWizard();
    document.getElementById('setup-view').classList.remove('hidden');
    return;
  }
  document.getElementById('main-view').classList.remove('hidden');
  // Restore last tab from hash
  if (location.hash === '#settings') switchTab('settings', false);
  await refreshAll();
  _pollingTimer = setInterval(pollStatus, 12000);
}

async function refreshAll() {
  await Promise.all([pollStatus(), loadSettings(), loadSIPEndpoints(), loadRoutingBoard()]);
}

// ─── Status polling ──────────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const r = await fetch('api/status');
    if (!r.ok) return;
    const s = await r.json();
    applyStatus(s);
  } catch (_) {}
}

function applyStatus(s) {
  // Badge
  const badge = document.getElementById('status-badge');
  if (s.vps_connected) {
    badge.textContent = 'Connected';
    badge.className = 'badge badge-ok';
  } else {
    badge.textContent = 'Disconnected';
    badge.className = 'badge badge-err';
  }
  // Node info
  setText('node-id-val', s.node_id || '—');
  setText('account-id-val', s.account_id || '—');
  setText('server-url-val', s.server_url || '—');
  setText('copyable-account', s.account_id || '—');
  // VPS dot
  setDot('vps-dot', s.vps_connected);
  setText('vps-label', s.vps_connected ? 'Connected' : 'Disconnected');
  // Asterisk dot
  const astRow = document.getElementById('ast-status-row');
  if (s.asterisk_connected !== undefined) {
    if (astRow) astRow.classList.remove('hidden');
    setDot('ast-dot', s.asterisk_connected);
    setText('ast-label', s.asterisk_connected ? 'Connected' : 'Disconnected');
  } else if (astRow) {
    astRow.classList.add('hidden');
  }
  // Active call card
  const cc = document.getElementById('card-call');
  if (cc) {
    if (s.active_call) {
      const c = s.active_call;
      cc.innerHTML =
        '<div class="card-title">Active Call</div>' +
        infoRow('State', c.state) +
        infoRow('Direction', c.direction) +
        infoRow('With', c.remote_label || c.remote_node_id) +
        infoRow('ID', '<span style="font-family:monospace;font-size:11px">' +
                esc(c.call_id.slice(0, 18)) + '…</span>');
    } else {
      cc.innerHTML = '<div class="card-title">Calls</div><p class="muted">No active call</p>';
    }
  }
}

// ─── Settings load/save ──────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const r = await fetch('api/settings');
    if (!r.ok) return;
    const s = await r.json();
    applySettingsToForm(s);
  } catch (_) {}
}

function applySettingsToForm(s) {
  _loadedSettings = JSON.parse(JSON.stringify(s || {}));
  _targets = JSON.parse(JSON.stringify(s.call_targets || []));
  _routing = JSON.parse(JSON.stringify(s.routing || {}));
  _availability = JSON.parse(JSON.stringify(s.availability || {}));
  _routeOverrides = JSON.parse(JSON.stringify(s.route_overrides || {}));
  _automation = JSON.parse(JSON.stringify(s.automation || {}));
  _automationTriggers = JSON.parse(JSON.stringify(_automation.triggers || []));
  setVal('routing-strategy', _routing.strategy || 'priority');
  setVal('routing-ring-seconds', _routing.ring_seconds || 25);
  setVal('routing-max-attempts', _routing.max_attempts || 4);
  setVal('routing-final-fallback', _routing.final_fallback_target || '');
  setCheck('routing-skip-unavailable', _routing.skip_unavailable !== false);
  setVal('site-availability-mode', _availability.mode || 'available');
  setVal('site-availability-reason', _availability.reason || '');
  setCheck('automation-webhook-enabled', !!_automation.webhook_enabled);
  setVal('automation-webhook-id', _automation.webhook_id || '');
  setVal('automation-webhook-secret', _automation.webhook_secret || '');
  setVal('automation-cooldown', _automation.cooldown_seconds || 10);
  applyQuickRoutePreset(getVal('quick-kind') || 'node');
  renderRoutingBoard();
  renderTargets();
  renderAutomationTriggers();
  renderAutomationPreview();
  _settingsDirty = false;
  setSaveStatus('', '');
}

function collectSettings() {
  const previousPort = parseInt(_loadedSettings.local_api_port);
  return {
    local_api_port: Number.isFinite(previousPort) ? previousPort : 8799,
    asterisk: {
      enabled: false,
      host: '127.0.0.1',
      ami_port: 5038,
      ami_user: 'simson',
      ami_secret: '',
      context: 'from-simson',
      extension_prefix: '9',
      auto_configure: false,
    },
    webrtc: {
      turn_enabled: false,
      turn_url: '',
      turn_username: 'simson',
      turn_credential: '',
      sip_enabled: false,
      sip_ws_url: '',
      sip_username: 'webrtc-pool',
      sip_password: '',
      sip_domain: '',
    },
    routing: collectRouting(),
    availability: {
      mode: getVal('site-availability-mode') || 'available',
      reason: getVal('site-availability-reason').trim(),
    },
    route_overrides: _routeOverrides || {},
    call_targets: collectTargets(),
    automation: collectAutomation(),
  };
}

async function saveSettings() {
  const btn = document.getElementById('btn-save');
  const errBox = document.getElementById('save-errors-box');
  const restartNote = document.getElementById('save-restart-note');

  btn.disabled = true;
  btn.textContent = 'Saving…';
  errBox.classList.add('hidden');
  restartNote.classList.add('hidden');
  setSaveStatus('', '');

  const data = collectSettings();
  try {
    const r = await fetch('api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const resp = await r.json();
    if (r.ok) {
      _settingsDirty = false;
      setSaveStatus('✓ Settings saved', 'ok');
      if (resp.restart_required) {
        restartNote.classList.remove('hidden');
      }
    } else {
      const errors = resp.errors || [resp.error || 'Unknown error'];
      errBox.innerHTML =
        '<b>Please fix the following errors:</b><ul>' +
        errors.map(e => '<li>' + esc(e) + '</li>').join('') +
        '</ul>';
      errBox.classList.remove('hidden');
      setSaveStatus('✗ Not saved', 'err');
    }
  } catch (e) {
    setSaveStatus('✗ Network error: ' + esc(e.message), 'err');
  }
  btn.disabled = false;
  btn.textContent = 'Save Settings';
}

// ─── Routing policy / live board ─────────────────────────────────────────────
function collectRouting() {
  return {
    strategy: getVal('routing-strategy') || 'priority',
    ring_seconds: parseInt(getVal('routing-ring-seconds')) || 25,
    max_attempts: parseInt(getVal('routing-max-attempts')) || 4,
    skip_unavailable: getCheck('routing-skip-unavailable'),
    final_fallback_target: getVal('routing-final-fallback').trim(),
  };
}

async function loadRoutingBoard() {
  try {
    const r = await fetch('api/routing');
    if (!r.ok) return;
    _liveRouting = await r.json();
    if (_liveRouting.routing) _routing = _liveRouting.routing;
    if (_liveRouting.availability) _availability = _liveRouting.availability;
    renderRoutingBoard();
  } catch (_) {}
}

function renderRoutingBoard() {
  const board = document.getElementById('route-board');
  const badge = document.getElementById('routing-mode-badge');
  const liveCall = document.getElementById('live-call-board');
  const siteMode = (_availability.mode || getVal('site-availability-mode') || 'available');

  if (badge) {
    badge.textContent = siteMode;
    badge.className = 'section-badge ' +
      (siteMode === 'available' ? 'section-badge-on' : 'section-badge-off');
  }

  if (liveCall) {
    const call = _liveRouting.active_call;
    if (call) {
      const elapsed = formatDuration(call.active_for || 0);
      const owner = call.answered_by_user_name || call.answered_by_user_id ||
        call.target_user_name || call.target_user_id || call.caller_user_id || 'site';
      const route = call.forwarded_to
        ? ` · forwarded to ${call.forwarded_extension || call.forwarded_to}`
        : '';
      liveCall.classList.remove('hidden');
      liveCall.innerHTML = '<b>Live call:</b> ' + esc(call.state) + ' · ' +
        esc(call.remote_label || call.remote_node_id || call.call_id) +
        ' · ' + esc(owner) + ' · ' + esc(elapsed) + esc(route);
    } else {
      liveCall.classList.add('hidden');
      liveCall.innerHTML = '';
    }
  }

  if (!board) return;
  const liveTargets = Array.isArray(_liveRouting.targets) ? _liveRouting.targets : [];
  const byId = Object.fromEntries(liveTargets.map(t => [t.id, t]));
  const targets = (_targets || []).map(t => byId[t.id] || t);

  if (!targets.length) {
    board.innerHTML = '<div class="targets-empty">Add call targets below to build your routing board.</div>';
    return;
  }

  board.innerHTML = targets.map(t => {
    const id = t.id || '';
    const av = t.availability || _routeOverrides[id] || {mode:'available', reason:''};
    const mode = av.mode || 'available';
    const detail = [
      targetTypeLabel(t.type || 'node'),
      t.node_id || t.extension || '',
      av.reason || '',
    ].filter(Boolean).join(' · ');
    return `<div class="route-row">
      <div class="route-row-main">
        <div class="route-row-title">${esc(t.label || id || 'Unnamed target')}</div>
        <div class="route-row-sub">${esc(detail || id)}</div>
      </div>
      <span class="mode-pill mode-${esc(mode)}">${esc(mode)}</span>
      <div class="route-actions">
        <button class="btn-sm-ghost" onclick="setTargetAvailability(${jsString(id)},'available')">Available</button>
        <button class="btn-sm-ghost" onclick="setTargetAvailability(${jsString(id)},'busy')">Busy</button>
        <button class="btn-sm-ghost" onclick="setTargetAvailability(${jsString(id)},'offline')">Offline</button>
      </div>
    </div>`;
  }).join('');
}

async function setSiteAvailability(mode) {
  _availability = {
    mode,
    reason: getVal('site-availability-reason').trim(),
  };
  markSettingsDirty();
  renderRoutingBoard();
  try {
    await fetch('api/availability', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_availability),
    });
  } catch (_) {}
}

async function setTargetAvailability(targetId, mode) {
  if (!targetId) return;
  _routeOverrides[targetId] = {mode, reason: ''};
  markSettingsDirty();
  renderRoutingBoard();
  try {
    const r = await fetch('api/target-availability', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({target_id: targetId, mode, reason: ''}),
    });
    if (r.ok) loadRoutingBoard();
  } catch (_) {}
}

function markSettingsDirty() {
  _settingsDirty = true;
  setSaveStatus('Unsaved changes', '');
}

function applyQuickRoutePreset(kind) {
  const isNode = kind === 'node';
  const isGateway = kind === 'gateway';
  const nodeWrap = document.getElementById('quick-node-wrap');
  const extWrap = document.getElementById('quick-ext-wrap');
  const trunkWrap = document.getElementById('quick-trunk-wrap');
  if (nodeWrap) nodeWrap.style.display = isNode ? '' : 'none';
  if (extWrap) extWrap.style.display = isNode ? 'none' : '';
  if (trunkWrap) trunkWrap.style.display = isGateway ? '' : 'none';
  setText('quick-ext-label', isGateway ? 'Outside Number' : 'SIP Extension');
  const ext = document.getElementById('quick-ext');
  if (ext) ext.placeholder = isGateway ? '+919123208334' : '1025';
  const trunk = document.getElementById('quick-trunk');
  if (trunk && isGateway && !trunk.value) trunk.value = '7009';
  const timeout = document.getElementById('quick-timeout');
  if (timeout && !timeout.value) timeout.value = getVal('routing-ring-seconds') || '25';
}

function targetTypeLabel(type) {
  return ({
    node: 'HAOS node',
    device: 'Device',
    sip: 'SIP phone',
    gateway: 'Gateway / outside line',
    asterisk: 'SIP / gateway',
    queue: 'Queue',
  })[type] || type || 'Target';
}

function createQuickRoute() {
  const kind = getVal('quick-kind') || 'node';
  const label = getVal('quick-label').trim();
  const id = (getVal('quick-id').trim() || slugify(label || getVal('quick-node') || getVal('quick-ext'))).slice(0, 64);
  const nodeId = getVal('quick-node').trim();
  const ext = getVal('quick-ext').trim();
  const trunk = getVal('quick-trunk').trim();
  const timeout = parseInt(getVal('quick-timeout')) || parseInt(getVal('routing-ring-seconds')) || 25;
  const fallbacks = splitTargetList(getVal('quick-fallbacks'));
  if (!id || !label) {
    setSaveStatus('Quick route needs a friendly name', 'err');
    return;
  }
  if (_targets.some(t => t.id === id)) {
    setSaveStatus('Target ID already exists: ' + id, 'err');
    return;
  }
  if (kind === 'node' && !nodeId) {
    setSaveStatus('HAOS Node ID is required for dashboard/addon routes', 'err');
    return;
  }
  if (kind !== 'node' && !ext) {
    setSaveStatus('Extension or number is required for SIP/gateway routes', 'err');
    return;
  }
  if (kind === 'gateway' && !trunk) {
    setSaveStatus('Gateway/trunk is required for outside-number routes', 'err');
    return;
  }

  _targets.push({
    type: kind,
    id,
    label,
    node_id: kind === 'node' ? nodeId : '',
    extension: kind === 'node' ? '' : ext,
    context: 'from-simson',
    trunk: kind === 'gateway' ? trunk : '',
    caller_id: '',
    timeout,
    fallback_targets: fallbacks,
    icon: kind === 'node' ? '🏠' : kind === 'gateway' ? '🌐' : '☎',
    _open: false,
  });
  markSettingsDirty();
  clearQuickRoute(false);
  renderTargets();
  renderRoutingBoard();
  renderAutomationTriggers();
  setSaveStatus('Route added. Press Save Settings to keep it.', 'ok');
}

function clearQuickRoute(resetKind = true) {
  ['quick-label','quick-id','quick-node','quick-ext','quick-fallbacks'].forEach(id => setVal(id, ''));
  setVal('quick-timeout', getVal('routing-ring-seconds') || '25');
  if (resetKind) setVal('quick-kind', 'node');
  applyQuickRoutePreset(getVal('quick-kind') || 'node');
}

function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'target_' + (_targets.length + 1);
}

// ─── SIP Endpoints management ────────────────────────────────────────────────
let _sipEndpoints = [];

function normalizeSIPEndpoint(ep) {
  if (!ep || typeof ep !== 'object') return null;
  return {
    id: ep.id ?? ep.ID ?? '',
    extension: ep.extension ?? ep.Extension ?? '',
    username: ep.username ?? ep.Username ?? '',
    password: ep.password ?? ep.Password ?? '',
    description: ep.description ?? ep.Description ?? '',
    route_to: ep.route_to ?? ep.RouteTo ?? '',
    video_enabled: ep.video_enabled ?? ep.VideoEnabled ?? false,
    enabled: ep.enabled ?? ep.Enabled ?? true,
    created_at: ep.created_at ?? ep.CreatedAt ?? '',
    updated_at: ep.updated_at ?? ep.UpdatedAt ?? '',
  };
}

function normalizeSIPEndpointsList(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map(normalizeSIPEndpoint)
    .filter(Boolean);
}

async function loadSIPEndpoints() {
  try {
    const r = await fetch('api/sip-endpoints');
    if (!r.ok) {
      document.getElementById('sip-endpoints-body').innerHTML =
        '<p class="muted">Unable to load SIP endpoints.</p>';
      return;
    }
    const data = await r.json();
    let endpoints = [];
    if (Array.isArray(data)) {
      endpoints = data;
    } else if (data && Array.isArray(data.endpoints)) {
      endpoints = data.endpoints;
    } else if (data && Array.isArray(data.items)) {
      endpoints = data.items;
    } else {
      _sipEndpoints = [];
      if (data && data.error) {
        document.getElementById('sip-endpoints-body').innerHTML =
          '<p class="muted">Unable to load SIP endpoints: ' + esc(data.error) + '</p>';
        return;
      }
    }
    _sipEndpoints = normalizeSIPEndpointsList(endpoints);
    renderSIPEndpoints();
  } catch (e) {
    document.getElementById('sip-endpoints-body').innerHTML =
      '<p class="muted">Error: ' + esc(e.message) + '</p>';
  }
}

function renderSIPEndpoints() {
  const body = document.getElementById('sip-endpoints-body');
  if (!body) return;
  const endpoints = Array.isArray(_sipEndpoints) ? _sipEndpoints : [];

  const html = `
    <div style="margin-bottom:14px">
      <div class="alert alert-info" style="margin-top:0;margin-bottom:12px">
        Phone/ATA setup: SIP server/domain is your VPS hostname, port 5060,
        transport TCP or UDP, username/auth username from the endpoint below,
        and codecs PCMU/G.711u plus PCMA/G.711a only. For an analog landline
        phone, put these same SIP settings in the ATA box.
      </div>
      <button class="btn-sm" onclick="showCreateSIPForm()" style="margin-bottom:12px">
        + Add SIP Phone
      </button>
      <div id="sip-create-form" class="hidden" style="background:var(--surface2);border:1px solid var(--border);
                border-radius:var(--radius-sm);padding:14px;margin-bottom:14px">
        <div class="field-row" style="flex-direction:column">
          <div class="field" style="width:100%">
            <label>Extension</label>
            <input type="text" id="sip-ext" placeholder="1001" autocomplete="off">
            <div class="field-hint">Dial number for this phone. Use the same value as Username unless your phone requires a separate auth ID.</div>
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label>Username <span class="hint-tag">— SIP auth username</span></label>
            <input type="text" id="sip-user" placeholder="phone1" autocomplete="off">
          </div>
          <div class="field">
            <label>Password <span class="hint-tag">— SIP auth password</span></label>
            <input type="password" id="sip-pass" autocomplete="new-password">
          </div>
        </div>
        <div class="field-row" style="flex-direction:column">
          <div class="field" style="width:100%">
            <label>Label <span class="hint-tag">— optional description</span></label>
            <input type="text" id="sip-desc" placeholder="Front desk phone" autocomplete="off">
          </div>
        </div>
        <div class="field-row" style="flex-direction:column">
          <div class="field" style="width:100%">
            <label>Route To Node ID <span class="hint-tag">— optional dedicated destination</span></label>
            <input type="text" id="sip-route" placeholder="living_room">
            <div class="field-hint">Set this to the Node ID shown on Overview to make this SIP/landline device ring that HAOS addon.</div>
          </div>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="sip-enabled" checked>
          <label for="sip-enabled">Endpoint enabled</label>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="sip-video-enabled">
          <label for="sip-video-enabled">Video capable device <span class="hint-tag">H.264 camera / monitor only</span></label>
        </div>
        <div style="display:flex;gap:10px;margin-top:10px">
          <button class="btn btn-primary btn-sm" style="padding:8px 16px"
                  onclick="createSIPEndpoint(event)">Create</button>
          <button class="btn-secondary btn-sm" style="padding:8px 16px;background:var(--surface3);border:1px solid var(--border)"
                  onclick="hideSIPForm()">Cancel</button>
        </div>
        <div id="sip-create-result"></div>
      </div>
    </div>

    <div id="sip-list">
      ${endpoints.length === 0
        ? '<p class="muted">no sip phones configured</p>'
        : endpoints.map((ep, i) => `
          <div style="padding:12px;background:var(--surface2);border-radius:8px;
                      margin-bottom:10px;border:1px solid var(--border)">
            <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
              <div style="min-width:0">
                <div style="font-weight:600;color:var(--text);font-size:14px">
                  [${esc(ep.extension)}] ${esc(ep.description || ep.username)}
                </div>
                <div style="color:var(--text3);font-size:12px;margin-top:4px;line-height:1.5">
                  Username: <code style="background:var(--surface3);padding:2px 6px;border-radius:3px;font-family:monospace">${esc(ep.username)}</code>
                  · Status: <b style="color:${ep.enabled ? 'var(--green-light)' : 'var(--red-light)'}">${ep.enabled ? 'Enabled' : 'Disabled'}</b>
                  · Media: <b>${ep.video_enabled ? 'Audio + H.264 video' : 'Audio only'}</b>
                  · Route: <b>${esc(ep.route_to || 'Any available node')}</b>
                </div>
              </div>
              <button class="btn-icon del"
                      onclick="deleteSIPEndpoint('${ep.id}', ${i})"
                      title="Delete SIP endpoint">✕</button>
            </div>
            <div class="field-row" style="margin-top:12px">
              <div class="field">
                <label>Description</label>
                <input type="text" id="ep-desc-${i}" value="${esc(ep.description)}" placeholder="Front desk phone">
              </div>
              <div class="field">
                <label>Route To Node ID</label>
                <input type="text" id="ep-route-${i}" value="${esc(ep.route_to)}" placeholder="living_room">
              </div>
            </div>
            <div class="field-row" style="align-items:flex-end">
              <div class="field">
                <label>Rotate Password <span class="hint-tag">— optional</span></label>
                <input type="password" id="ep-pass-${i}" placeholder="Leave blank to keep current password">
              </div>
              <div class="field" style="max-width:180px">
                <label class="checkbox-row" style="padding:0">
                  <input type="checkbox" id="ep-enabled-${i}" ${ep.enabled ? 'checked' : ''}>
                  <span>Enabled</span>
                </label>
                <label class="checkbox-row" style="padding:0;margin-top:8px">
                  <input type="checkbox" id="ep-video-${i}" ${ep.video_enabled ? 'checked' : ''}>
                  <span>Video capable</span>
                </label>
              </div>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:6px">
              <button class="btn-secondary btn-sm"
                      style="padding:8px 16px;background:var(--surface3);border:1px solid var(--border)"
                      onclick="updateSIPEndpoint('${ep.id}', ${i}, event)">Save Changes</button>
            </div>
          </div>
        `).join('')
      }
    </div>
  `;
  body.innerHTML = html;
  renderDoorCameraGuideOptions();
}

function showCreateSIPForm() {
  const form = document.getElementById('sip-create-form');
  if (form) form.classList.remove('hidden');
}

function hideSIPForm() {
  const form = document.getElementById('sip-create-form');
  if (form) form.classList.add('hidden');
  ['sip-ext','sip-user','sip-pass','sip-desc','sip-route'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  setCheck('sip-enabled', true);
  setCheck('sip-video-enabled', false);
  const resultDiv = document.getElementById('sip-create-result');
  if (resultDiv) resultDiv.innerHTML = '';
}

async function createSIPEndpoint(event) {
  const ext = getVal('sip-ext').trim();
  const user = getVal('sip-user').trim();
  const pass = getVal('sip-pass').trim();
  const desc = getVal('sip-desc').trim();
  const routeTo = getVal('sip-route').trim();
  const enabled = getCheck('sip-enabled');
  const videoEnabled = getCheck('sip-video-enabled');
  const resultDiv = document.getElementById('sip-create-result');

  if (!ext || !user || !pass) {
    if (resultDiv) resultDiv.innerHTML =
      '<div class="alert alert-error" style="margin-top:10px">Extension, username, and password are required</div>';
    return;
  }

  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Creating…';

  try {
    const r = await fetch('api/sip-endpoints', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        extension: ext,
        username: user,
        password: pass,
        description: desc,
        route_to: routeTo,
        video_enabled: videoEnabled,
        enabled,
      }),
    });

    if (r.ok) {
      const epRaw = await r.json();
      const ep = normalizeSIPEndpoint(epRaw);
      if (ep) _sipEndpoints.push(ep);
      if (resultDiv) resultDiv.innerHTML =
        '<div class="alert alert-success" style="margin-top:10px">✓ Phone created! Reloading…</div>';
      setTimeout(() => {
        renderSIPEndpoints();
        hideSIPForm();
      }, 800);
    } else {
      const err = await r.json();
      if (resultDiv) resultDiv.innerHTML =
        '<div class="alert alert-error" style="margin-top:10px">✗ ' +
        esc(err.error || 'Failed to create phone') + '</div>';
      btn.disabled = false;
      btn.textContent = 'Create';
    }
  } catch (e) {
    if (resultDiv) resultDiv.innerHTML =
      '<div class="alert alert-error" style="margin-top:10px">✗ ' + esc(e.message) + '</div>';
    btn.disabled = false;
    btn.textContent = 'Create';
  }
}

async function updateSIPEndpoint(id, idx, event) {
  const btn = event?.target;
  const description = getVal(`ep-desc-${idx}`).trim();
  const route_to = getVal(`ep-route-${idx}`).trim();
  const password = getVal(`ep-pass-${idx}`).trim();
  const enabled = getCheck(`ep-enabled-${idx}`);
  const video_enabled = getCheck(`ep-video-${idx}`);

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Saving…';
  }

  try {
    const r = await fetch(`api/sip-endpoints/${id}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({description, route_to, password, video_enabled, enabled}),
    });
    const data = await r.json();
    if (!r.ok) {
      throw new Error(data.error || 'Failed to update SIP endpoint');
    }

    const updated = normalizeSIPEndpoint(data);
    if (updated) _sipEndpoints[idx] = updated;
    renderSIPEndpoints();
    setSaveStatus('✓ SIP endpoint updated', 'ok');
  } catch (e) {
    alert('Update failed: ' + e.message);
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Save Changes';
    }
  }
}

async function deleteSIPEndpoint(id, idx) {
  if (!confirm('Delete this SIP phone? It will no longer be able to register.')) return;

  try {
    const r = await fetch(`api/sip-endpoints/${id}`, {method: 'DELETE'});
    if (r.ok) {
      _sipEndpoints.splice(idx, 1);
      renderSIPEndpoints();
    } else {
      alert('Delete failed. See browser console for details.');
    }
  } catch (e) {
    alert('Delete error: ' + e.message);
  }
}

// ─── Call targets ─────────────────────────────────────────────────────────────
function renderTargets() {
  const list = document.getElementById('targets-list');
  const empty = document.getElementById('targets-empty');
  const countBadge = document.getElementById('targets-count-badge');
  if (countBadge) {
    countBadge.textContent = _targets.length;
    countBadge.className = 'section-badge ' +
      (_targets.length > 0 ? 'section-badge-on' : 'section-badge-off');
  }
  if (_targets.length === 0) {
    list.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  list.innerHTML = _targets.map((t, i) => {
    const emoji = t.icon || {node:'🏠',device:'📱',asterisk:'☎',queue:'📋'}[t.type] || '📞';
    const isOpen = !!t._open;
    const mode = (_routeOverrides[t.id || ''] || {}).mode || 'available';
    return `<div class="target-card" id="tc-${i}">
      <div class="target-head" onclick="toggleTarget(${i})">
        <span class="target-emoji">${esc(emoji)}</span>
        <span class="target-name">${esc(t.label || t.id || 'Target ' + (i+1))}</span>
        <span class="target-type-pill">${esc(targetTypeLabel(t.type || 'node'))}</span>
        <span class="mode-pill mode-${esc(mode)}">${esc(mode)}</span>
        <div class="target-actions" onclick="event.stopPropagation()">
          <button class="btn-icon del" onclick="removeTarget(${i})" title="Remove target">✕</button>
        </div>
      </div>
      ${isOpen ? targetForm(t, i) : ''}
    </div>`;
  }).join('');
}

function toggleTarget(i) {
  _targets[i]._open = !_targets[i]._open;
  // Flush form values before re-render
  collectTargetValues(i);
  renderTargets();
}

function targetForm(t, i) {
  const typeLabels = {
    node: 'HAOS node / dashboard',
    sip: 'SIP phone / desk extension',
    gateway: 'Gateway / outside phone',
    device: 'Specific device',
    asterisk: 'SIP phone or gateway',
    queue: 'Queue / group',
  };
  const types = ['node','sip','gateway','device','queue','asterisk'];
  const typeOpts = types.map(v =>
    `<option value="${v}"${t.type===v?' selected':''}>${typeLabels[v]}</option>`).join('');
  const isAst = ['asterisk','sip','gateway'].includes(t.type);
  const isGateway = t.type === 'gateway';
  return `<div class="target-form">
    <div class="field-row">
      <div class="field" style="max-width:140px">
        <label>Route Type</label>
        <select id="t${i}-type" onchange="onTargetTypeChange(${i},this.value)">${typeOpts}</select>
      </div>
      <div class="field">
        <label>ID <span class="hint-tag">unique key</span></label>
        <input type="text" id="t${i}-id" value="${esc(t.id||'')}"
               placeholder="living_room" oninput="targetField(${i},'id',this.value)">
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Label</label>
        <input type="text" id="t${i}-label" value="${esc(t.label||'')}"
               placeholder="Living Room" oninput="targetField(${i},'label',this.value)">
      </div>
      <div class="field" style="max-width:100px">
        <label>Icon <span class="hint-tag">emoji</span></label>
        <input type="text" id="t${i}-icon" value="${esc(t.icon||'')}"
               placeholder="🏠" oninput="targetField(${i},'icon',this.value)">
      </div>
    </div>
    <div class="field-row" id="t${i}-node-row"${isAst?' style="display:none"':''}>
      <div class="field" style="width:100%">
        <label>HAOS Node ID <span class="hint-tag">for dashboard/addon routes</span></label>
        <input type="text" id="t${i}-node" value="${esc(t.node_id||'')}"
               placeholder="ha_kitchen" oninput="targetField(${i},'node_id',this.value)">
      </div>
    </div>
    <div class="field-row" id="t${i}-ast-row"${!isAst?' style="display:none"':''}>
      <div class="field">
        <label>${isGateway ? 'Outside Number' : 'SIP Extension'}</label>
        <input type="text" id="t${i}-ext" value="${esc(t.extension||'')}"
               placeholder="101 or 919876543210" oninput="targetField(${i},'extension',this.value)">
        <div class="field-hint">Use a SIP extension like 1025, or an outside number when Gateway/Trunk is set.</div>
      </div>
      <div class="field">
        <label>Context</label>
        <input type="text" id="t${i}-ctx" value="${esc(t.context||'')}"
               placeholder="from-simson" oninput="targetField(${i},'context',this.value)">
      </div>
    </div>
    <div class="field-row" id="t${i}-trunk-row"${!isAst?' style="display:none"':''}>
      <div class="field" style="width:100%">
        <label>Gateway / Trunk <span class="hint-tag">optional</span></label>
        <input type="text" id="t${i}-trunk" value="${esc(t.trunk||'')}"
               placeholder="provider-trunk"
               oninput="targetField(${i},'trunk',this.value)">
        <div class="field-hint">For outside calls use the gateway endpoint/trunk, e.g. 7009. Leave empty for an internal SIP phone.</div>
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label>Caller ID <span class="hint-tag">optional</span></label>
        <input type="text" id="t${i}-cid" value="${esc(t.caller_id||'')}"
               placeholder='"Front Door" &lt;9001&gt;' oninput="targetField(${i},'caller_id',this.value)">
      </div>
      <div class="field" style="max-width:110px">
        <label>Timeout <span class="hint-tag">sec</span></label>
        <input type="number" id="t${i}-timeout" value="${t.timeout||30}"
               min="5" max="300" oninput="targetField(${i},'timeout',parseInt(this.value)||30)">
      </div>
    </div>
    <div class="field-row" style="flex-direction:column">
      <div class="field" style="width:100%">
        <label>Try Next If Busy / No Answer <span class="hint-tag">target IDs</span></label>
        <input type="text" id="t${i}-fallbacks" value="${esc((t.fallback_targets||[]).join(', '))}"
               placeholder="front_desk, mobile_backup"
               oninput="targetField(${i},'fallback_targets',splitTargetList(this.value))">
        <div class="field-hint">Comma-separated target IDs. Example: office2, front_desk_phone, mobile_backup.</div>
      </div>
    </div>
    <div style="display:flex;justify-content:flex-end;margin-top:6px">
      <button type="button" class="btn-secondary btn"
              style="font-size:12px;padding:7px 14px"
              onclick="toggleTarget(${i})">Done</button>
    </div>
  </div>`;
}

function onTargetTypeChange(i, value) {
  _targets[i].type = value;
  markSettingsDirty();
  const nodeRow = document.getElementById(`t${i}-node-row`);
  const astRow = document.getElementById(`t${i}-ast-row`);
  const trunkRow = document.getElementById(`t${i}-trunk-row`);
  const isAst = ['asterisk','sip','gateway'].includes(value);
  if (nodeRow) nodeRow.style.display = isAst ? 'none' : '';
  if (astRow) astRow.style.display = isAst ? '' : 'none';
  if (trunkRow) trunkRow.style.display = isAst ? '' : 'none';
  // Update pill without full re-render
  const pill = document.querySelector(`#tc-${i} .target-type-pill`);
  if (pill) pill.textContent = targetTypeLabel(value);
}
function targetField(i, key, value) {
  if (_targets[i]) _targets[i][key] = value;
  markSettingsDirty();
}
function splitTargetList(value) {
  return String(value || '')
    .split(',')
    .map(v => v.trim())
    .filter(Boolean);
}

function collectTargetValues(i) {
  // Flush any in-flight input values back to _targets[i] before re-render
  if (!_targets[i]) return;
  const fields = {
    id:`t${i}-id`, label:`t${i}-label`, icon:`t${i}-icon`,
    node_id:`t${i}-node`, extension:`t${i}-ext`, context:`t${i}-ctx`,
    trunk:`t${i}-trunk`, caller_id:`t${i}-cid`,
  };
  for (const [key, elId] of Object.entries(fields)) {
    const el = document.getElementById(elId);
    if (el) _targets[i][key] = el.value;
  }
  const fallbacks = document.getElementById(`t${i}-fallbacks`);
  if (fallbacks) _targets[i].fallback_targets = splitTargetList(fallbacks.value);
  const to = document.getElementById(`t${i}-timeout`);
  if (to) _targets[i].timeout = parseInt(to.value) || 30;
  const ty = document.getElementById(`t${i}-type`);
  if (ty) _targets[i].type = ty.value;
}

function collectTargets() {
  // Flush all open forms first
  _targets.forEach((_, i) => collectTargetValues(i));
  return _targets.map(t => {
    const clean = {...t};
    delete clean._open;
    return clean;
  });
}

function addTarget() {
  _targets.push({
    type: 'node', id: '', label: '', node_id: '', extension: '',
    context: '', trunk: '', caller_id: '', timeout: parseInt(getVal('routing-ring-seconds')) || 25,
    fallback_targets: [], icon: '', _open: true,
  });
  markSettingsDirty();
  renderTargets();
  renderRoutingBoard();
  renderAutomationTriggers();
  // Scroll to new target
  const last = document.getElementById('targets-list')?.lastElementChild;
  if (last) last.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function formatDuration(seconds) {
  seconds = Math.max(0, parseInt(seconds || 0));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function removeTarget(i) {
  const removed = _targets[i];
  _targets.splice(i, 1);
  if (removed?.id && _routeOverrides[removed.id]) delete _routeOverrides[removed.id];
  markSettingsDirty();
  renderTargets();
  renderRoutingBoard();
  renderAutomationTriggers();
}

// ─── Automation presets / webhooks ──────────────────────────────────────────
function scrollToSIPPhones() {
  document.getElementById('section-sip-endpoints')?.scrollIntoView({
    behavior: 'smooth', block: 'start',
  });
}

function doorEndpointLabel(ep) {
  if (!ep) return '';
  const flags = [
    ep.video_enabled ? 'H.264 video' : 'audio only',
    ep.enabled ? 'enabled' : 'disabled',
  ].join(' · ');
  return `${ep.description || ep.username || ep.extension} · ext ${ep.extension} · ${flags}`;
}

function renderDoorCameraGuideOptions() {
  const source = document.getElementById('door-guide-source');
  const target = document.getElementById('door-guide-target');
  if (!source || !target) return;

  const previousSource = source.value;
  const previousTarget = target.value;
  const endpoints = Array.isArray(_sipEndpoints) ? _sipEndpoints : [];
  const options = endpoints.map(ep =>
    `<option value="${esc(ep.extension)}">${esc(doorEndpointLabel(ep))}</option>`
  ).join('');
  const empty = '<option value="">No SIP phones configured yet</option>';
  source.innerHTML = '<option value="">Select outdoor camera station…</option>' + (options || empty);
  target.innerHTML = '<option value="">Select indoor video phone…</option>' + (options || empty);

  const hasExtension = value => endpoints.some(ep => String(ep.extension) === String(value));
  if (hasExtension(previousSource)) source.value = previousSource;
  if (hasExtension(previousTarget)) target.value = previousTarget;

  const videoEndpoints = endpoints.filter(ep => ep.enabled && ep.video_enabled);
  if (!source.value && videoEndpoints.length) source.value = String(videoEndpoints[0].extension);
  if (!target.value) {
    const next = videoEndpoints.find(ep => String(ep.extension) !== String(source.value));
    if (next) target.value = String(next.extension);
  }
  renderDoorCameraGuideStatus();
}

function findDoorTargetByExtension(extension) {
  return (_targets || []).find(t =>
    ['sip', 'asterisk'].includes(String(t.type || '')) &&
    String(t.extension || '').trim() === String(extension || '').trim()
  );
}

function findDoorTriggerTarget(trigger) {
  return (_targets || []).find(t => String(t.id || '') === String(trigger?.target_id || ''));
}

function renderDoorCameraGuideStatus(message = '') {
  const box = document.getElementById('door-guide-status');
  if (!box) return;
  const sourceExt = getVal('door-guide-source').trim();
  const targetExt = getVal('door-guide-target').trim();
  const source = (_sipEndpoints || []).find(ep => String(ep.extension) === sourceExt);
  const target = (_sipEndpoints || []).find(ep => String(ep.extension) === targetExt);
  const existing = (_automationTriggers || []).filter(t => String(t.mode || '') === 'door_station');

  let html = message ? `<div style="margin-bottom:7px"><b>${esc(message)}</b></div>` : '';
  if (!(_sipEndpoints || []).length) {
    html += 'Add the outdoor door station and indoor monitor under <b>SIP Phone Endpoints</b> first. Mark both as <b>Video capable</b>.';
  } else if (!sourceExt || !targetExt) {
    html += 'Choose the outdoor camera station and the indoor phone that should receive its live video.';
  } else if (sourceExt === targetExt) {
    html += '<span style="color:var(--red-light)">Choose two different SIP phones: one outdoor source and one indoor destination.</span>';
  } else if (!source?.enabled || !target?.enabled) {
    html += '<span style="color:var(--red-light)">Both selected SIP endpoints must be enabled.</span>';
  } else if (!source?.video_enabled || !target?.video_enabled) {
    html += '<span style="color:var(--yellow-light)">Enable <b>Video capable</b> on both selected SIP endpoints before creating this flow.</span>';
  } else {
    html += `<b>Ready:</b> unknown-face webhook → call outdoor station <b>${esc(sourceExt)}</b> → bridge live audio + H.264 video → ring indoor phone <b>${esc(targetExt)}</b>.`;
  }

  if (existing.length) {
    html += '<div class="door-flow-summary"><b>Saved door flows</b><br>' +
      existing.map(t => {
        const destination = findDoorTriggerTarget(t);
        return `${esc(t.label || t.id)}: outdoor ext ${esc(t.source_extension || '—')} → ` +
          `indoor ${esc(destination?.label || destination?.extension || t.target_id || '—')} ` +
          `(ext ${esc(destination?.extension || '—')})`;
      }).join('<br>') + '</div>';
  }
  box.innerHTML = html;
}

function uniqueAutomationId(base) {
  const existing = new Set((_automationTriggers || []).map(t => String(t.id || '')));
  if (!existing.has(base)) return base;
  let suffix = 2;
  while (existing.has(`${base}_${suffix}`)) suffix += 1;
  return `${base}_${suffix}`;
}

function ensureDoorPhoneTarget(ep) {
  const existing = findDoorTargetByExtension(ep.extension);
  if (existing) return existing;
  const base = `door_phone_${slugify(ep.description || ep.username || ep.extension)}`;
  const ids = new Set((_targets || []).map(t => String(t.id || '')));
  let id = base;
  let suffix = 2;
  while (ids.has(id)) {
    id = `${base}_${suffix}`;
    suffix += 1;
  }
  const target = {
    type: 'sip',
    id,
    label: ep.description || ep.username || `SIP ${ep.extension}`,
    node_id: '',
    extension: String(ep.extension),
    context: '',
    trunk: '',
    caller_id: '',
    timeout: parseInt(getVal('door-guide-timeout')) || 30,
    fallback_targets: [],
    icon: '📹',
  };
  _targets.push(target);
  return target;
}

function createDoorCameraFlow() {
  const sourceExt = getVal('door-guide-source').trim();
  const targetExt = getVal('door-guide-target').trim();
  const source = (_sipEndpoints || []).find(ep => String(ep.extension) === sourceExt);
  const target = (_sipEndpoints || []).find(ep => String(ep.extension) === targetExt);
  const timeout = parseInt(getVal('door-guide-timeout')) || 30;
  const label = getVal('door-guide-label').trim() || 'Unknown visitor at front door';

  if (!source || !target) {
    renderDoorCameraGuideStatus('Select both SIP phones before creating the flow.');
    return;
  }
  if (sourceExt === targetExt) {
    renderDoorCameraGuideStatus('The outdoor station and indoor phone must be different devices.');
    return;
  }
  if (!source.enabled || !target.enabled || !source.video_enabled || !target.video_enabled) {
    renderDoorCameraGuideStatus('Both devices must be enabled and marked Video capable first.');
    return;
  }
  if (timeout < 5 || timeout > 120) {
    renderDoorCameraGuideStatus('Indoor phone ring time must be between 5 and 120 seconds.');
    return;
  }

  const savedTarget = ensureDoorPhoneTarget(target);
  _automationTriggers.push({
    id: uniqueAutomationId(`unknown_face_${sourceExt}`),
    label,
    target_id: savedTarget.id,
    caller_id: `"${label}" <${sourceExt}>`,
    mode: 'door_station',
    source_extension: sourceExt,
    timeout,
    enabled: true,
  });
  if (!getVal('automation-webhook-id').trim() || getVal('automation-webhook-secret').trim().length < 24) {
    generateWebhookCredentials();
  } else {
    setCheck('automation-webhook-enabled', true);
  }
  markSettingsDirty();
  renderTargets();
  renderRoutingBoard();
  renderAutomationTriggers();
  renderAutomationPreview();
  renderDoorCameraGuideStatus('Door camera flow created. Press Save Settings to activate it.');
}

function collectAutomation() {
  return {
    webhook_enabled: getCheck('automation-webhook-enabled'),
    webhook_id: getVal('automation-webhook-id').trim(),
    webhook_secret: getVal('automation-webhook-secret').trim(),
    cooldown_seconds: parseInt(getVal('automation-cooldown')) || 10,
    triggers: _automationTriggers.map(t => ({
      id: String(t.id || '').trim(),
      label: String(t.label || '').trim(),
      target_id: String(t.target_id || '').trim(),
      caller_id: String(t.caller_id || '').trim(),
      mode: String(t.mode || 'standard').trim(),
      source_extension: String(t.source_extension || '').trim(),
      timeout: parseInt(t.timeout) || 30,
      enabled: t.enabled !== false,
    })),
  };
}

function renderAutomationTriggers() {
  const list = document.getElementById('automation-list');
  const empty = document.getElementById('automation-empty');
  const badge = document.getElementById('automation-count-badge');
  if (!list || !empty) return;
  if (badge) {
    badge.textContent = _automationTriggers.length;
    badge.className = 'section-badge ' +
      (_automationTriggers.length ? 'section-badge-on' : 'section-badge-off');
  }
  if (!_automationTriggers.length) {
    list.innerHTML = '';
    empty.style.display = '';
    renderDoorCameraGuideStatus();
    return;
  }
  empty.style.display = 'none';
  list.innerHTML = _automationTriggers.map((t, i) => {
    const mode = String(t.mode || 'standard');
    const options = automationTargetOptions(t.target_id || '', mode);
    const doorOnly = mode === 'door_station' ? '' : 'display:none';
    const target = findDoorTriggerTarget(t);
    const summary = mode === 'door_station'
      ? `Unknown-face webhook → outdoor camera ext ${t.source_extension || '—'} → live audio + H.264 video → ${target?.label || t.target_id || 'select indoor phone'} (ext ${target?.extension || '—'})`
      : `Automation preset → ${target?.label || t.target_id || 'select a saved route'}`;
    return `<div class="automation-row">
      <div class="automation-row-head">
        <span>${mode === 'door_station' ? '📹' : '⚡'}</span>
        <span class="automation-row-title">${esc(t.label || t.id || 'New automation trigger')}</span>
        <span class="section-badge ${mode === 'door_station' ? 'section-badge-on' : 'section-badge-off'}">${mode === 'door_station' ? 'door video' : 'standard'}</span>
        <label class="checkbox-row" style="padding:0">
          <input type="checkbox"${t.enabled !== false ? ' checked' : ''}
                 onchange="automationTriggerField(${i},'enabled',this.checked)">
          <span>Enabled</span>
        </label>
        <button class="btn-icon del" onclick="removeAutomationTrigger(${i})" title="Remove trigger">✕</button>
      </div>
      <div class="door-flow-summary">${esc(summary)}</div>
      <div class="routing-grid" style="margin-top:0">
        <div class="field">
          <label>Trigger ID <span class="hint-tag">used by HA automation</span></label>
          <input value="${esc(t.id || '')}" placeholder="doorbell_call"
                 oninput="automationTriggerField(${i},'id',this.value)">
        </div>
        <div class="field">
          <label>Friendly Name</label>
          <input value="${esc(t.label || '')}" placeholder="Doorbell to Dining Phone"
                 oninput="automationTriggerField(${i},'label',this.value)">
        </div>
        <div class="field">
          <label>Preset Mode</label>
          <select onchange="automationTriggerField(${i},'mode',this.value)">
            <option value="standard"${mode === 'standard' ? ' selected' : ''}>Standard call preset</option>
            <option value="door_station"${mode === 'door_station' ? ' selected' : ''}>Door camera SIP bridge</option>
          </select>
          <div class="field-hint">Door mode calls the outdoor station first, then bridges its live SIP media to the indoor phone.</div>
        </div>
        <div class="field">
          <label>Call Target <span class="hint-tag">saved route</span></label>
          <select onchange="automationTriggerField(${i},'target_id',this.value)">
            <option value="">Select a saved target…</option>
            ${options}
          </select>
          <div class="field-hint">To call a desk phone, create a Routing Target with type SIP desk phone first.</div>
        </div>
        <div class="field">
          <label>Caller ID <span class="hint-tag">optional</span></label>
          <input value="${esc(t.caller_id || '')}" placeholder='"Doorbell" &lt;100&gt;'
                 oninput="automationTriggerField(${i},'caller_id',this.value)">
        </div>
        <div class="field" style="${doorOnly}">
          <label>Outdoor SIP Extension <span class="hint-tag">camera station</span></label>
          <input value="${esc(t.source_extension || '')}" placeholder="1101"
                 oninput="automationTriggerField(${i},'source_extension',this.value)">
          <div class="field-hint">The door station must be registered on this site and configured to auto-answer SIP callback calls.</div>
        </div>
        <div class="field" style="${doorOnly}">
          <label>Door Ring Time <span class="hint-tag">seconds</span></label>
          <input type="number" min="5" max="120" value="${esc(t.timeout || 30)}"
                 onchange="automationTriggerField(${i},'timeout',this.value)">
        </div>
      </div>
    </div>`;
  }).join('');
  renderDoorCameraGuideStatus();
}

function automationTargetOptions(selected, mode = 'standard') {
  return (_targets || []).filter(t => {
    return mode !== 'door_station' || ['sip', 'asterisk'].includes(String(t.type || ''));
  }).map(t => {
    const id = String(t.id || '');
    const detail = [targetTypeLabel(t.type || 'node'), t.extension || t.node_id || '']
      .filter(Boolean).join(' · ');
    return `<option value="${esc(id)}"${id === selected ? ' selected' : ''}>` +
      `${esc(t.label || id)}${detail ? ' — ' + esc(detail) : ''}</option>`;
  }).join('');
}

function addAutomationTrigger() {
  _automationTriggers.push({
    id: '',
    label: '',
    target_id: '',
    caller_id: '',
    mode: 'standard',
    source_extension: '',
    timeout: 30,
    enabled: true,
  });
  markSettingsDirty();
  renderAutomationTriggers();
  document.getElementById('automation-list')?.lastElementChild?.scrollIntoView({
    behavior: 'smooth', block: 'nearest',
  });
}

function removeAutomationTrigger(i) {
  _automationTriggers.splice(i, 1);
  markSettingsDirty();
  renderAutomationTriggers();
  renderAutomationPreview();
}

function automationTriggerField(i, key, value) {
  if (!_automationTriggers[i]) return;
  _automationTriggers[i][key] = value;
  markSettingsDirty();
  if (key === 'mode') renderAutomationTriggers();
  if (key === 'id' || key === 'label' || key === 'mode' || key === 'target_id' || key === 'source_extension') {
    renderAutomationPreview();
    renderDoorCameraGuideStatus();
  }
}

function randomHex(bytes = 24) {
  const values = new Uint8Array(bytes);
  crypto.getRandomValues(values);
  return Array.from(values, b => b.toString(16).padStart(2, '0')).join('');
}

function generateWebhookCredentials() {
  const id = `site_${randomHex(8)}`;
  setVal('automation-webhook-id', id);
  setVal('automation-webhook-secret', randomHex(24));
  setCheck('automation-webhook-enabled', true);
  markSettingsDirty();
  renderAutomationPreview();
}

function renderAutomationPreview() {
  const preview = document.getElementById('automation-webhook-preview');
  if (!preview) return;
  const id = getVal('automation-webhook-id').trim();
  const secret = getVal('automation-webhook-secret').trim();
  const trigger = _automationTriggers.find(t =>
    String(t.mode || '') === 'door_station' && String(t.id || '').trim()
  ) || _automationTriggers.find(t => String(t.id || '').trim());
  if (!getCheck('automation-webhook-enabled') || !id) {
    preview.innerHTML = '<div class="field-hint" style="margin-top:10px">Generate credentials to enable an external webhook.</div>';
    return;
  }
  const port = parseInt(_loadedSettings.local_api_port) || 8799;
  const path = `http://${location.hostname}:${port}/api/automation/webhook/${encodeURIComponent(id)}`;
  const triggerId = String(trigger?.id || 'doorbell_call').trim();
  preview.innerHTML = `
    <div class="field-hint" style="margin-top:12px">Direct addon webhook URL. Use the HAOS LAN hostname or IP if this browser is connected through a proxy.</div>
    <div class="code-box">${esc(path)}</div>
    <div class="field-hint" style="margin-top:10px">Face-recognition mismatch action: POST JSON with the private secret header</div>
    <div class="code-box">curl -X POST '${esc(path)}' \\
  -H 'Content-Type: application/json' \\
  -H 'X-Simson-Webhook-Secret: ${esc(secret || 'YOUR_SECRET')}' \\
  -d '{"trigger_id":"${esc(triggerId)}"}'</div>
    <div class="field-hint" style="margin-top:10px">Home Assistant automation action</div>
    <div class="code-box">action:
  - service: simson.run_trigger
    data:
      trigger_id: ${esc(triggerId)}</div>`;
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function switchTab(name, updateHash = true) {
  _currentTab = name;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const activeTab = document.querySelector(`.tab[data-tab="${name}"]`);
  if (activeTab) activeTab.classList.add('active');
  ['overview', 'settings'].forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.toggle('hidden', t !== name);
  });
  if (updateHash) location.hash = name === 'settings' ? 'settings' : '';
}

// ─── Setup wizard ─────────────────────────────────────────────────────────────
function renderSetupWizard() {
  let tokenSection = '';
  let stepOffset = 0;
  if (HAS_ADMIN_TOKEN) {
    tokenSection = `<div class="alert alert-success" style="margin-bottom:16px">
      ✓ Admin token found in addon configuration — no need to enter it here.
    </div>`;
  } else {
    stepOffset = 1;
    tokenSection = `<div id="setup-token-field">
      <div class="field" style="margin-bottom:16px">
        <label>Admin Token
          <span class="hint-tag">— paste here if not set in addon Configuration tab</span>
        </label>
        <input type="password" id="f-token" placeholder="Paste your VPS admin token"
               autocomplete="off">
      </div>
    </div>`;
  }
  document.getElementById('setup-token-section').innerHTML = tokenSection;

  const steps = [
    HAS_ADMIN_TOKEN ? null :
      `Set your <b>VPS admin token</b> in the addon's <b>Configuration</b> tab,
       or paste it in the field above.`,
    `Choose a <b>node label</b> below (e.g. "Living Room"). This is the display name for this node.`,
    `<b>Adding a second HA instance?</b> Paste the <b>Account ID</b> from your first node
     so both share the same account. Leave empty for a brand-new setup.`,
  ].filter(Boolean);

  document.getElementById('setup-steps').innerHTML = steps.map((txt, i) => `
    <div class="step-row">
      <div class="step-num">${i + 1}</div>
      <div class="step-text">${txt}</div>
    </div>
  `).join('');
}

async function doSetup() {
  const btn = document.getElementById('btn-setup');
  const result = document.getElementById('setup-result');
  const token = HAS_ADMIN_TOKEN ? '' : (getVal('f-token') || '');
  if (!HAS_ADMIN_TOKEN && !token) {
    result.innerHTML = '<div class="alert alert-error">Admin token is required.</div>';
    return;
  }
  const label = getVal('f-label').trim();
  if (!label) {
    result.innerHTML = '<div class="alert alert-error">Node label is required.</div>';
    return;
  }
  const account = getVal('f-account').trim();
  btn.disabled = true;
  btn.textContent = 'Setting up…';
  result.innerHTML = '<div class="alert alert-info">Creating account and node on VPS…</div>';
  try {
    const resp = await fetch('api/provision', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({admin_token: token, node_label: label, account_id: account}),
    });
    const data = await resp.json();
    if (resp.ok) {
      result.innerHTML =
        '<div class="alert alert-success">✓ Setup complete!<br>' +
        '<b>Account:</b> ' + esc(data.account_id) + '<br>' +
        '<b>Node:</b> ' + esc(data.node_id) + '<br>' +
        '<small>Credentials saved. Reloading in 3 seconds…</small></div>';
      setTimeout(() => location.reload(), 3000);
    } else {
      result.innerHTML =
        '<div class="alert alert-error">✗ ' + esc(data.error || 'Setup failed') + '</div>';
      btn.disabled = false;
      btn.textContent = 'Set Up Node';
    }
  } catch (e) {
    result.innerHTML =
      '<div class="alert alert-error">✗ Network error: ' + esc(e.message) + '</div>';
    btn.disabled = false;
    btn.textContent = 'Set Up Node';
  }
}

async function doReset() {
  if (!confirm('This will clear saved credentials and show the setup wizard. Continue?')) return;
  const btn = document.getElementById('btn-reset');
  btn.disabled = true;
  btn.textContent = 'Resetting…';
  try {
    await fetch('api/reset', {method: 'POST'});
    document.getElementById('reset-result').innerHTML =
      '<div class="alert alert-success">Reset complete. Reloading…</div>';
    setTimeout(() => location.reload(), 1500);
  } catch (e) {
    document.getElementById('reset-result').innerHTML =
      '<div class="alert alert-error">Reset failed: ' + esc(e.message) + '</div>';
    btn.disabled = false;
    btn.textContent = 'Reset Setup';
  }
}

async function copyAccountId() {
  const val = document.getElementById('copyable-account')?.textContent || '';
  if (!val || val === '—') return;
  try {
    await navigator.clipboard.writeText(val);
    const btn = document.getElementById('btn-copy-account');
    if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 2000); }
  } catch (_) {}
}

// ─── DOM helpers ─────────────────────────────────────────────────────────────
function setVal(id, v) { const el = document.getElementById(id); if (el) el.value = v ?? ''; }
function getVal(id) { return document.getElementById(id)?.value ?? ''; }
function setCheck(id, v) { const el = document.getElementById(id); if (el) el.checked = !!v; }
function getCheck(id) { return !!document.getElementById(id)?.checked; }
function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
function setDot(id, ok) {
  const el = document.getElementById(id);
  if (el) el.className = 'dot ' + (ok ? 'dot-ok' : 'dot-err');
}
function setSaveStatus(msg, type) {
  const el = document.getElementById('save-status-text');
  if (!el) return;
  el.textContent = msg;
  el.className = type === 'ok' ? 'save-status-ok' : type === 'err' ? 'save-status-err' : '';
}
function infoRow(label, value) {
  return `<div class="info-row"><span class="info-label">${esc(label)}</span>` +
         `<span class="info-value">${typeof value === 'string' ? esc(value) : value}</span></div>`;
}
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function jsString(s) {
  return JSON.stringify(String(s ?? ''));
}
</script>
</body>
</html>"""
