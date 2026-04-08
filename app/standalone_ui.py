"""Standalone web UI HTML served at / when running without Home Assistant."""

STANDALONE_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simson — __NODE_LABEL__</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0d0d0d;--surface:#1a1a1a;--surface2:#242424;--border:#2a2a2a;
    --text:#e8e8e8;--muted:#666;--accent:#1565c0;--accent2:#0d47a1;
    --green:#2e7d32;--red:#c62828;--orange:#e65100;--radius:14px;
  }
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
       min-height:100vh;display:flex;flex-direction:column;align-items:center;
       justify-content:flex-start;padding:16px}
  .app{width:100%;max-width:440px;display:flex;flex-direction:column;gap:12px}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
        padding:18px;display:flex;flex-direction:column;gap:10px}
  /* Header */
  .header{display:flex;align-items:center;gap:12px}
  .header-icon{font-size:28px}
  .header-title{font-size:18px;font-weight:700}
  .header-sub{font-size:12px;color:var(--muted)}
  .dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
  .dot-ok{background:#4caf50} .dot-err{background:#f44336} .dot-warn{background:#ff9800}
  .badge{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:.5px}
  .badge-ok{background:#1b5e2033;color:#66bb6a;border:1px solid #2e7d3244}
  .badge-err{background:#b71c1c33;color:#ef5350;border:1px solid #c6282844}
  .badge-idle{background:#1a1a1a;color:#555;border:1px solid #2a2a2a}
  /* Status row */
  .status-row{display:flex;align-items:center;justify-content:space-between;font-size:13px}
  /* Dial */
  .dial-row{display:flex;gap:8px}
  .dial-row input{flex:1;background:var(--surface2);border:1px solid var(--border);
    border-radius:8px;padding:10px 14px;color:var(--text);font-size:15px;outline:none}
  .dial-row input:focus{border-color:var(--accent)}
  /* Buttons */
  .btn{border:none;border-radius:10px;padding:11px 18px;font-size:14px;font-weight:600;
       cursor:pointer;transition:all .15s;color:#fff}
  .btn:active{transform:scale(.96)} .btn:disabled{opacity:.4;cursor:default}
  .btn-call{background:var(--green);flex:1}  .btn-call:hover{background:#388e3c}
  .btn-hangup{background:var(--red);flex:1}  .btn-hangup:hover{background:#d32f2f}
  .btn-answer{background:var(--green)}       .btn-answer:hover{background:#388e3c}
  .btn-decline{background:var(--red)}        .btn-decline:hover{background:#d32f2f}
  .btn-mute{background:var(--surface2);border:1px solid var(--border);color:var(--text)}
  .btn-row{display:flex;gap:8px;flex-wrap:wrap}
  /* Incoming */
  .incoming-card{background:#0a1f0a;border:2px solid #4caf5088;animation:pulse 1.5s infinite}
  @keyframes pulse{0%,100%{border-color:#4caf5088}50%{border-color:#4caf50cc}}
  .incoming-from{font-size:22px;font-weight:700;text-align:center;margin:4px 0}
  .incoming-type{text-align:center;font-size:13px;color:var(--muted);margin-bottom:8px}
  /* Active */
  .active-card{background:#091226;border:2px solid #1565c066}
  .timer{font-size:28px;font-weight:700;text-align:center;letter-spacing:2px;color:#90caf9}
  .remote-name{font-size:16px;text-align:center;color:var(--muted);margin-bottom:4px}
  /* Targets */
  .targets-grid{display:flex;flex-direction:column;gap:6px}
  .target-row{display:flex;align-items:center;justify-content:space-between;
    padding:10px 12px;background:var(--surface2);border-radius:8px;font-size:13px}
  .target-name{font-weight:600}
  .target-type{font-size:11px;color:var(--muted);text-transform:uppercase}
  .btn-sm{padding:6px 14px;font-size:12px;border-radius:7px}
  /* History */
  .history-list{display:flex;flex-direction:column;gap:4px;max-height:200px;overflow-y:auto}
  .history-row{display:flex;align-items:center;gap:10px;font-size:12px;
    padding:6px 8px;border-radius:6px;background:var(--surface2)}
  .history-dir{color:var(--muted)}
  .history-label{flex:1;font-weight:500}
  .history-state{font-size:11px;color:var(--muted)}
  /* Log */
  #log{font-size:11px;color:#444;font-family:monospace;max-height:80px;overflow-y:auto;margin-top:4px}
  audio{display:none}
  /* Section title */
  .section-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:2px}
</style>
</head>
<body>
<div class="app" id="app">
  <!-- Header -->
  <div class="card">
    <div class="header">
      <div class="header-icon">📞</div>
      <div>
        <div class="header-title" id="node-label">__NODE_LABEL__</div>
        <div class="header-sub" id="node-id">__NODE_ID__</div>
      </div>
      <div style="margin-left:auto">
        <span class="badge badge-idle" id="status-badge">Connecting…</span>
      </div>
    </div>
  </div>

  <!-- Incoming call (hidden by default) -->
  <div class="card incoming-card" id="incoming-card" style="display:none">
    <div class="section-title">📲 Incoming Call</div>
    <div class="incoming-from" id="incoming-from">Unknown</div>
    <div class="incoming-type" id="incoming-type">Voice call</div>
    <div class="btn-row" style="justify-content:center">
      <button class="btn btn-answer" onclick="answerCall()">✅ Answer</button>
      <button class="btn btn-decline" onclick="declineCall()">❌ Decline</button>
    </div>
  </div>

  <!-- Active call (hidden by default) -->
  <div class="card active-card" id="active-card" style="display:none">
    <div class="section-title">🔊 Active Call</div>
    <div class="remote-name" id="active-remote">Unknown</div>
    <div class="timer" id="call-timer">0:00</div>
    <div class="btn-row" style="justify-content:center">
      <button class="btn btn-mute btn-sm" id="btn-mute" onclick="toggleMute()">🎙 Mute</button>
      <button class="btn btn-hangup" onclick="hangupCall()">📵 Hang Up</button>
    </div>
  </div>

  <!-- Dial -->
  <div class="card" id="dial-card">
    <div class="section-title">Dial by Node ID</div>
    <div class="dial-row">
      <input type="text" id="dial-node" placeholder="Node ID or asterisk extension" />
      <button class="btn btn-call btn-sm" onclick="dialNode()" style="flex:none;padding:10px 16px">📞 Call</button>
    </div>
  </div>

  <!-- Targets -->
  <div class="card" id="targets-card">
    <div class="section-title">Call Targets</div>
    <div class="targets-grid" id="targets-list">
      <div style="color:var(--muted);font-size:13px">Loading targets…</div>
    </div>
  </div>

  <!-- History -->
  <div class="card" id="history-card">
    <div class="section-title">Recent Calls</div>
    <div class="history-list" id="history-list">
      <div style="color:var(--muted);font-size:12px">No history yet.</div>
    </div>
  </div>

  <!-- Log -->
  <div id="log"></div>
</div>

<audio id="ringtone" loop></audio>
<audio id="remote-audio" autoplay></audio>

<script>
// ── State ─────────────────────────────────────────────────────────────────────
const BASE = window.location.origin;
let _callId = null;
let _currentRemote = "";
let _callStart = null;
let _timerInterval = null;
let _muted = false;
let _pc = null;
let _localStream = null;
let _pendingCandidates = [];
let _callState = "idle";

// ── Logging ───────────────────────────────────────────────────────────────────
function log(msg) {
  const el = document.getElementById("log");
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent.slice(0,500);
}

// ── Status ────────────────────────────────────────────────────────────────────
function updateStatus(connected) {
  const b = document.getElementById("status-badge");
  if (connected) { b.textContent = "Online"; b.className = "badge badge-ok"; }
  else            { b.textContent = "Offline"; b.className = "badge badge-err"; }
}

// ── Periodic status poll ──────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const r = await fetch(BASE + "/api/status");
    if (r.ok) {
      const d = await r.json();
      updateStatus(d.vps_connected);
    }
  } catch(_) { updateStatus(false); }
}
setInterval(pollStatus, 8000);
pollStatus();

// ── Load targets ──────────────────────────────────────────────────────────────
async function loadTargets() {
  try {
    const r = await fetch(BASE + "/api/targets");
    if (!r.ok) return;
    const d = await r.json();
    const list = document.getElementById("targets-list");
    const targets = d.targets || [];
    if (targets.length === 0) {
      list.innerHTML = '<div style="color:var(--muted);font-size:13px">No targets configured.</div>';
      return;
    }
    list.innerHTML = targets.map(t => `
      <div class="target-row">
        <div>
          <div class="target-name">${esc(t.label || t.id)}</div>
          <div class="target-type">${esc(t.type || "node")}</div>
        </div>
        <button class="btn btn-call btn-sm" onclick="dialTarget('${esc(t.id)}','${esc(t.type||'')}')">📞 Call</button>
      </div>`).join("");
  } catch(e) { log("targets load error: " + e); }
}
loadTargets();

// ── Load history ──────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const r = await fetch(BASE + "/api/history");
    if (!r.ok) return;
    const d = await r.json();
    const list = document.getElementById("history-list");
    const history = d.history || [];
    if (history.length === 0) {
      list.innerHTML = '<div style="color:var(--muted);font-size:12px">No history yet.</div>';
      return;
    }
    list.innerHTML = history.slice(0,20).map(h => {
      const dir = h.direction === "incoming" ? "⬇" : "⬆";
      const dt = h.started_at ? new Date(h.started_at*1000).toLocaleTimeString() : "";
      const state = h.end_reason || h.state || "";
      return `<div class="history-row">
        <span class="history-dir">${dir}</span>
        <span class="history-label">${esc(h.remote_label||h.remote_node_id||"?")}</span>
        <span class="history-state">${esc(state)} ${dt}</span>
      </div>`;
    }).join("");
  } catch(e) { log("history load error: " + e); }
}
loadHistory();

// ── SSE ───────────────────────────────────────────────────────────────────────
function connectSSE() {
  const es = new EventSource(BASE + "/api/events");
  es.onopen = () => { log("SSE connected"); updateStatus(true); };
  es.onerror = () => { log("SSE disconnected — reconnecting…"); updateStatus(false); setTimeout(connectSSE, 5000); };
  es.onmessage = (e) => {
    try { handleEvent(JSON.parse(e.data)); } catch(err) { log("parse error: " + err); }
  };
}
connectSSE();

function handleEvent(ev) {
  const type = ev.type;
  if (type === "incoming_call") {
    _callId = ev.call_id;
    _currentRemote = ev.from_label || ev.from_node_id || "Unknown";
    showIncoming(_currentRemote, ev.call_type);
    playRingtone();
  } else if (type === "call_status") {
    const s = ev.status;
    _callState = s;
    if (s === "active") {
      _callId = ev.call_id;
      _currentRemote = _currentRemote || ev.remote_node_id || "";
      stopRingtone();
      showActive(_currentRemote);
      startTimer();
      startWebRTC(ev.remote_node_id);
    } else if (["ended","failed","missed","declined","timeout"].includes(s)) {
      stopRingtone();
      showIdle();
      stopTimer();
      cleanupWebRTC();
      _callId = null;
      setTimeout(loadHistory, 2000);
    }
  } else if (type === "webrtc_signal") {
    handleWebRTCSignal(ev);
  }
}

// ── UI show/hide ──────────────────────────────────────────────────────────────
function showIncoming(from, callType) {
  document.getElementById("incoming-from").textContent = from;
  document.getElementById("incoming-type").textContent =
    (callType === "sip" ? "SIP/Phone call" : "Voice call");
  document.getElementById("incoming-card").style.display = "";
  document.getElementById("active-card").style.display = "none";
}
function showActive(remote) {
  document.getElementById("active-remote").textContent = remote || "Active Call";
  document.getElementById("incoming-card").style.display = "none";
  document.getElementById("active-card").style.display = "";
}
function showIdle() {
  document.getElementById("incoming-card").style.display = "none";
  document.getElementById("active-card").style.display = "none";
  _callState = "idle";
}

// ── Timer ─────────────────────────────────────────────────────────────────────
function startTimer() {
  _callStart = Date.now();
  _timerInterval = setInterval(() => {
    const s = Math.floor((Date.now() - _callStart) / 1000);
    const m = Math.floor(s / 60), ss = s % 60;
    document.getElementById("call-timer").textContent =
      m + ":" + String(ss).padStart(2,"0");
  }, 1000);
}
function stopTimer() {
  clearInterval(_timerInterval);
  document.getElementById("call-timer").textContent = "0:00";
  _callStart = null;
}

// ── Ringtone ──────────────────────────────────────────────────────────────────
function playRingtone() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  let stop = false;
  function beep() {
    if (stop) return;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.frequency.value = 660; g.gain.value = 0.1;
    o.start(); o.stop(ctx.currentTime + 0.4);
    setTimeout(() => { if (!stop) beep(); }, 1200);
  }
  beep();
  window._stopRingtone = () => { stop = true; ctx.close(); };
}
function stopRingtone() {
  if (window._stopRingtone) { window._stopRingtone(); window._stopRingtone = null; }
}

// ── Actions ───────────────────────────────────────────────────────────────────
async function dialNode() {
  const input = document.getElementById("dial-node").value.trim();
  if (!input) return;
  _currentRemote = input;
  _callState = "requesting";
  try {
    const body = input.match(/^\d+$/)
      ? { target_id: "asterisk_" + input, call_type: "sip" }
      : { target_node_id: input, call_type: "voice" };
    const r = await fetch(BASE + "/api/call", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (r.ok) { _callId = d.call_id; log("call started: " + d.call_id); }
    else       { log("call error: " + (d.error||r.status)); alert(d.error || "Failed to start call"); }
  } catch(e) { log("dial error: " + e); }
}

async function dialTarget(targetId, type) {
  _currentRemote = targetId;
  try {
    const r = await fetch(BASE + "/api/call", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ target_id: targetId, call_type: type === "asterisk" ? "sip" : "voice" }),
    });
    const d = await r.json();
    if (r.ok) { _callId = d.call_id; log("call started: " + d.call_id); }
    else       { log("call error: " + (d.error||r.status)); alert(d.error || "Failed to start call"); }
  } catch(e) { log("dial error: " + e); }
}

async function answerCall() {
  stopRingtone();
  document.getElementById("incoming-card").style.display = "none";
  try {
    await fetch(BASE + "/api/answer", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ call_id: _callId || "" }),
    });
    showActive(_currentRemote);
    startTimer();
  } catch(e) { log("answer error: " + e); }
}

async function declineCall() {
  stopRingtone();
  showIdle();
  try {
    await fetch(BASE + "/api/reject", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ call_id: _callId || "", reason: "declined" }),
    });
  } catch(e) { log("decline error: " + e); }
  _callId = null;
}

async function hangupCall() {
  stopTimer();
  cleanupWebRTC();
  const cid = _callId;
  showIdle();
  _callId = null;
  try {
    await fetch(BASE + "/api/hangup", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ call_id: cid || "" }),
    });
  } catch(e) { log("hangup error: " + e); }
  setTimeout(loadHistory, 2000);
}

function toggleMute() {
  _muted = !_muted;
  if (_localStream) _localStream.getAudioTracks().forEach(t => t.enabled = !_muted);
  document.getElementById("btn-mute").textContent = _muted ? "🔇 Unmute" : "🎙 Mute";
}

// ── WebRTC ────────────────────────────────────────────────────────────────────
async function startWebRTC(remoteNodeId) {
  if (_pc) return;
  try {
    _localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    _pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
    _localStream.getTracks().forEach(t => _pc.addTrack(t, _localStream));
    _pc.ontrack = (ev) => {
      const audio = document.getElementById("remote-audio");
      if (ev.streams[0]) audio.srcObject = ev.streams[0];
    };
    _pc.onicecandidate = (ev) => {
      if (ev.candidate) sendSignal({ type: "ice", candidate: ev.candidate });
    };
    const polite = (document.getElementById("node-id").textContent || "") < (remoteNodeId || "");
    if (!polite) {
      const offer = await _pc.createOffer();
      await _pc.setLocalDescription(offer);
      sendSignal({ type: "offer", sdp: offer });
    }
    for (const c of _pendingCandidates) {
      await _pc.addIceCandidate(c).catch(() => {});
    }
    _pendingCandidates = [];
  } catch(e) { log("webrtc error: " + e); }
}

async function handleWebRTCSignal(ev) {
  if (ev.signal_type === "offer" || ev.sdp?.type === "offer") {
    if (!_pc) await startWebRTC(ev.from_node_id || "");
    if (!_pc) return;
    await _pc.setRemoteDescription(new RTCSessionDescription(ev.sdp || ev));
    const answer = await _pc.createAnswer();
    await _pc.setLocalDescription(answer);
    sendSignal({ type: "answer", sdp: answer });
  } else if (ev.signal_type === "answer" || ev.sdp?.type === "answer") {
    if (_pc && _pc.signalingState !== "stable") {
      await _pc.setRemoteDescription(new RTCSessionDescription(ev.sdp || ev)).catch(() => {});
    }
  } else if (ev.candidate || ev.signal_type === "ice") {
    const c = ev.candidate;
    if (_pc && _pc.remoteDescription) {
      await _pc.addIceCandidate(c).catch(() => {});
    } else {
      _pendingCandidates.push(c);
    }
  }
}

function sendSignal(signal) {
  fetch(BASE + "/api/webrtc/signal", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ call_id: _callId, signal }),
  }).catch(() => {});
}

function cleanupWebRTC() {
  if (_pc) { _pc.close(); _pc = null; }
  if (_localStream) { _localStream.getTracks().forEach(t => t.stop()); _localStream = null; }
  const audio = document.getElementById("remote-audio");
  audio.srcObject = null;
}

// ── Utility ───────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

// Keyboard shortcut: Enter in dial box triggers call
document.getElementById("dial-node").addEventListener("keydown", e => {
  if (e.key === "Enter") dialNode();
});
</script>
</body>
</html>"""
