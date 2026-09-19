import{b as d,d as o}from"./chunk-XSKVCSHS.js";import{c as x}from"./chunk-RP7N3B43.js";import{a as m,e,f as S,g as l,h as _}from"./chunk-6R6CGC23.js";import{a as r,b as w,c as k}from"./chunk-OPL7LVHU.js";var A={setup:()=>import("./setup-NIFYGTRF.js").then(a=>a.renderSetup),overview:()=>import("./overview-JDHCY4FO.js").then(a=>a.renderOverview),routing:()=>import("./routing-VFHGJCIQ.js").then(a=>a.renderRouting),sip:()=>import("./sip-F6FN5GPA.js").then(a=>a.renderSip),media:()=>import("./studio-SZM4VKS4.js").then(a=>a.renderMediaStudio),automation:()=>import("./automation-KGZRC2RA.js").then(a=>a.renderAutomation),advanced:()=>import("./advanced-XP5LMCJW.js").then(a=>a.renderAdvanced)},f=new Map,h=0;function N(){document.body.innerHTML=`
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
              <button class="btn secondary" data-action="refresh">Refresh</button>
              <button class="btn" data-action="save">Save Changes</button>
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
  `,L(),document.body.addEventListener("click",async t=>{let n=t.target.closest("[data-page]");if(n){if(e.page==="media"&&n.dataset.page!=="media"){let{stopMediaPreview:i}=await import("./studio-SZM4VKS4.js");i(!1)}e.page=n.dataset.page,e.navOpen=!1,p();return}if(t.target.closest("[data-action]"))try{let{onClick:i}=await import("./clicks-I7GH46ZX.js");await i(t)}catch(i){d(i.message,"bad")}});let a=async t=>{try{let{onInput:n}=await import("./inputs-B5M3CR5S.js");n(t)}catch(n){d(n.message,"bad")}};document.body.addEventListener("input",a),document.body.addEventListener("change",a)}function L(){r("nav").innerHTML=l.map(([t,n,i])=>`
    <button class="${e.page===t?"active":""}" data-page="${t}" aria-current="${e.page===t?"page":"false"}">
      <span>${$(t)}</span>
      <span><b>${n}</b><br><small>${i}</small></span>
    </button>
  `).join(""),r("sidebar")?.classList.toggle("nav-open",e.navOpen);let a=r("mobile-nav-toggle");a&&a.setAttribute("aria-expanded",String(e.navOpen))}function $(a){return{overview:"\u25C9",routing:"\u21C4",sip:"\u260F",media:"\u25EB",automation:"\u26A1",advanced:"\u2699"}[a]||"\u2022"}async function p(){let a=++h;L();let t=l.find(([i])=>i===e.page)||l[0];r("page-title").textContent=t[1],r("page-kicker").textContent=t[2],r("side-node").textContent=e.status?.node_id||"not provisioned",r("side-conn").innerHTML=e.status?.vps_connected?'<span style="color:var(--success)">Online</span>':'<span style="color:var(--danger)">Offline</span>',document.querySelector(".save-bar").hidden=e.page==="media",document.querySelector('.top-actions [data-action="save"]').hidden=e.page==="media";let n=m.provisioned?e.page in A?e.page:"overview":"setup";try{f.has(n)||(r("content").innerHTML='<div class="page-loading" role="status">Opening workspace\u2026</div>',f.set(n,await A[n]())),a===h&&f.get(n)()}catch(i){if(a!==h)return;r("content").innerHTML='<div class="page-loading" role="alert">This workspace could not load. Select it again to retry.</div>',d(i.message,"bad")}}var b=!1,y="";async function J(){d("Refreshing\u2026");let[a,t,n,i,c,M,v,u,g]=await Promise.all([o("api/health").catch(()=>null),o("api/status").catch(()=>null),o("api/settings").catch(()=>null),o("api/nodes").catch(()=>({nodes:[]})),o("api/sip-endpoints").catch(()=>[]),o("api/routing").catch(()=>null),o("api/advanced-routes").then(s=>({data:s,error:""})).catch(s=>({data:[],error:s?.message||"Request failed"})),o("api/call-features").then(s=>({data:s,error:""})).catch(s=>({data:null,error:s?.message||"Phone controls could not be loaded"})),o("api/notification-targets").then(s=>({data:s,error:""})).catch(s=>({data:{targets:[]},error:s?.message||"Notification discovery failed"}))]);e.health=a,e.status=t,y=R(t),e.settings=n?k(S,n):_(),e.nodes=Array.isArray(i?.nodes)?i.nodes:[];let O=Array.isArray(c)?c:Array.isArray(c?.endpoints)?c.endpoints:[];if(e.sip=O.map(x).filter(Boolean),e.routing=M,e.advancedRoutes=Array.isArray(v.data)?v.data:[],e.advancedRoutesError=v.error||"",u.data&&(e.callFeatures=u.data),e.callFeaturesError=u.error||"",e.notificationTargets=Array.isArray(g.data?.targets)?g.data.targets:[],e.notificationTargetsError=g.error||"",e.advancedDraft?.id){let s=e.advancedRoutes.find(T=>T.id===e.advancedDraft.id);e.advancedDraft=s?structuredClone(s):null}e.loaded=!0,e.dirty||d("Everything saved","ok"),p()}function R(a){let t=a?.active_call||null;return JSON.stringify({connected:!!a?.vps_connected,asterisk:!!a?.asterisk_connected,active:t?{call_id:t.call_id||"",state:t.state||"",direction:t.direction||"",caller:t.caller||t.from||t.source||"",callee:t.callee||t.to||t.target||"",started_at:t.started_at||t.created_at||"",active_for:Number(t.active_for||t.duration_seconds||0)}:null})}async function G(){if(!(!e.loaded||b||document.hidden)){b=!0;try{let a=await o("api/status"),t=R(a);if(t===y)return;e.status=a,y=t,e.page==="overview"&&await p();let n=r("side-conn");n&&(n.innerHTML=a?.vps_connected?'<span style="color:var(--success)">Online</span>':'<span style="color:var(--danger)">Offline</span>')}catch{}finally{b=!1}}}export{J as a,G as b,N as c,L as d,p as e};
