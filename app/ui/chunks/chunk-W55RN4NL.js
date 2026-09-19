import{c as f}from"./chunk-RP7N3B43.js";import{c as l,d as e,e as d}from"./chunk-6R6CGC23.js";import{a as p,b as n,d as b}from"./chunk-OPL7LVHU.js";function D(){try{let a=JSON.parse(localStorage.getItem(l)||"{}");e.selectedAudioInput=String(a.audioInput||""),e.selectedVideoInput=String(a.videoInput||""),e.selectedAudioOutput=String(a.audioOutput||""),e.videoEnabled=a.videoEnabled!==!1}catch{try{localStorage.removeItem(l)}catch{}}}function S(){try{localStorage.setItem(l,JSON.stringify({audioInput:e.selectedAudioInput,videoInput:e.selectedVideoInput,audioOutput:e.selectedAudioOutput,videoEnabled:e.videoEnabled}))}catch{}}function x(a,i,t){return a.label||`${t} ${i+1}`}function m(a,i,t){return a.length?a.map((r,o)=>b(r.deviceId,x(r,o,t),i||a[0]?.deviceId)).join(""):`<option value="">No ${n(t.toLowerCase())} detected</option>`}function w(){return!!(navigator.mediaDevices?.getUserMedia&&navigator.mediaDevices?.enumerateDevices)}function $(){return d.sip.map(f).filter(a=>a&&a.enabled!==!1&&a.video_enabled)}function u(){let a=w(),i=window.isSecureContext,t=$(),r=!!e.previewStream,o=!!e.previewStream?.getVideoTracks?.().length,c=e.permission==="granted"?"Devices ready":e.permission==="denied"?"Permission blocked":"Permission required";p("content").innerHTML=`
    <section class="media-hero">
      <div class="media-hero-copy">
        <span class="eyebrow">Realtime media</span>
        <h2>Look and sound ready.</h2>
        <p>Check your camera and microphone before a conversation. This private preview stays in the addon. Choose the devices used for calls in the dashboard card\u2019s Devices tab.</p>
        <div class="media-status-row">
          <span class="media-status ${e.permission}"><i></i>${n(c)}</span>
          <span class="media-status ${i?"granted":"denied"}"><i></i>${i?"Secure context":"HTTPS required"}</span>
          <span class="media-status neutral"><i></i>${e.videoInputs.length} camera${e.videoInputs.length===1?"":"s"}</span>
        </div>
      </div>
      <div class="media-orb" aria-hidden="true"><span></span><b>SIMSON</b></div>
    </section>

    ${e.error?`<div class="inline-notice error"><div><b>Media setup needs attention</b><span>${n(e.error)}</span></div></div>`:""}
    ${a?"":'<div class="inline-notice error"><div><b>Browser media is unavailable</b><span>Open this panel in a current Chrome, Edge, Safari, or Firefox browser.</span></div></div>'}

    <div class="media-layout">
      <section class="media-stage-card">
        <div class="media-stage" data-empty="${o?"false":"true"}">
          <video id="media-preview" autoplay muted playsinline></video>
          <div class="media-stage-empty">
            <span class="media-camera-glyph">\u25C9</span>
            <strong>${e.permission==="granted"?"Camera ready":"Preview your camera"}</strong>
            <small>Your preview remains inside this browser.</small>
          </div>
          <div class="media-stage-topline">
            <span class="live-chip">${r?"LIVE PREVIEW":"PRIVATE PREVIEW"}</span>
            <span>${n(e.videoInputs.find(s=>s.deviceId===e.selectedVideoInput)?.label||"Default camera")}</span>
          </div>
        </div>
        <div class="media-stage-actions">
          <button class="btn" data-action="${r?"media-stop":"media-preview"}" ${!a||!i?"disabled":""}>${r?"Stop preview":"Start preview"}</button>
          <button class="btn secondary" data-action="media-detect" ${!a||!i?"disabled":""}>Detect devices</button>
          <div class="mic-meter" aria-label="Microphone level"><span id="media-meter"></span></div>
        </div>
      </section>

      <section class="card media-controls-card">
        <div class="card-title">Browser call devices</div>
        <div class="card-sub">Device names appear after browser permission is granted.</div>
        <label class="media-toggle">
          <span><b>Include camera in preview</b><small>Audio-only fallback remains automatic.</small></span>
          <input id="media-video-enabled" type="checkbox" ${e.videoEnabled?"checked":""}>
        </label>
        <label class="field media-field"><span>Microphone</span>
          <select id="media-audio-input">${m(e.audioInputs,e.selectedAudioInput,"Microphone")}</select>
        </label>
        <label class="field media-field"><span>Camera</span>
          <select id="media-video-input" ${e.videoEnabled?"":"disabled"}>${m(e.videoInputs,e.selectedVideoInput,"Camera")}</select>
        </label>
        <label class="field media-field"><span>Speaker</span>
          <select id="media-audio-output">${m(e.audioOutputs,e.selectedAudioOutput,"Speaker")}</select>
          <small>Speaker selection depends on browser support. Mobile browsers normally use the system output.</small>
        </label>
      </section>
    </div>

    <section class="card lan-camera-card">
      <div class="lan-camera-head">
        <div><div class="card-title">LAN and SIP cameras</div><div class="card-sub">Video-capable endpoints already discovered or provisioned for this site.</div></div>
        <button class="btn secondary small" data-action="media-open-sip">Manage SIP devices</button>
      </div>
      <div class="lan-camera-grid">
        ${t.length?t.map(s=>`
          <article class="lan-camera-item">
            <div class="lan-camera-icon">\u25A3</div>
            <div><b>${n(s.description||s.extension)}</b><span>Extension ${n(s.extension)} \xB7 H.264</span></div>
            <em>${s.registered?"Online":"Configured"}</em>
          </article>`).join(""):`
          <div class="lan-camera-empty"><b>No LAN video endpoints yet</b><span>Add your camera from SIP Phones to see it here. Network cameras need to be provisioned before they can be used.</span></div>`}
      </div>
    </section>
  `,M()}async function E(){if(!w())throw new Error("This browser does not support camera or microphone discovery.");if(!window.isSecureContext)throw new Error("Camera and microphone access requires HTTPS or localhost.");e.error="";let a=null;try{try{a=await navigator.mediaDevices.getUserMedia({audio:!0,video:e.videoEnabled})}catch(t){if(!e.videoEnabled)throw t;a=await navigator.mediaDevices.getUserMedia({audio:!0,video:!1}),e.error="Camera permission was not granted. Audio remains available."}e.permission="granted";let i=await navigator.mediaDevices.enumerateDevices();e.audioInputs=i.filter(t=>t.kind==="audioinput"),e.videoInputs=i.filter(t=>t.kind==="videoinput"),e.audioOutputs=i.filter(t=>t.kind==="audiooutput"),e.audioInputs.some(t=>t.deviceId===e.selectedAudioInput)||(e.selectedAudioInput=e.audioInputs[0]?.deviceId||""),e.videoInputs.some(t=>t.deviceId===e.selectedVideoInput)||(e.selectedVideoInput=e.videoInputs[0]?.deviceId||""),e.audioOutputs.some(t=>t.deviceId===e.selectedAudioOutput)||(e.selectedAudioOutput=e.audioOutputs[0]?.deviceId||""),S()}catch(i){e.permission=i?.name==="NotAllowedError"?"denied":"prompt",e.error=i?.message||"Could not access browser media devices."}finally{a?.getTracks().forEach(i=>i.stop())}d.page==="media"&&u()}function h(){let a=e.selectedAudioInput?{deviceId:{exact:e.selectedAudioInput},echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0}:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0},i=e.videoEnabled?e.selectedVideoInput?{deviceId:{exact:e.selectedVideoInput},width:{ideal:1280},height:{ideal:720},frameRate:{ideal:24,max:30}}:{width:{ideal:1280},height:{ideal:720},frameRate:{ideal:24,max:30}}:!1;return{audio:a,video:i}}async function T(){A(!1);let a=e.previewGeneration;if(e.permission!=="granted"&&await E(),!(a!==e.previewGeneration||d.page!=="media"))try{let i;try{i=await navigator.mediaDevices.getUserMedia(h())}catch(t){if(!e.videoEnabled)throw t;i=await navigator.mediaDevices.getUserMedia({...h(),video:!1}),e.error="The selected camera is unavailable. Microphone preview is still active."}if(a!==e.previewGeneration||d.page!=="media"){i.getTracks().forEach(t=>t.stop());return}e.previewStream=i,i.getVideoTracks().length&&(e.error=""),u(),C(e.previewStream)}catch(i){e.error=i?.message||"Could not start the selected media devices.",u()}}function M(){let a=p("media-preview");!a||!e.previewStream||(a.srcObject!==e.previewStream&&(a.srcObject=e.previewStream),a.play().catch(()=>{}))}function A(a=!0){e.previewGeneration=(e.previewGeneration||0)+1,e.analyserFrame&&cancelAnimationFrame(e.analyserFrame),e.analyserFrame=0,e.analyserContext?.close().catch(()=>{}),e.analyserContext=null,e.previewStream?.getTracks().forEach(i=>i.stop()),e.previewStream=null,a&&d.page==="media"&&u()}function C(a){let i=a?.getAudioTracks?.()[0],t=window.AudioContext||window.webkitAudioContext;if(!i||!t)return;let r=new t,o=r.createAnalyser();o.fftSize=256,r.createMediaStreamSource(new MediaStream([i])).connect(o);let c=new Uint8Array(o.frequencyBinCount);e.analyserContext=r;let s=()=>{o.getByteFrequencyData(c);let g=c.reduce((I,y)=>I+y,0)/c.length,v=p("media-meter");v&&(v.style.width=`${Math.min(100,Math.max(4,g*1.7))}%`),e.analyserFrame=requestAnimationFrame(s)};s()}export{D as a,S as b,x as c,m as d,w as e,$ as f,u as g,E as h,h as i,T as j,M as k,A as l,C as m};
