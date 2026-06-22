"""Configuration loader.

Split into two tiers:
  1. Minimal HA addon options (/data/options.json, written by Supervisor):
       server_url, admin_token, log_level
  2. In-addon settings (/data/settings.json, managed by the built-in Settings UI):
       asterisk, webrtc/TURN/SIP, call_targets, local_api_port

Node credentials (account_id, node_id, install_token) live exclusively in
/data/credentials.json managed by the setup wizard / auto-provisioner and are
never read from options.json to prevent stale values causing auth failures.
"""

import json
import logging
import os

from provisioner import load_saved_credentials
from settings import load_settings

OPTIONS_FILE = "/data/options.json"

logger = logging.getLogger("simson.config")


def _safe_int(value, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _load_options() -> dict:
    """Load addon options written by HA Supervisor before container start."""
    try:
        with open(OPTIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


class Config:
    """Addon configuration.

    Tier-1 options (server_url, admin_token, log_level) come from
    /data/options.json set via the HA addon Configuration tab.

    Tier-2 settings (asterisk, webrtc, call_targets, local_api_port) come from
    /data/settings.json managed entirely through the built-in Settings UI.
    Environment variable overrides are still honoured for headless/CI deployments.

    Node credentials (account_id, node_id, install_token) come ONLY from
    /data/credentials.json so the addon config UI cannot accidentally corrupt them.
    """

    def __init__(self):
        opts = _load_options()
        s = load_settings()  # /data/settings.json — may not exist yet

        # ── Tier-1: minimal addon options ─────────────────────────────────
        self.server_url: str = opts.get("server_url", os.environ.get("SIMSON_SERVER_URL", ""))
        self.admin_token: str = opts.get("admin_token", os.environ.get("SIMSON_ADMIN_TOKEN", ""))
        self.log_level: str = opts.get("log_level", os.environ.get("SIMSON_LOG_LEVEL", "info")).upper()

        # ── Node credentials (/data/credentials.json ONLY) ────────────────
        self.account_id: str = ""
        self.node_id: str = ""
        self.install_token: str = ""
        self.node_label: str = ""
        self.capabilities: list[str] = ["haos", "voice"]

        saved = load_saved_credentials()
        if saved:
            self.account_id = saved["account_id"]
            self.node_id = saved["node_id"]
            self.install_token = saved["install_token"]
            self.node_label = saved.get("node_label", "")
            if saved.get("capabilities"):
                self.capabilities = saved["capabilities"]

        # ── Tier-2: settings managed via the in-addon UI ──────────────────
        # Asterisk AMI
        ast = s.get("asterisk", {})
        self.asterisk_enabled: bool = ast.get(
            "enabled",
            os.environ.get("SIMSON_ASTERISK_ENABLED", "false").lower() in ("true", "1", "yes"),
        )
        self.asterisk_host: str = ast.get("host", os.environ.get("SIMSON_ASTERISK_HOST", "127.0.0.1"))
        self.asterisk_ami_port: int = _safe_int(
            ast.get("ami_port", os.environ.get("SIMSON_ASTERISK_AMI_PORT", 5038)),
            5038,
            1,
            65535,
        )
        self.asterisk_ami_user: str = ast.get(
            "ami_user", os.environ.get("SIMSON_ASTERISK_AMI_USER", "simson")
        )
        self.asterisk_ami_secret: str = ast.get(
            "ami_secret", os.environ.get("SIMSON_ASTERISK_AMI_SECRET", "")
        )
        self.asterisk_context: str = ast.get(
            "context", os.environ.get("SIMSON_ASTERISK_CONTEXT", "from-simson")
        )
        self.asterisk_ext_prefix: str = ast.get(
            "extension_prefix", os.environ.get("SIMSON_ASTERISK_EXT_PREFIX", "9")
        )
        self.asterisk_auto_configure: bool = ast.get(
            "auto_configure",
            os.environ.get("SIMSON_ASTERISK_AUTO_CONFIGURE", "false").lower() in ("true", "1", "yes"),
        )

        # Local API / ingress port
        self.local_api_port: int = _safe_int(
            s.get("local_api_port", os.environ.get("SIMSON_LOCAL_API_PORT", 8799)),
            8799,
            1,
            65535,
        )

        # WebRTC / ICE / TURN / SIP
        wrtc = s.get("webrtc", {})
        self.turn_enabled: bool = wrtc.get(
            "turn_enabled",
            os.environ.get("SIMSON_TURN_ENABLED", "false").lower() in ("true", "1", "yes"),
        )
        self.turn_url: str = wrtc.get("turn_url", os.environ.get("SIMSON_TURN_URL", ""))
        self.turn_username: str = wrtc.get(
            "turn_username", os.environ.get("SIMSON_TURN_USERNAME", "simson")
        )
        self.turn_credential: str = wrtc.get(
            "turn_credential", os.environ.get("SIMSON_TURN_CREDENTIAL", "")
        )
        # SIP-over-WebSocket for browser ↔ Asterisk ConfBridge audio
        self.sip_enabled: bool = wrtc.get(
            "sip_enabled",
            os.environ.get("SIMSON_SIP_ENABLED", "false").lower() in ("true", "1", "yes"),
        )
        self.sip_ws_url: str = wrtc.get("sip_ws_url", os.environ.get("SIMSON_SIP_WS_URL", ""))
        self.sip_username: str = wrtc.get(
            "sip_username", os.environ.get("SIMSON_SIP_USERNAME", "webrtc-pool")
        )
        self.sip_password: str = wrtc.get("sip_password", os.environ.get("SIMSON_SIP_PASSWORD", ""))
        self.sip_domain: str = wrtc.get("sip_domain", os.environ.get("SIMSON_SIP_DOMAIN", ""))

        # Per-site routing policy and manual availability controls.
        routing = s.get("routing", {})
        self.routing_policy: dict = {
            "strategy": routing.get("strategy", "priority"),
            "ring_seconds": _safe_int(routing.get("ring_seconds", 25), 25, 5, 300),
            "max_attempts": _safe_int(routing.get("max_attempts", 4), 4, 1, 10),
            "skip_unavailable": bool(routing.get("skip_unavailable", True)),
            "final_fallback_target": routing.get("final_fallback_target", ""),
            "gateway_inbound_mode": routing.get("gateway_inbound_mode", "haos_then_fallback"),
            "gateway_direct_target": routing.get("gateway_direct_target", ""),
            "default_gateway_trunk": routing.get("default_gateway_trunk", ""),
        }
        availability = s.get("availability", {})
        self.availability: dict = {
            "mode": availability.get("mode", "available"),
            "reason": availability.get("reason", ""),
        }
        self.route_overrides: dict = s.get("route_overrides", {}) or {}
        automation = s.get("automation", {}) or {}
        self.automation: dict = {
            "webhook_enabled": bool(automation.get("webhook_enabled", False)),
            "webhook_id": str(automation.get("webhook_id", "")).strip(),
            "webhook_secret": str(automation.get("webhook_secret", "")).strip(),
            "cooldown_seconds": _safe_int(automation.get("cooldown_seconds", 90), 90, 1, 3600),
            "block_while_call_active": bool(automation.get("block_while_call_active", True)),
            "persistent_notifications": bool(automation.get("persistent_notifications", True)),
            "notify_services": str(automation.get("notify_services", "")).strip(),
            "dashboard_path": str(automation.get("dashboard_path", "/lovelace/default_view")).strip(),
            "triggers": automation.get("triggers", []) or [],
        }

        # Call targets — normalised list stored in settings.json
        self.call_targets: list[dict] = []
        for t in s.get("call_targets", []):
            self.call_targets.append({
                "type": t.get("type", "node"),
                "id": t.get("id", ""),
                "label": t.get("label", t.get("id", "")),
                "node_id": t.get("node_id", ""),
                "extension": t.get("extension", ""),
                "context": t.get("context", self.asterisk_context),
                "trunk": t.get("trunk", ""),
                "caller_id": t.get("caller_id", ""),
                "timeout": _safe_int(
                    t.get("timeout", self.routing_policy["ring_seconds"]),
                    self.routing_policy["ring_seconds"],
                    5,
                    300,
                ),
                "fallback_targets": t.get("fallback_targets", []),
                "icon": t.get("icon", ""),
            })

        # HA Supervisor token (always from env — never in options.json)
        self.supervisor_token: str = os.environ.get("SUPERVISOR_TOKEN", "")

    def needs_provisioning(self) -> bool:
        """True if credentials are missing but admin_token is available."""
        return bool(self.admin_token) and not self.install_token

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        errors = []
        if not self.server_url:
            errors.append("server_url is required")
        if self.server_url and not self.server_url.startswith(("ws://", "wss://")):
            errors.append("server_url must start with ws:// or wss://")
        # Credentials can be missing if we have an admin_token (auto-provision).
        if not self.needs_provisioning():
            if not self.account_id:
                errors.append("No credentials found. Open the Simson panel and complete setup.")
            if not self.node_id:
                errors.append("node_id missing — open the Simson panel to set up this node.")
            if not self.install_token:
                errors.append("install_token missing — open the Simson panel to set up this node.")
        if self.asterisk_enabled and not self.asterisk_ami_secret:
            errors.append("asterisk ami_secret is required when asterisk is enabled")
        return errors
