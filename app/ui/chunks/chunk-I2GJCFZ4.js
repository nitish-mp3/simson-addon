import{b as d,d as o}from"./chunk-XNCLTULO.js";import{c as x}from"./chunk-RP7N3B43.js";import{a as m,e,f as S,g as l,h as _}from"./chunk-6R6CGC23.js";import{a as r,b as w,c as k}from"./chunk-OPL7LVHU.js";var L={setup:()=>import("./setup-NIFYGTRF.js").then(t=>t.renderSetup),overview:()=>import("./overview-JKNDZTF5.js").then(t=>t.renderOverview),routing:()=>import("./routing-OVVKYMG2.js").then(t=>t.renderRouting),sip:()=>import("./sip-G2TLQ5FF.js").then(t=>t.renderSip),media:()=>import("./studio-SZM4VKS4.js").then(t=>t.renderMediaStudio),automation:()=>import("./automation-RZ6YUKC4.js").then(t=>t.renderAutomation),advanced:()=>import("./advanced-6CNHUIWX.js").then(t=>t.renderAdvanced)},f=new Map,h=0;function H(){document.body.innerHTML=`
    <div class="shell">
      <div class="app-frame">
        <aside class="sidebar" id="sidebar">
          <div class="brand">
            <div class="brand-mark">S</div>
            <div>
              <div class="brand-title">Simson</div>
              <div class="brand-sub">Site call control \xB7 v${w(m.version)}</div>
            </div>
          </div>
          <button class="mobile-nav-toggle" id="mobile-nav-toggle" data-action="toggle-nav" type="button" aria-controls="nav" aria-expanded="false">
            <span aria-hidden="true">\u2630</span><span>Navigation</span>
          </button>
          <nav class="nav" id="nav"></nav>
          <div class="sidebar-footer">
            <div class="mini-card">
              <div class="mini-label">Node</div>
              <div class="mini-value" id="side-node">loading\u2026</div>
            </div>
            <div class="mini-card">
              <div class="mini-label">Connection</div>
              <div class="mini-value" id="side-conn">checking\u2026</div>
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
              <span class="save-state top-save-state" id="top-save-state" role="status" aria-live="polite">Loading settings\u2026</span>
              <button class="btn secondary" data-action="refresh"><span aria-hidden="true">\u21BB</span> Refresh</button>
              <button class="btn" data-action="save"><span aria-hidden="true">\u2713</span> Save changes</button>
            </div>
          </header>
          <section class="content" id="content"></section>
        </main>
      </div>
      <div class="save-bar">
        <div class="save-state" id="save-state" role="status" aria-live="polite">Loading settings\u2026</div>
        <button class="btn secondary" data-action="refresh">Reload</button>
        <button class="btn" data-action="save">Save Settings</button>
      </div>
      <div class="toast" id="toast" role="status" aria-live="polite"></div>
    </div>
  `,A(),document.body.addEventListener("click",async a=>{let n=a.target.closest("[data-page]");if(n){if(e.page==="media"&&n.dataset.page!=="media"){let{stopMediaPreview:i}=await import("./studio-SZM4VKS4.js");i(!1)}e.page=n.dataset.page,e.navOpen=!1,p();return}if(a.target.closest("[data-action]"))try{let{onClick:i}=await import("./clicks-EZP6CJIB.js");await i(a)}catch(i){d(i.message,"bad")}});let t=async a=>{try{let{onInput:n}=await import("./inputs-FDDX3OVA.js");n(a)}catch(n){d(n.message,"bad")}};document.body.addEventListener("input",t),document.body.addEventListener("change",t)}function A(){r("nav").innerHTML=l.map(([a,n,i])=>`
    <button class="${e.page===a?"active":""}" data-page="${a}" aria-current="${e.page===a?"page":"false"}">
      <span>${$(a)}</span>
      <span><b>${n}</b><br><small>${i}</small></span>
    </button>
  `).join(""),r("sidebar")?.classList.toggle("nav-open",e.navOpen);let t=r("mobile-nav-toggle");t&&t.setAttribute("aria-expanded",String(e.navOpen))}function $(t){return{overview:"\u25C9",routing:"\u21C4",sip:"\u260F",media:"\u25EB",automation:"\u26A1",advanced:"\u2699"}[t]||"\u2022"}async function p(){let t=++h;A();let a=l.find(([i])=>i===e.page)||l[0];r("page-title").textContent=a[1],r("page-kicker").textContent=a[2],r("side-node").textContent=e.status?.node_id||"not provisioned",r("side-conn").innerHTML=e.status?.vps_connected?'<span style="color:var(--success)">Online</span>':'<span style="color:var(--danger)">Offline</span>',document.querySelector(".save-bar").hidden=e.page==="media",document.querySelector('.top-actions [data-action="save"]').hidden=e.page==="media",document.querySelector(".top-save-state").textContent=e.dirty?"You have unsaved changes":e.status?.vps_connected?"All changes saved":"Node connection offline",document.querySelector(".top-save-state").classList.toggle("is-dirty",!!e.dirty);let n=m.provisioned?e.page in L?e.page:"overview":"setup";try{f.has(n)||(r("content").innerHTML='<div class="page-loading" role="status">Opening workspace\u2026</div>',f.set(n,await L[n]())),t===h&&f.get(n)()}catch(i){if(t!==h)return;r("content").innerHTML='<div class="page-loading" role="alert">This workspace could not load. Select it again to retry.</div>',d(i.message,"bad")}}var b=!1,y="";async function J(){d("Refreshing\u2026");let[t,a,n,i,c,M,v,u,g]=await Promise.all([o("api/health").catch(()=>null),o("api/status").catch(()=>null),o("api/settings").catch(()=>null),o("api/nodes").catch(()=>({nodes:[]})),o("api/sip-endpoints").catch(()=>[]),o("api/routing").catch(()=>null),o("api/advanced-routes").then(s=>({data:s,error:""})).catch(s=>({data:[],error:s?.message||"Request failed"})),o("api/call-features").then(s=>({data:s,error:""})).catch(s=>({data:null,error:s?.message||"Phone controls could not be loaded"})),o("api/notification-targets").then(s=>({data:s,error:""})).catch(s=>({data:{targets:[]},error:s?.message||"Notification discovery failed"}))]);e.health=t,e.status=a,y=R(a),e.settings=n?k(S,n):_(),e.nodes=Array.isArray(i?.nodes)?i.nodes:[];let O=Array.isArray(c)?c:Array.isArray(c?.endpoints)?c.endpoints:[];if(e.sip=O.map(x).filter(Boolean),e.routing=M,e.advancedRoutes=Array.isArray(v.data)?v.data:[],e.advancedRoutesError=v.error||"",u.data&&(e.callFeatures=u.data),e.callFeaturesError=u.error||"",e.notificationTargets=Array.isArray(g.data?.targets)?g.data.targets:[],e.notificationTargetsError=g.error||"",e.advancedDraft?.id){let s=e.advancedRoutes.find(T=>T.id===e.advancedDraft.id);e.advancedDraft=s?structuredClone(s):null}e.loaded=!0,e.dirty||d("Everything saved","ok"),p()}function R(t){let a=t?.active_call||null;return JSON.stringify({connected:!!t?.vps_connected,asterisk:!!t?.asterisk_connected,active:a?{call_id:a.call_id||"",state:a.state||"",direction:a.direction||"",caller:a.caller||a.from||a.source||"",callee:a.callee||a.to||a.target||"",started_at:a.started_at||a.created_at||"",active_for:Number(a.active_for||a.duration_seconds||0)}:null})}async function Y(){if(!(!e.loaded||b||document.hidden)){b=!0;try{let t=await o("api/status"),a=R(t);if(a===y)return;e.status=t,y=a,e.page==="overview"&&await p();let n=r("side-conn");n&&(n.innerHTML=t?.vps_connected?'<span style="color:var(--success)">Online</span>':'<span style="color:var(--danger)">Offline</span>')}catch{}finally{b=!1}}}export{J as a,Y as b,H as c,A as d,p as e};
