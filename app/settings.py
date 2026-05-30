"""Settings manager — loads/saves user-configurable settings to /data/settings.json.

These settings supplement the minimal addon options (server_url, admin_token, log_level)
and are managed entirely through the built-in Settings UI rather than the HA addon
configuration tab.  Separating them from options.json means users never have to
touch YAML for Asterisk, TURN, SIP, or call-target changes.
"""

import copy
import json
import logging
import os
import re

logger = logging.getLogger("simson.settings")

SETTINGS_FILE = "/data/settings.json"
ASTERISK_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Canonical defaults — every key that the UI and Config class expect must
# appear here so a missing or partial settings.json always yields a safe result.
DEFAULT_SETTINGS: dict = {
    "local_api_port": 8799,
    "asterisk": {
        "enabled": False,
        "host": "127.0.0.1",
        "ami_port": 5038,
        "ami_user": "simson",
        "ami_secret": "",
        "context": "from-simson",
        "extension_prefix": "9",
        "auto_configure": False,
    },
    "webrtc": {
        "turn_enabled": False,
        "turn_url": "",
        "turn_username": "simson",
        "turn_credential": "",
        "sip_enabled": False,
        "sip_ws_url": "",
        "sip_username": "webrtc-pool",
        "sip_password": "",
        "sip_domain": "",
    },
    "routing": {
        "strategy": "priority",
        "ring_seconds": 25,
        "max_attempts": 4,
        "skip_unavailable": True,
        "final_fallback_target": "",
    },
    "availability": {
        "mode": "available",
        "reason": "",
    },
    "route_overrides": {},
    "call_targets": [],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict that is *override* merged on top of *base* recursively."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    """Return the current settings, deep-merged over defaults.

    Always returns a complete dict — missing keys fall back to DEFAULT_SETTINGS.
    Never raises; logs and returns defaults on parse failure.
    """
    if not os.path.isfile(SETTINGS_FILE):
        logger.debug("No settings file found — using defaults (%s)", SETTINGS_FILE)
        return copy.deepcopy(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            stored = json.load(f)
        if not isinstance(stored, dict):
            raise ValueError("settings file must contain a JSON object")
        merged = _deep_merge(DEFAULT_SETTINGS, stored)
        logger.debug("Loaded settings from %s", SETTINGS_FILE)
        return merged
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "Could not read settings file (%s): %s — using defaults", SETTINGS_FILE, exc
        )
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(data: dict) -> None:
    """Persist *data* to /data/settings.json atomically.

    Merges with defaults first so the file always contains a complete snapshot.
    Raises OSError on write failure.
    """
    full = _deep_merge(DEFAULT_SETTINGS, data)
    os.makedirs(os.path.dirname(SETTINGS_FILE) or ".", exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)
        try:
            os.chmod(SETTINGS_FILE, 0o600)
        except OSError:
            pass
        logger.info("Settings saved to %s", SETTINGS_FILE)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def validate_settings(data: dict) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    errors: list[str] = []

    # ── Port ────────────────────────────────────────────────────────────────
    try:
        port = int(data.get("local_api_port", 8799))
        if not 1024 <= port <= 65535:
            errors.append("Local API port must be between 1024 and 65535")
    except (TypeError, ValueError):
        errors.append("Local API port must be a valid integer")

    # ── Asterisk ────────────────────────────────────────────────────────────
    ast = data.get("asterisk") or {}
    if ast.get("enabled"):
        if not str(ast.get("ami_secret", "")).strip():
            errors.append("Asterisk: AMI secret is required when Asterisk is enabled")
        try:
            ami_port = int(ast.get("ami_port", 5038))
            if not 1 <= ami_port <= 65535:
                errors.append("Asterisk: AMI port must be between 1 and 65535")
        except (TypeError, ValueError):
            errors.append("Asterisk: AMI port must be a valid integer")

    # ── WebRTC / TURN ───────────────────────────────────────────────────────
    wrtc = data.get("webrtc") or {}
    if wrtc.get("turn_enabled") and not str(wrtc.get("turn_url", "")).strip():
        errors.append("TURN: URL is required when TURN relay is enabled")
    if wrtc.get("sip_enabled"):
        if not str(wrtc.get("sip_ws_url", "")).strip():
            errors.append("SIP: WebSocket URL is required when SIP-over-WebSocket is enabled")
        if not str(wrtc.get("sip_password", "")).strip():
            errors.append("SIP: password is required when SIP-over-WebSocket is enabled")
        if not str(wrtc.get("sip_domain", "")).strip():
            errors.append("SIP: domain is required when SIP-over-WebSocket is enabled")

    # ── Routing policy / availability ─────────────────────────────────────
    routing = data.get("routing") or {}
    strategy = str(routing.get("strategy", "priority")).strip() or "priority"
    if strategy not in ("priority", "round_robin"):
        errors.append("Routing: strategy must be priority or round_robin")
    try:
        ring_seconds = int(routing.get("ring_seconds", 25))
        if not 5 <= ring_seconds <= 300:
            errors.append("Routing: ring seconds must be between 5 and 300")
    except (TypeError, ValueError):
        errors.append("Routing: ring seconds must be a valid integer")
    try:
        max_attempts = int(routing.get("max_attempts", 4))
        if not 1 <= max_attempts <= 20:
            errors.append("Routing: max attempts must be between 1 and 20")
    except (TypeError, ValueError):
        errors.append("Routing: max attempts must be a valid integer")

    availability = data.get("availability") or {}
    if str(availability.get("mode", "available")).strip() not in ("available", "busy", "offline"):
        errors.append("Availability: this site must be available, busy, or offline")

    overrides = data.get("route_overrides") or {}
    if not isinstance(overrides, dict):
        errors.append("Routing: route overrides must be an object")
    else:
        for key, value in overrides.items():
            if not str(key).strip():
                errors.append("Routing: route override ids cannot be empty")
                break
            if not isinstance(value, dict):
                errors.append(f"Routing: override '{key}' must be an object")
                break
            if str(value.get("mode", "available")).strip() not in ("available", "busy", "offline"):
                errors.append(f"Routing: override '{key}' must be available, busy, or offline")
                break

    # ── Call targets ────────────────────────────────────────────────────────
    seen_ids: set[str] = set()
    for idx, target in enumerate(data.get("call_targets") or [], start=1):
        tid = str(target.get("id", "")).strip()
        if not tid:
            errors.append(f"Call target #{idx}: id is required")
        elif tid in seen_ids:
            errors.append(f"Call target #{idx}: duplicate id '{tid}'")
        else:
            seen_ids.add(tid)
        if not str(target.get("label", "")).strip():
            errors.append(f"Call target #{idx}: label is required")
        target_type = str(target.get("type", "node")).strip()
        if target_type not in ("node", "device", "asterisk", "sip", "gateway", "queue"):
            errors.append(
                f"Call target #{idx}: type must be node, sip, gateway, device, queue, or asterisk"
            )
        if target_type in ("asterisk", "sip", "gateway") and not str(target.get("extension", "")).strip():
            errors.append(f"Call target #{idx}: SIP extension/number is required")
        if target_type == "gateway" and not str(target.get("trunk", "")).strip():
            errors.append(f"Call target #{idx}: gateway/trunk is required for outside-number routes")
        if target_type in ("node", "device") and not str(target.get("node_id", "")).strip():
            errors.append(f"Call target #{idx}: HAOS node ID is required")
        trunk = str(target.get("trunk", "")).strip()
        if trunk and not ASTERISK_NAME_RE.match(trunk):
            errors.append(
                f"Call target #{idx}: trunk may only contain letters, numbers, dash, and underscore"
            )
        fallbacks = target.get("fallback_targets") or []
        if not isinstance(fallbacks, list):
            errors.append(f"Call target #{idx}: fallback target IDs must be a list")
        else:
            for fallback_id in fallbacks:
                if not str(fallback_id).strip():
                    errors.append(f"Call target #{idx}: fallback target IDs cannot be empty")
                    break
                if str(fallback_id).strip() == tid:
                    errors.append(f"Call target #{idx}: fallback target cannot point to itself")
                    break
        try:
            to = int(target.get("timeout", 30))
            if not 5 <= to <= 300:
                errors.append(f"Call target #{idx}: timeout must be 5–300 seconds")
        except (TypeError, ValueError):
            errors.append(f"Call target #{idx}: timeout must be a valid integer")

    return errors
