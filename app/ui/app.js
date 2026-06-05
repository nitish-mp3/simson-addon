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
};

const defaults = {
  local_api_port: 8799,
  routing: {
    strategy: "priority",
    ring_seconds: 25,
    max_attempts: 4,
    skip_unavailable: true,
    final_fallback_target: "",
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
  el.style.color = tone === "bad" ? "var(--red)" : tone === "ok" ? "var(--green)" : "var(--muted)";
}

function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2600);
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
    const err = new Error(data.error || `Request failed: ${res.status}`);
    err.data = data;
    err.status = res.status;
    throw err;
  }
  return data;
}

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
              <div class="mini-value" id="side-node">loading...</div>
            </div>
            <div class="mini-card">
              <div class="mini-label">Connection</div>
              <div class="mini-value" id="side-conn">checking...</div>
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
        <div class="save-state" id="save-state">Loading settings...</div>
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
  $("side-conn").innerHTML = state.status?.vps_connected ? "Online" : "Offline";
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

function normalizeSipEndpoint(ep) {
  if (!ep || typeof ep !== "object") return null;
  return {
    id: ep.id ?? ep.ID ?? "",
    account_id: ep.account_id ?? ep.AccountID ?? "",
    extension: ep.extension ?? ep.Extension ?? "",
    username: ep.username ?? ep.Username ?? "",
    description: ep.description ?? ep.Description ?? "",
    route_to: ep.route_to ?? ep.RouteTo ?? "",
    video_enabled: Boolean(ep.video_enabled ?? ep.VideoEnabled ?? ep.video ?? false),
    enabled: ep.enabled ?? ep.Enabled ?? true,
  };
}

function renderSetup() {
  $("content").innerHTML = `
    <div class="grid cols-2">
      <div class="card glow">
        <div class="card-title">Provision this HAOS site</div>
        <div class="card-sub">Create a site node on the VPS. Credentials are saved by the addon, not exposed in the dashboard.</div>
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
            <label>Account ID optional</label>
            <input name="account_id" placeholder="leave blank for new">
          </div>
        </div>
        <div style="margin-top:16px"><button class="btn" data-action="provision">Provision</button></div>
      </form>
    </div>
  `;
}

function renderOverview() {
  const s = state.status || {};
  const settings = getSettings();
  const active = s.active_call;
  $("content").innerHTML = `
    <div class="grid cols-3">
      ${stat("VPS", s.vps_connected ? "Online" : "Offline", s.server_url || "not configured", s.vps_connected ? "ok" : "bad")}
      ${stat("Asterisk", s.asterisk_connected ? "Connected" : "Unknown", "AMI and SIP bridge state", s.asterisk_connected ? "ok" : "warn")}
      ${stat("Automation guard", `${settings.automation.cooldown_seconds}s`, settings.automation.block_while_call_active ? "Blocks repeats while calls are active" : "Cooldown only", "ok")}
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
          <div class="row">
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
      <span class="${tone === "bad" ? "pill bad" : tone === "warn" ? "pill warn" : "pill ok"}">${esc(sub)}</span>
    </div>
  `;
}

function renderRouting() {
  const settings = getSettings();
  $("content").innerHTML = `
    <div class="grid cols-2">
      <div class="card glow">
        <div class="card-head">
          <div>
            <div class="card-title">Routing policy</div>
            <div class="card-sub">Decide how long Simson rings each target before trying a fallback.</div>
          </div>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Strategy</label>
            <select data-path="routing.strategy">
              ${option("priority", "Try saved fallback order", settings.routing.strategy)}
              ${option("round_robin", "Round robin", settings.routing.strategy)}
            </select>
          </div>
          <div class="field">
            <label>Ring before next target</label>
            <input type="number" min="5" max="300" data-path="routing.ring_seconds" value="${esc(settings.routing.ring_seconds)}">
          </div>
          <div class="field">
            <label>Max attempts</label>
            <input type="number" min="1" max="20" data-path="routing.max_attempts" value="${esc(settings.routing.max_attempts)}">
          </div>
          <div class="field">
            <label>Final fallback target</label>
            <input data-path="routing.final_fallback_target" value="${esc(settings.routing.final_fallback_target)}" placeholder="security_desk">
          </div>
          <div class="field full">
            <label><input type="checkbox" data-path="routing.skip_unavailable" ${settings.routing.skip_unavailable ? "checked" : ""}> Skip busy/offline targets</label>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Quick add route</div>
        <div class="card-sub">Create HAOS, SIP, or outside gateway targets without hunting through a long form.</div>
        <div class="form-grid" style="margin-top:14px">
          <div class="field">
            <label>Kind</label>
            <select id="quick-kind">
              <option value="node">HAOS node</option>
              <option value="sip">SIP phone</option>
              <option value="gateway">Outside via gateway</option>
            </select>
          </div>
          <div class="field">
            <label>Name</label>
            <input id="quick-label" placeholder="Dining phone">
          </div>
          <div class="field">
            <label>Node / extension / number</label>
            <input id="quick-value" list="node-list" placeholder="1025 or office2">
          </div>
          <div class="field">
            <label>Fallback IDs</label>
            <input id="quick-fallbacks" placeholder="security, office2">
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
          <div class="card-sub">Mark availability, set fallbacks, and keep targets site-scoped.</div>
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
    <div class="row">
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
  return `
    <div class="row" data-target-index="${idx}">
      <div class="row-main">
        <div>
          <div class="row-title">${esc(t.label || t.id)}</div>
          <div class="row-sub">${esc(t.type)} · ${esc(t.node_id || t.extension || t.trunk || "")}</div>
        </div>
        <div class="row-actions">
          <span class="pill ${mode === "available" ? "ok" : mode === "busy" ? "warn" : "bad"}">${esc(mode)}</span>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="available">Available</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="busy">Busy</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${esc(t.id)}" data-mode="offline">Offline</button>
          <button class="btn small red" data-action="delete-target" data-index="${idx}">Delete</button>
        </div>
      </div>
      <div class="form-grid">
        <div class="field">
          <label>Route ID</label>
          <input data-target="${idx}" data-key="id" value="${esc(t.id)}">
        </div>
        <div class="field">
          <label>Label</label>
          <input data-target="${idx}" data-key="label" value="${esc(t.label)}">
        </div>
        <div class="field">
          <label>Node ID</label>
          <input data-target="${idx}" data-key="node_id" list="node-list" value="${esc(t.node_id)}">
        </div>
        <div class="field">
          <label>Extension / number</label>
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
      <div class="data-head">
        <span>Extension</span><span>User</span><span>Route</span><span>Media</span><span>Status</span>
      </div>
      ${state.sip.map(sipRow).join("")}
    </div>
  `;
}

function sipRow(raw) {
  const ep = normalizeSipEndpoint(raw) || {};
  const enabled = ep.enabled !== false;
  return `
    <div class="data-row">
      <span><b>${esc(ep.extension || "-")}</b><small>${esc(ep.description || "")}</small></span>
      <span>${esc(ep.username || "-")}</span>
      <span>${esc(ep.route_to || "any node")}</span>
      <span>${ep.video_enabled ? "Audio + H.264" : "Audio"}</span>
      <span><span class="pill ${enabled ? "ok" : "bad"}">${enabled ? "enabled" : "disabled"}</span></span>
    </div>
  `;
}

function renderAutomation() {
  const settings = getSettings();
  const auto = settings.automation;
  const videoSip = state.sip.map(normalizeSipEndpoint).filter((ep) => ep && ep.enabled !== false && ep.video_enabled);
  const doorTargets = settings.call_targets.filter((t) => ["sip", "asterisk", "node", "device"].includes(t.type));
  $("content").innerHTML = `
    <div class="grid cols-2">
      <div class="card glow">
        <div class="card-head">
          <div>
            <div class="card-title">Anti-spam guard</div>
            <div class="card-sub">Stops unknown-face devices from immediately retriggering after a call ends.</div>
          </div>
          <span class="pill ok">${esc(auto.cooldown_seconds)}s cooldown</span>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Default cooldown seconds</label>
            <input type="number" min="1" max="3600" data-path="automation.cooldown_seconds" value="${esc(auto.cooldown_seconds)}">
            <div class="hint">Recommended for face detection: 90-180 seconds.</div>
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
        </div>
        <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
          <button class="btn secondary" data-action="generate-webhook">Generate credentials</button>
        </div>
        ${webhookPreview(auto)}
      </div>
      <div class="card">
        <div class="card-title">Door camera flow</div>
        <div class="card-sub">Source is the outdoor camera station. SIP/video destinations receive native audio + H.264 video; HAOS nodes receive a normal Simson call/event.</div>
        <div class="door-flow multi" style="margin-top:14px">
          <div class="door-step">
            <label>1 · Outdoor source</label>
            <select id="door-source">${videoSip.map((ep) => option(ep.extension, `${ep.extension} · ${ep.description || ep.username}`, "")).join("")}</select>
          </div>
          <div class="door-arrow">→</div>
          <div class="door-step destination">
            <label>2 · Destinations</label>
            <div class="check-list">
              ${doorTargets.map((t) => `
                <label class="check-row">
                  <input type="checkbox" class="door-target-check" value="${esc(t.id)}">
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
          <div class="field">
            <label>Flow name</label>
            <input id="door-label" value="Unknown visitor at front door">
          </div>
          <div class="field">
            <label>Ring time seconds</label>
            <input id="door-timeout" type="number" min="5" max="120" value="30">
          </div>
          <div class="field">
            <label>Trigger cooldown seconds</label>
            <input id="door-cooldown" type="number" min="1" max="3600" value="${esc(auto.cooldown_seconds || 90)}">
          </div>
          <div class="field">
            <label>Caller ID</label>
            <input id="door-caller" placeholder="Unknown visitor">
          </div>
          <div class="field full">
            <label>Fan-out mode</label>
            <select id="door-fanout">
              <option value="parallel">Ring selected destinations at the same time</option>
              <option value="priority">Priority order (save now, route engine can step later)</option>
            </select>
            <div class="hint">For video, parallel SIP destinations require the outdoor station to support multiple simultaneous calls. If not, select one SIP video destination and use HA automations for extra actions.</div>
          </div>
        </div>
        <div style="margin-top:14px"><button class="btn orange" data-action="create-door-flow">Create Door Flow</button></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <div class="card-title">Automation triggers</div>
          <div class="card-sub">Each trigger is allowed to call only its saved target.</div>
        </div>
      </div>
      <div class="list">
        ${auto.triggers.map(triggerRow).join("") || `<div class="empty">No automation triggers yet.</div>`}
      </div>
    </div>
  `;
}

function targetDescriptor(target) {
  if (!target) return "";
  if (["sip", "asterisk"].includes(target.type)) return `SIP/video extension ${target.extension || target.id}`;
  if (["node", "device"].includes(target.type)) return `HAOS node ${target.node_id || target.id}`;
  return `${target.type || "target"} ${target.extension || target.node_id || target.id}`;
}

function webhookPreview(auto) {
  if (!auto.webhook_id) {
    return `<div class="empty" style="margin-top:14px">Generate credentials to get device callback URLs.</div>`;
  }
  return `
    <div class="row" style="margin-top:14px">
      <div class="row-title">Device callback URL</div>
      <div class="row-sub">For GET-only panels, use /api/automation/device/&lt;webhook_id&gt;/&lt;trigger_id&gt;</div>
      <input readonly value="/api/automation/device/${esc(auto.webhook_id)}/TRIGGER_ID">
    </div>
  `;
}

function triggerRow(t) {
  const targetIds = Array.isArray(t.target_ids) && t.target_ids.length ? t.target_ids : [t.target_id].filter(Boolean);
  const targetText = targetIds.join(", ");
  return `
    <div class="row">
      <div class="row-main">
        <div>
          <div class="row-title">${esc(t.label || t.id)}</div>
          <div class="row-sub">${esc(t.mode || "standard")} · targets ${esc(targetText || "none")} · cooldown ${esc(t.cooldown_seconds || getSettings().automation.cooldown_seconds || 90)}s</div>
        </div>
        <div class="row-actions">
          <span class="pill ${t.enabled !== false ? "ok" : "bad"}">${t.enabled !== false ? "enabled" : "disabled"}</span>
          <button class="btn small red" data-action="delete-trigger" data-id="${esc(t.id)}">Delete</button>
        </div>
      </div>
      ${t.mode === "door_station" && getSettings().automation.webhook_id ? `<input readonly value="/api/automation/device/${esc(getSettings().automation.webhook_id)}/${esc(t.id)}">` : ""}
    </div>
  `;
}

function renderAdvanced() {
  $("content").innerHTML = `
    <div class="card">
      <div class="card-title">Raw settings snapshot</div>
      <div class="card-sub">For support/debugging. Editing here is intentionally disabled so accidental raw JSON changes do not break live routing.</div>
      <textarea rows="24" readonly>${esc(JSON.stringify(getSettings(), null, 2))}</textarea>
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

function onInput(event) {
  const el = event.target;
  if (el.matches("[data-path]")) {
    const value = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
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
  try {
    if (action === "refresh") await refresh();
    if (action === "save") await saveSettings();
    if (action === "provision") await provision();
    if (action === "add-route") addRoute();
    if (action === "delete-target") deleteTarget(btn.dataset.index);
    if (action === "target-mode") setTargetMode(btn.dataset.id, btn.dataset.mode);
    if (action === "create-sip") await createSip();
    if (action === "generate-webhook") generateWebhook();
    if (action === "create-door-flow") createDoorFlow();
    if (action === "delete-trigger") deleteTrigger(btn.dataset.id);
  } catch (err) {
    toast(err.data?.error || err.message || "Action failed");
    setSaveState(err.data?.error || err.message || "Action failed", "bad");
  }
}

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
    trunk: kind === "gateway" ? "7009" : "",
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
    video_enabled: $("sip-video").checked,
    enabled: true,
  };
  await api("api/sip-endpoints", { method: "POST", body: JSON.stringify(payload) });
  toast("SIP phone created.");
  await refresh();
}

function generateWebhook() {
  const auto = getSettings().automation;
  auto.webhook_enabled = true;
  auto.webhook_id = auto.webhook_id || `site_${crypto.randomUUID().replaceAll("-", "").slice(0, 16)}`;
  auto.webhook_secret = crypto.randomUUID().replaceAll("-", "") + crypto.randomUUID().replaceAll("-", "");
  setDirty("Webhook credentials generated. Save to activate.");
  renderAutomation();
}

function createDoorFlow() {
  const source = $("door-source").value;
  const targets = Array.from(document.querySelectorAll(".door-target-check:checked")).map((el) => el.value);
  const label = $("door-label").value.trim() || "Unknown visitor";
  if (!source || !targets.length) {
    toast("Pick the outdoor source and at least one destination.");
    return;
  }
  const trigger = {
    id: slug(`unknown_face_${source}_${targets.join("_")}`).slice(0, 64),
    label,
    enabled: true,
    mode: "door_station",
    target_id: targets[0],
    target_ids: targets,
    fanout_mode: $("door-fanout").value || "parallel",
    source_extension: source,
    caller_id: $("door-caller").value.trim() || label,
    timeout: Number($("door-timeout").value) || 30,
    cooldown_seconds: Number($("door-cooldown").value) || getSettings().automation.cooldown_seconds || 90,
  };
  const triggers = getSettings().automation.triggers;
  const existing = triggers.findIndex((item) => item.id === trigger.id);
  if (existing >= 0) triggers.splice(existing, 1, trigger);
  else triggers.push(trigger);
  setDirty("Door flow created. Save to activate.");
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
  toast("Provisioned. Reloading...");
  setTimeout(() => location.reload(), 900);
}

async function saveSettings() {
  setSaveState("Saving...");
  const payload = getSettings();
  await api("api/settings", { method: "POST", body: JSON.stringify(payload) });
  state.dirty = false;
  setSaveState("Saved", "ok");
  toast("Settings saved.");
  await refresh();
}

async function refresh() {
  setSaveState("Refreshing...");
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
