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
const VERSION = "standalone-ui-3.8.0";
const BASE = window.location.origin;
const FALLBACK_ICE_SERVERS = [
  { urls: "stun:stun.l.google.com:19302" },
  { urls: "stun:stun1.l.google.com:19302" },
];

let _callId = null;
let _currentRemote = "";
let _remoteNodeId = "";
let _currentCallType = "voice";
let _sipBridgeId = "";
let _callStartMs = null;
let _timerInterval = null;
let _muted = false;
let _pc = null;
let _localStream = null;
let _pendingCandidates = [];
let _pendingOffer = null;
let _startingWebRTC = false;
let _callState = "idle";
let _isCaller = false;
let _webrtcConfig = null;
let _sipUA = null;
let _pendingSIPBridgeId = null;
let _ringCtx = null;
let _ringLoop = null;

function log(msg) {
  const el = document.getElementById("log");
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent.slice(0, 900);
}

function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function updateStatus(connected) {
  const badge = document.getElementById("status-badge");
  if (connected) {
    badge.textContent = "Online";
    badge.className = "badge badge-ok";
  } else {
    badge.textContent = "Offline";
    badge.className = "badge badge-err";
  }
}

function showIncoming(from, callType) {
  document.getElementById("incoming-from").textContent = from || "Unknown";
  document.getElementById("incoming-type").textContent =
    callType === "sip" ? "Desk phone / SIP bridge call" : "Voice call";
  document.getElementById("incoming-card").style.display = "";
  document.getElementById("active-card").style.display = "none";
}

function showActive(remote, callType = _currentCallType) {
  document.getElementById("active-remote").textContent =
    remote || (callType === "sip" ? "SIP Bridge" : "Active Call");
  document.getElementById("incoming-card").style.display = "none";
  document.getElementById("active-card").style.display = "";
}

function showIdle() {
  document.getElementById("incoming-card").style.display = "none";
  document.getElementById("active-card").style.display = "none";
  _callState = "idle";
}

function startTimer(answeredAtSeconds = null) {
  if (_timerInterval) clearInterval(_timerInterval);
  _callStartMs = answeredAtSeconds ? answeredAtSeconds * 1000 : Date.now();
  const tick = () => {
    const total = Math.max(0, Math.floor((Date.now() - _callStartMs) / 1000));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    document.getElementById("call-timer").textContent = `${mins}:${String(secs).padStart(2, "0")}`;
  };
  tick();
  _timerInterval = setInterval(tick, 1000);
}

function stopTimer() {
  if (_timerInterval) clearInterval(_timerInterval);
  _timerInterval = null;
  _callStartMs = null;
  document.getElementById("call-timer").textContent = "0:00";
}

function playRingtone() {
  stopRingtone();
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    _ringCtx = ctx;
    _ringLoop = setInterval(() => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 660;
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.35);
    }, 1300);
  } catch (e) {
    log("ringtone unavailable: " + e.message);
  }
}

function stopRingtone() {
  if (_ringLoop) {
    clearInterval(_ringLoop);
    _ringLoop = null;
  }
  if (_ringCtx) {
    _ringCtx.close().catch(() => {});
    _ringCtx = null;
  }
}

function isSipCall(remoteNodeId = _remoteNodeId, callType = _currentCallType) {
  return callType === "sip" || String(remoteNodeId || "").startsWith("sip:");
}

async function pollStatus() {
  try {
    const r = await fetch(BASE + "/api/status");
    if (!r.ok) return;
    const data = await r.json();
    updateStatus(data.vps_connected);
    syncFromStatus(data);
  } catch (_) {
    updateStatus(false);
  }
}

function syncFromStatus(data) {
  const active = data.active_call;
  if (!active) {
    if (_callState !== "idle") {
      stopRingtone();
      cleanupMedia();
      showIdle();
      stopTimer();
    }
    return;
  }

  _callId = active.call_id;
  _callState = active.state;
  _remoteNodeId = active.remote_node_id || _remoteNodeId;
  _currentRemote = active.remote_label || active.remote_node_id || _currentRemote;
  _currentCallType = active.call_type || _currentCallType;
  _sipBridgeId = active.sip_bridge_id || _sipBridgeId;
  _isCaller = active.direction === "outgoing";

  if (active.state === "incoming") {
    showIncoming(_currentRemote, _currentCallType);
    playRingtone();
  } else if (active.state === "active") {
    stopRingtone();
    showActive(_currentRemote, _currentCallType);
    startTimer(active.answered_at || active.started_at || null);
    if (isSipCall()) {
      if (_sipBridgeId) startSIPCall(_sipBridgeId).catch(e => log("sip bridge start error: " + e.message));
    } else if (_remoteNodeId) {
      startWebRTC().catch(e => log("webrtc start error: " + e.message));
    }
  }
}

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
          <div class="target-name">${esc(t.label || t.extension || t.id)}</div>
          <div class="target-type">${esc(t.type || "node")}${t.extension ? ` · ext ${esc(t.extension)}` : ""}</div>
        </div>
        <button class="btn btn-call btn-sm" onclick="dialTarget('${encodeURIComponent(t.id || "")}','${encodeURIComponent(t.type || "")}','${encodeURIComponent(t.node_id || "")}','${encodeURIComponent(t.label || t.extension || t.id || "")}')">📞 Call</button>
      </div>`).join("");
  } catch (e) {
    log("targets load error: " + e.message);
  }
}

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
    list.innerHTML = history.slice(0, 20).map(h => {
      const dir = h.direction === "incoming" ? "⬇" : "⬆";
      const dt = h.started_at ? new Date(h.started_at * 1000).toLocaleTimeString() : "";
      const state = h.end_reason || h.state || "";
      return `<div class="history-row">
        <span class="history-dir">${dir}</span>
        <span class="history-label">${esc(h.remote_label || h.remote_node_id || "?")}</span>
        <span class="history-state">${esc(state)} ${dt}</span>
      </div>`;
    }).join("");
  } catch (e) {
    log("history load error: " + e.message);
  }
}

function connectSSE() {
  const es = new EventSource(BASE + "/api/events");
  es.onopen = () => {
    log("SSE connected");
    updateStatus(true);
  };
  es.onerror = () => {
    log("SSE disconnected, retrying");
    updateStatus(false);
    setTimeout(connectSSE, 5000);
  };
  es.onmessage = (e) => {
    try {
      handleEvent(JSON.parse(e.data));
    } catch (err) {
      log("event parse error: " + err.message);
    }
  };
}

function handleEvent(ev) {
  if (ev.type === "init") {
    updateStatus(!!ev.vps_connected);
    return;
  }

  if (ev.type === "incoming_call") {
    _callId = ev.call_id;
    _callState = "incoming";
    _isCaller = false;
    _remoteNodeId = ev.from_node_id || "";
    _currentRemote = ev.from_label || ev.from_node_id || "Unknown";
    _currentCallType = ev.call_type || "voice";
    _sipBridgeId = ev.metadata?.sip_bridge_id || "";
    showIncoming(_currentRemote, _currentCallType);
    playRingtone();
    return;
  }

  if (ev.type === "call_status") {
    _callId = ev.call_id || _callId;
    _callState = ev.status || _callState;
    _remoteNodeId = ev.remote_node_id || _remoteNodeId;
    _currentCallType = ev.call_type || _currentCallType;
    _sipBridgeId = ev.sip_bridge_id || _sipBridgeId;

    if (ev.status === "ringing") {
      log("remote ringing");
      return;
    }

    if (ev.status === "active") {
      stopRingtone();
      _currentRemote = _currentRemote || ev.remote_node_id || "Connected";
      showActive(_currentRemote, _currentCallType);
      if (!_timerInterval) startTimer();
      if (isSipCall()) {
        if (_sipBridgeId) {
          startSIPCall(_sipBridgeId).catch(e => log("sip bridge start error: " + e.message));
        } else {
          log("active SIP call missing bridge id");
        }
      } else {
        startWebRTC().catch(e => log("webrtc start error: " + e.message));
      }
      return;
    }

    if (["ended", "failed", "missed", "declined", "timeout"].includes(ev.status)) {
      stopRingtone();
      stopTimer();
      cleanupMedia();
      showIdle();
      _callId = null;
      _remoteNodeId = "";
      _currentRemote = "";
      _currentCallType = "voice";
      _sipBridgeId = "";
      setTimeout(loadHistory, 800);
      return;
    }
  }

  if (ev.type === "webrtc_signal") {
    handleWebRTCSignal(ev).catch(e => log("webrtc signal error: " + e.message));
  }
}

async function dialNode() {
  const input = document.getElementById("dial-node").value.trim();
  if (!input) return;

  _currentRemote = input;
  _isCaller = true;
  _callState = "requesting";

  const isNumeric = /^\d+$/.test(input);
  const body = isNumeric
    ? { target_id: "asterisk_" + input, call_type: "sip" }
    : { target_node_id: input, call_type: "voice" };

  _currentCallType = isNumeric ? "sip" : "voice";
  _remoteNodeId = isNumeric ? `sip:${input}` : input;

  try {
    const r = await fetch(BASE + "/api/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (r.ok) {
      _callId = d.call_id;
      log("call started: " + d.call_id);
    } else {
      log("call error: " + (d.error || r.status));
      alert(d.error || "Failed to start call");
    }
  } catch (e) {
    log("dial error: " + e.message);
  }
}

async function dialTarget(targetId, type, nodeId = "", label = "") {
  targetId = decodeURIComponent(targetId || "");
  type = decodeURIComponent(type || "");
  nodeId = decodeURIComponent(nodeId || "");
  label = decodeURIComponent(label || "");
  _currentRemote = label || targetId;
  _isCaller = true;
  _callState = "requesting";
  _currentCallType = type === "asterisk" ? "sip" : "voice";
  _remoteNodeId = type === "asterisk" ? `sip:${targetId.replace(/^asterisk_/, "")}` : (nodeId || targetId);

  try {
    const r = await fetch(BASE + "/api/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: targetId, call_type: _currentCallType }),
    });
    const d = await r.json();
    if (r.ok) {
      _callId = d.call_id;
      log("call started: " + d.call_id);
    } else {
      log("call error: " + (d.error || r.status));
      alert(d.error || "Failed to start call");
    }
  } catch (e) {
    log("dial error: " + e.message);
  }
}

async function answerCall() {
  stopRingtone();
  try {
    const resp = await fetch(BASE + "/api/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ call_id: _callId || "" }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Answer failed");
    }
    showActive(_currentRemote, _currentCallType);
    startTimer();
    if (isSipCall() && _sipBridgeId) {
      startSIPCall(_sipBridgeId).catch(e => log("sip bridge answer error: " + e.message));
    }
  } catch (e) {
    log("answer error: " + e.message);
  }
}

async function declineCall() {
  stopRingtone();
  cleanupMedia();
  showIdle();
  try {
    await fetch(BASE + "/api/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ call_id: _callId || "", reason: "declined" }),
    });
  } catch (e) {
    log("decline error: " + e.message);
  }
  _callId = null;
}

async function hangupCall() {
  const cid = _callId;
  stopTimer();
  cleanupMedia();
  showIdle();
  _callId = null;
  try {
    await fetch(BASE + "/api/hangup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ call_id: cid || "" }),
    });
  } catch (e) {
    log("hangup error: " + e.message);
  }
  setTimeout(loadHistory, 800);
}

function toggleMute() {
  _muted = !_muted;
  if (_localStream) {
    _localStream.getAudioTracks().forEach(t => { t.enabled = !_muted; });
  }
  document.getElementById("btn-mute").textContent = _muted ? "🔇 Unmute" : "🎙 Mute";
}

async function fetchWebRTCConfig() {
  if (_webrtcConfig) return _webrtcConfig;
  try {
    const resp = await fetch(BASE + "/api/webrtc-config");
    if (resp.ok) {
      _webrtcConfig = await resp.json();
      return _webrtcConfig;
    }
  } catch (_) {}
  return { ice_servers: FALLBACK_ICE_SERVERS, sip: { enabled: false } };
}

async function ensureLocalAudio() {
  if (_localStream) return _localStream;
  _localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  return _localStream;
}

async function startWebRTC() {
  if (_pc || _startingWebRTC || !_remoteNodeId) return;
  _startingWebRTC = true;
  try {
    const cfg = await fetchWebRTCConfig();
    const iceServers = cfg.ice_servers || FALLBACK_ICE_SERVERS;
    await ensureLocalAudio();
    _pc = new RTCPeerConnection({ iceServers });
    _pendingCandidates = [];

    _pc.ontrack = (ev) => {
      const audio = document.getElementById("remote-audio");
      if (ev.streams?.[0]) {
        audio.srcObject = ev.streams[0];
      } else {
        const ms = new MediaStream();
        ms.addTrack(ev.track);
        audio.srcObject = ms;
      }
      audio.play().catch(() => {});
    };

    _pc.onicecandidate = (ev) => {
      if (ev.candidate) {
        sendSignal("ice-candidate", {
          candidate: ev.candidate.candidate,
          sdpMid: ev.candidate.sdpMid,
          sdpMLineIndex: ev.candidate.sdpMLineIndex,
        });
      }
    };

    _pc.onconnectionstatechange = () => {
      if (_pc?.connectionState === "failed") {
        log("webrtc connection failed");
      }
    };

    if (_isCaller && _localStream) {
      _localStream.getTracks().forEach(track => _pc.addTrack(track, _localStream));
      const offer = await _pc.createOffer();
      await _pc.setLocalDescription(offer);
      sendSignal("offer", {
        type: _pc.localDescription.type,
        sdp: _pc.localDescription.sdp,
      });
    }

    if (_pendingOffer) {
      const offerEvent = _pendingOffer;
      _pendingOffer = null;
      await handleWebRTCSignal(offerEvent);
    }
  } finally {
    _startingWebRTC = false;
  }
}

async function handleWebRTCSignal(ev) {
  const signalType = ev.signal_type || "";
  const data = ev.data;

  if (!signalType || !data) return;

  if (signalType === "offer") {
    if (_startingWebRTC) {
      _pendingOffer = ev;
      return;
    }
    if (!_pc) await startWebRTC();
    if (!_pc) return;

    if (_localStream && !_pc.getSenders().some(s => s.track)) {
      _localStream.getTracks().forEach(track => _pc.addTrack(track, _localStream));
    }

    await _pc.setRemoteDescription(new RTCSessionDescription(data));
    const answer = await _pc.createAnswer();
    await _pc.setLocalDescription(answer);
    sendSignal("answer", {
      type: _pc.localDescription.type,
      sdp: _pc.localDescription.sdp,
    });
    for (const candidate of _pendingCandidates) {
      await _pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {});
    }
    _pendingCandidates = [];
    return;
  }

  if (signalType === "answer") {
    if (_pc && _pc.signalingState === "have-local-offer") {
      await _pc.setRemoteDescription(new RTCSessionDescription(data));
      for (const candidate of _pendingCandidates) {
        await _pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {});
      }
      _pendingCandidates = [];
    }
    return;
  }

  if (signalType === "ice-candidate") {
    if (_pc && _pc.remoteDescription) {
      await _pc.addIceCandidate(new RTCIceCandidate(data)).catch(() => {});
    } else {
      _pendingCandidates.push(data);
    }
  }
}

function sendSignal(signalType, data) {
  if (!_callId || !_remoteNodeId) return;
  fetch(BASE + "/api/webrtc/signal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      call_id: _callId,
      to_node_id: _remoteNodeId,
      signal_type: signalType,
      data,
    }),
  }).catch(e => log("signal send error: " + e.message));
}

class MinimalSIPUA {
  constructor({ uri, password, wsUrl, iceServers, onAudioTrack, onRegistered, onError, onBye }) {
    this._uri = uri;
    this._password = password;
    this._wsUrl = wsUrl;
    this._iceServers = iceServers || [];
    this._onAudioTrack = onAudioTrack;
    this._onRegistered = onRegistered;
    this._onError = onError;
    this._onBye = onBye;
    this._ws = null;
    this._pc = null;
    this._localStream = null;
    this._cseq = 1;
    this._tag = this._rand(10);
    this._regCallId = this._rand(16) + "@" + this._domain();
    this._callId = null;
    this._registered = false;
    this._regInterval = null;
    this._inviteCSeq = null;
    this._lastAck = null;
    this._regRetryCount = 0;
    this._regRetryMax = 3;
    this._regRetryDelay = 1000;
  }

  connect() {
    try {
      this._ws = new WebSocket(this._wsUrl, "sip");
    } catch (e) {
      this._onError && this._onError(new Error("SIP WS connection failed: " + e.message));
      return;
    }
    this._ws.onopen = () => this._register();
    this._ws.onmessage = (e) => {
      if (e.data && e.data.trim()) this._handleRaw(e.data);
    };
    this._ws.onerror = () => this._onError && this._onError(new Error("SIP WebSocket error"));
    this._ws.onclose = () => {
      this._registered = false;
      if (this._regInterval) clearInterval(this._regInterval);
      this._regInterval = null;
    };
  }

  disconnect() {
    if (this._registered) this._sendUnregister();
    setTimeout(() => { this._ws && this._ws.close(); }, 400);
    this._cleanup();
  }

  async dial(extension) {
    if (!this._registered) {
      this._onError && this._onError(new Error("SIP not registered"));
      return;
    }
    try {
      this._localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (e) {
      this._onError && this._onError(e);
      return;
    }
    this._pc = new RTCPeerConnection({ iceServers: this._iceServers });
    this._pc.ontrack = (ev) => this._onAudioTrack && this._onAudioTrack(ev.streams?.[0] || null, ev.track);
    for (const t of this._localStream.getAudioTracks()) this._pc.addTrack(t, this._localStream);

    const offer = await this._pc.createOffer();
    await this._pc.setLocalDescription(offer);
    await this._waitICE();

    this._callId = this._rand(16) + "@" + this._domain();
    this._lastAck = null;
    const target = "sip:" + extension + "@" + this._domain();
    this._inviteCSeq = this._cseq;
    this._send(this._buildRequest("INVITE", target, this._callId, this._cseq++, "", this._pc.localDescription.sdp));
  }

  _rand(n = 8) { return Math.random().toString(36).slice(2, 2 + n); }
  _domain() { return this._uri.split("@")[1]; }
  _user() { return this._uri.split(":")[1]?.split("@")[0] || ""; }

  _buildRequest(method, targetUri, callId, cseq, extraHeaders = "", body = "", toUri = null) {
    const via = `SIP/2.0/WS ${this._domain()};branch=z9hG4bK${this._rand()};rport`;
    const from = `<${this._uri}>;tag=${this._tag}`;
    const to = `<${toUri || targetUri}>`;
    const ctLen = body ? `Content-Type: application/sdp\r\nContent-Length: ${body.length}` : "Content-Length: 0";
    return `${method} ${targetUri} SIP/2.0\r\n` +
      `Via: ${via}\r\nMax-Forwards: 70\r\nFrom: ${from}\r\nTo: ${to}\r\n` +
      `Call-ID: ${callId}\r\nCSeq: ${cseq} ${method}\r\nContact: <${this._uri};transport=ws>\r\n` +
      `User-Agent: Simson/${VERSION}\r\n` + (extraHeaders || "") + `${ctLen}\r\n\r\n${body}`;
  }

  _buildResponse(code, phrase, from, to, callId, via, cseq, body = "") {
    const ctLen = body ? `Content-Type: application/sdp\r\nContent-Length: ${body.length}` : "Content-Length: 0";
    return `SIP/2.0 ${code} ${phrase}\r\nVia: ${via}\r\nFrom: ${from}\r\nTo: ${to}\r\n` +
      `Call-ID: ${callId}\r\nCSeq: ${cseq}\r\nContact: <${this._uri};transport=ws>\r\n${ctLen}\r\n\r\n${body}`;
  }

  _send(msg) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) this._ws.send(msg);
  }

  _register() {
    this._send(this._buildRequest("REGISTER", "sip:" + this._domain(), this._regCallId, this._cseq++, "Expires: 3600\r\n", "", this._uri));
  }

  _sendUnregister() {
    this._send(this._buildRequest("REGISTER", "sip:" + this._domain(), this._regCallId, this._cseq++, "Expires: 0\r\n", "", this._uri));
  }

  _hdr(raw, name) {
    const lo = name.toLowerCase();
    const line = raw.split("\r\n").find(l => l.toLowerCase().startsWith(lo + ":"));
    return line ? line.slice(name.length + 1).trim() : null;
  }

  _body(raw) {
    const idx = raw.indexOf("\r\n\r\n");
    return idx >= 0 ? raw.slice(idx + 4) : "";
  }

  _handleRaw(data) {
    try {
      const first = data.split("\r\n")[0];
      if (first.startsWith("SIP/2.0")) {
        const code = parseInt(first.split(" ")[1], 10);
        const cseqHdr = this._hdr(data, "CSeq") || "";
        const method = cseqHdr.split(" ")[1] || "";
        this._handleResponse(code, method, data);
      } else {
        const method = first.split(" ")[0];
        this._handleRequest(method, data);
      }
    } catch (_) {}
  }

  _handleResponse(code, method, raw) {
    if (method === "REGISTER") {
      if (code === 200) {
        this._registered = true;
        this._regRetryCount = 0;
        if (this._regInterval) clearInterval(this._regInterval);
        this._regInterval = setInterval(() => { if (this._registered) this._register(); }, 300000);
        this._onRegistered && this._onRegistered();
      } else if (code === 401 || code === 407) {
        this._handleDigestChallenge(code, raw, "REGISTER", "sip:" + this._domain());
      } else if (this._regRetryCount < this._regRetryMax) {
        this._regRetryCount++;
        const delay = this._regRetryDelay * Math.pow(2, this._regRetryCount - 1);
        setTimeout(() => { if (!this._registered) this._register(); }, delay);
      } else {
        this._onError && this._onError(new Error("SIP REGISTER rejected: " + code));
      }
      return;
    }

    if (method === "INVITE") {
      if (code >= 100 && code < 200) return;
      if (code === 200) {
        this._handleInvite200OK(raw);
      } else if (code === 401 || code === 407) {
        const target = "sip:" + (this._activeBridge || "") + "@" + this._domain();
        this._handleDigestChallenge(code, raw, "INVITE", target);
      } else {
        this._cleanup();
        this._callId = null;
        this._onError && this._onError(new Error("SIP INVITE failed: " + code));
      }
    }
  }

  _handleRequest(method, raw) {
    if (method === "INVITE") this._handleIncomingInvite(raw);
    if (method === "BYE") this._handleBye(raw);
  }

  async _handleInvite200OK(raw) {
    if (!this._pc) return;
    if (this._lastAck) {
      this._send(this._lastAck);
      return;
    }

    const sdp = this._body(raw);
    if (!sdp) return;
    await this._pc.setRemoteDescription({ type: "answer", sdp }).catch(() => {});
    const cseqHdr = this._hdr(raw, "CSeq") || "";
    const ackCSeq = parseInt(cseqHdr, 10) || this._inviteCSeq || 1;
    const toHdr = this._hdr(raw, "To") || "";
    const fromHdr = this._hdr(raw, "From") || "";
    const callId = this._hdr(raw, "Call-ID") || this._callId;
    const contactHdr = this._hdr(raw, "Contact") || "";
    const ackUri = contactHdr.match(/<([^>]+)>/)?.[1] || "sip:" + this._domain();
    const via = `SIP/2.0/WS ${this._domain()};branch=z9hG4bK${this._rand()};rport`;
    const ack = `ACK ${ackUri} SIP/2.0\r\nVia: ${via}\r\nMax-Forwards: 70\r\nFrom: ${fromHdr}\r\nTo: ${toHdr}\r\nCall-ID: ${callId}\r\nCSeq: ${ackCSeq} ACK\r\nContent-Length: 0\r\n\r\n`;
    this._lastAck = ack;
    this._send(ack);
  }

  async _handleIncomingInvite(raw) {
    const from = this._hdr(raw, "From") || "";
    const to = this._hdr(raw, "To") || "";
    const callId = this._hdr(raw, "Call-ID") || this._rand(16);
    const via = this._hdr(raw, "Via") || "";
    const cseq = this._hdr(raw, "CSeq") || "1 INVITE";
    const sdpOffer = this._body(raw);
    this._send(this._buildResponse(100, "Trying", from, to, callId, via, cseq));

    if (!sdpOffer) {
      this._send(this._buildResponse(400, "Bad Request", from, to, callId, via, cseq));
      return;
    }

    if (!this._pc) {
      try {
        this._localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      } catch (_) {
        this._send(this._buildResponse(486, "Busy Here", from, to, callId, via, cseq));
        return;
      }
      this._pc = new RTCPeerConnection({ iceServers: this._iceServers });
      this._pc.ontrack = (ev) => this._onAudioTrack && this._onAudioTrack(ev.streams?.[0] || null, ev.track);
      for (const t of this._localStream.getAudioTracks()) this._pc.addTrack(t, this._localStream);
    }

    const toWithTag = to + ";tag=" + this._rand(8);
    this._callId = callId;
    await this._pc.setRemoteDescription({ type: "offer", sdp: sdpOffer });
    const answer = await this._pc.createAnswer();
    await this._pc.setLocalDescription(answer);
    await this._waitICE();
    this._send(this._buildResponse(200, "OK", from, toWithTag, callId, via, cseq, this._pc.localDescription.sdp));
  }

  _handleBye(raw) {
    const from = this._hdr(raw, "From") || "";
    const to = this._hdr(raw, "To") || "";
    const callId = this._hdr(raw, "Call-ID") || "";
    const via = this._hdr(raw, "Via") || "";
    const cseq = this._hdr(raw, "CSeq") || "1 BYE";
    this._send(this._buildResponse(200, "OK", from, to, callId, via, cseq));
    this._cleanup();
    this._callId = null;
    this._onBye && this._onBye();
  }

  _handleDigestChallenge(code, raw, method, uri) {
    const hdrName = code === 401 ? "WWW-Authenticate" : "Proxy-Authenticate";
    const auth = this._hdr(raw, hdrName) || "";
    const realm = auth.match(/realm="([^"]+)"/)?.[1] || this._domain();
    const nonce = auth.match(/nonce="([^"]+)"/)?.[1] || "";
    const opaque = auth.match(/opaque="([^"]+)"/)?.[1] || "";
    const qop = auth.match(/qop="([^"]+)"/)?.[1] || "";
    const ha1 = this._md5(this._user() + ":" + realm + ":" + this._password);
    const ha2 = this._md5(method + ":" + uri);
    let resp;
    let authHeader;
    if (qop && qop.split(",").map(q => q.trim()).includes("auth")) {
      const nc = "00000001";
      const cnonce = this._rand(8);
      resp = this._md5(ha1 + ":" + nonce + ":" + nc + ":" + cnonce + ":auth:" + ha2);
      authHeader = `Digest username="${this._user()}",realm="${realm}",nonce="${nonce}",uri="${uri}",response="${resp}",algorithm=MD5,qop=auth,nc=${nc},cnonce="${cnonce}"`;
    } else {
      resp = this._md5(ha1 + ":" + nonce + ":" + ha2);
      authHeader = `Digest username="${this._user()}",realm="${realm}",nonce="${nonce}",uri="${uri}",response="${resp}",algorithm=MD5`;
    }
    if (opaque) authHeader += `,opaque="${opaque}"`;
    const authLine = (code === 401 ? "Authorization" : "Proxy-Authorization") + ": " + authHeader;

    if (method === "REGISTER") {
      this._send(this._buildRequest("REGISTER", "sip:" + this._domain(), this._regCallId, this._cseq++, "Expires: 3600\r\n" + authLine + "\r\n", "", this._uri));
    } else if (method === "INVITE") {
      const sdp = this._pc?.localDescription?.sdp || "";
      this._inviteCSeq = this._cseq;
      this._send(this._buildRequest("INVITE", uri, this._callId, this._cseq++, authLine + "\r\n", sdp));
    }
  }

  _waitICE() {
    return new Promise((resolve) => {
      if (!this._pc || this._pc.iceGatheringState === "complete") {
        resolve();
        return;
      }
      const done = () => {
        if (this._pc?.iceGatheringState === "complete") resolve();
      };
      this._pc.addEventListener("icegatheringstatechange", done);
      setTimeout(resolve, 4000);
    });
  }

  _cleanup() {
    if (this._regInterval) {
      clearInterval(this._regInterval);
      this._regInterval = null;
    }
    if (this._pc) {
      this._pc.close();
      this._pc = null;
    }
    if (this._localStream) {
      this._localStream.getTracks().forEach(t => t.stop());
      this._localStream = null;
    }
    this._lastAck = null;
    this._inviteCSeq = null;
  }

  _md5(str) {
    const add = (a, b) => ((a + b) | 0);
    const rl = (n, s) => (n << s) | (n >>> (32 - s));
    const S = [7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21];
    const K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 0x100000000) >>> 0);
    const bytes = new TextEncoder().encode(str);
    const n = bytes.length;
    const padLen = (55 - n % 64 + 64) % 64;
    const msg = new Uint8Array(n + 1 + padLen + 8);
    msg.set(bytes);
    msg[n] = 0x80;
    const dv = new DataView(msg.buffer);
    dv.setUint32(n + 1 + padLen, (n * 8) >>> 0, true);
    dv.setUint32(n + 1 + padLen + 4, Math.floor(n / 0x20000000), true);
    let a = 0x67452301, b = 0xefcdab89, c = 0x98badcfe, d = 0x10325476;
    for (let i = 0; i < msg.length; i += 64) {
      const M = Array.from({ length: 16 }, (_, j) => dv.getInt32(i + j * 4, true));
      let A = a, B = b, C = c, D = d;
      for (let j = 0; j < 64; j++) {
        let F, g;
        if (j < 16) { F = (B & C) | (~B & D); g = j; }
        else if (j < 32) { F = (D & B) | (~D & C); g = (5 * j + 1) % 16; }
        else if (j < 48) { F = B ^ C ^ D; g = (3 * j + 5) % 16; }
        else { F = C ^ (B | ~D); g = (7 * j) % 16; }
        const temp = D;
        D = C;
        C = B;
        B = add(B, rl(add(add(add(A, F), M[g]), K[j]), S[j]));
        A = temp;
      }
      a = add(a, A);
      b = add(b, B);
      c = add(c, C);
      d = add(d, D);
    }
    return [a, b, c, d].map(v =>
      [(v >>> 0) & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff]
        .map(byte => byte.toString(16).padStart(2, "0")).join("")
    ).join("");
  }
}

async function startSIPCall(bridgeId) {
  if (!bridgeId) return;
  if (_pendingSIPBridgeId === bridgeId || (_sipUA && _sipUA._activeBridge === bridgeId)) return;
  _pendingSIPBridgeId = bridgeId;

  if (_sipUA) {
    try { _sipUA.disconnect(); } catch (_) {}
    _sipUA = null;
  }

  const cfg = await fetchWebRTCConfig();
  const sip = cfg.sip || {};
  if (!sip.enabled || !sip.ws_url || !sip.username || !sip.password || !sip.domain) {
    _pendingSIPBridgeId = null;
    log("SIP bridge unavailable: configure SIP-over-WebSocket in the addon settings");
    return;
  }

  const uri = "sip:" + sip.username + "@" + sip.domain;
  _sipUA = new MinimalSIPUA({
    uri,
    password: sip.password,
    wsUrl: sip.ws_url,
    iceServers: cfg.ice_servers || FALLBACK_ICE_SERVERS,
    onAudioTrack: (stream, track) => {
      const audio = document.getElementById("remote-audio");
      if (stream) {
        audio.srcObject = stream;
      } else {
        const ms = new MediaStream();
        ms.addTrack(track);
        audio.srcObject = ms;
      }
      audio.play().catch(() => {});
    },
    onRegistered: () => {
      _sipUA._activeBridge = bridgeId;
      _pendingSIPBridgeId = null;
      _sipUA.dial(bridgeId).catch(e => {
        log("SIP dial error: " + e.message);
        cleanupSIPUA();
      });
    },
    onError: (e) => {
      log("SIP error: " + e.message);
      _pendingSIPBridgeId = null;
      cleanupSIPUA();
    },
    onBye: () => {
      cleanupSIPUA();
      if (_callId) {
        fetch(BASE + "/api/hangup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ call_id: _callId }),
        }).catch(() => {});
      }
    },
  });
  _sipUA.connect();
}

function cleanupSIPUA() {
  if (_sipUA) {
    try { _sipUA.disconnect(); } catch (_) {}
    _sipUA = null;
  }
  _pendingSIPBridgeId = null;
}

function cleanupMedia() {
  cleanupSIPUA();
  if (_pc) {
    _pc.close();
    _pc = null;
  }
  if (_localStream) {
    _localStream.getTracks().forEach(t => t.stop());
    _localStream = null;
  }
  _pendingCandidates = [];
  _pendingOffer = null;
  _muted = false;
  document.getElementById("btn-mute").textContent = "🎙 Mute";
  const audio = document.getElementById("remote-audio");
  audio.pause();
  audio.srcObject = null;
}

document.getElementById("dial-node").addEventListener("keydown", e => {
  if (e.key === "Enter") dialNode();
});

setInterval(pollStatus, 8000);
pollStatus();
loadTargets();
loadHistory();
connectSSE();
</script>
</body>
</html>"""
