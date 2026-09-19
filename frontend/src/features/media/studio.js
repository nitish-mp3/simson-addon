import { MEDIA_PREFS_KEY, mediaStudio, state } from '../../state/store.js';
import { esc, option, $ } from '../../shared/dom.js';
import { normalizeSipEndpoint } from '../../shared/endpoints.js';

export function loadMediaPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem(MEDIA_PREFS_KEY) || "{}");
    mediaStudio.selectedAudioInput = String(saved.audioInput || "");
    mediaStudio.selectedVideoInput = String(saved.videoInput || "");
    mediaStudio.selectedAudioOutput = String(saved.audioOutput || "");
    mediaStudio.videoEnabled = saved.videoEnabled !== false;
  } catch (_) {
    try { localStorage.removeItem(MEDIA_PREFS_KEY); } catch (_) { /* Browser storage is unavailable. */ }
  }
}

export function saveMediaPreferences() {
  try {
    localStorage.setItem(MEDIA_PREFS_KEY, JSON.stringify({
      audioInput: mediaStudio.selectedAudioInput,
      videoInput: mediaStudio.selectedVideoInput,
      audioOutput: mediaStudio.selectedAudioOutput,
      videoEnabled: mediaStudio.videoEnabled,
    }));
  } catch (_) { /* Browser storage may be disabled; media still works for this session. */ }
}

export function mediaDeviceLabel(device, index, fallback) {
  return device.label || `${fallback} ${index + 1}`;
}

export function mediaSelectOptions(devices, selected, fallback) {
  if (!devices.length) return `<option value="">No ${esc(fallback.toLowerCase())} detected</option>`;
  return devices.map((device, index) => option(
    device.deviceId,
    mediaDeviceLabel(device, index, fallback),
    selected || devices[0]?.deviceId,
  )).join("");
}

export function browserMediaSupport() {
  return Boolean(navigator.mediaDevices?.getUserMedia && navigator.mediaDevices?.enumerateDevices);
}

export function videoCapableSipEndpoints() {
  return state.sip
    .map(normalizeSipEndpoint)
    .filter((endpoint) => endpoint && endpoint.enabled !== false && endpoint.video_enabled);
}

export function renderMediaStudio() {
  const supported = browserMediaSupport();
  const secure = window.isSecureContext;
  const cameras = videoCapableSipEndpoints();
  const previewing = Boolean(mediaStudio.previewStream);
  const hasPreviewVideo = Boolean(mediaStudio.previewStream?.getVideoTracks?.().length);
  const permissionLabel = mediaStudio.permission === "granted"
    ? "Devices ready"
    : mediaStudio.permission === "denied"
      ? "Permission blocked"
      : "Permission required";

  $("content").innerHTML = `
    <section class="media-hero">
      <div class="media-hero-copy">
        <span class="eyebrow">Realtime media</span>
        <h2>Look and sound ready.</h2>
        <p>Check your camera and microphone before a conversation. This private preview stays in the addon. Choose the devices used for calls in the dashboard card’s Devices tab.</p>
        <div class="media-status-row">
          <span class="media-status ${mediaStudio.permission}"><i></i>${esc(permissionLabel)}</span>
          <span class="media-status ${secure ? "granted" : "denied"}"><i></i>${secure ? "Secure context" : "HTTPS required"}</span>
          <span class="media-status neutral"><i></i>${mediaStudio.videoInputs.length} camera${mediaStudio.videoInputs.length === 1 ? "" : "s"}</span>
        </div>
      </div>
      <div class="media-orb" aria-hidden="true"><span></span><b>SIMSON</b></div>
    </section>

    ${mediaStudio.error ? `<div class="inline-notice error"><div><b>Media setup needs attention</b><span>${esc(mediaStudio.error)}</span></div></div>` : ""}
    ${!supported ? `<div class="inline-notice error"><div><b>Browser media is unavailable</b><span>Open this panel in a current Chrome, Edge, Safari, or Firefox browser.</span></div></div>` : ""}

    <div class="media-layout">
      <section class="media-stage-card">
        <div class="media-stage" data-empty="${hasPreviewVideo ? "false" : "true"}">
          <video id="media-preview" autoplay muted playsinline></video>
          <div class="media-stage-empty">
            <span class="media-camera-glyph">◉</span>
            <strong>${mediaStudio.permission === "granted" ? "Camera ready" : "Preview your camera"}</strong>
            <small>Your preview remains inside this browser.</small>
          </div>
          <div class="media-stage-topline">
            <span class="live-chip">${previewing ? "LIVE PREVIEW" : "PRIVATE PREVIEW"}</span>
            <span>${esc(mediaStudio.videoInputs.find((item) => item.deviceId === mediaStudio.selectedVideoInput)?.label || "Default camera")}</span>
          </div>
        </div>
        <div class="media-stage-actions">
          <button class="btn" data-action="${previewing ? "media-stop" : "media-preview"}" ${!supported || !secure ? "disabled" : ""}>${previewing ? "Stop preview" : "Start preview"}</button>
          <button class="btn secondary" data-action="media-detect" ${!supported || !secure ? "disabled" : ""}>Detect devices</button>
          <div class="mic-meter" aria-label="Microphone level"><span id="media-meter"></span></div>
        </div>
      </section>

      <section class="card media-controls-card">
        <div class="card-title">Browser call devices</div>
        <div class="card-sub">Device names appear after browser permission is granted.</div>
        <label class="media-toggle">
          <span><b>Include camera in preview</b><small>Audio-only fallback remains automatic.</small></span>
          <input id="media-video-enabled" type="checkbox" ${mediaStudio.videoEnabled ? "checked" : ""}>
        </label>
        <label class="field media-field"><span>Microphone</span>
          <select id="media-audio-input">${mediaSelectOptions(mediaStudio.audioInputs, mediaStudio.selectedAudioInput, "Microphone")}</select>
        </label>
        <label class="field media-field"><span>Camera</span>
          <select id="media-video-input" ${mediaStudio.videoEnabled ? "" : "disabled"}>${mediaSelectOptions(mediaStudio.videoInputs, mediaStudio.selectedVideoInput, "Camera")}</select>
        </label>
        <label class="field media-field"><span>Speaker</span>
          <select id="media-audio-output">${mediaSelectOptions(mediaStudio.audioOutputs, mediaStudio.selectedAudioOutput, "Speaker")}</select>
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
        ${cameras.length ? cameras.map((endpoint) => `
          <article class="lan-camera-item">
            <div class="lan-camera-icon">▣</div>
            <div><b>${esc(endpoint.description || endpoint.extension)}</b><span>Extension ${esc(endpoint.extension)} · H.264</span></div>
            <em>${endpoint.registered ? "Online" : "Configured"}</em>
          </article>`).join("") : `
          <div class="lan-camera-empty"><b>No LAN video endpoints yet</b><span>Add your camera from SIP Phones to see it here. Network cameras need to be provisioned before they can be used.</span></div>`}
      </div>
    </section>
  `;
  attachMediaPreview();
}

export async function detectMediaDevices() {
  if (!browserMediaSupport()) throw new Error("This browser does not support camera or microphone discovery.");
  if (!window.isSecureContext) throw new Error("Camera and microphone access requires HTTPS or localhost.");
  mediaStudio.error = "";
  let probe = null;
  try {
    try {
      probe = await navigator.mediaDevices.getUserMedia({ audio: true, video: mediaStudio.videoEnabled });
    } catch (error) {
      if (!mediaStudio.videoEnabled) throw error;
      probe = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      mediaStudio.error = "Camera permission was not granted. Audio remains available.";
    }
    mediaStudio.permission = "granted";
    const devices = await navigator.mediaDevices.enumerateDevices();
    mediaStudio.audioInputs = devices.filter((device) => device.kind === "audioinput");
    mediaStudio.videoInputs = devices.filter((device) => device.kind === "videoinput");
    mediaStudio.audioOutputs = devices.filter((device) => device.kind === "audiooutput");
    if (!mediaStudio.audioInputs.some((item) => item.deviceId === mediaStudio.selectedAudioInput)) {
      mediaStudio.selectedAudioInput = mediaStudio.audioInputs[0]?.deviceId || "";
    }
    if (!mediaStudio.videoInputs.some((item) => item.deviceId === mediaStudio.selectedVideoInput)) {
      mediaStudio.selectedVideoInput = mediaStudio.videoInputs[0]?.deviceId || "";
    }
    if (!mediaStudio.audioOutputs.some((item) => item.deviceId === mediaStudio.selectedAudioOutput)) {
      mediaStudio.selectedAudioOutput = mediaStudio.audioOutputs[0]?.deviceId || "";
    }
    saveMediaPreferences();
  } catch (error) {
    mediaStudio.permission = error?.name === "NotAllowedError" ? "denied" : "prompt";
    mediaStudio.error = error?.message || "Could not access browser media devices.";
  } finally {
    probe?.getTracks().forEach((track) => track.stop());
  }
  if (state.page === 'media') renderMediaStudio();
}

export function mediaConstraints() {
  const audio = mediaStudio.selectedAudioInput
    ? { deviceId: { exact: mediaStudio.selectedAudioInput }, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    : { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
  const video = !mediaStudio.videoEnabled ? false : mediaStudio.selectedVideoInput
    ? { deviceId: { exact: mediaStudio.selectedVideoInput }, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 24, max: 30 } }
    : { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 24, max: 30 } };
  return { audio, video };
}

export async function startMediaPreview() {
  stopMediaPreview(false);
  const generation = mediaStudio.previewGeneration;
  if (mediaStudio.permission !== "granted") await detectMediaDevices();
  if (generation !== mediaStudio.previewGeneration || state.page !== 'media') return;
  try {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(mediaConstraints());
    } catch (error) {
      if (!mediaStudio.videoEnabled) throw error;
      stream = await navigator.mediaDevices.getUserMedia({ ...mediaConstraints(), video: false });
      mediaStudio.error = "The selected camera is unavailable. Microphone preview is still active.";
    }
    if (generation !== mediaStudio.previewGeneration || state.page !== 'media') {
      stream.getTracks().forEach(track => track.stop());
      return;
    }
    mediaStudio.previewStream = stream;
    if (stream.getVideoTracks().length) mediaStudio.error = "";
    renderMediaStudio();
    startMicrophoneMeter(mediaStudio.previewStream);
  } catch (error) {
    mediaStudio.error = error?.message || "Could not start the selected media devices.";
    renderMediaStudio();
  }
}

export function attachMediaPreview() {
  const video = $("media-preview");
  if (!video || !mediaStudio.previewStream) return;
  if (video.srcObject !== mediaStudio.previewStream) video.srcObject = mediaStudio.previewStream;
  video.play().catch(() => {});
}

export function stopMediaPreview(renderPage = true) {
  mediaStudio.previewGeneration = (mediaStudio.previewGeneration || 0) + 1;
  if (mediaStudio.analyserFrame) cancelAnimationFrame(mediaStudio.analyserFrame);
  mediaStudio.analyserFrame = 0;
  mediaStudio.analyserContext?.close().catch(() => {});
  mediaStudio.analyserContext = null;
  mediaStudio.previewStream?.getTracks().forEach((track) => track.stop());
  mediaStudio.previewStream = null;
  if (renderPage && state.page === "media") renderMediaStudio();
}

export function startMicrophoneMeter(stream) {
  const audioTrack = stream?.getAudioTracks?.()[0];
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!audioTrack || !AudioContextClass) return;
  const context = new AudioContextClass();
  const analyser = context.createAnalyser();
  analyser.fftSize = 256;
  context.createMediaStreamSource(new MediaStream([audioTrack])).connect(analyser);
  const samples = new Uint8Array(analyser.frequencyBinCount);
  mediaStudio.analyserContext = context;
  const tick = () => {
    analyser.getByteFrequencyData(samples);
    const average = samples.reduce((sum, value) => sum + value, 0) / samples.length;
    const meter = $("media-meter");
    if (meter) meter.style.width = `${Math.min(100, Math.max(4, average * 1.7))}%`;
    mediaStudio.analyserFrame = requestAnimationFrame(tick);
  };
  tick();
}
