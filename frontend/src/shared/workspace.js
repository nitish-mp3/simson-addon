const expanded = new Map();

function sectionNavigation(page, sections) {
  const content = document.getElementById('content');
  const key = `${page}:section`;
  const nav = document.createElement('nav');
  nav.className = 'workspace-sections';
  nav.setAttribute('aria-label', `${page} sections`);
  for (const [label, panel] of sections) {
    if (!panel) continue;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    const select = () => {
      expanded.set(key, label);
      for (const [otherLabel, otherPanel] of sections) {
        if (otherPanel) otherPanel.hidden = otherLabel !== label;
      }
      for (const item of nav.children) item.setAttribute('aria-pressed', String(item === button));
    };
    button.addEventListener('click', select);
    nav.append(button);
    panel.hidden = label !== (expanded.get(key) || sections[0][0]);
    button.setAttribute('aria-pressed', String(!panel.hidden));
  }
  content.prepend(nav);
}

export function compactWorkspace(page) {
  const content = document.getElementById('content');
  content.classList.add('compact-workspace');
  if (page === 'routing') {
    const advanced = content.querySelector('.advanced-routing');
    const targets = content.querySelector('#target-list')?.closest('.card');
    const policy = content.querySelector('.grid.cols-2');
    const groups = [['Policy & defaults', policy], ['Destinations', targets], ['Multi-level routes', advanced]].filter(([,element]) => element);
    sectionNavigation('routing', groups);
  }
  if (page === 'automation') {
    const workflow = content.querySelector('.automation-grid');
    const workflowCards = [...(workflow?.children || [])].filter(element => element.matches('.card'));
    const triggerCard = [...content.querySelectorAll(':scope > .card')].find(element => element.textContent.includes('Automation triggers'));
    const sections = workflowCards.map(element => [element.querySelector('.card-title')?.textContent.trim() || 'Automation', element]);
    if (triggerCard) sections.push(['Saved triggers', triggerCard]);
    if (sections.length > 1) sectionNavigation('automation', sections);
  }
  if (page === 'advanced') {
    const identity = content.querySelector(':scope > .grid');
    const diagnostics = [...content.querySelectorAll(':scope > .card')].find(card => card.textContent.includes('Raw settings snapshot'));
    const sections = [['Site identity', identity], ['Diagnostics', diagnostics]].filter(([,panel]) => panel);
    if (sections.length > 1) sectionNavigation('advanced', sections);
  }
  const rows = [...content.querySelectorAll('.sip-manage-row, #target-list > .row')];
  for (const [index, row] of rows.entries()) {
    const heading = row.querySelector('.sip-main, .row-main');
    if (!heading) continue;
    const details = document.createElement('details');
    details.className = 'endpoint-details';
    const summary = document.createElement('summary');
    const name = heading.querySelector('.row-title, .sip-title, b, strong')?.textContent || `Endpoint ${index + 1}`;
    const key = `${page}:${name}`;
    summary.textContent = `Configure ${name}`;
    details.open = expanded.get(key) || false;
    details.addEventListener('toggle', () => expanded.set(key, details.open));
    details.append(summary);
    if (page === 'sip') {
      const description = heading.querySelector('.row-sub');
      if (description) details.append(description);
    }
    for (const child of [...row.children]) if (child !== heading) details.append(child);
    if (page === 'sip') {
      const grid = details.querySelector('.sip-edit-grid');
      if (grid) {
        const optional = [...grid.children].filter(child => child.matches('.full') && !child.matches('.gateway-policy'));
        if (optional.length) {
          const panel = document.createElement('details');
          panel.className = 'endpoint-details full';
          const label = document.createElement('summary');
          label.textContent = 'Prompts, limits & advanced call behavior';
          const fields = document.createElement('div');
          fields.className = 'form-grid';
          fields.append(...optional);
          panel.append(label, fields);
          grid.append(panel);
        }
      }
    }
    row.append(details);
  }
  if (rows.length) {
    const toolbar = document.createElement('label');
    toolbar.className = 'inventory-search';
    toolbar.textContent = `Find a ${page === 'sip' ? 'device' : 'routing target'}`;
    const input = document.createElement('input');
    input.type = 'search';
    input.placeholder = 'Filter by name, extension or status';
    const result = document.createElement('span');
    result.setAttribute('role', 'status');
    const filter = () => {
      let count = 0;
      for (const row of rows) {
        row.hidden = !row.textContent.toLowerCase().includes(input.value.trim().toLowerCase());
        if (!row.hidden) count++;
      }
      result.textContent = `${count} of ${rows.length} shown`;
    };
    input.addEventListener('input', filter);
    toolbar.append(input, result);
    rows[0].parentElement.before(toolbar);
    filter();
  }
  if (page === 'sip') {
    const notice = content.querySelector('.inline-notice');
    notice?.remove();
    const reminder = [...content.querySelectorAll('.card')].find(card => card.textContent.includes('Phone setup reminder'));
    reminder?.remove();
    const create = content.querySelector('.card.glow');
    if (create) {
      create.closest('.grid')?.classList.add('sip-create-layout');
      const details = document.createElement('details');
      details.className = 'create-device';
      const summary = document.createElement('summary');
      summary.innerHTML = '<span class="create-device-icon" aria-hidden="true">＋</span><span><b>Add a SIP phone or gateway</b><small>Create an extension and set up a handset or trunk.</small></span><span class="create-device-action">Add device <span aria-hidden="true">↗</span></span>';
      create.before(details);
      details.append(summary, create);
      const form = create.querySelector('.form-grid');
      if (form && form.children.length > 5) {
        const options = document.createElement('details');
        options.className = 'endpoint-details';
        const label = document.createElement('summary');
        label.textContent = 'Optional call behavior, prompts & permissions';
        const fields = document.createElement('div');
        fields.className = 'form-grid';
        for (const child of [...form.children].slice(5)) fields.append(child);
        options.append(label, fields);
        form.after(options);
      }
      const guide = document.createElement('details');
      guide.className = 'connection-guide';
      guide.innerHTML = '<summary>Set up a handset manually</summary><div><p>Use these settings on a SIP phone:</p><dl><dt>Server</dt><dd>simson-vps.vipsy.in</dd><dt>Port</dt><dd>5060 · UDP or TCP</dd><dt>Audio</dt><dd>PCMU (G.711u) and PCMA (G.711a)</dd><dt>Video</dt><dd>Enable H.264 when supported</dd></dl></div>';
      create.closest('.grid')?.after(guide);
      const inventory = [...content.querySelectorAll('.card')].find(card => card.textContent.includes('Registered SIP devices'));
      if (inventory) content.prepend(inventory);
    }
    const hero = document.createElement('div');
    hero.className = 'page-intro sip-intro';
    hero.innerHTML = '<div><span class="eyebrow">EXTENSIONS & DEVICES</span><h2>Your phone system</h2><p>Manage handsets, gateways, and their availability at this site.</p></div><div class="intro-summary"><span class="intro-count">'+rows.length+'</span><span>configured<br>devices</span></div>';
    content.prepend(hero);
  }
}
