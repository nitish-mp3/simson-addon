import { esc, $ } from '../shared/dom.js';
import { boot, pages, state } from '../state/store.js';
import { setSaveState } from '../shared/feedback.js';

const loaders = {
  setup: () => import('../pages/setup.js').then(module => module.renderSetup),
  overview: () => import('../pages/overview.js').then(module => module.renderOverview),
  routing: () => import('../pages/routing.js').then(module => module.renderRouting),
  sip: () => import('../pages/sip.js').then(module => module.renderSip),
  media: () => import('../features/media/studio.js').then(module => module.renderMediaStudio),
  automation: () => import('../pages/automation.js').then(module => module.renderAutomation),
  advanced: () => import('../pages/advanced.js').then(module => module.renderAdvanced),
};
const renderers = new Map();
let revision = 0;

export function shell() {
  document.body.innerHTML = `
    <div class="shell">
      <div class="app-frame">
        <aside class="sidebar" id="sidebar">
          <div class="brand">
            <div class="brand-mark">S</div>
            <div>
              <div class="brand-title">Simson</div>
              <div class="brand-sub">Site call control · v${esc(boot.version)}</div>
            </div>
          </div>
          <button class="mobile-nav-toggle" id="mobile-nav-toggle" data-action="toggle-nav" type="button" aria-controls="nav" aria-expanded="false">
            <span aria-hidden="true">☰</span><span>Navigation</span>
          </button>
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
              <span class="save-state top-save-state" id="top-save-state" role="status" aria-live="polite">Loading settings…</span>
              <button class="btn secondary" data-action="refresh"><span aria-hidden="true">↻</span> Refresh</button>
              <button class="btn" data-action="save"><span aria-hidden="true">✓</span> Save changes</button>
            </div>
          </header>
          <section class="content" id="content"></section>
        </main>
      </div>
      <div class="save-bar">
        <div class="save-state" id="save-state" role="status" aria-live="polite">Loading settings…</div>
        <button class="btn secondary" data-action="refresh">Reload</button>
        <button class="btn" data-action="save">Save Settings</button>
      </div>
      <div class="toast" id="toast" role="status" aria-live="polite"></div>
    </div>
  `;
  renderNav();
  document.body.addEventListener('click', async event => {
    const navigation = event.target.closest('[data-page]');
    if (navigation) {
      if (state.page === 'media' && navigation.dataset.page !== 'media') {
        const { stopMediaPreview } = await import('../features/media/studio.js');
        stopMediaPreview(false);
      }
      state.page = navigation.dataset.page;
      state.navOpen = false;
      render();
      return;
    }
    if (!event.target.closest('[data-action]')) return;
    try { const { onClick } = await import('./clicks.js'); await onClick(event); }
    catch (error) { setSaveState(error.message, 'bad'); }
  });
  const input = async event => {
    try { const { onInput } = await import('./inputs.js'); onInput(event); }
    catch (error) { setSaveState(error.message, 'bad'); }
  };
  document.body.addEventListener('input', input);
  document.body.addEventListener('change', input);
}

export function renderNav() {
  $("nav").innerHTML = pages.map(([id, title, sub]) => `
    <button class="${state.page === id ? "active" : ""}" data-page="${id}" aria-current="${state.page === id ? "page" : "false"}">
      <span>${icon(id)}</span>
      <span><b>${title}</b><br><small>${sub}</small></span>
    </button>
  `).join("");
  $("sidebar")?.classList.toggle("nav-open", state.navOpen);
  const toggle = $("mobile-nav-toggle");
  if (toggle) toggle.setAttribute("aria-expanded", String(state.navOpen));
}

export function icon(id) {
  return {
    overview: "◉",
    routing: "⇄",
    sip: "☏",
    media: "◫",
    automation: "⚡",
    advanced: "⚙",
  }[id] || "•";
}

export async function render() {
  const current = ++revision;
  renderNav();
  const page = pages.find(([id]) => id === state.page) || pages[0];
  $("page-title").textContent = page[1];
  $("page-kicker").textContent = page[2];
  $("side-node").textContent = state.status?.node_id || "not provisioned";
  $("side-conn").innerHTML = state.status?.vps_connected
    ? '<span style="color:var(--success)">Online</span>'
    : '<span style="color:var(--danger)">Offline</span>';
  document.querySelector('.save-bar').hidden = state.page === 'media';
  document.querySelector('.top-actions [data-action="save"]').hidden = state.page === 'media';
  document.querySelector('.top-save-state').textContent = state.dirty ? 'You have unsaved changes' : state.status?.vps_connected ? 'All changes saved' : 'Node connection offline';
  document.querySelector('.top-save-state').classList.toggle('is-dirty', Boolean(state.dirty));

  const name = !boot.provisioned ? 'setup' : state.page in loaders ? state.page : 'overview';
  try {
    if (!renderers.has(name)) {
      $('content').innerHTML = '<div class="page-loading" role="status">Opening workspace…</div>';
      renderers.set(name, await loaders[name]());
    }
    if (current === revision) renderers.get(name)();
  } catch (error) {
    if (current !== revision) return;
    $('content').innerHTML = '<div class="page-loading" role="alert">This workspace could not load. Select it again to retry.</div>';
    setSaveState(error.message, 'bad');
  }
}
