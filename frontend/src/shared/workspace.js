const expanded = new Map();

export function compactWorkspace(page) {
  const content = document.getElementById('content');
  content.classList.add('compact-workspace');
  if (page === 'routing') {
    const advanced = content.querySelector('.advanced-routing');
    const targets = content.querySelector('#target-list')?.closest('.card');
    const policy = content.querySelector('.grid.cols-2');
    const groups = [['Policy & defaults', policy], ['Destinations', targets], ['Multi-level routes', advanced]].filter(([,element]) => element);
    const nav = document.createElement('nav');
    nav.className = 'workspace-sections';
    nav.setAttribute('aria-label', 'Routing sections');
    const key = 'routing:section';
    for (const [label, element] of groups) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      const select = () => {
        expanded.set(key, label);
        groups.forEach(([,panel]) => panel.hidden = panel !== element);
        [...nav.children].forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      };
      button.addEventListener('click', select);
      nav.append(button);
      element.hidden = label !== (expanded.get(key) || groups[0][0]);
      button.setAttribute('aria-pressed', String(!element.hidden));
    }
    content.prepend(nav);
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
    const create = content.querySelector('.card.glow');
    if (create) {
      const details = document.createElement('details');
      details.className = 'create-device';
      const summary = document.createElement('summary');
      summary.textContent = 'Add a SIP phone or gateway';
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
      const inventory = content.querySelector('.data-table')?.closest('.card');
      if (inventory) content.prepend(inventory);
    }
  }
}
