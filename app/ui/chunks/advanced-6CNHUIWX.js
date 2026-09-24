import{a as s}from"./chunk-MH4MHY7U.js";import{e as t,h as d}from"./chunk-6R6CGC23.js";import{a,b as e}from"./chunk-OPL7LVHU.js";function r(){let i=t.status||{};a("content").innerHTML=`
    <div class="grid cols-2">
      <div class="card">
        <div class="card-title">Site identity</div>
        <div class="card-sub">Move this addon only through this guarded form. Leave install token blank to create a fresh node on the selected account, or paste the exact token for an existing node. Nothing is saved unless the VPS accepts it.</div>
        <div class="form-grid" style="margin-top:16px">
          <div class="field">
            <label>Account ID</label>
            <input id="identity-account" value="${e(i.account_id||"")}" placeholder="site account id">
          </div>
          <div class="field">
            <label>Node ID</label>
            <input id="identity-node" value="${e(i.node_id||"")}" placeholder="this HAOS node id">
          </div>
          <div class="field full">
            <label>Install token optional</label>
            <input id="identity-token" type="password" placeholder="blank = create fresh node token with admin access">
          </div>
          <div class="field full">
            <label>Node label optional</label>
            <input id="identity-label" value="${e(i.node_label||"")}" placeholder="friendly name">
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
          <div class="row-title">${e(i.server_url||"No VPS URL")}</div>
          <div class="row-sub">Current VPS endpoint</div>
        </div>
        <div class="row" style="margin-top:8px;">
          <div class="row-title">${i.vps_connected?"Online":"Offline"}</div>
          <div class="row-sub">Connection state</div>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-title">Raw settings snapshot</div>
      <div class="card-sub">For support/debugging. Editing here is intentionally disabled so accidental raw JSON changes do not break live routing.</div>
      <textarea rows="24" readonly style="margin-top:12px;">${e(JSON.stringify(d(),null,2))}</textarea>
    </div>
  `,s("advanced")}export{r as renderAdvanced};
