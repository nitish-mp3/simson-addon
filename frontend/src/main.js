import { state, LIVE_STATUS_POLL_MS, mediaStudio } from './state/store.js';
import { loadMediaPreferences, renderMediaStudio } from './features/media/studio.js';
import { shell, render } from './app/shell.js';
import { refresh, refreshLiveStatus } from './services/sync.js';
import { setSaveState } from './shared/feedback.js';

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

loadMediaPreferences();

shell();

render();

refresh().catch((err) => {
  setSaveState(err.message || "Could not load dashboard", "bad");
  render();
});

setInterval(refreshLiveStatus, LIVE_STATUS_POLL_MS);

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshLiveStatus();
});

navigator.mediaDevices?.addEventListener?.("devicechange", async () => {
  if (mediaStudio.permission !== "granted") return;
  const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
  mediaStudio.audioInputs = devices.filter((device) => device.kind === "audioinput");
  mediaStudio.videoInputs = devices.filter((device) => device.kind === "videoinput");
  mediaStudio.audioOutputs = devices.filter((device) => device.kind === "audiooutput");
  if (state.page === "media") renderMediaStudio();
});
