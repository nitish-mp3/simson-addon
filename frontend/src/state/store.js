export const boot = window.__SIMSON__ || {};

export const LIVE_STATUS_POLL_MS = 2000;

export const MEDIA_PREFS_KEY = "simson.media.preferences.v1";

export const mediaStudio = {
  audioInputs: [],
  videoInputs: [],
  audioOutputs: [],
  selectedAudioInput: "",
  selectedVideoInput: "",
  selectedAudioOutput: "",
  videoEnabled: true,
  permission: "prompt",
  error: "",
  previewStream: null,
  analyserContext: null,
  analyserFrame: 0,
};

export const state = {
  page: "overview",
  status: null,
  settings: null,
  nodes: [],
  sip: [],
  routing: null,
  advancedRoutes: [],
  advancedRoutesError: "",
  callFeatures: {
    transfer_code: "*84",
    conference_code: "*85",
    invite_listen_code: "*86",
    invite_whisper_code: "*87",
    invite_barge_code: "*88",
    enabled: true,
  },
  callFeaturesError: "",
  activeInvite: {
    source_extension: "",
    target: "",
    mode: "barge",
  },
  notificationTargets: [],
  notificationTargetsError: "",
  notificationPickerOpen: false,
  health: null,
  advancedDraft: null,
  navOpen: false,
  dirty: false,
  loaded: false,
  selectedDoorTriggerId: "",
  phoneProvisioning: {
    enabled: false,
    sessionId: "",
    slots: [],
    selectedSlot: "",
    deviceName: "",
    phoneIp: "",
  },
};

export const defaults = {
  local_api_port: 8799,
  routing: {
    strategy: "priority",
    ring_seconds: 25,
    max_attempts: 4,
    skip_unavailable: true,
    final_fallback_target: "",
    gateway_inbound_mode: "haos_then_fallback",
    gateway_direct_target: "",
    default_gateway_trunk: "",
  },
  availability: { mode: "available", reason: "" },
  route_overrides: {},
  call_targets: [],
  automation: {
    webhook_enabled: false,
    webhook_id: "",
    webhook_secret: "",
    cooldown_seconds: 90,
    block_while_call_active: true,
    persistent_notifications: true,
    notify_services: "",
    dashboard_path: "/lovelace/default_view",
    triggers: [],
  },
};

export const pages = [
  ["overview", "Overview", "Live health"],
  ["routing", "Routing", "Targets and fallback"],
  ["sip", "SIP Phones", "Extensions and video"],
  ["media", "Media Studio", "Camera and microphone"],
  ["automation", "Door Automation", "Webhooks and cooldowns"],
  ["advanced", "Advanced", "Raw settings"],
];

