/* =========================================================
   Simson Dashboard — Core Logic (Preserved)
   UI Generation & Event Handling (Rewritten for Premium UX)
   ========================================================= */

const boot = window.__SIMSON__ || {};

const state = {
  page: "overview",
  status: null,
  settings: null,
  nodes: [],
  sip: [],
  routing: null,
  dirty: false,
  loaded: false,
  selectedDoorTriggerId: "",
};

const defaults = {
  local_api_port: 8799,
  routing: {
    strategy: "priority",
    ring_seconds: 25,
    max_attempts: 4,
    skip_unavailable: true,
    final_fallback_target: "",
    gateway_inbound_mode: "haos_then_fallback",
    gateway_direct_target: "",
    default_gateway_trunk: "",
  },
  availability: { mode: "available", reason: "" },
  route_overrides: {},
  call_targets: [],
  automation: {
    webhook_enabled: false,
    webhook_id: "",
    webhook_secret: "",
    cooldown_seconds: 90,
    block_while_call_active: true,
    persistent_notifications: true,
    notify_services: "",
    dashboard_path: "/lovelace/default_view",
    triggers: [],
  },
};

const pages = [
  ["overview", "Overview", "Live health"],
  ["routing", "Routing", "Targets and fallback"],
  ["sip", "SIP Phones", "Extensions and video"],
  ["automation", "Door Automation", "Webhooks and cooldowns"],
  ["advanced", "Advanced", "Raw settings"],
];

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#39;",
}[ch]));

function deepMerge(base, override) {
  const out = structuredClone(base);
  Object.entries(override || {}).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value) && out[key] && typeof out[key] === "object" && !Array.isArray(out[key])) {
      out[key] = deepMerge(out[key], value);
    } else {
      out[key] = structuredClone(value);
    }
  });
  return out;
}

function getSettings() {
  state.settings = deepMerge(defaults, state.settings || {});
  state.settings.automation = deepMerge(defaults.automation, state.settings.automation || {});
  state.settings.routing = deepMerge(defaults.routing, state.settings.routing || {});
  state.settings.availability = deepMerge(defaults.availability, state.settings.availability || {});
  state.settings.call_targets = Array.isArray(state.settings.call_targets) ? state.settings.call_targets : [];
  state.settings.automation.triggers = Array.isArray(state.settings.automation.triggers) ? state.settings.automation.triggers : [];
  return state.settings;
}

function setDirty(message = "Unsaved changes") {
  state.dirty = true;
  setSaveState(message);
}

function setSaveState(text, tone = "") {
  const el = $("save-state");
  if (!el) return;
  el.textContent = text || "Everything saved";
  el.style.color = tone === "bad" ? "var(--danger)" : tone === "ok" ? "var(--success)" : "var(--text-secondary)";
}

function toast(text) {
  const el = $("toast");
  if (!el) return;
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2800);
}

function externalBaseUrl() {
  const settings = getSettings();
  const port = String(settings.local_api_port || defaults.local_api_port || 8799);
  const host = window.location.hostname || "homeassistant.local";
  const direct = window.location.port === port;
  const protocol = direct ? window.location.protocol : "http:";
  return `${protocol}//${host}:${port}`;
}

function deviceCallbackPath(triggerId = "TRIGGER_ID") {
  const auto = getSettings().automation;
  return `/api/automation/device/${auto.webhook_id || "WEBHOOK_ID"}/${triggerId}`;
}

function deviceCallbackUrl(triggerId = "TRIGGER_ID") {
  return `${externalBaseUrl()}${deviceCallbackPath(triggerId)}`;
}

function stableDoorCallbackPath() {
  const auto = getSettings().automation;
  return `/api/automation/webhook/${auto.webhook_id || "WEBHOOK_ID"}`;
}

function stableDoorCallbackUrl() {
  return `${externalBaseUrl()}${stableDoorCallbackPath()}`;
}

function randomHex(bytes = 24) {
  const values = new Uint8Array(bytes);
  if (window.crypto && typeof window.crypto.getRandomValues === "function") {
    window.crypto.getRandomValues(values);
  } else {
    for (let i = 0; i < values.length; i += 1) {
      values[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(values, (b) => b.toString(16).padStart(2, "0")).join("");
}

function syncDoorFlowForm() {
  const selected = $("door-trigger-select")?.value || "";
  const selectedDoor = selected ? (getSettings().automation.triggers || []).find((t) => t.id === selected) : null;
  const currentSource = $("door-source")?.value || "";
  const previousId = state.selectedDoorTriggerId;

  if (selectedDoor && selectedDoor.source_extension && selectedDoor.source_extension !== currentSource) {
    state.selectedDoorTriggerId = "";
  } else {
    state.selectedDoorTriggerId = selected;
  }

  // Only re-render if the selection actually changed — prevents choppy DOM thrash
  if (state.selectedDoorTriggerId !== previousId) {
    renderAutomation();
  }
}

function effectiveDoorCooldown(value) {
  const parsed = Number(value);
  const safe = Number.isFinite(parsed) && parsed > 0 ? parsed : 90;
  return Math.max(20, Math.min(3600, Math.round(safe)));
}

function sourceSipLabel(extension) {
  const ext = String(extension || "").trim();
  if (!ext) return "No outdoor source selected";
  const ep = state.sip.map(normalizeSipEndpoint).find((item) => item && String(item.extension) === ext);
  const label = ep?.description || ep?.username || ext;
  return `${label} (${ext})`;
}

function targetListText(ids) {
  const list = Array.isArray(ids) ? ids.filter(Boolean) : [];
  if (!list.length) return "No destinations selected";
  return list.map(targetDisplayName).join(" + ");
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text || res.statusText };
  }
  if (!res.ok) {
    const detail = Array.isArray(data.errors) && data.errors.length
      ? data.errors.join("; ")
      : data.error || data.message || `Request failed: ${res.status}`;
    const err = new Error(detail);
    err.data = data;
    err.status = res.status;
    throw err;
  }
  return data;
}

/* =========================================================
   Shell & Layout
   ========================================================= */

function shell() {
  document.body.innerHTML = `
    <div class="shell">
      <div class="app-frame">
        <aside class="sidebar">
          <div class="brand">
            <div class="brand-mark">☎</div>
            <div>
              <div class="brand-title">Simson</div>
              <div class="brand-sub">Site call control · v${esc(boot.version)}</div>
            </div>
          </div>
          <nav class="nav" id="nav"></nav>
          <div class="sidebar-footer">
            <div class="mini-card">
              <div class="mini-label">Node</div>
              <div class="mini-value" id="side-node">loading…</div>
            </div>
            <div class="mini-card">
              <div class="mini-label">Connection</div>
              <div class="mini-value" id="side-conn">checking…</div>
            </div>
          </div>
        </aside>
        <main class="workspace">
          <header class="topbar">
            <div>
              <div class="kicker" id="page-kicker">Live health</div>
              <h1 class="page-title" id="page-title">Pulse</h1>
            </div>
            <div class="top-actions">
              <button class="btn secondary" data-action="refresh">Refresh</button>
              <button class="btn" data-action="save">Save Changes</button>
            </div>
          </header>
          <section class="content" id="content"></section>
        </main>
      </div>
      <div class="save-bar">
        <div class="save-state" id="save-state">Loading settings…</div>
        <button class="btn secondary" data-action="refresh">Reload</button>
        <button class="btn" data-action="save">Save Settings</button>
      </div>
      <div class="toast" id="toast"></div>
    </div>
  `;
  renderNav();
  document.body.addEventListener("click", onClick);
  document.body.addEventListener("input", onInput);
  document.body.addEventListener("change", onInput);
}

function renderNav() {
  $("nav").innerHTML = pages.map(([id, title, sub]) => `
    <button class="${state.page === id ? "active" : ""}" data-page="${id}">
      <span>${icon(id)}</span>
      <span><b>${title}</b><br><small>${sub}</small></span>
    </button>
  `).join("");
}

function icon(id) {
  return {
    overview: "◉",
    routing: "⇄",
    sip: "☏",
    automation: "⚡",
    advanced: "⚙",
  }[id] || "•";
}

function render() {
  renderNav();
  const page = pages.find(([id]) => id === state.page) || pages[0];
  $("page-title").textContent = page[1];
  $("page-kicker").textContent = page[2];
  $("side-node").textContent = state.status?.node_id || "not provisioned";
  $("side-conn").innerHTML = state.status?.vps_connected
    ? '<span style="color:var(--success)">Online</span>'
    : '<span style="color:var(--danger)">Offline</span>';

  if (!boot.provisioned) {
    renderSetup();
    return;
  }
  const renderer = {
    overview: renderOverview,
    routing: renderRouting,
    sip: renderSip,
    automation: renderAutomation,
    advanced: renderAdvanced,
  }[state.page] || renderOverview;
  renderer();
}

/* =========================================================
   Data Helpers
   ========================================================= */

function normalizeSipEndpoint(ep) {
  if (!ep || typeof ep !== "object") return null;
  return {
    id: ep.id ?? ep.ID ?? "",
    account_id: ep.account_id ?? ep.AccountID ?? "",
    extension: ep.extension ?? ep.Extension ?? "",
    username: ep.username ?? ep.Username ?? "",
    description: ep.description ?? ep.Description ?? "",
    route_to: ep.route_to ?? ep.RouteTo ?? "",
    default_outbound: Boolean(ep.default_outbound ?? ep.DefaultOutbound ?? false),
    video_enabled: Boolean(ep.video_enabled ?? ep.VideoEnabled ?? ep.video ?? false),
    auto_answer: Boolean(ep.auto_answer ?? ep.AutoAnswer ?? false),
    auto_answer_callers: ep.auto_answer_callers ?? ep.AutoAnswerCallers ?? "",
    auto_speaker: Boolean(ep.auto_speaker ?? ep.AutoSpeaker ?? false),
    auto_speaker_callers: ep.auto_speaker_callers ?? ep.AutoSpeakerCallers ?? "",
    callback_bridge: Boolean(ep.callback_bridge ?? ep.CallbackBridge ?? false),
    callback_bridge_callers: ep.callback_bridge_callers ?? ep.CallbackBridgeCallers ?? "",
    callback_caller_auto_answer: Boolean(ep.callback_caller_auto_answer ?? ep.CallbackCallerAutoAnswer ?? false),
    callback_caller_auto_speaker: Boolean(ep.callback_caller_auto_speaker ?? ep.CallbackCallerAutoSpeaker ?? false),
    enabled: ep.enabled ?? ep.Enabled ?? true,
    registered: Boolean(ep.registered ?? ep.Registered ?? false),
    contact_status: ep.contact_status ?? ep.ContactStatus ?? "",
    contact_uri: ep.contact_uri ?? ep.ContactURI ?? "",
    contact_address: ep.contact_address ?? ep.ContactAddress ?? "",
    contact_latency_ms: ep.contact_latency_ms ?? ep.ContactLatencyMS ?? "",
  };
}

function gatewayEndpoints() {
  return state.sip.map(normalizeSipEndpoint).filter((ep) => ep && isGatewaySip(ep));
}

function defaultGatewayTrunk() {
  const settings = getSettings();
  const configured = String(settings.routing.default_gateway_trunk || "").trim();
  if (configured) return configured;
  const marked = gatewayEndpoints().find((ep) => ep.default_outbound);
  if (marked?.extension) return marked.extension;
  return gatewayEndpoints()[0]?.extension || "";
}

function targetSelectOptions(selected = "", includeBlank = true) {
  const values = [];
  const add = (value, label) => {
    const text = String(value || "").trim();
    if (!text || values.some((item) => item.value === text)) return;
    values.push({ value: text, label: label || text });
  };
  if (includeBlank) values.push({ value: "", label: "None" });
  getSettings().call_targets.forEach((target) => add(target.id, `${target.label || target.id} (${target.type || "target"})`));
  state.sip.map(normalizeSipEndpoint).filter(Boolean).forEach((ep) => add(ep.extension, `${ep.extension} · ${ep.description || ep.username || "SIP"}`));
  state.nodes.forEach((node) => add(node.id, `${node.label || node.id} · HAOS node`));
  return values.map((item) => option(item.value, item.label, selected)).join("");
}

function gatewaySelectOptions(selected = "") {
  const gateways = gatewayEndpoints();
  const current = String(selected || "").trim();
  const rows = gateways.length ? gateways : state.sip.map(normalizeSipEndpoint).filter(Boolean);
  const opts = [`<option value="">Auto-select best registered gateway</option>`];
  rows.forEach((ep) => {
    const label = `${ep.extension} · ${ep.description || ep.username || "gateway"}${ep.default_outbound ? " · current default" : ""}`;
    opts.push(option(ep.extension, label, current));
  });
  return opts.join("");
}

/* =========================================================
   Setup
   ========================================================= */

function renderSetup() {
  $("content").innerHTML = `
    <div class="grid cols-2">
      <div class="card glow">
        <div class="card-title">Provision this HAOS site</div>
        <div class="card-sub">Leave Account ID blank for a new independent site. Paste an existing Account ID only when this HAOS must join that same site.</div>
      </div>
      <form class="card" id="setup-form">
        <div class="form-grid">
          <div class="field full">
            <label>Admin token</label>
            <input name="admin_token" type="password" placeholder="VPS admin token">
          </div>
          <div class="field">
            <label>Site / node label</label>
            <input name="node_label" placeholder="Front office">
          </div>
          <div class="field">
            <label>Existing Account ID optional</label>
            <input name="account_id" placeholder="blank = new independent site">
          </div>
        </div>
        <div style="margin-top:16px"><button class="btn" data-action="provision">Provision</button></div>
      </form>
    </div>
  `;
}

/* =========================================================
   Overview
   ========================================================= */

function renderOverview() {
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
            <div class="row-title">${esc(active.caller_name || active.caller_id || active.call_id)}</div>
            <div class="row-sub">${esc(active.direction || "call")} · ${esc(active.call_type || "")}</div>
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

function stat(title, value, sub, tone) {
  return `
    <div class="stat">
      <span>${esc(title)}</span>
      <b>${esc(value)}</b>
      <span class="pill ${tone === "bad" ? "bad" : tone === "warn" ? "warn" : "ok"}">${esc(sub)}</span>
    </div>
  `;
}

/* =========================================================
   Routing
   ========================================================= */

function renderRouting() {
  const settings = getSettings();
  const defaultTrunk = defaultGatewayTrunk();
  const inboundMode = settings.routing.gateway_inbound_mode || "haos_then_fallback";
  const directTarget = settings.routing.gateway_direct_target || "";
  $("content").innerHTML = `
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
              ${gatewaySelectOptions(settings.routing.default_gateway_trunk || "")}
            </select>
            <div class="hint">SIP phones can dial outside numbers directly. Use a gateway prefix only when forcing a specific line.</div>
          </div>
          <div class="field">
            <label>Inbound gateway behavior</label>
            <select data-path="routing.gateway_inbound_mode">
              ${option("haos_then_fallback", "Ring HAOS first, then fallback", inboundMode)}
              ${option("direct_target", "Send directly to selected target", inboundMode)}
            </select>
            <div class="hint">Use direct mode for landline/GSM gateways that should always ring a SIP phone or route immediately.</div>
          </div>
          <div class="field">
            <label>Direct inbound target</label>
            <select data-path="routing.gateway_direct_target">
              ${targetSelectOptions(directTarget, true)}
            </select>
            <div class="hint">Only used when inbound behavior is direct. Pick a SIP phone, route target, or HAOS node.</div>
          </div>
          <div class="field">
            <label>Strategy</label>
            <select data-path="routing.strategy">
              ${option("priority", "Try saved fallback order", settings.routing.strategy)}
              ${option("round_robin", "Round robin", settings.routing.strategy)}
            </select>
          </div>
          <div class="field">
            <label>Ring HAOS before fallback</label>
            <input type="number" min="5" max="300" data-path="routing.ring_seconds" value="${esc(settings.routing.ring_seconds)}">
            <div class="hint">Gateway calls ring this dashboard first for this many seconds.</div>
          </div>
          <div class="field">
            <label>Max attempts</label>
            <input type="number" min="1" max="20" data-path="routing.max_attempts" value="${esc(settings.routing.max_attempts)}">
          </div>
          <div class="field">
            <label>Gateway fallback target</label>
            <input data-path="routing.final_fallback_target" value="${esc(settings.routing.final_fallback_target)}" placeholder="1025 or security_desk">
            <div class="hint">Only this explicit target, or a gateway route's fallback list, receives missed gateway calls.</div>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="routing.skip_unavailable" ${settings.routing.skip_unavailable ? "checked" : ""}> Skip busy/offline targets</label>
          </div>
        </div>
        <div class="flow-preview route-preview" style="margin-top:14px;">
          <strong>Gateway call path</strong>
          <span>PSTN/GSM gateway call</span>
          <b>→</b>
          ${inboundMode === "direct_target"
            ? `<span>direct transfer</span><b>→</b><span>${esc(directTarget || "no target selected")}</span>`
            : `<span>HAOS card for ${esc(settings.routing.ring_seconds)}s</span><b>→</b><span>${esc(settings.routing.final_fallback_target || "no automatic SIP fallback")}</span>`}
        </div>
        <div class="flow-preview route-preview" style="margin-top:10px;">
          <strong>Outside dial path</strong>
          <span>SIP phone dials number</span>
          <b>→</b>
          <span>${esc(defaultTrunk || "auto gateway")}</span>
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
            </select>
          </div>
          <div class="field">
            <label>Name</label>
            <input id="quick-label" placeholder="Dining phone">
          </div>
          <div class="field">
            <label>Destination</label>
            <input id="quick-value" list="node-list" placeholder="1025, office2, or outside number">
          </div>
          <div class="field">
            <label>Fallback IDs for this route</label>
            <input id="quick-fallbacks" placeholder="1025, security, office2">
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn orange" data-action="add-route">Add Route</button></div>
      </div>
    </div>
    <datalist id="node-list">${state.nodes.map((n) => `<option value="${esc(n.id)}">${esc(n.label || n.id)}</option>`).join("")}</datalist>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Routing targets</div>
          <div class="card-sub">Each row shows exactly what it is: HAOS node, SIP extension, or outbound gateway route.</div>
        </div>
      </div>
      <div class="list" id="target-list">
        ${settings.call_targets.map(targetRow).join("") || `<div class="empty">No route targets yet.</div>`}
      </div>
    </div>
  `;
}

function targetRowReadonly(t) {
  return `
    <div class="row" style="padding:10px 14px;">
      <div class="row-main">
        <div>
          <div class="row-title">${esc(t.label || t.id)}</div>
          <div class="row-sub">${esc(t.type)} · ${esc(t.node_id || t.extension || t.trunk || "site")}</div>
        </div>
        <span class="pill">${esc(t.id)}</span>
      </div>
    </div>
  `;
}

function targetRow(t) {
  const idx = getSettings().call_targets.indexOf(t);
  const mode = getSettings().route_overrides?.[t.id]?.mode || "available";
  const descriptor = targetFlowDescription(t);
  return `
    <div class="row" data-target-index="${idx}">
      <div class="row-main">
        <div style="min-width:0;">
          <div class="row-title">${esc(t.label || t.id)}</div>
          <div class="row-sub">${esc(descriptor)}</div>
        </div>
        <div class="row-actions">
          <span class="pill ${mode === "available" ? "ok" : mode === "busy" ? "warn" : "bad"}">${esc(mode)}</span>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="available">Available</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="busy">Busy</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="offline">Offline</button>
          <button class="btn small red" data-action="delete-target" data-index="${idx}">Delete</button>
        </div>
      </div>
      <div class="form-grid" style="margin-top:10px;">
        <div class="field">
          <label>Route ID</label>
          <input data-target="${idx}" data-key="id" value="${esc(t.id)}">
        </div>
        <div class="field">
          <label>Label</label>
          <input data-target="${idx}" data-key="label" value="${esc(t.label)}">
        </div>
        <div class="field">
          <label>HAOS node ID</label>
          <input data-target="${idx}" data-key="node_id" list="node-list" value="${esc(t.node_id)}">
        </div>
        <div class="field">
          <label>SIP extension / outside number</label>
          <input data-target="${idx}" data-key="extension" value="${esc(t.extension)}">
        </div>
        <div class="field full">
          <label>Fallback target IDs</label>
          <input data-target="${idx}" data-key="fallback_targets_text" value="${esc((t.fallback_targets || []).join(", "))}">
        </div>
      </div>
    </div>
  `;
}

function targetFlowDescription(t) {
  if (!t) return "";
  if (["sip", "asterisk"].includes(t.type)) return `Incoming target: SIP extension ${t.extension || t.id}`;
  if (["node", "device"].includes(t.type)) return `Incoming target: HAOS node ${t.node_id || t.id}`;
  if (t.type === "gateway") return `Outbound only: dial ${t.extension || "number"} via trunk ${t.trunk || "default"}`;
  return `${t.type || "target"} · ${t.node_id || t.extension || t.trunk || ""}`;
}

/* =========================================================
   SIP
   ========================================================= */

function renderSip() {
  $("content").innerHTML = `
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

function sipTable() {
  if (!state.sip.length) return `<div class="empty">No SIP endpoints returned yet.</div>`;
  return `
    <div class="data-table">
      ${state.sip.map(sipRow).join("")}
    </div>
  `;
}

function sipRow(raw) {
  const ep = normalizeSipEndpoint(raw) || {};
  const enabled = ep.enabled !== false;
  const endpointId = ep.id || ep.extension || ep.username;
  const isGateway = isGatewaySip(ep);
  const registered = Boolean(ep.registered);
  const contactText = ep.contact_address
    ? `${ep.contact_address}${ep.contact_latency_ms ? ` · ${ep.contact_latency_ms}ms` : ""}`
    : (ep.contact_status || "no live contact");
  const autoAnswerText = ep.auto_answer
    ? (ep.auto_answer_callers ? `auto-answer from ${ep.auto_answer_callers}` : "auto-answer from anyone")
    : "manual answer";
  const speakerText = ep.auto_speaker
    ? (ep.auto_speaker_callers ? `speaker from ${ep.auto_speaker_callers}` : "speaker follows auto-answer")
    : "speaker off";
  const callbackText = ep.callback_bridge
    ? `caller callback from ${ep.callback_bridge_callers || "no allowlist"}${ep.callback_caller_auto_speaker ? " with caller speaker" : ep.callback_caller_auto_answer ? " with caller auto-answer" : ""}`
    : "caller callback off";
  return `
    <div class="sip-manage-row ${isGateway ? "protected" : ""}">
      <div class="sip-main">
        <div style="min-width:0;">
          <div class="row-title">${esc(ep.extension || "-")} ${ep.description ? `<span>${esc(ep.description)}</span>` : ""}</div>
          <div class="row-sub">User ${esc(ep.username || "-")} · ${esc(ep.route_to || "any available node")} · ${ep.video_enabled ? "Audio + H.264" : "Audio only"} · ${esc(autoAnswerText)} · ${esc(speakerText)} · ${esc(callbackText)}</div>
          <div class="row-sub">Live contact: ${esc(contactText)}</div>
        </div>
        <div class="row-actions">
          <span class="pill ${enabled ? "ok" : "bad"}">${enabled ? "enabled" : "disabled"}</span>
          <span class="pill ${registered ? "ok" : "warn"}">${registered ? "registered" : "offline"}</span>
          ${ep.default_outbound ? `<span class="pill ok">default outside gateway</span>` : ""}
          ${isGateway ? `<span class="pill warn">gateway protected</span>` : ""}
        </div>
      </div>
      <div class="sip-edit-grid">
        <div class="field">
          <label>Label</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="description" value="${esc(ep.description || "")}" placeholder="Kitchen monitor">
        </div>
        <div class="field">
          <label>Route to HAOS node</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="route_to" list="node-list" value="${esc(ep.route_to || "")}" placeholder="any available node">
        </div>
        <div class="field">
          <label>Rotate password</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="password" type="password" placeholder="new password only">
        </div>
        <div class="sip-checks">
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="enabled" type="checkbox" ${enabled ? "checked" : ""}> Enabled</label>
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="video_enabled" type="checkbox" ${ep.video_enabled ? "checked" : ""}> H.264 video</label>
          ${isGateway ? `<label><input data-sip-id="${esc(endpointId)}" data-sip-key="default_outbound" type="checkbox" ${ep.default_outbound ? "checked" : ""}> Default outside gateway</label>` : ""}
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="auto_answer" type="checkbox" ${ep.auto_answer ? "checked" : ""}> Auto-answer</label>
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="auto_speaker" type="checkbox" ${ep.auto_speaker ? "checked" : ""}> Speaker on auto-answer</label>
        </div>
        <div class="field full">
          <label>Only auto-answer from caller extension(s)</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="auto_answer_callers" value="${esc(ep.auto_answer_callers || "")}" placeholder="1025, 1602">
          <div class="hint">Blank means any caller. For precise behavior like <b>1025 → ${esc(ep.extension || "this phone")}</b>, put <b>1025</b> here.</div>
        </div>
        <div class="field full">
          <label>Only request speaker/intercom from caller extension(s)</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="auto_speaker_callers" value="${esc(ep.auto_speaker_callers || "")}" placeholder="${esc(ep.auto_answer_callers || "1025, 1602")}">
          <div class="hint">Blank reuses the auto-answer caller list. This sends intercom/speaker hints to the <b>called</b> phone; Asterisk cannot force the original caller handset into speaker after it has already placed a call.</div>
        </div>
        <div class="field full feature-box">
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="callback_bridge" type="checkbox" ${ep.callback_bridge ? "checked" : ""}> Caller callback bridge</label>
          <div class="hint">Use when the <b>caller</b> phone also needs auto-answer/speaker. Simson replaces the original dial attempt with a fresh callback to the caller, then bridges to this target.</div>
        </div>
        <div class="field full">
          <label>Only callback-bridge these caller extension(s)</label>
          <input data-sip-id="${esc(endpointId)}" data-sip-key="callback_bridge_callers" value="${esc(ep.callback_bridge_callers || "")}" placeholder="1025, 1026">
          <div class="hint">Required allowlist. Example: set this on target <b>${esc(ep.extension || "1603")}</b> to <b>1025</b> for only 1025 → ${esc(ep.extension || "1603")}.</div>
        </div>
        <div class="sip-checks full">
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="callback_caller_auto_answer" type="checkbox" ${ep.callback_caller_auto_answer ? "checked" : ""}> Caller callback auto-answer</label>
          <label><input data-sip-id="${esc(endpointId)}" data-sip-key="callback_caller_auto_speaker" type="checkbox" ${ep.callback_caller_auto_speaker ? "checked" : ""}> Caller callback speaker/intercom</label>
        </div>
      </div>
      <div class="sip-actions">
        <button class="btn small secondary" data-action="save-sip" data-id="${esc(endpointId)}">Save Device</button>
        ${isGateway
          ? `<button class="btn small red ghost" data-action="delete-sip" data-id="${esc(endpointId)}" data-ext="${esc(ep.extension || endpointId)}" title="Gateway trunks require typed confirmation">Delete Gateway</button>`
          : `<button class="btn small red" data-action="delete-sip" data-id="${esc(endpointId)}" data-ext="${esc(ep.extension || endpointId)}">Delete</button>`}
      </div>
    </div>
  `;
}

function isGatewaySip(ep) {
  const text = `${ep.extension || ""} ${ep.username || ""} ${ep.description || ""}`.toLowerCase();
  return /^700[0-9]/.test(String(ep.extension || "")) || text.includes("gateway") || text.includes("gsm") || text.includes("fxo") || text.includes("landline");
}

/* =========================================================
   Automation
   ========================================================= */

function renderAutomation() {
  const settings = getSettings();
  const auto = settings.automation;
  const globalCooldown = effectiveDoorCooldown(auto.cooldown_seconds);
  const videoSip = state.sip.map(normalizeSipEndpoint).filter((ep) => ep && ep.enabled !== false && ep.video_enabled);
  const doorTargets = settings.call_targets.filter((t) => ["sip", "asterisk", "node", "device"].includes(t.type));
  const doorTriggers = (auto.triggers || []).filter((item) => item.mode === "door_station");
  const selectedDoorTriggerId = state.selectedDoorTriggerId || "";
  const selectedDoor = doorTriggers.find((item) => item.id === selectedDoorTriggerId) || {};
  const existingTargetIds = Array.isArray(selectedDoor.target_ids) && selectedDoor.target_ids.length
    ? selectedDoor.target_ids
    : [selectedDoor.target_id].filter(Boolean);
  const selectedDoorTargets = new Set(existingTargetIds.map(String));
  const selectedSource = selectedDoor.source_extension || videoSip[0]?.extension || "";
  const selectedFanout = selectedDoor.fanout_mode || "parallel";

  $("content").innerHTML = `
    <div class="automation-grid">
      <div class="card glow">
        <div class="card-head">
          <div>
            <div class="card-title">Anti-spam guard</div>
            <div class="card-sub">Stops unknown-face devices from immediately retriggering after a call ends.</div>
          </div>
          <span class="pill ok">${esc(globalCooldown)}s cooldown</span>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Default cooldown seconds</label>
            <input type="number" min="20" max="3600" data-path="automation.cooldown_seconds" value="${esc(globalCooldown)}">
            <div class="hint">Minimum 20s. Recommended for face detection: 90-180 seconds.</div>
          </div>
          <div class="field">
            <label>Webhook ID</label>
            <input data-path="automation.webhook_id" value="${esc(auto.webhook_id)}" placeholder="site_unknown_face">
          </div>
          <div class="field full">
            <label>Webhook secret</label>
            <input type="password" data-path="automation.webhook_secret" value="${esc(auto.webhook_secret)}" placeholder="generate a long private secret">
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.webhook_enabled" ${auto.webhook_enabled ? "checked" : ""}> Enable webhook callbacks</label>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.block_while_call_active" ${auto.block_while_call_active !== false ? "checked" : ""}> Suppress triggers while a call is already active</label>
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="automation.persistent_notifications" ${auto.persistent_notifications !== false ? "checked" : ""}> Create Home Assistant notifications for door events</label>
          </div>
          <div class="field full">
            <label>Mobile app notify services</label>
            <input data-path="automation.notify_services" value="${esc(auto.notify_services || "")}" placeholder="notify.23090ra98i, notify.mobile_app_your_phone">
            <div class="hint">Use the notify entity/service that works in HA automations. Modern notify entities like notify.23090ra98i are sent through notify.send_message.</div>
          </div>
          <div class="field full">
            <label>Notification opens this HA dashboard path</label>
            <input data-path="automation.dashboard_path" value="${esc(auto.dashboard_path || "/lovelace/default_view")}" placeholder="/lovelace/sip_webrtc">
            <div class="hint">Tap a call notification to open this dashboard/card. Use the path after your Home Assistant host.</div>
          </div>
        </div>
        <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
          <button class="btn secondary" data-action="generate-webhook">Generate credentials</button>
          <button class="btn secondary" data-action="test-notification">Send Test Notification</button>
        </div>
        ${webhookPreview(auto)}
      </div>
      <div class="card">
        <div class="card-title">Door camera flow</div>
        <div class="card-sub">Door flows are separate from gateway fallback. Choose one outdoor source, then choose every SIP monitor or HAOS card that should be notified/ring.</div>
        <div class="door-flow multi" style="margin-top:14px">
          <div class="door-step">
            <label>1 · Outdoor source</label>
            <select id="door-source">${videoSip.map((ep) => option(ep.extension, `${ep.extension} · ${ep.description || ep.username}`, selectedSource)).join("")}</select>
            <div class="hint">This SIP device is called first so it can publish live audio + H.264 video.</div>
          </div>
          <div class="door-arrow">→</div>
          <div class="door-step destination">
            <label>2 · Destinations</label>
            <div class="check-list">
              ${doorTargets.map((t) => `
                <label class="check-row">
                  <input type="checkbox" class="door-target-check" value="${esc(t.id)}" ${selectedDoorTargets.has(String(t.id)) ? "checked" : ""}>
                  <span>
                    <strong>${esc(t.label || t.id)}</strong>
                    <small>${esc(targetDescriptor(t))}</small>
                  </span>
                </label>
              `).join("") || `<div class="empty">Add SIP phones or HAOS node routes first.</div>`}
            </div>
          </div>
        </div>
        <div class="form-grid" style="margin-top:14px">
          <div class="field full">
            <label>Saved door flow</label>
            <select id="door-trigger-select">
              <option value="">Create new door flow</option>
              ${doorTriggers.length ? doorTriggers.map((t) => option(
                t.id,
                `${t.label || t.id} — ${sourceSipLabel(t.source_extension || selectedSource)} → ${targetListText(Array.isArray(t.target_ids) ? t.target_ids : [t.target_id].filter(Boolean))}`,
                t.id === selectedDoorTriggerId
              )).join("") : ``}
            </select>
          </div>
          <div class="field">
            <label>Flow name</label>
            <input id="door-label" value="${esc(selectedDoor.label || "Unknown visitor at front door")}">
          </div>
          <div class="field">
            <label>Ring time seconds</label>
            <input id="door-timeout" type="number" min="5" max="120" value="${esc(selectedDoor.timeout || 30)}">
          </div>
          <div class="field">
            <label>Trigger cooldown seconds</label>
            <input id="door-cooldown" type="number" min="20" max="3600" value="${esc(effectiveDoorCooldown(selectedDoor.cooldown_seconds || globalCooldown))}">
            <div class="hint">Minimum 20s to prevent repeated face-detection calls.</div>
          </div>
          <div class="field">
            <label>Caller ID</label>
            <input id="door-caller" value="${esc(selectedDoor.caller_id || "")}" placeholder="Unknown visitor">
          </div>
          <div class="field full">
            <label>Fan-out mode</label>
            <select id="door-fanout">
              ${option("parallel", "Ring selected destinations at the same time", selectedFanout)}
              ${option("priority", "Try destinations in priority order", selectedFanout)}
            </select>
            <div class="hint">Native H.264 video is safest with one SIP monitor. If you select SIP + HAOS together, Simson uses shared bridge fanout so HAOS rings too; video remains native only in SIP-only monitor flows.</div>
          </div>
          <div class="field full">
            <div class="flow-preview">
              <strong>Current selected flow</strong>
              <span>Source: ${esc(sourceSipLabel(selectedSource))}</span>
              <b>→</b>
              <span>Destinations: ${esc(targetListText(existingTargetIds) || "none")}</span>
            </div>
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn orange" data-action="create-door-flow">${selectedDoorTriggerId ? "Update Door Flow" : "Create Door Flow"}</button></div>
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
          <select id="intercom-source">${state.sip.map(normalizeSipEndpoint).filter(Boolean).map((ep) => option(ep.extension, `${ep.extension} · ${ep.description || ep.username}`, "")).join("")}</select>
        </div>
        <div class="field">
          <label>Target SIP/node</label>
          <select id="intercom-target">${targetSelectOptions("", false)}</select>
        </div>
        <div class="field">
          <label>Source mode</label>
          <select id="intercom-source-mode">
            ${option("speaker", "Auto-answer + speaker/intercom", "speaker")}
            ${option("answer", "Auto-answer only", "")}
            ${option("manual", "Manual answer", "")}
          </select>
        </div>
        <div class="field">
          <label>Target mode</label>
          <select id="intercom-target-mode">
            ${option("speaker", "Auto-answer + speaker/intercom", "speaker")}
            ${option("answer", "Auto-answer only", "")}
            ${option("manual", "Manual answer", "")}
          </select>
        </div>
        <div class="field full">
          <label>Generated full URL</label>
          <input id="intercom-url" class="mono" readonly value="${esc(intercomUrlPreview())}">
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
        ${auto.triggers.map(triggerRow).join("") || `<div class="empty">No automation triggers yet.</div>`}
      </div>
    </div>
  `;
}

function vpsHttpBase() {
  const raw = String(state.status?.server_url || boot.server_url || "").trim();
  if (!raw) return "";
  if (raw.startsWith("wss://")) return `https://${raw.slice(6).replace(/\/ws\/?$/, "")}`;
  if (raw.startsWith("ws://")) return `http://${raw.slice(5).replace(/\/ws\/?$/, "")}`;
  return raw.replace(/\/ws\/?$/, "").replace(/\/$/, "");
}

function intercomUrlPreview() {
  const source = $("intercom-source")?.value || state.sip.map(normalizeSipEndpoint).filter(Boolean)[0]?.extension || "";
  const firstTarget = getSettings().call_targets[0]?.id
    || state.sip.map(normalizeSipEndpoint).filter(Boolean).find((ep) => ep.extension !== source)?.extension
    || "";
  const target = $("intercom-target")?.value || firstTarget;
  const sourceMode = $("intercom-source-mode")?.value || "speaker";
  const targetMode = $("intercom-target-mode")?.value || "speaker";
  const base = vpsHttpBase();
  const accountID = state.status?.account_id || "";
  const nodeID = state.status?.node_id || "";
  const token = state.status?.install_token || "";
  if (!base || !accountID || !nodeID || !token || !source || !target) return "";
  const url = new URL("/node/sip-intercom", base);
  url.searchParams.set("account_id", accountID);
  url.searchParams.set("node_id", nodeID);
  url.searchParams.set("install_token", token);
  url.searchParams.set("source", source);
  url.searchParams.set("target", target);
  url.searchParams.set("source_auto_mode", sourceMode);
  url.searchParams.set("target_auto_mode", targetMode);
  url.searchParams.set("timeout_sec", "30");
  return url.toString();
}

function refreshIntercomUrl() {
  const el = $("intercom-url");
  if (el) el.value = intercomUrlPreview();
}

function targetDescriptor(target) {
  if (!target) return "";
  if (["sip", "asterisk"].includes(target.type)) return `SIP/video extension ${target.extension || target.id}`;
  if (["node", "device"].includes(target.type)) return `HAOS node ${target.node_id || target.id}`;
  return `${target.type || "target"} ${target.extension || target.node_id || target.id}`;
}

function targetDisplayName(id) {
  const target = getSettings().call_targets.find((item) => String(item.id) === String(id));
  if (!target) return String(id || "");
  const label = target.label || target.id;
  const suffix = target.extension ? ` (${target.extension})` : target.node_id ? ` (${target.node_id})` : "";
  return `${label}${suffix}`;
}

function webhookPreview(auto) {
  if (!auto.webhook_id) {
    return `<div class="empty" style="margin-top:14px">Generate credentials to get device callback URLs.</div>`;
  }
  const doorTriggers = (getSettings().automation.triggers || []).filter(
    (item) => item.mode === "door_station" && String(item.id || "").trim()
  );
  if (doorTriggers.length === 1) {
    return `
      <div class="row" style="margin-top:14px">
        <div class="row-title">Door panel callback URL</div>
        <div class="row-sub">Paste this single full URL into the outdoor device. Change destinations below without changing the device URL.</div>
        <input class="mono" readonly value="${esc(stableDoorCallbackUrl())}" style="margin-top:8px;">
        <div class="row-sub" style="margin-top:6px;">POST with secret also works: ${esc(stableDoorCallbackPath())}. Advanced per-trigger URL: ${esc(deviceCallbackPath("TRIGGER_ID"))}</div>
      </div>
    `;
  }
  return `
    <div class="field-hint" style="margin-top:14px"><strong>${doorTriggers.length} saved door flow(s)</strong></div>
    <div class="field-hint" style="margin-top:7px">Use a per-trigger callback URL for each outdoor device. Legacy stable callback requires exactly one enabled door flow.</div>
    ${doorTriggers.map((trigger) => `
      <div class="row" style="margin-top:12px">
        <div class="row-title">${esc(trigger.label || trigger.id)}</div>
        <div class="row-sub">Trigger ID: ${esc(trigger.id)}</div>
        <input class="mono" readonly value="${esc(deviceCallbackUrl(trigger.id))}" style="margin-top:6px;">
      </div>
    `).join("")}
  `;
}

function triggerRow(t) {
  const targetIds = Array.isArray(t.target_ids) && t.target_ids.length ? t.target_ids : [t.target_id].filter(Boolean);
  const targetText = targetIds.map(targetDisplayName).join(" + ");
  const cooldown = t.mode === "door_station"
    ? effectiveDoorCooldown(t.cooldown_seconds || getSettings().automation.cooldown_seconds)
    : (t.cooldown_seconds || getSettings().automation.cooldown_seconds || 90);
  const isDoor = t.mode === "door_station";
  const fanout = t.fanout_mode === "priority" ? "priority order" : "same time";
  return `
    <div class="row ${isDoor ? "door-trigger-row" : ""}">
      <div class="row-main">
        <div style="min-width:0;">
          <div class="row-title">${esc(t.label || t.id)}</div>
          ${isDoor ? `
            <div class="route-line">
              <span class="route-chip source">Outdoor ${esc(sourceSipLabel(t.source_extension))}</span>
              <span class="route-arrow">→</span>
              <span class="route-chip destination">${esc(targetText || "no destination")}</span>
            </div>
            <div class="row-sub">Door camera bridge · ${esc(targetIds.length)} destination(s) · fan-out ${esc(fanout)} · cooldown ${esc(cooldown)}s · ring ${esc(t.timeout || 30)}s</div>
          ` : `
            <div class="row-sub">${esc(t.mode || "standard")} · targets ${esc(targetText || "none")} · cooldown ${esc(cooldown)}s</div>
          `}
        </div>
        <div class="row-actions">
          <span class="pill ${t.enabled !== false ? "ok" : "bad"}">${t.enabled !== false ? "enabled" : "disabled"}</span>
          <button class="btn small red" data-action="delete-trigger" data-id="${esc(t.id)}">Delete</button>
        </div>
      </div>
      ${isDoor && getSettings().automation.webhook_id ? `
        <div class="callback-box">
          <label>Single device callback URL for this full flow</label>
          <input class="mono" readonly value="${esc(deviceCallbackUrl(t.id))}">
          <div class="row-sub">Paste this one URL into the outdoor panel. It runs the saved source and every selected destination above.</div>
        </div>
      ` : ""}
    </div>
  `;
}

/* =========================================================
   Advanced
   ========================================================= */

function renderAdvanced() {
  const s = state.status || {};
  $("content").innerHTML = `
    <div class="grid cols-2">
      <div class="card">
        <div class="card-title">Site identity</div>
        <div class="card-sub">Move this addon only through this guarded form. Leave install token blank to create a fresh node on the selected account, or paste the exact token for an existing node. Nothing is saved unless the VPS accepts it.</div>
        <div class="form-grid" style="margin-top:16px">
          <div class="field">
            <label>Account ID</label>
            <input id="identity-account" value="${esc(s.account_id || "")}" placeholder="site account id">
          </div>
          <div class="field">
            <label>Node ID</label>
            <input id="identity-node" value="${esc(s.node_id || "")}" placeholder="this HAOS node id">
          </div>
          <div class="field full">
            <label>Install token optional</label>
            <input id="identity-token" type="password" placeholder="blank = create fresh node token with admin access">
          </div>
          <div class="field full">
            <label>Node label optional</label>
            <input id="identity-label" value="${esc(s.node_label || "")}" placeholder="friendly name">
          </div>
        </div>
        <div class="actions" style="margin-top:16px;">
          <button class="btn secondary" data-action="save-identity">Validate & Save Identity</button>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Operational note</div>
        <div class="card-sub">Changing identity affects which site receives calls and routing events. SIP phones and gateway trunks are scoped to the selected VPS account.</div>
        <div class="row" style="margin-top:12px;">
          <div class="row-title">${esc(s.server_url || "No VPS URL")}</div>
          <div class="row-sub">Current VPS endpoint</div>
        </div>
        <div class="row" style="margin-top:8px;">
          <div class="row-title">${s.vps_connected ? "Online" : "Offline"}</div>
          <div class="row-sub">Connection state</div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-title">Raw settings snapshot</div>
      <div class="card-sub">For support/debugging. Editing here is intentionally disabled so accidental raw JSON changes do not break live routing.</div>
      <textarea rows="24" readonly style="margin-top:12px;">${esc(JSON.stringify(getSettings(), null, 2))}</textarea>
    </div>
  `;
}

function option(value, label, selected) {
  return `<option value="${esc(value)}" ${String(selected) === String(value) ? "selected" : ""}>${esc(label)}</option>`;
}

function setByPath(path, value) {
  const settings = getSettings();
  const parts = path.split(".");
  let obj = settings;
  while (parts.length > 1) {
    const key = parts.shift();
    obj[key] = obj[key] || {};
    obj = obj[key];
  }
  obj[parts[0]] = value;
}

/* =========================================================
   Event Handling (Robust)
   ========================================================= */

function onInput(event) {
  const el = event.target;

  // Handle door flow selects via delegation instead of inline onchange
  if (el.id === "door-source" || el.id === "door-trigger-select") {
    syncDoorFlowForm();
    return;
  }

  if (el.id && el.id.startsWith("intercom-")) {
    refreshIntercomUrl();
    return;
  }

  if (el.matches("[data-sip-id][data-sip-key]")) {
    setDirty("SIP device edited. Save Settings or Save Device to apply it.");
    return;
  }
  if (el.matches("[data-path]")) {
    let value = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
    if (el.dataset.path === "automation.cooldown_seconds") {
      value = effectiveDoorCooldown(value);
      if (el.type === "number" && Number(el.value) < value) el.value = value;
    }
    setByPath(el.dataset.path, value);
    setDirty();
  }
  if (el.matches("[data-target]")) {
    const target = getSettings().call_targets[Number(el.dataset.target)];
    if (!target) return;
    if (el.dataset.key === "fallback_targets_text") {
      target.fallback_targets = splitList(el.value);
    } else {
      target[el.dataset.key] = el.value;
    }
    setDirty();
  }
}

async function onClick(event) {
  const btn = event.target.closest("button");
  if (!btn) return;

  if (btn.dataset.page) {
    state.page = btn.dataset.page;
    render();
    return;
  }

  const action = btn.dataset.action;
  if (!action) return;
  event.preventDefault();

  // Prevent double-clicks
  if (btn.dataset.loading === "true") return;
  const setLoading = (v) => { btn.dataset.loading = v ? "true" : ""; btn.disabled = v; };

  try {
    setLoading(true);
    if (action === "refresh") await refresh();
    if (action === "save") await saveSettings();
    if (action === "save-identity") await saveIdentity();
    if (action === "provision") await provision();
    if (action === "add-route") addRoute();
    if (action === "delete-target") deleteTarget(btn.dataset.index);
    if (action === "target-mode") setTargetMode(btn.dataset.id, btn.dataset.mode);
    if (action === "create-sip") await createSip();
    if (action === "save-sip") await saveSip(btn.dataset.id);
    if (action === "delete-sip") await deleteSip(btn.dataset.id, btn.dataset.ext);
    if (action === "generate-webhook") generateWebhook();
    if (action === "test-notification") await testNotification();
    if (action === "create-door-flow") createDoorFlow();
    if (action === "delete-trigger") deleteTrigger(btn.dataset.id);
  } catch (err) {
    const detail = Array.isArray(err.data?.errors) && err.data.errors.length
      ? err.data.errors.join("; ")
      : err.data?.error || err.message || "Action failed";
    toast(detail);
    setSaveState(detail, "bad");
  } finally {
    setLoading(false);
  }
}

/* =========================================================
   Actions
   ========================================================= */

function addRoute() {
  const kind = $("quick-kind").value;
  const label = $("quick-label").value.trim();
  const value = $("quick-value").value.trim();
  if (!label || !value) {
    toast("Route needs a name and destination.");
    return;
  }
  const id = slug(label || value);
  const target = {
    id,
    label,
    type: kind,
    node_id: kind === "node" ? value : "",
    extension: kind !== "node" ? value : "",
    trunk: kind === "gateway" ? defaultGatewayTrunk() : "",
    timeout: getSettings().routing.ring_seconds || 25,
    fallback_targets: splitList($("quick-fallbacks").value),
  };
  getSettings().call_targets.push(target);
  setDirty("Route added. Save to keep it.");
  renderRouting();
}

function deleteTarget(index) {
  getSettings().call_targets.splice(Number(index), 1);
  setDirty("Route deleted. Save to keep it.");
  renderRouting();
}

function setTargetMode(id, mode) {
  const settings = getSettings();
  settings.route_overrides[id] = { mode, reason: "" };
  setDirty("Availability changed. Save to keep it.");
  renderRouting();
}

async function createSip() {
  const payload = {
    extension: $("sip-ext").value.trim(),
    username: $("sip-user").value.trim() || $("sip-ext").value.trim(),
    password: $("sip-pass").value.trim(),
    description: $("sip-desc").value.trim(),
    route_to: $("sip-route").value.trim(),
    default_outbound: $("sip-default-outbound").checked,
    video_enabled: $("sip-video").checked,
    auto_answer: $("sip-auto-answer").checked,
    auto_answer_callers: $("sip-auto-answer-callers").value.trim(),
    auto_speaker: $("sip-auto-speaker").checked,
    auto_speaker_callers: $("sip-auto-speaker-callers").value.trim(),
    callback_bridge: $("sip-callback-bridge").checked,
    callback_bridge_callers: $("sip-callback-callers").value.trim(),
    callback_caller_auto_answer: $("sip-callback-caller-auto-answer").checked,
    callback_caller_auto_speaker: $("sip-callback-caller-auto-speaker").checked,
    enabled: true,
  };
  await api("api/sip-endpoints", { method: "POST", body: JSON.stringify(payload) });
  toast("SIP phone created.");
  await refresh();
}

function sipFieldValue(endpointId, key) {
  const el = document.querySelector(`[data-sip-id="${CSS.escape(endpointId)}"][data-sip-key="${key}"]`);
  if (!el) return "";
  return el.type === "checkbox" ? el.checked : el.value.trim();
}

function renderedSipEndpointIds() {
  return Array.from(document.querySelectorAll("[data-sip-id][data-sip-key]"))
    .map((el) => el.dataset.sipId)
    .filter(Boolean)
    .filter((id, index, all) => all.indexOf(id) === index);
}

function sipUpdatePayload(endpointId) {
  const payload = {
    description: sipFieldValue(endpointId, "description"),
    route_to: sipFieldValue(endpointId, "route_to"),
    default_outbound: Boolean(sipFieldValue(endpointId, "default_outbound")),
    video_enabled: Boolean(sipFieldValue(endpointId, "video_enabled")),
    auto_answer: Boolean(sipFieldValue(endpointId, "auto_answer")),
    auto_answer_callers: sipFieldValue(endpointId, "auto_answer_callers"),
    auto_speaker: Boolean(sipFieldValue(endpointId, "auto_speaker")),
    auto_speaker_callers: sipFieldValue(endpointId, "auto_speaker_callers"),
    callback_bridge: Boolean(sipFieldValue(endpointId, "callback_bridge")),
    callback_bridge_callers: sipFieldValue(endpointId, "callback_bridge_callers"),
    callback_caller_auto_answer: Boolean(sipFieldValue(endpointId, "callback_caller_auto_answer")),
    callback_caller_auto_speaker: Boolean(sipFieldValue(endpointId, "callback_caller_auto_speaker")),
    enabled: Boolean(sipFieldValue(endpointId, "enabled")),
  };
  const password = sipFieldValue(endpointId, "password");
  if (password) payload.password = password;
  return payload;
}

async function saveRenderedSipEdits() {
  const ids = renderedSipEndpointIds();
  if (!ids.length) return 0;
  for (const endpointId of ids) {
    await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}`, {
      method: "PUT",
      body: JSON.stringify(sipUpdatePayload(endpointId)),
    });
  }
  return ids.length;
}

async function saveSip(endpointId) {
  if (!endpointId) {
    toast("Missing SIP endpoint ID.");
    return;
  }
  const payload = sipUpdatePayload(endpointId);
  const password = Boolean(payload.password);
  await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  toast(password ? "SIP device saved and password rotated." : "SIP device saved.");
  await refresh();
}

async function deleteSip(endpointId, extension) {
  if (!endpointId) {
    toast("Missing SIP endpoint ID.");
    return;
  }
  const label = extension || endpointId;
  const endpoint = state.sip
    .map(normalizeSipEndpoint)
    .find((ep) => String(ep.id || ep.extension || ep.username) === String(endpointId));
  const gateway = endpoint ? isGatewaySip(endpoint) : /^700[0-9]/.test(String(label || ""));
  if (gateway) {
    const typed = prompt(`Gateway ${label} is protected because deleting it can break live PSTN/GSM/FXO calling.\n\nType ${label} to confirm deletion.`);
    if (typed !== String(label)) {
      toast("Gateway deletion cancelled.");
      return;
    }
  }
  if (!confirm(`Delete SIP device ${label}? The phone will stop registering until you create it again.`)) {
    return;
  }
  await api(`api/sip-endpoints/${encodeURIComponent(endpointId)}`, { method: "DELETE" });
  toast(`SIP device ${label} deleted.`);
  await refresh();
}

async function testNotification() {
  setSaveState("Testing notification…");
  const result = await api("api/notification/test", {
    method: "POST",
    body: JSON.stringify({
      notify_services: getSettings().automation.notify_services || "",
    }),
  });
  const sent = Number(result.sent || 0);
  const total = Number(result.total || 0);
  if (sent > 0) {
    toast(`Notification test sent to ${sent}/${total} target(s).`);
    setSaveState("Notification test sent", "ok");
    return;
  }
  throw new Error("No notification target accepted the test message.");
}

function generateWebhook() {
  const auto = getSettings().automation;
  auto.webhook_enabled = true;
  auto.webhook_id = auto.webhook_id || `site_${randomHex(16)}`;
  auto.webhook_secret = randomHex(24) + randomHex(24);
  setDirty("Webhook credentials generated. Save to activate.");
  renderAutomation();
}

function createDoorFlow() {
  const source = $("door-source").value;
  const targets = Array.from(document.querySelectorAll(".door-target-check:checked")).map((el) => el.value);
  const label = $("door-label").value.trim() || "Unknown visitor";
  const triggerSelect = $("door-trigger-select");
  const selectedTriggerId = triggerSelect ? triggerSelect.value : "";
  const rawCooldown = Number($("door-cooldown").value);
  const cooldown = effectiveDoorCooldown(rawCooldown || getSettings().automation.cooldown_seconds);
  if (!source || !targets.length) {
    toast("Pick the outdoor source and at least one destination.");
    return;
  }
  const sourceAsTarget = targets.some((targetId) => {
    const target = getSettings().call_targets.find((item) => String(item.id) === String(targetId));
    return ["sip", "asterisk"].includes(target?.type) && String(target.extension || "").trim() === String(source);
  });
  if (sourceAsTarget) {
    toast("Outdoor source cannot also be a SIP destination.");
    return;
  }
  const selectedTargets = targets
    .map((targetId) => getSettings().call_targets.find((item) => String(item.id) === String(targetId)))
    .filter(Boolean);
  const sipCount = selectedTargets.filter((target) => ["sip", "asterisk"].includes(target.type)).length;
  const haosCount = selectedTargets.filter((target) => ["node", "device"].includes(target.type)).length;
  if (sipCount > 1 && haosCount === 0 && $("door-fanout").value !== "priority") {
    toast("Native SIP video supports one monitor at a time. Add a HAOS target for shared fanout, or choose priority order.");
    return;
  }
  if (rawCooldown && rawCooldown < cooldown) {
    $("door-cooldown").value = cooldown;
    toast(`Door cooldown raised to ${cooldown}s minimum to prevent spam.`);
  }
  const automation = getSettings().automation;
  let existingDoor = null;
  if (selectedTriggerId) {
    existingDoor = (automation.triggers || []).find((item) => String(item.id || "") === String(selectedTriggerId));
    if (existingDoor && existingDoor.source_extension !== source) {
      existingDoor = null;
    }
  }
  const triggerId = String(existingDoor?.id || "").trim() || `door_${randomHex(10)}`;
  const trigger = {
    id: triggerId,
    label,
    enabled: true,
    mode: "door_station",
    target_id: targets[0],
    target_ids: targets,
    fanout_mode: $("door-fanout").value || "parallel",
    source_extension: source,
    caller_id: $("door-caller").value.trim() || label,
    timeout: Number($("door-timeout").value) || 30,
    cooldown_seconds: cooldown,
  };
  automation.triggers = automation.triggers || [];
  if (existingDoor) {
    const existingIndex = automation.triggers.indexOf(existingDoor);
    if (existingIndex >= 0) {
      automation.triggers[existingIndex] = trigger;
    } else {
      automation.triggers.push(trigger);
    }
  } else {
    automation.triggers.push(trigger);
  }
  state.selectedDoorTriggerId = triggerId;
  if (!automation.webhook_id || !automation.webhook_secret || automation.webhook_secret.length < 24) {
    automation.webhook_enabled = true;
    automation.webhook_id = automation.webhook_id || `site_${randomHex(16)}`;
    automation.webhook_secret = automation.webhook_secret && automation.webhook_secret.length >= 24
      ? automation.webhook_secret
      : randomHex(24) + randomHex(24);
  }
  const modeText = sipCount && haosCount
    ? "shared bridge fanout"
    : sipCount
      ? "native SIP video"
      : "HAOS browser bridge";
  setDirty(`Door flow ready: ${sourceSipLabel(source)} to ${targets.length} destination(s) using ${modeText}. Save once; the outdoor device URL stays the same.`);
  renderAutomation();
}

function deleteTrigger(id) {
  const auto = getSettings().automation;
  auto.triggers = auto.triggers.filter((item) => item.id !== id);
  setDirty("Trigger deleted. Save to keep it.");
  renderAutomation();
}

async function provision() {
  const form = $("setup-form");
  const payload = Object.fromEntries(new FormData(form).entries());
  await api("api/provision", { method: "POST", body: JSON.stringify(payload) });
  toast("Provisioned. Reloading…");
  setTimeout(() => location.reload(), 900);
}

async function saveIdentity() {
  const payload = {
    account_id: $("identity-account")?.value.trim() || "",
    node_id: $("identity-node")?.value.trim() || "",
    install_token: $("identity-token")?.value.trim() || "",
    node_label: $("identity-label")?.value.trim() || "",
  };
  if (!payload.account_id || !payload.node_id) {
    toast("Account ID and Node ID are required.");
    return;
  }
  const result = await api("api/identity", { method: "POST", body: JSON.stringify(payload) });
  const verb = result.action === "provisioned" ? "created and saved" : "validated and saved";
  toast(`Identity ${verb}. Restart the addon to reconnect with the new account.`);
  await refresh();
}

async function saveSettings() {
  setSaveState("Saving…");
  const sipSaved = await saveRenderedSipEdits();
  const payload = getSettings();
  payload.automation.cooldown_seconds = effectiveDoorCooldown(payload.automation.cooldown_seconds);
  payload.automation.triggers = (payload.automation.triggers || []).map((trigger) => {
    if (trigger?.mode !== "door_station") return trigger;
    return {
      ...trigger,
      cooldown_seconds: effectiveDoorCooldown(trigger.cooldown_seconds || payload.automation.cooldown_seconds),
      target_ids: Array.isArray(trigger.target_ids) && trigger.target_ids.length
        ? trigger.target_ids
        : [trigger.target_id].filter(Boolean),
    };
  });
  const saved = await api("api/settings", { method: "POST", body: JSON.stringify(payload) });
  state.dirty = false;
  setSaveState("Saved", "ok");
  const gatewaySync = saved?.gateway_default_sync;
  if (gatewaySync && gatewaySync.ok === false && !gatewaySync.skipped) {
    toast(`Settings saved, but VPS default gateway did not sync: ${gatewaySync.reason || "unknown error"}`);
  } else {
    toast(sipSaved ? `Settings saved. ${sipSaved} SIP device(s) updated.` : "Settings saved.");
  }
  await refresh();
}

async function refresh() {
  setSaveState("Refreshing…");
  const [status, settings, nodes, sip, routing] = await Promise.all([
    api("api/status").catch(() => null),
    api("api/settings").catch(() => null),
    api("api/nodes").catch(() => ({ nodes: [] })),
    api("api/sip-endpoints").catch(() => []),
    api("api/routing").catch(() => null),
  ]);
  state.status = status;
  state.settings = settings ? deepMerge(defaults, settings) : getSettings();
  state.nodes = Array.isArray(nodes?.nodes) ? nodes.nodes : [];
  const sipItems = Array.isArray(sip) ? sip : Array.isArray(sip?.endpoints) ? sip.endpoints : [];
  state.sip = sipItems.map(normalizeSipEndpoint).filter(Boolean);
  state.routing = routing;
  state.loaded = true;
  if (!state.dirty) setSaveState("Everything saved", "ok");
  render();
}

function splitList(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function slug(value) {
  return String(value || "route")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64) || `route_${Date.now()}`;
}

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

shell();
refresh().catch((err) => {
  setSaveState(err.message || "Could not load dashboard", "bad");
  render();
});
