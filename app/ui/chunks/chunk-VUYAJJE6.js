import{e as l,i as n}from"./chunk-RP7N3B43.js";import{h as d}from"./chunk-6R6CGC23.js";import{b as a}from"./chunk-OPL7LVHU.js";function b(e){return`
    <div class="row" style="padding:10px 14px;">
      <div class="row-main">
        <div>
          <div class="row-title">${a(e.label||e.id)}</div>
          <div class="row-sub">${a(e.type)} \xB7 ${a(e.node_id||e.extension||e.trunk||"site")}</div>
        </div>
        <span class="pill">${a(e.id)}</span>
      </div>
    </div>
  `}function g(e){let t=d().call_targets.indexOf(e),i=d().route_overrides?.[e.id]?.mode||"available",s=r(e),o=e.type==="gateway";return`
    <div class="row" data-target-index="${t}">
      <div class="row-main">
        <div style="min-width:0;">
          <div class="row-title">${a(e.label||e.id)}</div>
          <div class="row-sub">${a(s)}</div>
        </div>
        <div class="row-actions">
          <span class="pill ${i==="available"?"ok":i==="busy"?"warn":"bad"}">${a(i)}</span>
          <button class="btn small secondary" data-action="target-mode" data-id="${a(e.id)}" data-mode="available">Available</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${a(e.id)}" data-mode="busy">Busy</button>
          <button class="btn small secondary" data-action="target-mode" data-id="${a(e.id)}" data-mode="offline">Offline</button>
          <button class="btn small red" data-action="delete-target" data-index="${t}">Delete</button>
        </div>
      </div>
      <div class="form-grid" style="margin-top:10px;">
        <div class="field">
          <label>Route ID</label>
          <input data-target="${t}" data-key="id" value="${a(e.id)}">
        </div>
        <div class="field">
          <label>Label</label>
          <input data-target="${t}" data-key="label" value="${a(e.label)}">
        </div>
        <div class="field">
          <label>HAOS node ID</label>
          <input data-target="${t}" data-key="node_id" list="node-list" value="${a(e.node_id)}">
        </div>
        <div class="field">
          <label>SIP extension / outside number</label>
          <input data-target="${t}" data-key="extension" value="${a(e.extension)}">
        </div>
        ${o?`
          <div class="field">
            <label>Gateway trunk</label>
            <select data-target="${t}" data-key="trunk">
              ${n(e.trunk||l())}
            </select>
            <div class="hint">Short residence/intercom codes are dialed through this gateway; they do not need to be registered.</div>
          </div>
        `:""}
        <div class="field full">
          <label>Fallback target IDs</label>
          <input data-target="${t}" data-key="fallback_targets_text" value="${a((e.fallback_targets||[]).join(", "))}">
        </div>
      </div>
    </div>
  `}function r(e){if(!e)return"";if(["sip","asterisk"].includes(e.type))return`Incoming target: SIP extension ${e.extension||e.id}`;if(["node","device"].includes(e.type))return`Incoming target: HAOS node ${e.node_id||e.id}`;if(e.type==="gateway"){let t=String(e.extension||"").replace(/\D/g,"");return`${t&&t.length<7?"Building/intercom extension":"Outside number"}: dial ${e.extension||"number"} via gateway ${e.trunk||l()||"auto"}`}return`${e.type||"target"} \xB7 ${e.node_id||e.extension||e.trunk||""}`}export{b as a,g as b};
