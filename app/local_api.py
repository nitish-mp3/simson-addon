"""Local HTTP API — exposed via HA ingress for the integration to talk to."""

import asyncio
import copy
import hmac
import json
import logging
import os
import time
from urllib.parse import urlsplit, urlunsplit
from aiohttp import ClientSession, ClientTimeout, web

from call_manager import CallManager, CallState, RoutingIntent
from config import Config
from protocol import make_call_request, make_call_accept, make_call_reject, make_call_end, make_call_transfer, make_webrtc_signal
from provisioner import auto_provision, clear_saved_credentials, save_credentials
from phone_provisioning import PhoneProvisioningService, ProvisioningError
from settings import load_settings, save_settings, validate_settings
from settings_ui import INGRESS_UI_HTML
from target_directory import TargetDirectory

ADDON_VERSION = "4.9.6"
DEFAULT_PSTN_TRUNK = "7009"


def _safe_upstream_error(status: int, body: str, feature: str) -> dict:
    """Return a bounded, actionable error without leaking an HTML proxy page."""
    text = str(body or "").strip()
    content = text.lower()
    if status == 404 and feature == "advanced routing":
        return {
            "error": "Advanced routing is unavailable on the connected VPS. Deploy the matching Simson VPS build, then retry.",
            "code": "advanced_routes_unavailable",
            "upstream_status": status,
        }
    if "<!doctype html" in content or "<html" in content or "cloudflare" in content:
        return {
            "error": f"{feature.capitalize()} service is temporarily unavailable (HTTP {status}). Check the addon/VPS service and retry.",
            "code": "upstream_proxy_error",
            "upstream_status": status,
        }
    try:
        parsed = json.loads(text) if text else {}
    except (TypeError, ValueError):
        parsed = {}
    if isinstance(parsed, dict):
        message = str(parsed.get("error") or parsed.get("message") or "").strip()
        code = str(parsed.get("code") or "").strip()
        if message:
            result = {"error": message[:500], "upstream_status": status}
            if code:
                result["code"] = code[:100]
            return result
    return {
        "error": (text[:500] if text else f"{feature.capitalize()} request failed with HTTP {status}"),
        "code": "upstream_request_failed",
        "upstream_status": status,
    }


def _normalize_call_duration_rules(value) -> dict[str, int]:
    """Normalize the VPS JSON/object representation for the ingress UI."""
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, ValueError):
            value = {}
    if not isinstance(value, dict):
        return {}

    rules: dict[str, int] = {}
    for source, seconds in value.items():
        source_ext = str(source or "").strip()
        try:
            duration = int(seconds)
        except (TypeError, ValueError):
            continue
        if source_ext and 1 <= duration <= 86400:
            rules[source_ext] = duration
    return rules


def _normalized_prompt_text(value) -> str:
    """Mirror the VPS prompt normalization for reliable save verification."""
    return " ".join(str(value or "").split())


def _normalize_supervision(value) -> dict:
    """Normalize the per-supervisor policy returned by current or legacy VPS builds."""
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, ValueError):
            value = {}
    if not isinstance(value, dict):
        value = {}
    targets = value.get("targets", value.get("Targets", []))
    if not isinstance(targets, list):
        targets = []
    return {
        "enabled": bool(value.get("enabled", value.get("Enabled", False))),
        "listen": bool(value.get("listen", value.get("Listen", False))),
        "listen_key": str(value.get("listen_key", value.get("ListenKey", "*81")) or "*81").strip(),
        "whisper": bool(value.get("whisper", value.get("Whisper", False))),
        "whisper_key": str(value.get("whisper_key", value.get("WhisperKey", "*82")) or "*82").strip(),
        "barge": bool(value.get("barge", value.get("Barge", False))),
        "barge_key": str(value.get("barge_key", value.get("BargeKey", "*83")) or "*83").strip(),
        "targets": sorted({str(item or "").strip() for item in targets if str(item or "").strip()}),
    }


def _verify_sip_call_behavior_response(endpoint: dict, requested: dict) -> str:
    """Reject successful responses from an older VPS that ignored new fields."""
    if not isinstance(endpoint, dict):
        return "VPS returned an invalid SIP device after saving"

    checks = (
        ("pre_ring_announcement_text", "PreRingAnnouncementText"),
        ("answer_announcement_text", "AnswerAnnouncementText"),
    )
    for snake_key, legacy_key in checks:
        if snake_key not in requested:
            continue
        if snake_key not in endpoint and legacy_key not in endpoint:
            return (
                "The VPS SIP call-behavior API is outdated and ignored the new prompt settings. "
                f"Deploy the VPS server that matches addon version {ADDON_VERSION}, then save again."
            )
        actual = endpoint.get(snake_key, endpoint.get(legacy_key, ""))
        if _normalized_prompt_text(actual) != _normalized_prompt_text(requested.get(snake_key, "")):
            return f"VPS did not persist {snake_key.replace('_', ' ')}; no settings were reported as saved"

    if "call_duration_rules" in requested:
        if "call_duration_rules" not in endpoint and "CallDurationRules" not in endpoint:
            return (
                "The VPS SIP call-behavior API is outdated and ignored route call limits. "
                f"Deploy the VPS server that matches addon version {ADDON_VERSION}, then save again."
            )
        actual_rules = _normalize_call_duration_rules(
            endpoint.get("call_duration_rules", endpoint.get("CallDurationRules", {}))
        )
        expected_rules = _normalize_call_duration_rules(requested.get("call_duration_rules", {}))
        if actual_rules != expected_rules:
            return "VPS did not persist the route-specific connected call limits; no settings were reported as saved"

    if "supervision" in requested:
        if "supervision" not in endpoint and "Supervision" not in endpoint:
            return (
                "The VPS SIP API is outdated and ignored supervisor permissions. "
                f"Deploy the VPS server that matches addon version {ADDON_VERSION}, then save again."
            )
        actual_supervision = _normalize_supervision(endpoint.get("supervision", endpoint.get("Supervision", {})))
        expected_supervision = _normalize_supervision(requested.get("supervision", {}))
        if actual_supervision != expected_supervision:
            return "VPS did not persist the supervisor permissions; no settings were reported as saved"

    return ""


def _is_gateway_trunk(trunk: str) -> bool:
    """Return true for Synway/ATA style GSM/PSTN trunks.

    7009 was the first production GSM trunk, but every site can add its own
    70xx gateway endpoint.  Treat them consistently so a new trunk like 7010
    does not dial a different number format than the known-good gateway.
    """
    value = str(trunk or "").strip()
    digits = "".join(ch for ch in value if ch.isdigit())
    return (
        value == DEFAULT_PSTN_TRUNK
        or (digits == value and digits.startswith("70") and 3 <= len(digits) <= 8)
    )


def _normalize_pstn_digits(digits: str, trunk: str) -> str:
    """Normalize numbers for the current GSM gateway trunk.

    Synway's GSM port dials plain digits; for Indian mobile callbacks, sending
    91XXXXXXXXXX without a leading + can be treated as an invalid 12-digit
    domestic number by the SIM.  For Synway-like 70xx gateway trunks, dial the
    local 10-digit mobile number instead.
    """
    if _is_gateway_trunk(trunk) and len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    return digits


def _is_safe_sip_username(username: str) -> bool:
    value = str(username or "").strip()
    if len(value) < 2 or len(value) > 64:
        return False
    return all(ch.isalnum() or ch in "._-" for ch in value)

logger = logging.getLogger("simson.api")


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


class LocalAPI:
    """HTTP API running inside the addon for HA integration communication."""

    def __init__(self, cfg: Config, call_mgr: CallManager,
                 send_fn, asterisk=None, wss_client=None,
                 target_dir: TargetDirectory | None = None,
                 addon=None,
                 standalone_mode: bool = False,
                 phone_provisioning: PhoneProvisioningService | None = None):
        """
        Args:
            cfg: Addon config.
            call_mgr: Call state manager.
            send_fn: Async callable to send protocol messages to VPS.
            asterisk: Optional AsteriskAMI instance.
            wss_client: Optional WSSClient for connection status.
            target_dir: Optional TargetDirectory for call targets.
            addon: Optional SimsonAddon ref for user presence operations.
            standalone_mode: When True, serve interactive web UI at / for non-HAOS deployments.
        """
        self.cfg = cfg
        self.call_mgr = call_mgr
        self.send_fn = send_fn
        self.asterisk = asterisk
        self.wss_client = wss_client
        self.target_dir = target_dir
        self.addon = addon
        self.standalone_mode = standalone_mode
        self.app = web.Application()
        self._runner = None
        self._sse_subscribers: list[asyncio.Queue] = []
        self._automation_last_run: dict[str, float] = {}
        self._automation_block_until: dict[str, float] = {}
        self.phone_provisioning = phone_provisioning or PhoneProvisioningService()
        self._setup_routes()

    def _setup_routes(self):
        ui_dir = os.path.join(os.path.dirname(__file__), "ui")
        if os.path.isdir(ui_dir):
            self.app.router.add_static("/ui", path=ui_dir, name="settings_ui")
        self.app.router.add_get("/", self.handle_ingress)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_post("/api/notification/test", self.handle_notification_test)
        self.app.router.add_get("/api/notification-targets", self.handle_notification_targets)
        self.app.router.add_get("/api/calls", self.handle_list_calls)
        self.app.router.add_post("/api/calls", self.handle_make_call)
        self.app.router.add_post("/api/call", self.handle_make_call)
        self.app.router.add_post("/api/make-call", self.handle_make_call)
        self.app.router.add_post("/api/sip-intercom", self.handle_sip_intercom)
        self.app.router.add_get("/api/routing", self.handle_routing)
        self.app.router.add_post("/api/availability", self.handle_availability)
        self.app.router.add_post("/api/target-availability", self.handle_target_availability)
        self.app.router.add_post("/api/answer", self.handle_answer)
        self.app.router.add_post("/api/reject", self.handle_reject)
        self.app.router.add_post("/api/hangup", self.handle_hangup)
        self.app.router.add_post("/api/call/answer", self.handle_answer)
        self.app.router.add_post("/api/call/reject", self.handle_reject)
        self.app.router.add_post("/api/call/decline", self.handle_reject)
        self.app.router.add_post("/api/call/hangup", self.handle_hangup)
        self.app.router.add_post("/api/end", self.handle_hangup)
        self.app.router.add_post("/api/cancel", self.handle_hangup)
        self.app.router.add_post("/api/transfer", self.handle_transfer)
        self.app.router.add_get("/api/health", self.handle_health)
        self.app.router.add_get("/api/targets", self.handle_targets)
        self.app.router.add_post("/api/provision", self.handle_provision)
        self.app.router.add_post("/api/identity", self.handle_update_identity)
        self.app.router.add_post("/api/reset", self.handle_reset)
        self.app.router.add_get("/api/events", self.handle_sse)
        self.app.router.add_post("/api/webrtc/signal", self.handle_webrtc_signal)
        self.app.router.add_post("/api/user/heartbeat", self.handle_user_heartbeat)
        self.app.router.add_post("/api/user/unregister", self.handle_user_unregister)
        self.app.router.add_get("/api/users", self.handle_get_users)
        self.app.router.add_post("/api/remote-users", self.handle_remote_users)
        self.app.router.add_get("/api/history", self.handle_history)
        self.app.router.add_get("/api/webrtc-config", self.handle_webrtc_config)
        self.app.router.add_get("/api/settings", self.handle_get_settings)
        self.app.router.add_post("/api/settings", self.handle_post_settings)
        self.app.router.add_get("/api/nodes", self.handle_list_nodes)
        self.app.router.add_get("/api/automation", self.handle_get_automation)
        self.app.router.add_post("/api/automation/trigger/{trigger_id}", self.handle_run_automation_trigger)
        self.app.router.add_post("/api/automation/webhook/{webhook_id}", self.handle_automation_webhook)
        self.app.router.add_get("/api/automation/webhook/{webhook_id}", self.handle_automation_legacy_get)
        self.app.router.add_get(
            "/api/automation/device/{webhook_id}/{trigger_id}",
            self.handle_automation_device_webhook,
        )
        self.app.router.add_get("/api/sip-endpoints", self.handle_list_sip_endpoints)
        self.app.router.add_post("/api/phone-provision/discover", self.handle_phone_provision_discover)
        self.app.router.add_post("/api/sip-endpoints", self.handle_create_sip_endpoint)
        self.app.router.add_put("/api/sip-endpoints/{id}", self.handle_update_sip_endpoint)
        self.app.router.add_delete("/api/sip-endpoints/{id}", self.handle_delete_sip_endpoint)
        self.app.router.add_post("/api/sip-endpoints/{id}/clear-stuck", self.handle_clear_stuck_sip_endpoint)
        self.app.router.add_get("/api/advanced-routes", self.handle_list_advanced_routes)
        self.app.router.add_post("/api/advanced-routes", self.handle_create_advanced_route)
        self.app.router.add_put("/api/advanced-routes/{id}", self.handle_update_advanced_route)
        self.app.router.add_delete("/api/advanced-routes/{id}", self.handle_delete_advanced_route)
        self.app.router.add_get("/api/call-features", self.handle_get_call_features)
        self.app.router.add_put("/api/call-features", self.handle_put_call_features)
        self.app.router.add_post("/api/active-call-invite", self.handle_active_call_invite)

    async def start(self):
        """Start the local API server, falling back to alternate ports if needed."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()

        preferred = self.cfg.local_api_port
        candidates = [preferred] + [preferred + i for i in range(1, 4)]

        for port in candidates:
            try:
                site = web.TCPSite(self._runner, "0.0.0.0", port)
                await site.start()
                self.cfg.local_api_port = port  # update so callers see the real port
                if port != preferred:
                    logger.warning(
                        "Port %d in use — local API bound to fallback port %d. "
                        "Update the addon 'local_api_port' option to %d to avoid this.",
                        preferred, port, port,
                    )
                logger.info("Local API listening on port %d", port)
                return
            except OSError as e:
                logger.warning("Cannot bind port %d: %s", port, e)

        raise OSError(
            f"Could not bind local API on any of ports {candidates}. "
            "Set 'local_api_port' in addon options to a free port."
        )

    async def stop(self):
        """Stop the local API server."""
        if self._runner:
            await self._runner.cleanup()

    # --- Handlers ---

    async def handle_ingress(self, request: web.Request) -> web.Response:
        """Serve the in-addon SPA (setup wizard + settings panel)."""
        if self.standalone_mode:
            return await self._handle_standalone_ui(request)

        provisioned = bool(self.cfg.install_token)
        has_admin_token = bool(self.cfg.admin_token)

        html = (
            INGRESS_UI_HTML
            .replace("__PROVISIONED__", "true" if provisioned else "false")
            .replace("__HAS_ADMIN_TOKEN__", "true" if has_admin_token else "false")
            .replace("__VERSION__", ADDON_VERSION)
        )
        return web.Response(text=html, content_type="text/html")

    async def _handle_standalone_ui(self, request: web.Request) -> web.Response:
        """Serve full interactive web UI for standalone (non-HAOS) deployments."""
        from standalone_ui import STANDALONE_UI_HTML
        node_id = self.cfg.node_id or "unknown"
        node_label = getattr(self.cfg, "node_label", None) or node_id
        vps = self.cfg.server_url or ""
        html = STANDALONE_UI_HTML.replace("__NODE_ID__", node_id).replace(
            "__NODE_LABEL__", node_label
        ).replace("__VPS_URL__", vps)
        return web.Response(text=html, content_type="text/html")

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok",
            "addon_version": ADDON_VERSION,
            "node_id": self.cfg.node_id,
            "provisioned": bool(self.cfg.install_token),
            "capabilities": {
                "call_api": True,
                "call_endpoints": ["/api/call", "/api/make-call", "POST /api/calls"],
                "call_control_endpoints": [
                    "/api/answer",
                    "/api/reject",
                    "/api/hangup",
                    "/api/call/answer",
                    "/api/call/reject",
                    "/api/call/hangup",
                ],
                "sip_intercom": True,
                "phone_provisioning": {
                    "enabled": True,
                    "profiles": self.phone_provisioning.profiles(),
                },
                "automation_webhooks": True,
            },
        })

    async def handle_status(self, request: web.Request) -> web.Response:
        active = self.call_mgr.active_call
        vps_connected = self.wss_client.connected if self.wss_client else False
        status = {
            "node_id": self.cfg.node_id,
            "node_label": getattr(self.cfg, "node_label", ""),
            "account_id": self.cfg.account_id,
            "server_url": self.cfg.server_url,
            "install_token": self.cfg.install_token,
            "vps_connected": vps_connected,
            "provisioned": bool(self.cfg.install_token),
            "active_call": _call_to_dict(active) if active else None,
        }
        if self.asterisk:
            status["asterisk_connected"] = self.asterisk.connected
        status["availability"] = self.cfg.availability
        status["routing"] = self.cfg.routing_policy
        if self.addon and getattr(self.addon, "ha", None):
            status["last_call_event"] = getattr(self.addon.ha, "last_call_event", {}) or {}
            status["last_automation_event"] = getattr(self.addon.ha, "last_automation_event", {}) or {}
        return web.json_response(status)

    async def handle_notification_test(self, request: web.Request) -> web.Response:
        """Send a test push through the configured HA notify targets."""
        if not self.addon or not getattr(self.addon, "ha", None):
            return web.json_response({"error": "Home Assistant bridge is not available"}, status=503)

        try:
            body = await request.json()
        except Exception:
            body = {}
        settings = load_settings()
        automation = settings.get("automation", {}) if isinstance(settings, dict) else {}
        notify_text = str(body.get("notify_services", "") or automation.get("notify_services", ""))
        notify_services = [
            item.strip()
            for item in notify_text.split(",")
            if item.strip()
        ]
        if not notify_services:
            return web.json_response(
                {"error": "No mobile app notify services configured"},
                status=400,
            )

        results = []
        success_count = 0
        for service_ref in notify_services:
            ok = await self.addon.ha.send_notify_message(
                service_ref,
                f"Test notification from Simson node {self.cfg.node_id}.",
                title="Simson Notification Test",
                data={
                    "tag": "simson-notification-test",
                    "notification_icon": "mdi:phone-check",
                    "channel": "alarm_stream",
                    "importance": "max",
                    "priority": "high",
                    "ttl": 0,
                    "sound": "default",
                    "vibrationPattern": "100, 800, 100, 800, 100, 800, 100, 800, 100, 800",
                    "sticky": "true",
                    "persistent": True,
                    "visibility": "public",
                    "push": {
                        "sound": {"name": "default", "critical": 1, "volume": 1.0},
                        "interruption-level": "critical",
                    },
                },
            )
            if ok:
                success_count += 1
            results.append({"target": service_ref, "ok": ok})

        return web.json_response({
            "sent": success_count,
            "total": len(results),
            "results": results,
        }, status=200 if success_count else 502)

    async def handle_notification_targets(self, request: web.Request) -> web.Response:
        """List verified Home Assistant notification entities/services."""
        if not self.addon or not getattr(self.addon, "ha", None):
            return web.json_response({"error": "Home Assistant bridge is not available"}, status=503)
        settings = load_settings()
        automation = settings.get("automation", {}) if isinstance(settings, dict) else {}
        configured = [
            item.strip()
            for item in str(automation.get("notify_services", "") or "").split(",")
            if item.strip()
        ]
        targets = await self.addon.ha.discover_notify_targets(force=True)
        return web.json_response({"targets": targets, "configured": configured})

    async def handle_provision(self, request: web.Request) -> web.Response:
        """Provision account + node on VPS from the ingress panel."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        admin_token = body.get("admin_token", "").strip() or self.cfg.admin_token
        node_label = body.get("node_label", "").strip()
        account_id = body.get("account_id", "").strip()

        if not admin_token:
            return web.json_response(
                {"error": "admin_token is required — set it in the addon Configuration tab or paste it in the setup form"},
                status=400,
            )
        if not node_label:
            return web.json_response({"error": "node_label is required"}, status=400)

        try:
            creds = await auto_provision(
                server_url=self.cfg.server_url,
                admin_token=admin_token,
                node_label=node_label,
                account_id=account_id,
                capabilities=self.cfg.capabilities,
            )
        except Exception as e:
            logger.error("Provision via web UI failed: %s", e)
            return web.json_response({"error": str(e)}, status=502)

        # Update in-memory config so the main loop can pick up the credentials.
        self.cfg.account_id = creds["account_id"]
        self.cfg.node_id = creds["node_id"]
        self.cfg.install_token = creds["install_token"]

        logger.info("Provisioned via web UI: account=%s node=%s",
                     creds["account_id"], creds["node_id"])
        return web.json_response(creds, status=201)

    async def handle_reset(self, request: web.Request) -> web.Response:
        """Clear saved credentials so the setup wizard shows again."""
        clear_saved_credentials()
        self.cfg.account_id = ""
        self.cfg.node_id = ""
        self.cfg.install_token = ""
        logger.warning("Credentials reset via web UI — setup wizard will show on next load")
        return web.json_response({"reset": True})

    async def handle_update_identity(self, request: web.Request) -> web.Response:
        """Save account/node credentials from the guarded advanced UI.

        Changing only account_id while keeping the old install token leaves the
        addon unable to authenticate. Treat identity changes as a guarded
        operation: either validate a supplied token against the VPS before
        saving, or create a fresh node token with the admin API when the token
        field is left blank.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "json object required"}, status=400)

        account_id = str(body.get("account_id", "")).strip()
        node_id = str(body.get("node_id", "")).strip()
        install_token = str(body.get("install_token", "")).strip()
        node_label = str(body.get("node_label", "")).strip()

        missing = [
            label for label, value in (
                ("account_id", account_id),
                ("node_id", node_id),
            )
            if not value
        ]
        if missing:
            return web.json_response(
                {"error": f"Missing required field(s): {', '.join(missing)}"},
                status=422,
            )

        if install_token:
            ok, reason = await self._validate_identity_credentials(
                account_id,
                node_id,
                install_token,
            )
            if not ok:
                logger.warning(
                    "Rejected identity update for account=%s node=%s: %s",
                    account_id,
                    node_id,
                    reason,
                )
                return web.json_response(
                    {
                        "error": (
                            "These credentials were rejected by the VPS. "
                            "Check the account ID, node ID, and install token; "
                            "nothing was saved."
                        ),
                        "detail": reason,
                    },
                    status=401,
                )
            action = "validated"
        else:
            if not self.cfg.admin_token:
                return web.json_response(
                    {
                        "error": (
                            "Install token is required unless the addon has an "
                            "admin token configured to create a fresh node token."
                        )
                    },
                    status=422,
                )
            try:
                install_token = await self._provision_identity_node(
                    account_id,
                    node_id,
                    node_label or node_id,
                )
            except Exception as exc:
                logger.warning(
                    "Could not provision identity account=%s node=%s: %s",
                    account_id,
                    node_id,
                    exc,
                )
                return web.json_response(
                    {
                        "error": (
                            "Could not create this node on the VPS. If the node "
                            "already exists, paste its install token instead or "
                            "delete/recreate it from the VPS admin side."
                        ),
                        "detail": str(exc),
                    },
                    status=409,
                )
            action = "provisioned"

        save_credentials(
            account_id=account_id,
            node_id=node_id,
            install_token=install_token,
            node_label=node_label,
            capabilities=self.cfg.capabilities,
        )
        self.cfg.account_id = account_id
        self.cfg.node_id = node_id
        self.cfg.install_token = install_token
        self.cfg.node_label = node_label
        logger.warning(
            "Credentials %s via web UI: account=%s node=%s; addon restart recommended",
            action,
            account_id,
            node_id,
        )
        return web.json_response({
            "account_id": account_id,
            "node_id": node_id,
            "node_label": node_label,
            "action": action,
            "restart_required": True,
        })

    async def _validate_identity_credentials(
        self,
        account_id: str,
        node_id: str,
        install_token: str,
    ) -> tuple[bool, str]:
        """Return whether a candidate identity is accepted by the VPS."""
        if not self.cfg.server_url:
            return False, "server_url is not configured"
        base = self._ws_to_http_url(self.cfg.server_url)
        if not base:
            return False, "could not derive VPS HTTP URL from server_url"

        headers = {
            "X-Simson-Account-ID": account_id,
            "X-Simson-Node-ID": node_id,
            "X-Simson-Install-Token": install_token,
        }
        timeout = ClientTimeout(total=8)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(f"{base}/node/webrtc-config", headers=headers) as resp:
                    if resp.status == 200:
                        return True, "ok"
                    text = await resp.text()
                    return False, f"VPS returned HTTP {resp.status}: {text[:240]}"
        except Exception as exc:
            return False, f"VPS validation request failed: {exc}"

    async def _provision_identity_node(
        self,
        account_id: str,
        node_id: str,
        node_label: str,
    ) -> str:
        """Create/reuse an account and create a node, returning its fresh token."""
        if not self.cfg.server_url:
            raise RuntimeError("server_url is not configured")
        base = self._ws_to_http_url(self.cfg.server_url)
        if not base:
            raise RuntimeError("could not derive VPS HTTP URL from server_url")

        headers = {
            "Authorization": f"Bearer {self.cfg.admin_token}",
            "Content-Type": "application/json",
        }
        timeout = ClientTimeout(total=15)
        async with ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{base}/admin/accounts",
                headers=headers,
                json={"id": account_id, "name": node_label or account_id},
            ) as resp:
                if resp.status not in (201, 409):
                    text = await resp.text()
                    raise RuntimeError(f"account create returned HTTP {resp.status}: {text[:240]}")

            async with session.post(
                f"{base}/admin/accounts/{account_id}/nodes",
                headers=headers,
                json={
                    "id": node_id,
                    "label": node_label or node_id,
                    "node_type": "haos",
                    "capabilities": self.cfg.capabilities or ["haos", "voice"],
                },
            ) as resp:
                payload_text = await resp.text()
                if resp.status != 201:
                    raise RuntimeError(f"node create returned HTTP {resp.status}: {payload_text[:240]}")
                try:
                    payload = json.loads(payload_text)
                except Exception as exc:
                    raise RuntimeError(f"node create returned invalid JSON: {exc}") from exc
                token = str(payload.get("install_token", "")).strip()
                if not token:
                    raise RuntimeError("node create response did not include install_token")
                return token

    async def handle_get_settings(self, request: web.Request) -> web.Response:
        """Return current addon settings as JSON."""
        return web.json_response(load_settings())

    async def handle_post_settings(self, request: web.Request) -> web.Response:
        """Save addon settings submitted from the in-addon UI."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "json body must be an object"}, status=400)

        errors = validate_settings(body)
        if errors:
            logger.warning("Rejected settings update: %s", "; ".join(errors))
            return web.json_response({"errors": errors}, status=422)

        old = load_settings()
        restart_required = (
            body.get("local_api_port", 8799) != old.get("local_api_port", 8799)
            or body.get("asterisk", {}).get("enabled") != old.get("asterisk", {}).get("enabled")
            or body.get("asterisk", {}).get("host") != old.get("asterisk", {}).get("host")
            or body.get("asterisk", {}).get("ami_port") != old.get("asterisk", {}).get("ami_port")
            or body.get("asterisk", {}).get("ami_secret") != old.get("asterisk", {}).get("ami_secret")
        )

        save_settings(body)

        # Apply to in-memory config immediately.
        ast = body.get("asterisk", {})
        self.cfg.asterisk_enabled = ast.get("enabled", False)
        self.cfg.asterisk_host = ast.get("host", "127.0.0.1")
        self.cfg.asterisk_ami_port = int(ast.get("ami_port", 5038))
        self.cfg.asterisk_ami_user = ast.get("ami_user", "simson")
        self.cfg.asterisk_ami_secret = ast.get("ami_secret", "")
        self.cfg.asterisk_context = ast.get("context", "from-simson")
        self.cfg.asterisk_ext_prefix = ast.get("extension_prefix", "9")
        self.cfg.asterisk_auto_configure = ast.get("auto_configure", False)

        wrtc = body.get("webrtc", {})
        self.cfg.turn_enabled = wrtc.get("turn_enabled", False)
        self.cfg.turn_url = wrtc.get("turn_url", "")
        self.cfg.turn_username = wrtc.get("turn_username", "simson")
        self.cfg.turn_credential = wrtc.get("turn_credential", "")
        self.cfg.sip_enabled = wrtc.get("sip_enabled", False)
        self.cfg.sip_ws_url = wrtc.get("sip_ws_url", "")
        self.cfg.sip_username = wrtc.get("sip_username", "webrtc-pool")
        self.cfg.sip_password = wrtc.get("sip_password", "")
        self.cfg.sip_domain = wrtc.get("sip_domain", "")

        self.cfg.call_targets = body.get("call_targets", [])
        routing = body.get("routing", {})
        self.cfg.routing_policy = {
            "strategy": routing.get("strategy", "priority"),
            "ring_seconds": int(routing.get("ring_seconds", 25)),
            "max_attempts": int(routing.get("max_attempts", 4)),
            "skip_unavailable": bool(routing.get("skip_unavailable", True)),
            "final_fallback_target": routing.get("final_fallback_target", ""),
            "gateway_inbound_mode": routing.get("gateway_inbound_mode", "haos_then_fallback"),
            "gateway_direct_target": routing.get("gateway_direct_target", ""),
            "default_gateway_trunk": routing.get("default_gateway_trunk", ""),
        }
        availability = body.get("availability", {})
        self.cfg.availability = {
            "mode": availability.get("mode", "available"),
            "reason": availability.get("reason", ""),
        }
        self.cfg.route_overrides = body.get("route_overrides", {}) or {}
        self.cfg.automation = copy.deepcopy(body.get("automation", {}) or {})
        if self.target_dir:
            self.target_dir.reload()

        sync_result = await self._sync_default_outbound_gateway(
            self.cfg.routing_policy.get("default_gateway_trunk", "")
        )

        logger.info("Settings updated via UI (restart_required=%s)", restart_required)
        return web.json_response({
            "saved": True,
            "restart_required": restart_required,
            "gateway_default_sync": sync_result,
        })

    async def _sync_default_outbound_gateway(self, selected_trunk: str) -> dict:
        """Mirror the local default gateway setting to the VPS SIP endpoint table.

        SIP phones dial through the VPS directly, not through this addon process.
        Keeping the selected trunk on the VPS prevents the UI from saying "7013"
        while Asterisk still picks an older gateway such as 7009.
        """
        trunk = str(selected_trunk or "").strip()
        if not trunk or trunk == "auto":
            return {"ok": True, "skipped": True, "reason": "auto"}
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return {"ok": False, "skipped": True, "reason": "not provisioned"}

        http_url = self._ws_to_http_url(self.cfg.server_url)
        headers = {
            "Authorization": f"Bearer {self.cfg.admin_token}",
            "Content-Type": "application/json",
        }
        try:
            async with ClientSession(timeout=ClientTimeout(total=10)) as session:
                list_url = f"{http_url}/admin/accounts/{self.cfg.account_id}/sip-endpoints"
                async with session.get(list_url, headers=headers, ssl=False) as resp:
                    payload_text = await resp.text()
                    if resp.status != 200:
                        logger.warning(
                            "Could not list SIP endpoints while syncing default gateway: %s %s",
                            resp.status,
                            payload_text[:240],
                        )
                        return {"ok": False, "reason": f"list failed: HTTP {resp.status}"}
                    try:
                        payload = json.loads(payload_text) if payload_text else []
                    except Exception as exc:
                        logger.warning("Invalid SIP endpoint list while syncing default gateway: %s", exc)
                        return {"ok": False, "reason": "invalid endpoint list"}

                endpoints = self._normalize_sip_endpoints_payload(payload)
                gateway_ids: list[tuple[str, str, bool]] = []
                target_found = False
                for endpoint in endpoints:
                    ext = str(endpoint.get("extension") or "").strip()
                    endpoint_id = str(endpoint.get("id") or "").strip()
                    if not ext or not endpoint_id or not _is_gateway_trunk(ext):
                        continue
                    desired = ext == trunk
                    target_found = target_found or desired
                    gateway_ids.append((endpoint_id, ext, desired))

                if not target_found:
                    logger.warning(
                        "Default gateway %s is not a gateway endpoint in account %s",
                        trunk,
                        self.cfg.account_id,
                    )
                    return {"ok": False, "reason": f"gateway {trunk} not found"}

                updated = 0
                for endpoint_id, ext, desired in gateway_ids:
                    update_url = f"{http_url}/admin/sip-endpoints/{endpoint_id}"
                    async with session.put(
                        update_url,
                        json={"default_outbound": desired},
                        headers=headers,
                        ssl=False,
                    ) as resp:
                        payload_text = await resp.text()
                        if resp.status != 200:
                            logger.warning(
                                "Could not set default_outbound=%s on SIP endpoint %s/%s: %s %s",
                                desired,
                                ext,
                                endpoint_id,
                                resp.status,
                                payload_text[:240],
                            )
                            return {"ok": False, "reason": f"update {ext} failed: HTTP {resp.status}"}
                        updated += 1

                logger.info("Default outbound gateway synced to VPS: %s (%d endpoint updates)", trunk, updated)
                return {"ok": True, "trunk": trunk, "updated": updated}
        except Exception as exc:
            logger.warning("Default outbound gateway sync failed: %s", exc)
            return {"ok": False, "reason": str(exc)}

    async def handle_list_sip_endpoints(self, request: web.Request) -> web.Response:
        """List SIP endpoints for this account by calling VPS admin API."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"},
                status=400,
            )
        
        # Convert WebSocket URL to HTTP URL
        http_url = self._ws_to_http_url(self.cfg.server_url)
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{http_url}/admin/accounts/{self.cfg.account_id}/sip-endpoints"
                headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
                async with session.get(url, headers=headers, ssl=False) as resp:
                    if resp.status == 200:
                        try:
                            payload = await resp.json(content_type=None)
                        except Exception as e:
                            logger.warning("VPS SIP endpoint list returned invalid JSON: %s", e)
                            return web.json_response([])

                        endpoints = self._normalize_sip_endpoints_payload(payload)
                        if not isinstance(payload, list):
                            logger.warning(
                                "Unexpected VPS SIP endpoint payload type: %s; normalized to %d entries",
                                type(payload).__name__,
                                len(endpoints),
                            )
                        return web.json_response(endpoints)
                    else:
                        error = await resp.text()
                        logger.error(f"VPS SIP endpoint list failed: {resp.status} {error}")
                        return web.json_response(
                            {"error": f"VPS returned {resp.status}"}, status=resp.status
                        )
        except Exception as e:
            logger.error(f"SIP endpoint list error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _proxy_advanced_routes(
        self,
        method: str,
        route_id: str = "",
        payload: dict | None = None,
    ) -> web.Response:
        """Proxy account-scoped route plans without exposing the admin token."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"},
                status=400,
            )

        http_url = self._ws_to_http_url(self.cfg.server_url)
        if method in {"GET", "POST"} and not route_id:
            url = f"{http_url}/admin/accounts/{self.cfg.account_id}/advanced-routes"
        else:
            url = (
                f"{http_url}/admin/accounts/{self.cfg.account_id}"
                f"/advanced-routes/{route_id}"
            )
        headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}

        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=payload if method in {"POST", "PUT"} else None,
                    ssl=False,
                ) as resp:
                    body = await resp.text()
                    if resp.status >= 400:
                        data = _safe_upstream_error(resp.status, body, "advanced routing")
                        logger.error(
                            "VPS advanced route %s failed: HTTP %s code=%s",
                            method,
                            resp.status,
                            data.get("code", "upstream_request_failed"),
                        )
                        # An old VPS returning 404 is a service/version mismatch,
                        # not a missing route in the addon's own API.
                        status = 503 if resp.status == 404 else resp.status
                        return web.json_response(data, status=status)
                    try:
                        data = json.loads(body) if body else {"ok": True}
                    except Exception:
                        data = {"ok": True}
                    return web.json_response(data, status=resp.status)
        except Exception as exc:
            logger.error("Advanced route proxy error: %s", exc)
            return web.json_response({
                "error": "Could not reach the VPS advanced-routing service. Check VPS health and retry.",
                "code": "advanced_routes_unreachable",
            }, status=502)

    async def handle_list_advanced_routes(self, request: web.Request) -> web.Response:
        return await self._proxy_advanced_routes("GET")

    async def handle_create_advanced_route(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        return await self._proxy_advanced_routes("POST", payload=payload)

    async def handle_update_advanced_route(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        return await self._proxy_advanced_routes(
            "PUT",
            route_id=request.match_info["id"],
            payload=payload,
        )

    async def handle_delete_advanced_route(self, request: web.Request) -> web.Response:
        return await self._proxy_advanced_routes(
            "DELETE",
            route_id=request.match_info["id"],
        )

    async def _proxy_call_features(
        self, method: str, payload: dict | None = None
    ) -> web.Response:
        """Proxy the current site's PBX feature policy without exposing admin auth."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"}, status=400
            )
        url = (
            f"{self._ws_to_http_url(self.cfg.server_url)}/admin/accounts/"
            f"{self.cfg.account_id}/call-features"
        )
        headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
        try:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=payload if method == "PUT" else None,
                    ssl=False,
                ) as resp:
                    body = await resp.text()
                    try:
                        data = json.loads(body) if body else {"ok": True}
                    except Exception:
                        data = {"error": f"VPS returned HTTP {resp.status}"}
                    if resp.status >= 400:
                        logger.error("VPS call-feature %s failed: %s %s", method, resp.status, body[:300])
                    return web.json_response(data, status=resp.status)
        except Exception as exc:
            logger.error("Call-feature proxy error: %s", exc)
            return web.json_response(
                {"error": "Could not reach the VPS call-feature service"}, status=502
            )

    async def handle_get_call_features(self, request: web.Request) -> web.Response:
        return await self._proxy_call_features("GET")

    async def handle_put_call_features(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        return await self._proxy_call_features("PUT", payload)

    async def handle_active_call_invite(self, request: web.Request) -> web.Response:
        """Invite a SIP or explicit outside destination into one active SIP call."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response({"error": "Not yet provisioned — no account created on VPS"}, status=400)
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        url = (
            f"{self._ws_to_http_url(self.cfg.server_url)}/admin/accounts/"
            f"{self.cfg.account_id}/active-call-invite"
        )
        headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, headers=headers, json=payload, ssl=False) as resp:
                    text = await resp.text()
                    try:
                        data = json.loads(text) if text else {}
                    except Exception:
                        data = {"error": text or f"VPS returned HTTP {resp.status}"}
                    return web.json_response(data, status=resp.status)
        except Exception as exc:
            logger.error("Active-call invite proxy error: %s", exc)
            return web.json_response({"error": "Could not reach the VPS active-call service"}, status=502)

    async def handle_list_nodes(self, request: web.Request) -> web.Response:
        """List VPS nodes in this site/account so settings can use real route targets."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response({
                "nodes": [],
                "current_node_id": self.cfg.node_id,
                "account_id": self.cfg.account_id,
                "error": "Not yet provisioned — no account created on VPS",
            }, status=400)

        http_url = self._ws_to_http_url(self.cfg.server_url)
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{http_url}/admin/accounts/{self.cfg.account_id}/nodes"
                headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
                async with session.get(url, headers=headers, ssl=False) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error("VPS node list failed: %s %s", resp.status, error)
                        return web.json_response(
                            {"nodes": [], "error": f"VPS returned {resp.status}"},
                            status=resp.status,
                        )
                    payload = await resp.json(content_type=None)
        except Exception as e:
            logger.error("Node list error: %s", e)
            return web.json_response({"nodes": [], "error": str(e)}, status=500)

        raw_nodes = payload if isinstance(payload, list) else payload.get("nodes", []) if isinstance(payload, dict) else []
        nodes = []
        for node in raw_nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or node.get("ID") or "").strip()
            if not node_id:
                continue
            nodes.append({
                "id": node_id,
                "label": str(node.get("label") or node.get("Label") or node_id),
                "node_type": str(node.get("node_type") or node.get("NodeType") or "haos"),
                "enabled": bool(node.get("enabled", node.get("Enabled", True))),
                "is_current": node_id == self.cfg.node_id,
                "account_id": str(node.get("account_id") or node.get("AccountID") or self.cfg.account_id),
            })
        return web.json_response({
            "nodes": nodes,
            "current_node_id": self.cfg.node_id,
            "current_node_label": self.cfg.node_label or self.cfg.node_id,
            "account_id": self.cfg.account_id,
        })

    async def handle_phone_provision_discover(self, request: web.Request) -> web.Response:
        """Authenticate to a supported LAN phone and return writable SIP slots."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "request must be an object"}, status=400)
        try:
            # Bound the entire adapter, not only its individual HTTP requests.
            # This prevents HA ingress/Cloudflare from timing out with an HTML
            # 502 page when a LAN phone accepts TCP but never completes login.
            result = await asyncio.wait_for(
                self.phone_provisioning.discover(body),
                timeout=12,
            )
            return web.json_response(result)
        except ProvisioningError as exc:
            logger.warning("Phone provisioning discovery rejected: %s", exc)
            return web.json_response({"error": str(exc), "code": exc.code}, status=exc.status)
        except asyncio.TimeoutError:
            return web.json_response(
                {"error": "Timed out connecting to the phone management interface", "code": "device_timeout"},
                status=504,
            )
        except Exception as exc:
            logger.exception("Phone provisioning discovery failed")
            return web.json_response(
                {"error": "Could not test the phone management connection", "code": "device_test_failed"},
                status=502,
            )

    async def _create_vps_sip_endpoint(self, payload: dict) -> tuple[int, dict]:
        http_url = self._ws_to_http_url(self.cfg.server_url)
        url = f"{http_url}/admin/accounts/{self.cfg.account_id}/sip-endpoints"
        headers = {
            "Authorization": f"Bearer {self.cfg.admin_token}",
            "Content-Type": "application/json",
        }
        async with ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.post(url, json=payload, headers=headers, ssl=False) as response:
                text = await response.text()
                try:
                    data = json.loads(text) if text else {}
                except Exception:
                    data = {"error": text or f"VPS returned {response.status}"}
                if not isinstance(data, dict):
                    data = {"error": str(data)}
                return response.status, data

    async def _rollback_vps_sip_endpoint(self, endpoint_id: str) -> bool:
        if not endpoint_id:
            return False
        http_url = self._ws_to_http_url(self.cfg.server_url)
        url = f"{http_url}/admin/sip-endpoints/{endpoint_id}"
        headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
        try:
            async with ClientSession(timeout=ClientTimeout(total=10)) as session:
                async with session.delete(url, headers=headers, ssl=False) as response:
                    if response.status in (200, 204):
                        return True
                    logger.error("SIP endpoint rollback failed: %s %s", response.status, await response.text())
        except Exception:
            logger.exception("SIP endpoint rollback request failed")
        return False

    def _sip_server_for_phone(self, transport: str) -> str:
        configured = str(getattr(self.cfg, "sip_domain", "") or "").strip()
        host = configured
        if configured:
            parsed = urlsplit(configured if "://" in configured else f"//{configured}")
            host = parsed.hostname or configured.split(":", 1)[0]
        if not host:
            host = urlsplit(self.cfg.server_url).hostname or ""
        if not host:
            raise ProvisioningError(
                "SIP server hostname is not configured for automatic phone setup",
                status=500,
                code="sip_server_missing",
            )
        return f"{host}:5061" if transport == "tls" else host

    async def handle_create_sip_endpoint(self, request: web.Request) -> web.Response:
        """Create a VPS endpoint and optionally provision a tested LAN phone."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"},
                status=400,
            )
        
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        
        extension = str(body.get("extension", "") or "").strip()
        username = str(body.get("username", "") or "").strip() or extension
        password = str(body.get("password", "") or "").strip()
        if username and not _is_safe_sip_username(username):
            logger.warning(
                "Unsafe SIP username %r for extension %s; using extension as auth username",
                username,
                extension,
            )
            username = extension

        # Validate required fields
        if not extension or not password:
            return web.json_response(
                {"error": "extension and password are required"},
                status=400,
            )
        if not username or not _is_safe_sip_username(username):
            return web.json_response(
                {"error": "username/auth user must be 2-64 letters/numbers/dot/underscore/dash; for normal phones use the same value as extension"},
                status=400,
            )
        
        provisioning = body.get("phone_provisioning")
        if provisioning is not None:
            if not isinstance(provisioning, dict):
                return web.json_response({"error": "phone_provisioning must be an object"}, status=400)
            if not provisioning.get("session_id") or not provisioning.get("slot"):
                return web.json_response(
                    {"error": "Test the phone connection and select an available account slot before creating"},
                    status=400,
                )
            transport = str(provisioning.get("transport", "tcp") or "tcp").strip().lower()
            if transport not in {"tcp", "udp", "tls"}:
                return web.json_response({"error": "SIP transport must be TCP, UDP, or TLS"}, status=400)

        payload = {
            "extension": extension,
            "username": username,
            "password": password,
            "description": body.get("description", ""),
            "route_to": body.get("route_to", ""),
            "video_enabled": bool(body.get("video_enabled", False)),
            "auto_answer": bool(body.get("auto_answer", False)),
            "auto_answer_callers": str(body.get("auto_answer_callers", "") or ""),
            "auto_speaker": bool(body.get("auto_speaker", False)),
            "auto_speaker_callers": str(body.get("auto_speaker_callers", "") or ""),
            "callback_bridge": bool(body.get("callback_bridge", False)),
            "callback_bridge_callers": str(body.get("callback_bridge_callers", "") or ""),
            "callback_caller_auto_answer": bool(body.get("callback_caller_auto_answer", False)),
            "callback_caller_auto_speaker": bool(body.get("callback_caller_auto_speaker", False)),
            "default_outbound": bool(body.get("default_outbound", False)),
            "gateway_inbound_mode": str(body.get("gateway_inbound_mode", "") or ""),
            "gateway_direct_target": str(body.get("gateway_direct_target", "") or ""),
            "gateway_ivr_enabled": bool(body.get("gateway_ivr_enabled", False)),
            "gateway_ivr_sound": str(body.get("gateway_ivr_sound", "") or ""),
            "answer_announcement_text": str(body.get("answer_announcement_text", "") or ""),
            "pre_ring_announcement_text": str(body.get("pre_ring_announcement_text", "") or ""),
            "call_duration_rules": body.get("call_duration_rules", {}),
            "enabled": body.get("enabled", True),
        }
        try:
            status, endpoint = await self._create_vps_sip_endpoint(payload)
            if status not in (200, 201):
                endpoint.setdefault("error", f"VPS returned {status}")
                logger.error("VPS SIP create failed: %s %s", status, endpoint.get("error"))
                return web.json_response(endpoint, status=status)

            logger.info("SIP endpoint created: ext=%s", endpoint.get("extension", extension))
            if provisioning is None:
                return web.json_response(endpoint, status=status)

            endpoint_id = str(endpoint.get("id") or endpoint.get("ID") or "")
            transport = str(provisioning.get("transport", "tcp")).lower()
            try:
                phone_result = await self.phone_provisioning.apply(
                    str(provisioning.get("session_id")),
                    provisioning.get("slot"),
                    {
                        "extension": extension,
                        "username": username,
                        "password": password,
                        "label": str(body.get("description", "") or extension),
                        "server": self._sip_server_for_phone(transport),
                        "transport": transport,
                    },
                )
            except ProvisioningError as exc:
                rolled_back = await self._rollback_vps_sip_endpoint(endpoint_id)
                logger.error(
                    "Phone provisioning failed after SIP create; rollback=%s code=%s",
                    rolled_back,
                    exc.code,
                )
                return web.json_response({
                    "error": str(exc),
                    "code": exc.code,
                    "sip_endpoint_rolled_back": rolled_back,
                    "manual_cleanup_required": not rolled_back,
                }, status=exc.status if exc.status >= 400 else 502)
            except Exception:
                rolled_back = await self._rollback_vps_sip_endpoint(endpoint_id)
                logger.exception("Unexpected phone provisioning failure after SIP create")
                return web.json_response({
                    "error": "Phone configuration failed; the new VPS SIP endpoint was rolled back" if rolled_back else "Phone configuration failed and the new VPS SIP endpoint requires manual cleanup",
                    "code": "device_update_failed",
                    "sip_endpoint_rolled_back": rolled_back,
                    "manual_cleanup_required": not rolled_back,
                }, status=502)

            result = dict(endpoint)
            result["phone_provisioning"] = phone_result
            return web.json_response(result, status=status)
        except Exception as e:
            logger.exception("SIP endpoint create error")
            return web.json_response({"error": "Could not create the SIP endpoint"}, status=500)

    async def handle_update_sip_endpoint(self, request: web.Request) -> web.Response:
        """Update an existing SIP endpoint by calling VPS admin API."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"},
                status=400,
            )

        endpoint_id = request.match_info.get("id")
        if not endpoint_id:
            return web.json_response({"error": "endpoint id required"}, status=400)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        payload = {}
        if "description" in body:
            payload["description"] = body.get("description", "")
        if body.get("password"):
            payload["password"] = body["password"]
        if "route_to" in body:
            payload["route_to"] = body.get("route_to", "")
        if "video_enabled" in body:
            payload["video_enabled"] = bool(body.get("video_enabled"))
        if "auto_answer" in body:
            payload["auto_answer"] = bool(body.get("auto_answer"))
        if "auto_answer_callers" in body:
            payload["auto_answer_callers"] = str(body.get("auto_answer_callers", "") or "")
        if "auto_speaker" in body:
            payload["auto_speaker"] = bool(body.get("auto_speaker"))
        if "auto_speaker_callers" in body:
            payload["auto_speaker_callers"] = str(body.get("auto_speaker_callers", "") or "")
        if "callback_bridge" in body:
            payload["callback_bridge"] = bool(body.get("callback_bridge"))
        if "callback_bridge_callers" in body:
            payload["callback_bridge_callers"] = str(body.get("callback_bridge_callers", "") or "")
        if "callback_caller_auto_answer" in body:
            payload["callback_caller_auto_answer"] = bool(body.get("callback_caller_auto_answer"))
        if "callback_caller_auto_speaker" in body:
            payload["callback_caller_auto_speaker"] = bool(body.get("callback_caller_auto_speaker"))
        if "default_outbound" in body:
            payload["default_outbound"] = bool(body.get("default_outbound"))
        if "gateway_inbound_mode" in body:
            payload["gateway_inbound_mode"] = str(body.get("gateway_inbound_mode", "") or "")
        if "gateway_direct_target" in body:
            payload["gateway_direct_target"] = str(body.get("gateway_direct_target", "") or "")
        if "gateway_ivr_enabled" in body:
            payload["gateway_ivr_enabled"] = bool(body.get("gateway_ivr_enabled"))
        if "gateway_ivr_sound" in body:
            payload["gateway_ivr_sound"] = str(body.get("gateway_ivr_sound", "") or "")
        if "answer_announcement_text" in body:
            payload["answer_announcement_text"] = str(body.get("answer_announcement_text", "") or "")
        if "pre_ring_announcement_text" in body:
            payload["pre_ring_announcement_text"] = str(body.get("pre_ring_announcement_text", "") or "")
        if "call_duration_rules" in body:
            raw_rules = body.get("call_duration_rules")
            if not isinstance(raw_rules, dict):
                return web.json_response(
                    {"error": "call_duration_rules must be an object keyed by source SIP extension"},
                    status=400,
                )
            payload["call_duration_rules"] = raw_rules
        if "supervision" in body:
            raw_supervision = body.get("supervision")
            if not isinstance(raw_supervision, dict):
                return web.json_response(
                    {"error": "supervision must be an object"},
                    status=400,
                )
            payload["supervision"] = _normalize_supervision(raw_supervision)
        if "enabled" in body:
            payload["enabled"] = bool(body.get("enabled"))

        if not payload:
            return web.json_response({"error": "no updatable fields supplied"}, status=400)

        http_url = self._ws_to_http_url(self.cfg.server_url)

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{http_url}/admin/sip-endpoints/{endpoint_id}"
                headers = {
                    "Authorization": f"Bearer {self.cfg.admin_token}",
                    "Content-Type": "application/json",
                }
                async with session.put(url, json=payload, headers=headers, ssl=False) as resp:
                    if resp.status == 200:
                        endpoint = await resp.json()
                        verification_error = _verify_sip_call_behavior_response(endpoint, payload)
                        if verification_error:
                            logger.error("VPS SIP update verification failed: %s", verification_error)
                            return web.json_response(
                                {"error": verification_error, "save_verified": False},
                                status=409,
                            )
                        logger.info("SIP endpoint updated: %s", endpoint_id)
                        return web.json_response({**endpoint, "save_verified": True})

                    error_text = await resp.text()
                    try:
                        error_payload = json.loads(error_text) if error_text else {}
                    except Exception:
                        error_payload = {"error": error_text or f"VPS returned {resp.status}"}
                    if not isinstance(error_payload, dict):
                        error_payload = {"error": str(error_payload)}
                    error_payload.setdefault("error", f"VPS returned {resp.status}")
                    logger.error("VPS SIP update failed: %s %s", resp.status, error_text)
                    return web.json_response(error_payload, status=resp.status)
        except Exception as e:
            logger.error("SIP endpoint update error: %s", e)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_delete_sip_endpoint(self, request: web.Request) -> web.Response:
        """Delete a SIP endpoint by calling VPS admin API."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"},
                status=400,
            )
        
        endpoint_id = request.match_info.get("id")
        if not endpoint_id:
            return web.json_response({"error": "endpoint id required"}, status=400)
        
        http_url = self._ws_to_http_url(self.cfg.server_url)
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{http_url}/admin/sip-endpoints/{endpoint_id}"
                headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
                async with session.delete(url, headers=headers, ssl=False) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"SIP endpoint deleted: {endpoint_id}")
                        return web.json_response({"deleted": True})
                    else:
                        error_text = await resp.text()
                        try:
                            error_payload = json.loads(error_text) if error_text else {}
                        except Exception:
                            error_payload = {"error": error_text or f"VPS returned {resp.status}"}
                        if not isinstance(error_payload, dict):
                            error_payload = {"error": str(error_payload)}
                        error_payload.setdefault("error", f"VPS returned {resp.status}")
                        logger.error(f"VPS SIP delete failed: {resp.status} {error_text}")
                        return web.json_response(error_payload, status=resp.status)
        except Exception as e:
            logger.error(f"SIP endpoint delete error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_clear_stuck_sip_endpoint(self, request: web.Request) -> web.Response:
        """Release only the selected endpoint's orphaned PJSIP channels."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response({"error": "Not yet provisioned — no account created on VPS"}, status=400)
        endpoint_id = request.match_info.get("id")
        if not endpoint_id:
            return web.json_response({"error": "endpoint id required"}, status=400)
        url = (
            f"{self._ws_to_http_url(self.cfg.server_url)}/admin/accounts/"
            f"{self.cfg.account_id}/sip-endpoints/{endpoint_id}/clear-stuck"
        )
        headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post(url, headers=headers, ssl=False) as resp:
                    text = await resp.text()
                    try:
                        payload = json.loads(text) if text else {}
                    except Exception:
                        payload = {"error": text or f"VPS returned {resp.status}"}
                    return web.json_response(payload, status=resp.status)
        except Exception as exc:
            logger.error("SIP endpoint stuck-call cleanup failed: %s", exc)
            return web.json_response({"error": str(exc)}, status=502)

    # --- SSE (Server-Sent Events) for real-time push to Lovelace card ---

    async def handle_sse(self, request: web.Request) -> web.StreamResponse:
        """Stream real-time events (WebRTC signals, call state) to the card."""
        resp = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await resp.prepare(request)

        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._sse_subscribers.append(queue)
        logger.debug("SSE client connected (total: %d)", len(self._sse_subscribers))

        try:
            # Send initial state so card syncs immediately.
            init_event = {
                "type": "init",
                "node_id": self.cfg.node_id,
                "provisioned": bool(self.cfg.install_token),
                "vps_connected": self.wss_client.connected if self.wss_client else False,
            }
            await resp.write(f"data: {json.dumps(init_event)}\n\n".encode())

            while True:
                event = await queue.get()
                await resp.write(f"data: {json.dumps(event)}\n\n".encode())
        except (asyncio.CancelledError, ConnectionResetError, ConnectionError):
            pass
        finally:
            self._sse_subscribers.remove(queue)
            logger.debug("SSE client disconnected (remaining: %d)", len(self._sse_subscribers))
        return resp

    def push_sse_event(self, event: dict):
        """Push an event to all connected SSE subscribers (non-blocking)."""
        for q in self._sse_subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop if subscriber is too slow.

    # --- WebRTC signal relay ---

    async def handle_webrtc_signal(self, request: web.Request) -> web.Response:
        """Relay a WebRTC signal (SDP/ICE) from the card through VPS to the remote node."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = body.get("call_id", "")
        to_node = body.get("to_node_id", "")
        signal_type = body.get("signal_type", "")  # offer, answer, ice-candidate
        data = body.get("data")

        if not call_id or not to_node or not signal_type or data is None:
            return web.json_response({"error": "call_id, to_node_id, signal_type, data required"}, status=400)

        msg = make_webrtc_signal(call_id, self.cfg.node_id, to_node, signal_type, data)
        logger.info(
            "WebRTC signal OUT: %s to %s (call %s)",
            signal_type, to_node, call_id,
        )
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        return web.json_response({"relayed": True})

    async def handle_list_calls(self, request: web.Request) -> web.Response:
        calls = self.call_mgr.all_calls
        active = self.call_mgr.active_call
        return web.json_response({
            "active_call": _call_to_dict(active) if active else None,
            "calls": [_call_to_dict(c) for c in calls],
            "total": len(calls),
        })

    async def handle_routing(self, request: web.Request) -> web.Response:
        """Return live routing board data for this onsite addon."""
        targets = list(self.target_dir.all_targets()) if self.target_dir else []
        calls = [_call_to_dict(c) for c in self.call_mgr.all_calls]
        return web.json_response({
            "node_id": self.cfg.node_id,
            "availability": self.cfg.availability,
            "routing": self.cfg.routing_policy,
            "targets": [self._annotate_target(t) for t in targets],
            "calls": calls,
            "active_call": _call_to_dict(self.call_mgr.active_call) if self.call_mgr.active_call else None,
        })

    async def handle_availability(self, request: web.Request) -> web.Response:
        """Set this onsite addon's manual availability state."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        mode = str(body.get("mode", "available")).strip() or "available"
        if mode not in ("available", "busy", "offline"):
            return web.json_response({"error": "mode must be available, busy, or offline"}, status=400)

        settings = load_settings()
        settings["availability"] = {
            "mode": mode,
            "reason": str(body.get("reason", "")).strip(),
        }
        errors = validate_settings(settings)
        if errors:
            return web.json_response({"errors": errors}, status=422)
        save_settings(settings)
        self.cfg.availability = settings["availability"]
        return web.json_response({"availability": self.cfg.availability})

    async def handle_target_availability(self, request: web.Request) -> web.Response:
        """Mark a configured target as available, busy, or offline."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        target_id = str(body.get("target_id", "")).strip()
        mode = str(body.get("mode", "available")).strip() or "available"
        reason = str(body.get("reason", "")).strip()
        if not target_id:
            return web.json_response({"error": "target_id is required"}, status=400)
        if mode not in ("available", "busy", "offline"):
            return web.json_response({"error": "mode must be available, busy, or offline"}, status=400)

        settings = load_settings()
        overrides = settings.get("route_overrides") or {}
        overrides[target_id] = {"mode": mode, "reason": reason}
        settings["route_overrides"] = overrides
        errors = validate_settings(settings)
        if errors:
            return web.json_response({"errors": errors}, status=422)
        save_settings(settings)
        self.cfg.route_overrides = overrides
        return web.json_response({"target_id": target_id, "availability": overrides[target_id]})

    async def handle_make_call(self, request: web.Request) -> web.Response:
        """Initiate a call to another node or configured target."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "json body must be an object"}, status=400)

        body = self._normalize_make_call_body(body)
        if (
            body.get("source_extension") or body.get("source")
        ) and (
            body.get("target_extension") or body.get("target")
        ):
            return await self._start_sip_intercom(body)

        return await self._initiate_call(body)

    def _normalize_make_call_body(self, body: dict) -> dict:
        """Smooth over common HA service-field mistakes without guessing wildly."""
        normalized = dict(body)
        target_id = str(normalized.get("target_id", "") or "").strip()
        target_extension = str(normalized.get("target_extension", "") or normalized.get("target", "") or "").strip()
        source_extension = str(normalized.get("source_extension", "") or normalized.get("source", "") or "").strip()
        has_source = bool(source_extension)

        # Users often read "target_id" as "the SIP phone I am calling from" when
        # creating a two-phone intercom service call.  If target_extension is
        # present and target_id is just digits, treat it as source_extension.
        if target_extension and not has_source and target_id.isdigit():
            normalized["source_extension"] = target_id
            normalized.pop("target_id", None)
        elif source_extension and not target_extension and target_id.isdigit():
            normalized["target_extension"] = target_id
            normalized.pop("target_id", None)
        elif target_extension and not has_source:
            # A lone target_extension means "call this SIP phone from the HAOS
            # card", not "start a two-phone intercom".  Convert it to the same
            # synthetic target used by the card and call_sip_phone service.
            ext = target_extension.replace("sip:", "").strip()
            if ext.isdigit():
                normalized["target_id"] = f"asterisk_{ext}"
                normalized.setdefault("target_node_id", f"sip:{ext}")
                normalized["call_type"] = "sip"
                normalized.pop("target_extension", None)
                normalized.pop("target", None)
        return normalized

    async def handle_sip_intercom(self, request: web.Request) -> web.Response:
        """Start a source SIP phone -> target SIP phone callback/intercom bridge.

        This is the automation-friendly path for "make phone A call phone B"
        without requiring the source handset to place a visible failed call first.
        The VPS still enforces account scoping, registration, and per-endpoint
        callback-bridge allowlists.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "json body must be an object"}, status=400)

        return await self._start_sip_intercom(body)

    async def _start_sip_intercom(self, body: dict) -> web.Response:
        """Validated local wrapper for the VPS SIP intercom/callback endpoint."""
        source_extension = str(body.get("source_extension") or body.get("source") or "").strip()
        target_extension = str(body.get("target_extension") or body.get("target") or "").strip()
        if not source_extension.isdigit() or not target_extension.isdigit():
            return web.json_response(
                {"error": "source_extension and target_extension must be numeric SIP extensions"},
                status=400,
            )
        if source_extension == target_extension:
            return web.json_response(
                {"error": "source_extension and target_extension must be different"},
                status=400,
            )

        def clean_mode(value: str, default: str) -> str:
            mode = str(value or default).strip().lower()
            aliases = {
                "answer": "normal",
                "auto": "normal",
                "auto_answer": "normal",
                "auto-answer": "normal",
                "intercom": "speaker",
                "speakerphone": "speaker",
                "none": "normal",
                "off": "normal",
                "disabled": "normal",
            }
            mode = aliases.get(mode, mode)
            return mode if mode in ("", "normal", "speaker") else default

        timeout_sec = _safe_int(body.get("timeout_sec", 30), 30, 5, 120)
        payload = {
            "source_extension": source_extension,
            "target_extension": target_extension,
            "source_auto_mode": clean_mode(body.get("source_auto_mode", "speaker"), "speaker"),
            "target_auto_mode": clean_mode(body.get("target_auto_mode", "speaker"), "speaker"),
            "caller_id": str(body.get("caller_id", "") or "").strip(),
            "timeout_sec": timeout_sec,
        }

        if not self.cfg.account_id or not self.cfg.node_id or not self.cfg.install_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "SIP intercom requires a provisioned addon node"},
                status=400,
            )

        base = self._ws_to_http_url(self.cfg.server_url)
        headers = {
            "X-Simson-Account-ID": self.cfg.account_id,
            "X-Simson-Node-ID": self.cfg.node_id,
            "X-Simson-Install-Token": self.cfg.install_token,
            "Content-Type": "application/json",
        }
        timeout = ClientTimeout(total=10)
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.post(f"{base}/node/sip-intercom", json=payload, headers=headers, ssl=False) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {"error": await resp.text()}
                    if resp.status not in (200, 201, 202):
                        logger.error("VPS SIP intercom failed: %s %s", resp.status, data)
                        return web.json_response(data, status=resp.status)
        except Exception as exc:
            logger.error("SIP intercom request error: %s", exc)
            return web.json_response({"error": f"SIP intercom request failed: {exc}"}, status=502)

        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_sip_intercom", {
                "status": data.get("status", "calling"),
                "call_id": data.get("call_id", ""),
                "source_extension": source_extension,
                "target_extension": target_extension,
                "source_auto_mode": payload["source_auto_mode"],
                "target_auto_mode": payload["target_auto_mode"],
            })
        return web.json_response(data, status=202)

    async def _initiate_call(self, body: dict, source: str = "api") -> web.Response:
        """Initiate a call through the existing validated outbound path."""
        target_id = body.get("target_id", "")
        phone_number = body.get("phone_number", "")
        trunk = body.get("trunk", "")
        to_node = body.get("target_node_id", "") or body.get("to_node_id", "")
        call_type = body.get("call_type", "voice")
        target_user_id = body.get("target_user_id", "")
        target_user_name = body.get("target_user_name", "")
        caller_user_id = body.get("caller_user_id", "")

        routing = None

        # Direct PSTN/GSM dial: the card can pass a one-off number and trunk
        # instead of requiring a saved target for every outside phone number.
        if phone_number:
            digits = "".join(ch for ch in str(phone_number) if ch.isdigit())
            preferred_trunk = (self.cfg.routing_policy or {}).get("default_gateway_trunk", "")
            trunk = "".join(ch for ch in str(trunk or preferred_trunk or DEFAULT_PSTN_TRUNK).strip()
                            if ch.isalnum() or ch in ("-", "_"))
            dial_digits = _normalize_pstn_digits(digits, trunk)
            if not (2 <= len(digits) <= 15):
                return web.json_response(
                    {"error": "phone_number must contain 2-15 digits"}, status=400
                )
            if not trunk:
                return web.json_response({"error": "trunk is required"}, status=400)
            routing = RoutingIntent(
                target_type="asterisk",
                target_id=f"pstn_{trunk}_{dial_digits}",
                target_label=body.get("target_label", "") or f"+{digits}",
                extension=dial_digits,
                context=self.cfg.asterisk_context,
                trunk=trunk,
                caller_id=body.get("caller_id", ""),
                timeout=int(body.get("timeout", 60) or 60),
            )
            call_type = "sip"
            to_node = f"sip:{dial_digits}"

        # If target_id is given, resolve from directory.
        elif target_id and self.target_dir:
            routing = self.target_dir.resolve_routing(target_id)
            if not routing:
                # Auto-discovered Asterisk targets have id format "asterisk_{ext}"
                # but aren't stored in the directory.  Build a synthetic routing.
                if target_id.startswith("asterisk_"):
                    ext = target_id[len("asterisk_"):]
                    inferred_trunk = ""
                    digits = "".join(ch for ch in str(ext) if ch.isdigit())
                    if str(ext).strip().startswith("+") or len(digits) >= 7:
                        preferred_trunk = (self.cfg.routing_policy or {}).get("default_gateway_trunk", "")
                        inferred_trunk = "".join(
                            ch for ch in str(trunk or preferred_trunk or DEFAULT_PSTN_TRUNK).strip()
                            if ch.isalnum() or ch in ("-", "_")
                        )
                        ext = _normalize_pstn_digits(digits, inferred_trunk)
                    routing = RoutingIntent(
                        target_type="asterisk",
                        target_id=target_id,
                        target_label=ext,
                        extension=ext,
                        context=self.cfg.asterisk_context,
                        trunk=inferred_trunk,
                        timeout=60,
                    )
                else:
                    return web.json_response({"error": f"unknown target: {target_id}"}, status=404)

            if self._target_blocked(target_id):
                fallback_id = self._first_available_fallback(routing.fallback_targets)
                if not fallback_id:
                    availability = self._target_availability(target_id)
                    return web.json_response({
                        "error": "target unavailable",
                        "target_id": target_id,
                        "availability": availability,
                    }, status=409)
                fallback_routing = self.target_dir.resolve_routing(fallback_id)
                if not fallback_routing:
                    return web.json_response({
                        "error": f"fallback target unavailable: {fallback_id}",
                    }, status=409)
                logger.info(
                    "Target %s is unavailable; routing call to fallback %s",
                    target_id, fallback_id,
                )
                target_id = fallback_id
                routing = fallback_routing

            if routing.target_type in ("asterisk", "sip", "gateway"):
                call_type = "sip"
                ext = (routing.extension or "").strip()
                if routing.trunk:
                    ext = "".join(ch for ch in ext if ch.isdigit())
                if ext:
                    # Central VPS SIP path: route through Asterisk ConfBridge so
                    # the browser card joins the same audio room as the SIP phone.
                    to_node = f"sip:{ext}"
                else:
                    return web.json_response({"error": "asterisk target missing extension"}, status=400)
            else:
                to_node = self.target_dir.resolve_node_id(target_id)
        elif not to_node:
            return web.json_response({"error": "target_node_id or target_id required"}, status=400)

        # Check no active call for this user (allows multiple users on same node to call concurrently).
        if self.call_mgr.active_call_for_user(caller_user_id):
            return web.json_response({"error": "already in a call"}, status=409)

        # ── Normal VPS-routed call ────────────────────────────────────────────
        # Build metadata with routing info if available.
        metadata = {}
        remote_label = ""
        if routing:
            remote_label = routing.target_label or routing.extension or routing.target_id
            metadata["target_id"] = routing.target_id or target_id
            metadata["target_type"] = routing.target_type
            metadata["target_label"] = remote_label
            # Central SIP path (to_node_id = sip:EXT) needs conservative,
            # flat metadata for compatibility with older VPS payload decoders.
            if routing.target_type in ("asterisk", "sip", "gateway") and str(to_node).startswith("sip:"):
                # Always send a caller_id so the SIP phone shows a useful callback number.
                metadata["caller_id"] = (
                    str(body.get("caller_id", "")).strip()
                    or routing.caller_id
                    or f'"{self.cfg.node_label or self.cfg.node_id}" <100>'
                )
                metadata["extension"] = routing.extension
                metadata["context"] = routing.context
                metadata["trunk"] = routing.trunk
                metadata["target_extension"] = routing.extension
            else:
                metadata["routing"] = {
                    "target_type": routing.target_type,
                    "target_id": routing.target_id,
                    "extension": routing.extension,
                    "context": routing.context,
                    "trunk": routing.trunk,
                    "caller_id": routing.caller_id,
                    "timeout": routing.timeout,
                }

        # Per-user targeting: include target_user_id so only that user's card rings.
        if target_user_id:
            metadata["target_user_id"] = target_user_id
            metadata["target_user_name"] = target_user_name
        if caller_user_id:
            metadata["caller_user_id"] = caller_user_id
        if source != "api":
            metadata["automation_source"] = source

        # Build and send call.request.
        msg = make_call_request(self.cfg.node_id, to_node, call_type, metadata=metadata or None)
        call_id = msg["payload"]["call_id"]

        if self.addon and hasattr(self.addon, "track_outgoing_call_request"):
            self.addon.track_outgoing_call_request(msg.get("id", ""), call_id)

        # Register locally before sending so immediate VPS error(ref=id)
        # can always map back to an existing call and transition state.
        call = await self.call_mgr.outgoing_request(call_id, to_node, call_type, routing=routing,
                                                    caller_user_id=caller_user_id,
                                                    remote_label=remote_label or target_id or to_node)
        if self.addon and hasattr(self.addon, "_emit_call_event"):
            await self.addon._emit_call_event(call, "outgoing")

        try:
            await self.send_fn(msg)
        except Exception as e:
            if self.addon and hasattr(self.addon, "forget_outgoing_call_request"):
                self.addon.forget_outgoing_call_request(msg.get("id", ""))
            failed_call = await self.call_mgr.update_status(call_id, "failed", "send_failed")
            if self.addon and hasattr(self.addon, "_emit_call_event") and failed_call:
                await self.addon._emit_call_event(failed_call, "failed", "send_failed")
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        return web.json_response({
            "call_id": call_id,
            "status": "requesting",
            "target_id": target_id or to_node,
        }, status=201)

    async def handle_get_automation(self, request: web.Request) -> web.Response:
        """Return a safe automation summary for the onsite admin UI."""
        automation = self.cfg.automation or {}
        webhook_id = str(automation.get("webhook_id", "")).strip()
        return web.json_response({
            "webhook_enabled": bool(automation.get("webhook_enabled", False)),
            "webhook_id": webhook_id,
            "webhook_path": f"api/automation/webhook/{webhook_id}" if webhook_id else "",
            "cooldown_seconds": _safe_int(automation.get("cooldown_seconds", 90), 90, 1, 3600),
            "block_while_call_active": bool(automation.get("block_while_call_active", True)),
            "triggers": automation.get("triggers", []) or [],
        })

    async def handle_run_automation_trigger(self, request: web.Request) -> web.Response:
        """Run a configured preset from a local HA service or trusted caller."""
        return await self._execute_automation_trigger(
            request.match_info.get("trigger_id", ""),
            source="ha_service",
        )

    async def handle_automation_webhook(self, request: web.Request) -> web.Response:
        """Run an admin-approved preset through a secret-bearing webhook."""
        automation = self.cfg.automation or {}
        if not automation.get("webhook_enabled"):
            return web.json_response({"error": "webhooks are disabled"}, status=404)

        webhook_id = request.match_info.get("webhook_id", "")
        expected_id = str(automation.get("webhook_id", "")).strip()
        if not expected_id or not hmac.compare_digest(webhook_id, expected_id):
            return web.json_response({"error": "webhook not found"}, status=404)

        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            return web.json_response({"error": "json body must be an object"}, status=400)

        supplied_secret = request.headers.get("X-Simson-Webhook-Secret", "")
        if not supplied_secret:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                supplied_secret = auth_header[7:].strip()
        if not supplied_secret:
            supplied_secret = str(body.get("secret", "")).strip()

        expected_secret = str(automation.get("webhook_secret", "")).strip()
        if not expected_secret or not hmac.compare_digest(supplied_secret, expected_secret):
            logger.warning("Rejected automation webhook with invalid secret")
            return web.json_response({"error": "unauthorized"}, status=401)

        trigger_id = str(body.get("trigger_id", "")).strip()
        if not trigger_id:
            return web.json_response({"error": "trigger_id is required"}, status=400)
        return await self._execute_automation_trigger(trigger_id, source="webhook")

    async def handle_automation_device_webhook(self, request: web.Request) -> web.Response:
        """Run a saved preset from GET-only onsite hardware through a capability URL.

        Some camera panels cannot send POST bodies or custom headers. Their callback
        URL therefore carries the random webhook ID and a pre-approved trigger ID.
        The URL is a revocable bearer capability: keep it private and regenerate
        webhook credentials if it is exposed.
        """
        automation = self.cfg.automation or {}
        if not automation.get("webhook_enabled"):
            return web.json_response({"error": "webhooks are disabled"}, status=404)

        webhook_id = request.match_info.get("webhook_id", "")
        expected_id = str(automation.get("webhook_id", "")).strip()
        if not expected_id or not hmac.compare_digest(webhook_id, expected_id):
            return web.json_response({"error": "webhook not found"}, status=404)

        trigger_id = str(request.match_info.get("trigger_id", "")).strip()
        if not trigger_id:
            return web.json_response({"error": "trigger_id is required"}, status=400)
        logger.info("Running GET-only device webhook for saved trigger %s", trigger_id)
        return await self._execute_automation_trigger(trigger_id, source="device_webhook")

    async def handle_automation_legacy_get(self, request: web.Request) -> web.Response:
        """Run the single saved door flow for GET-only camera panels.

        This is the normal practical device URL: the outdoor panel calls one
        stable site callback, while the addon settings decide which destinations
        should ring. It can invoke only one enabled door preset, never an
        arbitrary trigger or destination.
        """
        automation = self.cfg.automation or {}
        if not automation.get("webhook_enabled"):
            return web.json_response({"error": "webhooks are disabled"}, status=404)

        webhook_id = request.match_info.get("webhook_id", "")
        expected_id = str(automation.get("webhook_id", "")).strip()
        if not expected_id or not hmac.compare_digest(webhook_id, expected_id):
            return web.json_response({"error": "webhook not found"}, status=404)

        door_triggers = [
            item
            for item in (automation.get("triggers", []) or [])
            if isinstance(item, dict)
            if item.get("enabled", True)
            if str(item.get("mode", "")).strip() == "door_station"
            if str(item.get("id", "")).strip()
        ]
        if len(door_triggers) != 1:
            return web.json_response(
                {
                    "error": "legacy GET callback requires exactly one enabled door station preset",
                    "use": "/api/automation/device/{webhook_id}/{trigger_id}",
                },
                status=409,
            )

        trigger_id = str(door_triggers[0]["id"]).strip()
        logger.info("Running GET-only camera webhook for saved door trigger %s", trigger_id)
        return await self._execute_automation_trigger(trigger_id, source="legacy_device_webhook")

    async def _execute_automation_trigger(self, trigger_id: str, source: str) -> web.Response:
        """Resolve a configured preset and invoke the normal call handler."""
        automation = self.cfg.automation or {}
        trigger = next(
            (
                item for item in (automation.get("triggers", []) or [])
                if isinstance(item, dict)
                if str(item.get("id", "")).strip() == str(trigger_id).strip()
            ),
            None,
        )
        if not trigger or not trigger.get("enabled", True):
            return web.json_response({"error": "automation trigger not found or disabled"}, status=404)

        if automation.get("block_while_call_active", True) and self.call_mgr.active_call:
            active = self.call_mgr.active_call
            logger.info(
                "Suppressed automation trigger %s from %s because call %s is %s",
                trigger_id,
                source,
                active.call_id,
                active.state.value,
            )
            return web.json_response({
                "error": "automation trigger suppressed while a call is active",
                "active_call_id": active.call_id,
                "active_state": active.state.value,
                "retry_after": 10,
            }, status=429)

        now = time.time()
        blocked_until = self._automation_block_until.get(trigger_id, 0)
        if now < blocked_until:
            retry_after = max(1, int(blocked_until - now))
            logger.info(
                "Suppressed automation trigger %s from %s for %ss VPS retry window",
                trigger_id,
                source,
                retry_after,
            )
            return web.json_response({
                "error": "automation trigger waiting for upstream retry window",
                "retry_after": retry_after,
            }, status=429)

        global_cooldown = _safe_int(automation.get("cooldown_seconds", 90), 90, 1, 3600)
        cooldown = _safe_int(trigger.get("cooldown_seconds", global_cooldown), global_cooldown, 1, 3600)
        if str(trigger.get("mode", "standard")).strip() == "door_station":
            cooldown = max(cooldown, 20)
        last_run = self._automation_last_run.get(trigger_id, 0)
        if now - last_run < cooldown:
            retry_after = max(1, int(cooldown - (now - last_run)))
            logger.info(
                "Suppressed automation trigger %s from %s for %ss cooldown",
                trigger_id,
                source,
                retry_after,
            )
            return web.json_response({
                "error": "automation trigger rate limited",
                "retry_after": retry_after,
                "cooldown_seconds": cooldown,
                "last_run_age_seconds": int(now - last_run),
            }, status=429)

        target_ids = self._trigger_target_ids(trigger)
        target_id = target_ids[0] if target_ids else ""
        if not target_ids:
            return web.json_response({"error": "automation trigger has no target"}, status=422)

        self._automation_last_run[trigger_id] = now
        logger.info("Running automation trigger %s from %s to target(s) %s", trigger_id, source, target_ids)
        if str(trigger.get("mode", "standard")).strip() == "door_station":
            response = await self._initiate_door_station_calls(trigger_id, trigger, source)
            if response.status >= 400 and response.status != 429:
                self._automation_last_run.pop(trigger_id, None)
            return response

        if len(target_ids) > 1:
            response = await self._initiate_standard_trigger_calls(trigger_id, trigger, source, target_ids)
            if response.status >= 400 and response.status != 429:
                self._automation_last_run.pop(trigger_id, None)
            return response

        response = await self._initiate_call({
            "target_id": target_id,
            "caller_id": str(trigger.get("caller_id", "")).strip(),
            "caller_user_id": f"automation:{trigger_id}",
        }, source=f"{source}:{trigger_id}")

        if response.status >= 400 and response.status != 429:
            self._automation_last_run.pop(trigger_id, None)
            return response

        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_automation_triggered", {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "target_id": target_id,
                "target_ids": target_ids,
                "source": source,
                "mode": str(trigger.get("mode", "standard")).strip() or "standard",
                "status": "started",
            })
        return response

    def _trigger_target_ids(self, trigger: dict) -> list[str]:
        """Return unique trigger target IDs, preserving legacy target_id support."""
        raw = trigger.get("target_ids")
        if not isinstance(raw, list):
            raw = []
        ids: list[str] = []
        for item in raw + [trigger.get("target_id", "")]:
            target_id = str(item or "").strip()
            if target_id and target_id not in ids:
                ids.append(target_id)
        return ids

    async def _initiate_standard_trigger_calls(
        self,
        trigger_id: str,
        trigger: dict,
        source: str,
        target_ids: list[str],
    ) -> web.Response:
        """Fan out a standard automation trigger to multiple saved targets."""
        results = []
        for target_id in target_ids:
            response = await self._initiate_call({
                "target_id": target_id,
                "caller_id": str(trigger.get("caller_id", "")).strip(),
                "caller_user_id": f"automation:{trigger_id}:{target_id}",
            }, source=f"{source}:{trigger_id}")
            results.append(self._response_summary(response, target_id))

        ok = [item for item in results if 200 <= item["status"] < 400]
        payload = {
            "trigger_id": trigger_id,
            "label": trigger.get("label", trigger_id),
            "target_ids": target_ids,
            "source": source,
            "mode": str(trigger.get("mode", "standard")).strip() or "standard",
            "status": "started" if ok else "failed",
            "results": results,
        }
        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_automation_triggered", payload)
        return web.json_response(payload, status=202 if ok else 502)

    def _response_summary(self, response: web.Response, target_id: str) -> dict:
        """Summarize an internal aiohttp response without leaking implementation details."""
        try:
            data = json.loads(response.text or "{}")
        except Exception:
            data = {"body": response.text}
        return {
            "target_id": target_id,
            "status": response.status,
            "ok": 200 <= response.status < 400,
            "data": data,
        }

    async def _initiate_door_station_call(self, trigger_id: str, trigger: dict, source: str) -> web.Response:
        """Backward-compatible wrapper for the old single-target door flow."""
        return await self._initiate_door_station_calls(trigger_id, trigger, source)

    async def _initiate_door_station_calls(self, trigger_id: str, trigger: dict, source: str) -> web.Response:
        """Start one or more tenant-scoped door-camera actions."""
        if not self.cfg.account_id or not self.cfg.node_id or not self.cfg.install_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "door station calls require a provisioned addon node"},
                status=400,
            )
        source_extension = str(trigger.get("source_extension", "")).strip()
        if not source_extension.isdigit():
            return web.json_response(
                {"error": "door station source must be a numeric SIP extension"},
                status=422,
            )

        try:
            timeout_sec = int(trigger.get("timeout", 30))
        except (TypeError, ValueError):
            return web.json_response({"error": "door station timeout must be an integer"}, status=422)
        if not 5 <= timeout_sec <= 120:
            return web.json_response({"error": "door station timeout must be between 5 and 120 seconds"}, status=422)

        target_ids = self._trigger_target_ids(trigger)
        if not target_ids:
            return web.json_response({"error": "door station trigger has no targets"}, status=422)

        fanout_mode = str(trigger.get("fanout_mode", "parallel")).strip() or "parallel"
        if fanout_mode not in ("parallel", "priority"):
            fanout_mode = "parallel"

        resolved_targets: list[tuple[str, RoutingIntent | None]] = []
        for target_id in target_ids:
            routing = self.target_dir.resolve_routing(target_id) if self.target_dir else None
            if not routing:
                resolved_targets.append((target_id, None))
            else:
                resolved_targets.append((target_id, routing))

        sip_targets = [
            (target_id, routing)
            for target_id, routing in resolved_targets
            if routing is not None and routing.target_type in ("sip", "asterisk")
        ]
        node_targets = [
            (target_id, routing)
            for target_id, routing in resolved_targets
            if routing is not None and routing.target_type in ("node", "device")
        ]

        results = []
        mixed_shared_bridge = bool(node_targets and sip_targets)
        if mixed_shared_bridge:
            results.extend(await self._initiate_door_station_node_targets(
                trigger_id,
                trigger,
                source,
                node_targets,
                source_extension,
                timeout_sec,
                sip_targets=sip_targets,
            ))
            ok = [item for item in results if item.get("ok")]
            retry_after = max(
                [
                    _safe_int(item.get("retry_after", 0), 0, 0, 3600)
                    for item in results
                    if int(item.get("status", 0) or 0) == 429
                ] or [0]
            )
            if retry_after:
                self._automation_block_until[trigger_id] = time.time() + retry_after
            payload = {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "source": source,
                "source_extension": source_extension,
                "target_ids": target_ids,
                "fanout_mode": fanout_mode,
                "mode": "door_station",
                "media_mode": "shared_bridge_audio",
                "status": "started" if ok else "failed",
                "retry_after": retry_after,
                "results": results,
            }
            if self.addon and getattr(self.addon, "ha", None):
                await self.addon.ha.publish_automation_event("simson_automation_triggered", payload)
            return web.json_response(payload, status=202 if ok else (429 if retry_after else 502))

        if len(sip_targets) > 1 and fanout_mode != "priority":
            return web.json_response(
                {
                    "error": (
                        "door stations can only serve one native SIP-video call at a time. "
                        "Select one SIP/video destination, add a HAOS target to use shared bridge fanout, "
                        "or choose priority mode."
                    )
                },
                status=422,
            )

        for target_id, routing in resolved_targets:
            if not routing:
                results.append({
                    "target_id": target_id,
                    "status": 404,
                    "ok": False,
                    "error": "target not found",
                })
                continue
            if routing.target_type in ("sip", "asterisk"):
                result = await self._initiate_door_station_sip_target(
                    trigger_id,
                    trigger,
                    source,
                    routing,
                    source_extension,
                    timeout_sec,
                )
            elif routing.target_type in ("node", "device"):
                # HAOS/browser cards are handled as one shared ConfBridge below.
                continue
            else:
                result = {
                    "target_id": target_id,
                    "target_type": routing.target_type,
                    "status": 422,
                    "ok": False,
                    "error": "door station targets must be SIP phones or HAOS nodes",
                }
            results.append(result)
            if fanout_mode == "priority" and result.get("ok"):
                skipped = [tid for tid in target_ids if tid not in {item.get("target_id") for item in results}]
                for skipped_id in skipped:
                    results.append({
                        "target_id": skipped_id,
                        "status": 204,
                        "ok": True,
                        "skipped": True,
                        "reason": "priority mode stopped after first successful target",
                    })
                break

        if node_targets:
            if fanout_mode != "priority" or not any(item.get("ok") for item in results):
                results.extend(await self._initiate_door_station_node_targets(
                    trigger_id,
                    trigger,
                    source,
                    node_targets,
                    source_extension,
                    timeout_sec,
                ))

        ok = [item for item in results if item.get("ok")]
        retry_after = max(
            [
                _safe_int(item.get("retry_after", 0), 0, 0, 3600)
                for item in results
                if int(item.get("status", 0) or 0) == 429
            ] or [0]
        )
        if retry_after:
            self._automation_block_until[trigger_id] = time.time() + retry_after
        payload = {
            "trigger_id": trigger_id,
            "label": trigger.get("label", trigger_id),
            "source": source,
            "source_extension": source_extension,
            "target_ids": target_ids,
            "fanout_mode": fanout_mode,
            "mode": "door_station",
            "status": "started" if ok else "failed",
            "retry_after": retry_after,
            "results": results,
        }
        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_automation_triggered", payload)
        return web.json_response(payload, status=202 if ok else (429 if retry_after else 502))

    async def _publish_door_station_node_notification(
        self,
        trigger_id: str,
        trigger: dict,
        source: str,
        routing: RoutingIntent,
        source_extension: str,
    ) -> dict:
        """Publish a safe HA event for mixed native SIP-video + HAOS flows."""
        target_id = routing.target_id
        reason = (
            "HAOS media bridge skipped because the outdoor SIP station is already "
            "in a native H.264 SIP call. Select only HAOS targets for browser "
            "audio, or only SIP/video targets for native video."
        )
        payload = {
            "trigger_id": trigger_id,
            "label": trigger.get("label", trigger_id),
            "source": source,
            "source_extension": source_extension,
            "target_id": target_id,
            "target_type": routing.target_type,
            "target_label": routing.target_label,
            "status": "skipped",
            "media_mode": "event_only",
            "reason": reason,
        }
        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_door_station_call", payload)
            await self._notify_door_station_skip(trigger, routing, source_extension, reason, payload)
        logger.info(
            "Door station trigger %s skipped HAOS media target %s: source %s is already used by native SIP video",
            trigger_id,
            target_id,
            source_extension,
        )
        return {
            "target_id": target_id,
            "target_type": routing.target_type,
            "status": 202,
            "ok": True,
            "phase": "event_only",
            "media_mode": "event_only",
            "reason": reason,
        }

    async def _notify_door_station_skip(
        self,
        trigger: dict,
        routing: RoutingIntent,
        source_extension: str,
        reason: str,
        payload: dict,
    ) -> None:
        """Notify HA users when a mixed door-video flow cannot ring HAOS media."""
        if not self.addon or not getattr(self.addon, "ha", None):
            return
        label = str(trigger.get("label", "Door camera event")).strip() or "Door camera event"
        target_label = routing.target_label or routing.target_id
        title = "Simson Door Event"
        message = (
            f"{label}: outdoor SIP {source_extension} is already serving the native "
            f"SIP video call, so HAOS target {target_label} was notified but not called. "
            "Select only HAOS targets for browser audio, or only SIP/video targets for native video."
        )
        settings = load_settings()
        automation = settings.get("automation") or {}
        if automation.get("persistent_notifications", True):
            await self.addon.ha.create_notification(
                f"simson_door_{str(trigger.get('id', 'event')).strip() or 'event'}",
                title,
                message,
            )
        notify_services = [
            item.strip()
            for item in str(automation.get("notify_services", "")).split(",")
            if item.strip()
        ]
        for service_ref in notify_services:
            await self.addon.ha.send_notify_message(
                service_ref,
                message,
                title=title,
                data={
                    "tag": f"simson-door-{str(trigger.get('id', 'event')).strip() or 'event'}",
                    "group": "simson-door",
                    "notification_icon": "mdi:cctv",
                    "simson": payload,
                },
            )

    async def _initiate_door_station_node_targets(
        self,
        trigger_id: str,
        trigger: dict,
        source: str,
        node_targets: list[tuple[str, RoutingIntent]],
        source_extension: str,
        timeout_sec: int,
        sip_targets: list[tuple[str, RoutingIntent]] | None = None,
    ) -> list[dict]:
        """Start one shared audio bridge for HAOS nodes and optional SIP phones."""
        sip_targets = sip_targets or []
        node_ids: list[str] = []
        target_ids: list[str] = []
        for target_id, routing in node_targets:
            node_id = self.target_dir.resolve_node_id(target_id) if self.target_dir else target_id
            node_id = str(node_id or "").strip()
            if not node_id:
                continue
            if node_id not in node_ids:
                node_ids.append(node_id)
            target_ids.append(target_id)
        sip_extensions: list[str] = []
        sip_target_ids: list[str] = []
        for target_id, routing in sip_targets:
            ext = str(routing.extension or "").strip()
            if not ext:
                continue
            if ext not in sip_extensions:
                sip_extensions.append(ext)
            sip_target_ids.append(target_id)

        if not node_ids and not sip_extensions:
            return [{
                "target_id": ",".join(target_ids) or "haos",
                "target_type": "node",
                "status": 422,
                "ok": False,
                "error": "HAOS door target has no node_id",
            }]

        payload = {
            "source_extension": source_extension,
            "target_node_ids": node_ids,
            "target_sip_extensions": sip_extensions,
            "caller_id": str(trigger.get("caller_id", "")).strip(),
            "trigger_id": trigger_id,
            "timeout_sec": timeout_sec,
        }
        base = self._ws_to_http_url(self.cfg.server_url)
        headers = {
            "X-Simson-Account-ID": self.cfg.account_id,
            "X-Simson-Node-ID": self.cfg.node_id,
            "X-Simson-Install-Token": self.cfg.install_token,
            "Content-Type": "application/json",
        }
        timeout = ClientTimeout(total=10)
        try:
            async with ClientSession(timeout=timeout) as session:
                url = f"{base}/node/door-node-events"
                async with session.post(url, json=payload, headers=headers, ssl=False) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {"error": await resp.text()}
                    if resp.status not in (200, 201, 202):
                        logger.error("VPS door HAOS event failed: %s %s", resp.status, data)
                        return [{
                            "target_id": ",".join(target_ids),
                            "target_type": "node",
                            "status": resp.status,
                            "ok": False,
                            "error": data.get("error", "door station HAOS request failed"),
                            "retry_after": data.get("retry_after", 0),
                        }]
        except Exception as exc:
            logger.error("Door station HAOS event error: %s", exc)
            return [{
                "target_id": ",".join(target_ids),
                "target_type": "node",
                "status": 502,
                "ok": False,
                "error": f"door station HAOS request failed: {exc}",
            }]

        logger.info(
            "Door station trigger %s started HAOS bridge %s -> %s",
            trigger_id,
            source_extension,
            ",".join(node_ids + [f"sip:{ext}" for ext in sip_extensions]),
        )
        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_door_station_call", {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "source": source,
                "source_extension": source_extension,
                "target_ids": target_ids,
                "target_node_ids": node_ids,
                "target_sip_extensions": data.get("target_sip_extensions", sip_extensions),
                "call_id": data.get("call_id", ""),
                "sip_bridge_id": data.get("sip_bridge_id", ""),
                "status": data.get("status", "calling_door_station"),
                "media_mode": "shared_bridge_audio" if sip_extensions else "webrtc_audio",
            })
        node_results = [
            {
                "target_id": target_id,
                "target_type": routing.target_type,
                "target_node_id": self.target_dir.resolve_node_id(target_id) if self.target_dir else target_id,
                "call_id": data.get("call_id", ""),
                "sip_bridge_id": data.get("sip_bridge_id", ""),
                "phase": data.get("status", "calling_door_station"),
                "status": 202,
                "ok": True,
                "media_mode": "shared_bridge_audio" if sip_extensions else "webrtc_audio",
            }
            for target_id, routing in node_targets
        ]
        sip_results = [
            {
                "target_id": target_id,
                "target_type": routing.target_type,
                "target_extension": str(routing.extension or "").strip(),
                "call_id": data.get("call_id", ""),
                "sip_bridge_id": data.get("sip_bridge_id", ""),
                "phase": data.get("status", "calling_door_station"),
                "status": 202,
                "ok": True,
                "media_mode": "shared_bridge_audio",
            }
            for target_id, routing in sip_targets
        ]
        return node_results + sip_results

    async def _initiate_door_station_sip_target(
        self,
        trigger_id: str,
        trigger: dict,
        source: str,
        routing: RoutingIntent,
        source_extension: str,
        timeout_sec: int,
    ) -> dict:
        """Start a native SIP door-camera bridge to one SIP-capable target."""
        target_id = routing.target_id
        target_extension = str(routing.extension or "").strip()
        if not target_extension.isdigit():
            return {
                "target_id": target_id,
                "target_type": routing.target_type,
                "status": 422,
                "ok": False,
                "error": "door station SIP target must have a numeric extension",
            }
        if source_extension == target_extension:
            return {
                "target_id": target_id,
                "target_type": routing.target_type,
                "target_extension": target_extension,
                "status": 422,
                "ok": False,
                "error": "door station source and target extension cannot match",
            }

        payload = {
            "source_extension": source_extension,
            "target_extension": target_extension,
            "caller_id": str(trigger.get("caller_id", "")).strip(),
            "trigger_id": trigger_id,
            "timeout_sec": timeout_sec,
        }
        base = self._ws_to_http_url(self.cfg.server_url)
        headers = {
            "X-Simson-Account-ID": self.cfg.account_id,
            "X-Simson-Node-ID": self.cfg.node_id,
            "X-Simson-Install-Token": self.cfg.install_token,
            "Content-Type": "application/json",
        }
        timeout = ClientTimeout(total=10)
        try:
            async with ClientSession(timeout=timeout) as session:
                url = f"{base}/node/door-events"
                async with session.post(url, json=payload, headers=headers, ssl=False) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {"error": await resp.text()}
                    if resp.status not in (200, 201, 202):
                        logger.error("VPS door event failed: %s %s", resp.status, data)
                        data.update({
                            "target_id": target_id,
                            "target_type": routing.target_type,
                            "target_extension": target_extension,
                            "status": resp.status,
                            "ok": False,
                        })
                        return data
        except Exception as exc:
            logger.error("Door station event error: %s", exc)
            return {
                "target_id": target_id,
                "target_type": routing.target_type,
                "target_extension": target_extension,
                "status": 502,
                "ok": False,
                "error": f"door station request failed: {exc}",
            }

        logger.info(
            "Door station trigger %s started native SIP bridge %s -> %s",
            trigger_id,
            source_extension,
            target_extension,
        )
        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.publish_automation_event("simson_door_station_call", {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "source": source,
                "source_extension": source_extension,
                "target_id": target_id,
                "target_extension": target_extension,
                "call_id": data.get("call_id", ""),
                "status": data.get("status", "calling_door_station"),
            })
        data.update({
            "target_id": target_id,
            "target_type": routing.target_type,
            "target_extension": target_extension,
            "phase": data.get("status", "calling_door_station"),
            "status": 202,
            "ok": True,
        })
        return data

    async def handle_answer(self, request: web.Request) -> web.Response:
        """Answer an incoming call."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = str(body.get("call_id", "") or "").strip()
        answered_by_user_id = body.get("answered_by_user_id", "")
        strict_call_id = bool(body.get("strict_call_id"))
        open_dashboard = bool(body.get("open_dashboard"))
        notify_ref = str(body.get("notify_ref", "") or "").strip()
        call, fallback_used = self._resolve_call_for_control(
            call_id,
            allowed_states={CallState.INCOMING, CallState.RINGING, CallState.ACTIVE},
            prefer_direction="incoming",
            allow_fallback=not strict_call_id,
        )
        if not call:
            return web.json_response({
                "error": "no answerable incoming call",
                "requested_call_id": call_id,
                "active_call": _call_to_dict(self.call_mgr.active_call) if self.call_mgr.active_call else None,
            }, status=404)

        if call.state == CallState.ACTIVE:
            dashboard_open_requested = False
            if open_dashboard and notify_ref:
                dashboard_open_requested = await self._open_call_dashboard(notify_ref)
            return web.json_response({
                "call_id": call.call_id,
                "status": "already_active",
                "dashboard_open_requested": dashboard_open_requested,
            })

        msg = make_call_accept(call.call_id, self.cfg.node_id,
                               answered_by_user_id=answered_by_user_id)
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        dashboard_open_requested = False
        if open_dashboard and notify_ref:
            dashboard_open_requested = await self._open_call_dashboard(notify_ref)

        return web.json_response({
            "call_id": call.call_id,
            "status": "accepted",
            "fallback_used": fallback_used,
            "dashboard_open_requested": dashboard_open_requested,
        })

    async def _open_call_dashboard(self, notify_ref: str) -> bool:
        """Open the call UI only on the Companion device that answered."""
        if not self.addon or not getattr(self.addon, "ha", None):
            return False

        settings = load_settings()
        automation = settings.get("automation") or {}
        configured_refs = {
            item.strip()
            for item in str(automation.get("notify_services", "") or "").split(",")
            if item.strip()
        }
        if notify_ref not in configured_refs:
            logger.warning("Ignoring dashboard-open request for unconfigured notifier %s", notify_ref)
            return False

        dashboard_path = str(
            automation.get("dashboard_path", "/lovelace/default_view")
            or "/lovelace/default_view"
        ).strip()
        if not dashboard_path.startswith("/") or dashboard_path.startswith("//"):
            dashboard_path = "/lovelace/default_view"

        return await self.addon.ha.send_notify_message(
            notify_ref,
            "command_webview",
            data={"command": dashboard_path},
        )

    async def handle_reject(self, request: web.Request) -> web.Response:
        """Reject an incoming call."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = str(body.get("call_id", "") or "").strip()
        reason = body.get("reason", "declined")
        strict_call_id = bool(body.get("strict_call_id"))
        terminate_call = bool(body.get("terminate_call"))
        call, fallback_used = self._resolve_call_for_control(
            call_id,
            allowed_states={CallState.INCOMING, CallState.RINGING, CallState.REQUESTING, CallState.ACTIVE},
            prefer_direction="incoming",
            allow_fallback=not strict_call_id,
        )
        if not call:
            return web.json_response({
                "error": "no rejectable call",
                "requested_call_id": call_id,
                "active_call": _call_to_dict(self.call_mgr.active_call) if self.call_mgr.active_call else None,
            }, status=404)

        was_active = call.state == CallState.ACTIVE
        if terminate_call and call.remote_node_id.startswith("asterisk:"):
            if not self.asterisk or not self.asterisk.connected:
                return web.json_response({"error": "Asterisk is unavailable"}, status=503)
            await self.asterisk.hangup_by_call_id(call.call_id)
            await self.call_mgr.end_call(call.call_id, reason)
            return web.json_response({
                "call_id": call.call_id,
                "status": "ended",
                "fallback_used": fallback_used,
                "terminated": True,
            })

        if was_active or terminate_call:
            msg = make_call_end(call.call_id, self.cfg.node_id, reason or "hangup")
        else:
            msg = make_call_reject(call.call_id, self.cfg.node_id, reason)

        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        await self.call_mgr.end_call(call.call_id, reason)
        return web.json_response({
            "call_id": call.call_id,
            "status": "ended" if (was_active or terminate_call) else "rejected",
            "fallback_used": fallback_used,
            "terminated": terminate_call,
        })

    async def handle_hangup(self, request: web.Request) -> web.Response:
        """Hang up the current call."""
        try:
            body = await request.json()
        except Exception:
            body = {}

        call_id = str(body.get("call_id", "") or "").strip()
        explicit_hangup = bool(body.get("explicit") or body.get("user_initiated"))
        strict_call_id = bool(body.get("strict_call_id"))

        call, fallback_used = self._resolve_call_for_control(
            call_id,
            allowed_states={CallState.REQUESTING, CallState.RINGING, CallState.INCOMING, CallState.ACTIVE},
            allow_fallback=not strict_call_id,
        )
        if not call:
            return web.json_response({
                "error": "no active call",
                "requested_call_id": call_id,
            }, status=404)
        call_id = call.call_id

        # Some browser SIP bridge failures can produce an automatic /api/hangup
        # immediately after answer. Do not let that helper-leg failure kill the
        # real PSTN/GSM bridge; the explicit Hang Up button can be pressed again
        # after the call is established, and VPS/Asterisk still ends the call
        # when the outside caller really disconnects.
        if (
            not explicit_hangup
            and not body
            and call.call_type == "sip"
            and call.state == CallState.ACTIVE
            and call.answered_at
            and (time.time() - call.answered_at) < 4
        ):
            logger.warning(
                "Ignoring immediate SIP hangup for %s %.2fs after answer; likely browser bridge transition",
                call_id,
                time.time() - call.answered_at,
            )
            return web.json_response({
                "call_id": call_id,
                "status": "ignored",
                "reason": "sip_bridge_grace_period",
            })

        # Direct Asterisk calls don't go through VPS — hang up via AMI instead.
        if call.remote_node_id.startswith("asterisk:") and self.asterisk and self.asterisk.connected:
            await self.asterisk.hangup_by_call_id(call_id)
            await self.call_mgr.end_call(call_id, "hangup")
            return web.json_response({"call_id": call_id, "status": "ended", "fallback_used": fallback_used})

        msg = make_call_end(call_id, self.cfg.node_id, "hangup")
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        await self.call_mgr.end_call(call_id, "hangup")
        return web.json_response({"call_id": call_id, "status": "ended", "fallback_used": fallback_used})

    def _resolve_call_for_control(
        self,
        call_id: str,
        allowed_states: set[CallState],
        prefer_direction: str = "",
        allow_fallback: bool = True,
    ) -> tuple[object | None, bool]:
        """Resolve a call-control target without surprising 404s.

        Home Assistant actions often omit call_id, and mobile notification
        actions can carry a stale call_id after the card has already refreshed.
        Prefer an exact live call, then safely fall back to this node's current
        live call so Answer/Reject/Hangup act on the thing the user sees ringing.
        """
        call_id = str(call_id or "").strip()
        if call_id:
            call = self.call_mgr.get(call_id)
            if call and call.state in allowed_states:
                return call, False
            if call and call.state == CallState.ACTIVE and CallState.ACTIVE in allowed_states:
                return call, False
            if not allow_fallback:
                return None, False

        active = self.call_mgr.active_call
        if active and active.state in allowed_states:
            if prefer_direction and active.direction != prefer_direction:
                # For reject/answer, do not control an unrelated outgoing call
                # unless it is the only live call and the caller provided no ID.
                if call_id:
                    return None, False
            return active, bool(call_id)

        for candidate in self.call_mgr.all_calls:
            if candidate.state not in allowed_states:
                continue
            if prefer_direction and candidate.direction != prefer_direction:
                continue
            return candidate, bool(call_id)
        return None, False

    async def handle_transfer(self, request: web.Request) -> web.Response:
        """Transfer an active SIP/gateway bridge call to another node/user."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = body.get("call_id", "")
        target_node_id = str(body.get("target_node_id", "")).strip()
        target_user_id = str(body.get("target_user_id", "")).strip()
        target_user_name = str(body.get("target_user_name", "")).strip()

        if not call_id:
            active = self.call_mgr.active_call
            if active:
                call_id = active.call_id
            else:
                return web.json_response({"error": "no active call"}, status=404)
        if not target_node_id:
            return web.json_response({"error": "target_node_id is required"}, status=400)

        call = self.call_mgr.get(call_id)
        if not call or call.state != CallState.ACTIVE:
            return web.json_response({"error": "call not found or not active"}, status=404)
        if call.call_type != "sip" and not call.metadata.get("sip_bridge_id"):
            return web.json_response(
                {"error": "only active SIP/gateway calls can be transferred"},
                status=400,
            )

        msg = make_call_transfer(
            call_id,
            self.cfg.node_id,
            target_node_id,
            target_user_id=target_user_id,
            target_user_name=target_user_name,
        )
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        return web.json_response({
            "call_id": call_id,
            "status": "transfer_requested",
            "target_node_id": target_node_id,
            "target_user_id": target_user_id,
        })

    async def handle_targets(self, request: web.Request) -> web.Response:
        """Return available call targets from the target directory.

        When Asterisk AMI is connected, registered PJSIP/SIP devices are
        automatically appended so the card shows them without any YAML config.
        """
        targets = list(self.target_dir.all_targets()) if self.target_dir else []

        if self.asterisk and self.asterisk.connected:
            try:
                discovered = await asyncio.wait_for(
                    self.asterisk.get_registered_devices(), timeout=5.0
                )
                configured_ids = {t["id"] for t in targets}
                for dev in discovered:
                    if dev["id"] not in configured_ids:
                        targets.append(dev)
                logger.debug("Merged %d auto-discovered Asterisk devices", len(discovered))
            except asyncio.TimeoutError:
                logger.warning("Asterisk device discovery timed out — skipping")
            except Exception as e:
                logger.warning("Asterisk device discovery error: %s", e)

        annotated = [self._annotate_target(t) for t in targets]
        return web.json_response({"targets": annotated, "total": len(annotated)})

    def _target_availability(self, target: dict | str) -> dict:
        """Return the effective manual availability for a target id/dict."""
        target_id = target if isinstance(target, str) else target.get("id", "")
        node_id = "" if isinstance(target, str) else target.get("node_id", "")
        overrides = self.cfg.route_overrides or {}
        state = overrides.get(target_id) or (overrides.get(node_id) if node_id else None) or {}
        mode = str(state.get("mode", "available")).strip() or "available"
        if mode not in ("available", "busy", "offline"):
            mode = "available"
        return {
            "mode": mode,
            "reason": str(state.get("reason", "")).strip(),
        }

    def _annotate_target(self, target: dict) -> dict:
        """Attach availability and routing hints without mutating config."""
        annotated = copy.deepcopy(target)
        availability = self._target_availability(annotated)
        annotated["availability"] = availability
        annotated["routable"] = availability.get("mode") == "available"
        return annotated

    def _target_blocked(self, target_id: str) -> bool:
        """True when policy says this target should not receive new routed calls."""
        if not target_id or not (self.cfg.routing_policy or {}).get("skip_unavailable", True):
            return False
        return self._target_availability(target_id).get("mode") in ("busy", "offline")

    def _first_available_fallback(self, target_ids: list) -> str:
        """Return the first fallback target allowed by the current site policy."""
        candidates = [str(t).strip() for t in (target_ids or []) if str(t).strip()]
        final_target = str((self.cfg.routing_policy or {}).get("final_fallback_target", "")).strip()
        if final_target and final_target not in candidates:
            candidates.append(final_target)
        for fallback_id in candidates:
            fallback_id = str(fallback_id).strip()
            if fallback_id and not self._target_blocked(fallback_id):
                return fallback_id
        return ""

    # --- User presence endpoints ---

    async def handle_user_heartbeat(self, request: web.Request) -> web.Response:
        """Register or refresh a user's presence on this node."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        user_id = body.get("user_id", "")
        user_name = body.get("user_name", "")

        if not user_id:
            return web.json_response({"error": "user_id required"}, status=400)

        if self.addon:
            self.addon.register_user(user_id, user_name)

        return web.json_response({"registered": True})

    async def handle_user_unregister(self, request: web.Request) -> web.Response:
        """Remove a user's presence from this node."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        user_id = body.get("user_id", "")
        if user_id and self.addon:
            self.addon.unregister_user(user_id)

        return web.json_response({"unregistered": True})

    async def handle_get_users(self, request: web.Request) -> web.Response:
        """Return currently online users on this node."""
        if not self.addon:
            return web.json_response({"users": [], "total": 0})
        users = self.addon.get_online_users()
        return web.json_response({"users": users, "total": len(users)})

    async def handle_remote_users(self, request: web.Request) -> web.Response:
        """Query VPS for users on a remote node."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        node_id = body.get("node_id", "")
        if not node_id:
            return web.json_response({"error": "node_id required"}, status=400)

        if not self.addon:
            return web.json_response({"users": [], "total": 0})

        users = await self.addon.query_remote_users(node_id)
        return web.json_response({"node_id": node_id, "users": users, "total": len(users)})

    async def handle_history(self, request: web.Request) -> web.Response:
        """Return call history."""
        limit = int(request.query.get("limit", "50"))
        history = self.call_mgr.get_history(limit)
        return web.json_response({"history": history, "total": len(history)})

    async def handle_webrtc_config(self, request: web.Request) -> web.Response:
        """Return WebRTC/ICE/TURN config and SIP-over-WS credentials for the browser card.

        The card fetches this before starting RTCPeerConnection so it can use
        the TURN relay even when only STUN fails (symmetric NAT, HTTPS context).
        """
        # ── ICE servers ──────────────────────────────────────────────────────
        ice_servers: list[dict] = [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "stun:stun1.l.google.com:19302"},
        ]
        if self.cfg.turn_enabled and self.cfg.turn_url:
            entry: dict = {"urls": self.cfg.turn_url}
            if self.cfg.turn_username:
                entry["username"] = self.cfg.turn_username
            if self.cfg.turn_credential:
                entry["credential"] = self.cfg.turn_credential
            ice_servers.append(entry)

        # ── SIP-over-WebSocket config (for Asterisk ConfBridge audio) ────────
        sip_ws_url = (self.cfg.sip_ws_url or "").strip()
        sip_domain = (self.cfg.sip_domain or "").strip()
        sip_username = (self.cfg.sip_username or "webrtc-pool").strip() or "webrtc-pool"
        sip_password = (self.cfg.sip_password or "").strip()
        sip_enabled = bool(self.cfg.sip_enabled)

        # Production path: the VPS owns central SIP/WebRTC credentials. Fetch it
        # every time so stale legacy addon settings cannot override the working
        # Asterisk media bridge.
        remote_cfg = await self._fetch_vps_webrtc_config()
        if remote_cfg:
            remote_ice = remote_cfg.get("ice_servers")
            if isinstance(remote_ice, list) and remote_ice:
                ice_servers = remote_ice

            remote_sip = remote_cfg.get("sip") or {}
            if isinstance(remote_sip, dict):
                remote_enabled = bool(remote_sip.get("enabled"))
                remote_ws_url = str(remote_sip.get("ws_url") or "").strip()
                remote_domain = str(remote_sip.get("domain") or "").strip()
                remote_username = str(remote_sip.get("username") or "").strip()
                remote_password = str(remote_sip.get("password") or "").strip()

                if remote_ws_url:
                    sip_ws_url = remote_ws_url
                if remote_domain:
                    sip_domain = remote_domain
                if remote_username:
                    sip_username = remote_username
                if remote_password:
                    sip_password = remote_password
                if remote_enabled:
                    sip_enabled = True

        # If SIP fields are partially configured, derive missing WS URL/domain
        # from server_url (e.g. wss://host/ws -> wss://host/sip/ws).
        if (not sip_ws_url or not sip_domain) and self.cfg.server_url:
            parsed = urlsplit(self.cfg.server_url)
            host = parsed.hostname or ""
            netloc = parsed.netloc or host
            scheme = "wss" if parsed.scheme == "wss" else "ws"
            base_path = (parsed.path or "").rstrip("/")
            if base_path.endswith("/ws"):
                base_path = base_path[:-3]
            if not base_path:
                base_path = ""
            if not sip_ws_url and netloc:
                sip_ws_url = f"{scheme}://{netloc}{base_path}/sip/ws"
            if not sip_domain and host:
                sip_domain = host

        sip_ready = bool(sip_ws_url and sip_username and sip_password and sip_domain)
        sip_config: dict = {
            "enabled": bool(sip_enabled and sip_ready),
            "ws_url": sip_ws_url,
            "username": sip_username,
            "password": sip_password,
            "domain": sip_domain,
        }

        return web.json_response({
            "ice_servers": ice_servers,
            "sip": sip_config,
        })

    async def _fetch_vps_webrtc_config(self) -> dict:
        """Fetch central WebRTC/SIP config from VPS.

        Prefer admin auth when configured, but also support node-scoped auth so
        deployed addons do not need users to manually duplicate SIP passwords.
        """
        if not self.cfg.server_url:
            return {}
        base = self._ws_to_http_url(self.cfg.server_url)
        if not base:
            return {}

        timeout = ClientTimeout(total=5)
        async with ClientSession(timeout=timeout) as session:
            # Existing deployments: admin token can read the canonical config.
            if self.cfg.admin_token:
                try:
                    headers = {"Authorization": f"Bearer {self.cfg.admin_token}"}
                    async with session.get(f"{base}/admin/webrtc-config", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, dict):
                                return data
                        logger.debug("VPS admin webrtc-config returned HTTP %s", resp.status)
                except Exception as exc:
                    logger.debug("VPS admin webrtc-config fetch failed: %s", exc)

            # Production path: node install token authenticates this addon only.
            if self.cfg.account_id and self.cfg.node_id and self.cfg.install_token:
                try:
                    headers = {
                        "X-Simson-Account-ID": self.cfg.account_id,
                        "X-Simson-Node-ID": self.cfg.node_id,
                        "X-Simson-Install-Token": self.cfg.install_token,
                    }
                    async with session.get(f"{base}/node/webrtc-config", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, dict):
                                return data
                        logger.debug("VPS node webrtc-config returned HTTP %s", resp.status)
                except Exception as exc:
                    logger.debug("VPS node webrtc-config fetch failed: %s", exc)

        return {}

    @staticmethod
    def _normalize_sip_endpoints_payload(payload) -> list:
        """Normalize possible VPS response shapes to a plain endpoints list."""
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            if isinstance(payload.get("endpoints"), list):
                items = payload["endpoints"]
            elif isinstance(payload.get("items"), list):
                items = payload["items"]
            else:
                items = []
        else:
            items = []

        endpoints: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            endpoints.append({
                "id": item.get("id", item.get("ID", "")),
                "account_id": item.get("account_id", item.get("AccountID", "")),
                "extension": item.get("extension", item.get("Extension", "")),
                "username": item.get("username", item.get("Username", "")),
                "description": item.get("description", item.get("Description", "")),
                "route_to": item.get("route_to", item.get("RouteTo", "")),
                "video_enabled": bool(item.get("video_enabled", item.get("VideoEnabled", False))),
                "auto_answer": bool(item.get("auto_answer", item.get("AutoAnswer", False))),
                "auto_answer_callers": item.get("auto_answer_callers", item.get("AutoAnswerCallers", "")),
                "auto_speaker": bool(item.get("auto_speaker", item.get("AutoSpeaker", False))),
                "auto_speaker_callers": item.get("auto_speaker_callers", item.get("AutoSpeakerCallers", "")),
                "callback_bridge": bool(item.get("callback_bridge", item.get("CallbackBridge", False))),
                "callback_bridge_callers": item.get("callback_bridge_callers", item.get("CallbackBridgeCallers", "")),
                "callback_caller_auto_answer": bool(item.get("callback_caller_auto_answer", item.get("CallbackCallerAutoAnswer", False))),
                "callback_caller_auto_speaker": bool(item.get("callback_caller_auto_speaker", item.get("CallbackCallerAutoSpeaker", False))),
                "default_outbound": bool(item.get("default_outbound", item.get("DefaultOutbound", False))),
                "gateway_inbound_mode": item.get("gateway_inbound_mode", item.get("GatewayInboundMode", "")),
                "gateway_direct_target": item.get("gateway_direct_target", item.get("GatewayDirectTarget", "")),
                "gateway_ivr_enabled": bool(item.get("gateway_ivr_enabled", item.get("GatewayIVREnabled", False))),
                "gateway_ivr_sound": item.get("gateway_ivr_sound", item.get("GatewayIVRSound", "")),
                "answer_announcement": item.get("answer_announcement", item.get("AnswerAnnouncement", "")),
                "answer_announcement_text": item.get("answer_announcement_text", item.get("AnswerAnnouncementText", "")),
                "pre_ring_announcement": item.get("pre_ring_announcement", item.get("PreRingAnnouncement", "")),
                "pre_ring_announcement_text": item.get("pre_ring_announcement_text", item.get("PreRingAnnouncementText", "")),
                "call_duration_rules": _normalize_call_duration_rules(
                    item.get("call_duration_rules", item.get("CallDurationRules", {}))
                ),
                "supervision": _normalize_supervision(
                    item.get("supervision", item.get("Supervision", item.get("SupervisionConfig", {})))
                ),
                "enabled": bool(item.get("enabled", item.get("Enabled", True))),
                "registered": bool(item.get("registered", item.get("Registered", False))),
                "contact_status": item.get("contact_status", item.get("ContactStatus", "")),
                "contact_uri": item.get("contact_uri", item.get("ContactURI", "")),
                "contact_address": item.get("contact_address", item.get("ContactAddress", "")),
                "contact_latency_ms": item.get("contact_latency_ms", item.get("ContactLatencyMS", "")),
                "created_at": item.get("created_at", item.get("CreatedAt", "")),
                "updated_at": item.get("updated_at", item.get("UpdatedAt", "")),
            })
        return endpoints

    def _ws_to_http_url(self, ws_url: str) -> str:
        """Convert a WS/WSS URL to an HTTP(S) base URL for admin API calls.

        Examples:
          wss://example.com/ws       -> https://example.com
          wss://example.com/simson/ws -> https://example.com/simson
          ws://example.com/ws/       -> http://example.com

        Query strings and fragments are intentionally dropped.
        """
        if not ws_url:
            return ws_url

        parsed = urlsplit(ws_url)
        scheme = parsed.scheme.lower()

        if scheme == "wss":
            out_scheme = "https"
        elif scheme == "ws":
            out_scheme = "http"
        else:
            # Keep non-WS URLs unchanged except for dropping query/fragment.
            out_scheme = parsed.scheme

        path = (parsed.path or "").rstrip("/")
        if path.endswith("/ws"):
            path = path[:-3].rstrip("/")

        return urlunsplit((out_scheme, parsed.netloc, path, "", ""))


def _call_to_dict(call) -> dict:
    """Serialise a CallInfo to a JSON-safe dict."""
    now = time.time()
    active_for = 0
    if call.state.value in ("requesting", "ringing", "incoming", "active"):
        base = call.answered_at or call.started_at or now
        active_for = max(0, int(now - base))
    metadata = call.metadata or {}

    def first(*values):
        for value in values:
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    remote_node = first(call.remote_node_id)
    remote_extension = remote_node.split(":", 1)[1] if ":" in remote_node else remote_node
    source_extension = first(
        metadata.get("source_extension"),
        metadata.get("sip_extension") if call.direction == "incoming" else "",
        remote_extension if call.direction == "incoming" and remote_node.startswith(("sip:", "asterisk:")) else "",
    )
    target_extension = first(
        metadata.get("target_extension"), metadata.get("extension"),
        remote_extension if call.direction == "outgoing" and remote_node.startswith(("sip:", "asterisk:")) else "",
    )
    caller_number = first(metadata.get("caller_number"), metadata.get("sip_caller_id"), metadata.get("caller_id"), source_extension)
    callee_number = first(metadata.get("callee_number"), metadata.get("phone_number"), target_extension, metadata.get("target_id"))
    remote_number = caller_number if call.direction == "incoming" else callee_number
    remote_number = remote_number or call.remote_label or remote_extension
    remote_name = first(
        metadata.get("caller_name") if call.direction == "incoming" else metadata.get("callee_name"),
        metadata.get("sip_caller_name") if call.direction == "incoming" else metadata.get("target_label"),
        call.remote_label, remote_number,
    )
    end_clock = call.ended_at or now
    duration_seconds = max(0, int(end_clock - call.answered_at)) if call.answered_at else 0
    ring_end = call.answered_at or call.ended_at or now
    ring_duration_seconds = max(0, int(ring_end - call.started_at)) if call.started_at else 0
    d = {
        "call_id": call.call_id,
        "remote_node_id": call.remote_node_id,
        "remote_label": call.remote_label,
        "call_type": call.call_type,
        "direction": call.direction,
        "state": call.state.value,
        "started_at": call.started_at,
        "answered_at": call.answered_at,
        "ended_at": call.ended_at,
        "active_for": active_for,
        "end_reason": call.end_reason,
        "fallback_attempt": call.fallback_attempt,
        "sip_bridge_id": call.metadata.get("sip_bridge_id", ""),
        "remote_number": remote_number,
        "remote_name": remote_name,
        "display_name": remote_name or remote_number,
        "caller_number": caller_number,
        "caller_name": first(metadata.get("caller_name"), metadata.get("sip_caller_name"), caller_number),
        "callee_number": callee_number,
        "callee_name": first(metadata.get("callee_name"), metadata.get("target_label"), callee_number),
        "source_extension": source_extension,
        "target_extension": target_extension,
        "extension": call.metadata.get("extension", ""),
        "context": call.metadata.get("context", ""),
        "trunk": call.metadata.get("trunk", ""),
        "gateway_extension": first(call.metadata.get("gateway_extension"), call.metadata.get("trunk")),
        "target_id": call.metadata.get("target_id", ""),
        "target_type": call.metadata.get("target_type", ""),
        "target_label": call.metadata.get("target_label", ""),
        "caller_id": call.metadata.get("caller_id", ""),
        "target_user_id": call.metadata.get("target_user_id", ""),
        "target_user_name": call.metadata.get("target_user_name", ""),
        "caller_user_id": call.caller_user_id,
        "caller_user_name": call.metadata.get("caller_user_name", ""),
        "answered_by_user_id": call.metadata.get("answered_by_user_id", ""),
        "answered_by_user_name": call.metadata.get("answered_by_user_name", ""),
        "forwarded_to": call.metadata.get("forwarded_to", ""),
        "forwarded_extension": call.metadata.get("forwarded_extension", ""),
        "duration_seconds": duration_seconds,
        "ring_duration_seconds": ring_duration_seconds,
    }
    if call.routing:
        d["routing"] = {
            "target_type": call.routing.target_type,
            "target_id": call.routing.target_id,
            "target_label": call.routing.target_label,
            "timeout": call.routing.timeout,
            "fallback_targets": call.routing.fallback_targets,
        }
    return d
