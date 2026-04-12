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

      <!-- Asterisk ------------------------------------------------ -->
      <div class="section" id="section-asterisk">
        <div class="section-head">
          <div class="section-head-left">
            <h3>☎ Asterisk Integration</h3>
            <span id="ast-section-badge" class="section-badge section-badge-off">Off</span>
          </div>
          <label class="switch" title="Enable Asterisk AMI">
            <input type="checkbox" id="s-ast-enabled" onchange="onAstToggle()">
            <span class="slider"></span>
          </label>
        </div>
        <div class="section-body collapsed" id="ast-body">
          <div style="height:14px"></div>
          <div class="field-row">
            <div class="field">
              <label>Host</label>
              <input type="text" id="s-ast-host" placeholder="127.0.0.1">
            </div>
            <div class="field" style="max-width:130px">
              <label>AMI Port</label>
              <input type="number" id="s-ast-port" placeholder="5038" min="1" max="65535">
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>AMI Username</label>
              <input type="text" id="s-ast-user" placeholder="simson" autocomplete="off">
            </div>
            <div class="field">
              <label>AMI Secret</label>
              <input type="password" id="s-ast-secret" autocomplete="new-password">
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>Dialplan Context</label>
              <input type="text" id="s-ast-context" placeholder="from-simson">
            </div>
            <div class="field" style="max-width:160px">
              <label>Extension Prefix</label>
              <input type="text" id="s-ast-prefix" placeholder="9">
            </div>
          </div>
          <div class="checkbox-row">
            <input type="checkbox" id="s-ast-autoconf">
            <label for="s-ast-autoconf">Auto-configure Asterisk on startup
              <span style="color:var(--text3);font-size:11px">(writes conf files, reloads modules)</span>
            </label>
          </div>
        </div>
      </div>

      <!-- TURN ---------------------------------------------------- -->
      <div class="section" id="section-turn">
        <div class="section-head">
          <div class="section-head-left">
            <h3>🔄 TURN Relay</h3>
            <span id="turn-section-badge" class="section-badge section-badge-off">Off</span>
          </div>
          <label class="switch" title="Enable TURN relay">
            <input type="checkbox" id="s-turn-enabled" onchange="onTurnToggle()">
            <span class="slider"></span>
          </label>
        </div>
        <div class="section-body collapsed" id="turn-body">
          <div style="height:14px"></div>
          <p class="field-hint" style="margin-bottom:12px">
            Improves audio reliability behind symmetric NAT. Requires a TURN server
            such as coturn.
          </p>
          <div class="field-row" style="flex-direction:column">
            <div class="field" style="width:100%">
              <label>TURN URL</label>
              <input type="text" id="s-turn-url"
                     placeholder="turn:your-turn-server.example.com:3478">
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>Username</label>
              <input type="text" id="s-turn-user" placeholder="simson" autocomplete="off">
            </div>
            <div class="field">
              <label>Credential</label>
              <input type="password" id="s-turn-cred" autocomplete="new-password">
            </div>
          </div>
        </div>
      </div>

      <!-- SIP-over-WebSocket -------------------------------------- -->
      <div class="section" id="section-sip">
        <div class="section-head">
          <div class="section-head-left">
            <h3>🎤 SIP-over-WebSocket</h3>
            <span id="sip-section-badge" class="section-badge section-badge-off">Off</span>
          </div>
          <label class="switch" title="Enable SIP-over-WebSocket">
            <input type="checkbox" id="s-sip-enabled" onchange="onSipToggle()">
            <span class="slider"></span>
          </label>
        </div>
        <div class="section-body collapsed" id="sip-body">
          <div style="height:14px"></div>
          <p class="field-hint" style="margin-bottom:12px">
            Browser-based SIP audio via Asterisk ConfBridge. Requires
            Asterisk &gt;= 16 with the PJSIP WebSocket transport enabled.
          </p>
          <div class="field-row" style="flex-direction:column">
            <div class="field" style="width:100%">
              <label>WebSocket URL</label>
              <input type="text" id="s-sip-url"
                     placeholder="ws://asterisk-host:8088/ws">
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>SIP Username</label>
              <input type="text" id="s-sip-user" placeholder="webrtc-pool" autocomplete="off">
            </div>
            <div class="field">
              <label>SIP Password</label>
              <input type="password" id="s-sip-pass" autocomplete="new-password">
            </div>
          </div>
          <div class="field-row" style="flex-direction:column">
            <div class="field" style="width:100%">
              <label>SIP Domain <span class="hint-tag">— leave empty to use server hostname</span></label>
              <input type="text" id="s-sip-domain" placeholder="asterisk-host.example.com">
            </div>
          </div>
        </div>
      </div>

      <!-- Call Targets -------------------------------------------- -->
      <div class="section">
        <div class="section-head" style="cursor:default">
          <div class="section-head-left">
            <h3>📋 Call Targets</h3>
            <span id="targets-count-badge" class="section-badge section-badge-off">0</span>
          </div>
          <button class="btn-sm" onclick="addTarget()">+ Add Target</button>
        </div>
        <div class="section-body" id="targets-body" style="padding-bottom:4px">
          <div id="targets-list"></div>
          <div id="targets-empty" class="targets-empty">
            No targets configured. Click <b>+ Add Target</b> to add one.
          </div>
        </div>
      </div>

      <!-- Port ---------------------------------------------------- -->
      <div class="section">
        <div class="section-head"><h3 class="section-head-left">🔌 Local API Port</h3></div>
        <div class="section-body">
          <div style="height:14px"></div>
          <div class="field-row">
            <div class="field" style="max-width:160px">
              <label>Port <span class="hint-tag">default: 8799</span></label>
              <input type="number" id="s-port" min="1024" max="65535" placeholder="8799">
            </div>
            <div class="field" style="justify-content:flex-end;padding-top:20px">
              <span class="field-hint">
                Changing the port requires an addon restart.<br>
                Must match the ingress port in config.json.
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Errors + Save bar --------------------------------------- -->
      <div id="save-errors-box" class="save-errors hidden"></div>
      <div id="save-restart-note" class="save-restart-note hidden">
        ⚠ Some changes (Asterisk connection, API port) will take full effect after restarting the addon.
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
  await Promise.all([pollStatus(), loadSettings()]);
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
  const ast = s.asterisk || {};
  setCheck('s-ast-enabled', ast.enabled);
  setVal('s-ast-host', ast.host ?? '127.0.0.1');
  setVal('s-ast-port', ast.ami_port ?? 5038);
  setVal('s-ast-user', ast.ami_user ?? 'simson');
  setVal('s-ast-secret', ast.ami_secret ?? '');
  setVal('s-ast-context', ast.context ?? 'from-simson');
  setVal('s-ast-prefix', ast.extension_prefix ?? '9');
  setCheck('s-ast-autoconf', ast.auto_configure);
  setSectionEnabled('ast-body', 'ast-section-badge', ast.enabled);

  const wrtc = s.webrtc || {};
  setCheck('s-turn-enabled', wrtc.turn_enabled);
  setVal('s-turn-url', wrtc.turn_url ?? '');
  setVal('s-turn-user', wrtc.turn_username ?? 'simson');
  setVal('s-turn-cred', wrtc.turn_credential ?? '');
  setSectionEnabled('turn-body', 'turn-section-badge', wrtc.turn_enabled);

  setCheck('s-sip-enabled', wrtc.sip_enabled);
  setVal('s-sip-url', wrtc.sip_ws_url ?? '');
  setVal('s-sip-user', wrtc.sip_username ?? 'webrtc-pool');
  setVal('s-sip-pass', wrtc.sip_password ?? '');
  setVal('s-sip-domain', wrtc.sip_domain ?? '');
  setSectionEnabled('sip-body', 'sip-section-badge', wrtc.sip_enabled);

  setVal('s-port', s.local_api_port ?? 8799);

  _targets = JSON.parse(JSON.stringify(s.call_targets || []));
  renderTargets();
  _settingsDirty = false;
  setSaveStatus('', '');
}

function collectSettings() {
  return {
    local_api_port: parseInt(getVal('s-port')) || 8799,
    asterisk: {
      enabled: getCheck('s-ast-enabled'),
      host: getVal('s-ast-host') || '127.0.0.1',
      ami_port: parseInt(getVal('s-ast-port')) || 5038,
      ami_user: getVal('s-ast-user') || 'simson',
      ami_secret: getVal('s-ast-secret'),
      context: getVal('s-ast-context') || 'from-simson',
      extension_prefix: getVal('s-ast-prefix') || '9',
      auto_configure: getCheck('s-ast-autoconf'),
    },
    webrtc: {
      turn_enabled: getCheck('s-turn-enabled'),
      turn_url: getVal('s-turn-url'),
      turn_username: getVal('s-turn-user') || 'simson',
      turn_credential: getVal('s-turn-cred'),
      sip_enabled: getCheck('s-sip-enabled'),
      sip_ws_url: getVal('s-sip-url'),
      sip_username: getVal('s-sip-user') || 'webrtc-pool',
      sip_password: getVal('s-sip-pass'),
      sip_domain: getVal('s-sip-domain'),
    },
    call_targets: collectTargets(),
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

// ─── Section toggles ─────────────────────────────────────────────────────────
function onAstToggle() {
  setSectionEnabled('ast-body', 'ast-section-badge', getCheck('s-ast-enabled'));
}
function onTurnToggle() {
  setSectionEnabled('turn-body', 'turn-section-badge', getCheck('s-turn-enabled'));
}
function onSipToggle() {
  setSectionEnabled('sip-body', 'sip-section-badge', getCheck('s-sip-enabled'));
}
function setSectionEnabled(bodyId, badgeId, on) {
  const body = document.getElementById(bodyId);
  const badge = document.getElementById(badgeId);
  if (body) body.classList.toggle('collapsed', !on);
  if (badge) {
    badge.textContent = on ? 'On' : 'Off';
    badge.className = 'section-badge ' + (on ? 'section-badge-on' : 'section-badge-off');
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
    return `<div class="target-card" id="tc-${i}">
      <div class="target-head" onclick="toggleTarget(${i})">
        <span class="target-emoji">${esc(emoji)}</span>
        <span class="target-name">${esc(t.label || t.id || 'Target ' + (i+1))}</span>
        <span class="target-type-pill">${esc(t.type || 'node')}</span>
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
  const types = ['node','device','asterisk','queue'];
  const typeOpts = types.map(v =>
    `<option value="${v}"${t.type===v?' selected':''}>${v}</option>`).join('');
  const isAst = t.type === 'asterisk';
  return `<div class="target-form">
    <div class="field-row">
      <div class="field" style="max-width:140px">
        <label>Type</label>
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
        <label>Node ID <span class="hint-tag">for type=node/device</span></label>
        <input type="text" id="t${i}-node" value="${esc(t.node_id||'')}"
               placeholder="ha_kitchen" oninput="targetField(${i},'node_id',this.value)">
      </div>
    </div>
    <div class="field-row" id="t${i}-ast-row"${!isAst?' style="display:none"':''}>
      <div class="field">
        <label>Asterisk Extension</label>
        <input type="text" id="t${i}-ext" value="${esc(t.extension||'')}"
               placeholder="101" oninput="targetField(${i},'extension',this.value)">
      </div>
      <div class="field">
        <label>Context</label>
        <input type="text" id="t${i}-ctx" value="${esc(t.context||'')}"
               placeholder="from-simson" oninput="targetField(${i},'context',this.value)">
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
    <div style="display:flex;justify-content:flex-end;margin-top:6px">
      <button type="button" class="btn-secondary btn"
              style="font-size:12px;padding:7px 14px"
              onclick="toggleTarget(${i})">Done</button>
    </div>
  </div>`;
}

function onTargetTypeChange(i, value) {
  _targets[i].type = value;
  const nodeRow = document.getElementById(`t${i}-node-row`);
  const astRow = document.getElementById(`t${i}-ast-row`);
  if (nodeRow) nodeRow.style.display = value === 'asterisk' ? 'none' : '';
  if (astRow) astRow.style.display = value === 'asterisk' ? '' : 'none';
  // Update pill without full re-render
  const pill = document.querySelector(`#tc-${i} .target-type-pill`);
  if (pill) pill.textContent = value;
}
function targetField(i, key, value) { if (_targets[i]) _targets[i][key] = value; }

function collectTargetValues(i) {
  // Flush any in-flight input values back to _targets[i] before re-render
  if (!_targets[i]) return;
  const fields = {
    id:`t${i}-id`, label:`t${i}-label`, icon:`t${i}-icon`,
    node_id:`t${i}-node`, extension:`t${i}-ext`, context:`t${i}-ctx`,
    caller_id:`t${i}-cid`,
  };
  for (const [key, elId] of Object.entries(fields)) {
    const el = document.getElementById(elId);
    if (el) _targets[i][key] = el.value;
  }
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
    context: '', trunk: '', caller_id: '', timeout: 30,
    fallback_targets: [], icon: '', _open: true,
  });
  renderTargets();
  // Scroll to new target
  const last = document.getElementById('targets-list')?.lastElementChild;
  if (last) last.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function removeTarget(i) {
  _targets.splice(i, 1);
  renderTargets();
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
</script>
</body>
</html>"""
