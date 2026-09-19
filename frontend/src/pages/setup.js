import { $ } from '../shared/dom.js';

export function renderSetup() {
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

