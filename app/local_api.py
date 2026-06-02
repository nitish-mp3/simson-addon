"""Local HTTP API — exposed via HA ingress for the integration to talk to."""

import asyncio
import copy
import hmac
import json
import logging
import time
from urllib.parse import urlsplit, urlunsplit
from aiohttp import ClientSession, ClientTimeout, web

from call_manager import CallManager, CallState, RoutingIntent
from config import Config
from protocol import make_call_request, make_call_accept, make_call_reject, make_call_end, make_call_transfer, make_webrtc_signal
from provisioner import auto_provision, clear_saved_credentials
from settings import load_settings, save_settings, validate_settings
from settings_ui import INGRESS_UI_HTML
from target_directory import TargetDirectory

ADDON_VERSION = "4.1.3"
DEFAULT_PSTN_TRUNK = "7009"


def _normalize_pstn_digits(digits: str, trunk: str) -> str:
    """Normalize numbers for the current GSM gateway trunk.

    Synway's GSM port dials plain digits; for Indian mobile callbacks, sending
    91XXXXXXXXXX without a leading + can be treated as an invalid 12-digit
    domestic number by the SIM.  For trunk 7009, dial the local 10-digit mobile
    number instead.
    """
    if str(trunk).strip() == DEFAULT_PSTN_TRUNK and len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    return digits

logger = logging.getLogger("simson.api")


class LocalAPI:
    """HTTP API running inside the addon for HA integration communication."""

    def __init__(self, cfg: Config, call_mgr: CallManager,
                 send_fn, asterisk=None, wss_client=None,
                 target_dir: TargetDirectory | None = None,
                 addon=None,
                 standalone_mode: bool = False):
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
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.handle_ingress)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/calls", self.handle_list_calls)
        self.app.router.add_post("/api/call", self.handle_make_call)
        self.app.router.add_get("/api/routing", self.handle_routing)
        self.app.router.add_post("/api/availability", self.handle_availability)
        self.app.router.add_post("/api/target-availability", self.handle_target_availability)
        self.app.router.add_post("/api/answer", self.handle_answer)
        self.app.router.add_post("/api/reject", self.handle_reject)
        self.app.router.add_post("/api/hangup", self.handle_hangup)
        self.app.router.add_post("/api/transfer", self.handle_transfer)
        self.app.router.add_get("/api/health", self.handle_health)
        self.app.router.add_get("/api/targets", self.handle_targets)
        self.app.router.add_post("/api/provision", self.handle_provision)
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
        self.app.router.add_get("/api/automation", self.handle_get_automation)
        self.app.router.add_post("/api/automation/trigger/{trigger_id}", self.handle_run_automation_trigger)
        self.app.router.add_post("/api/automation/webhook/{webhook_id}", self.handle_automation_webhook)
        self.app.router.add_get("/api/automation/webhook/{webhook_id}", self.handle_automation_legacy_get)
        self.app.router.add_get(
            "/api/automation/device/{webhook_id}/{trigger_id}",
            self.handle_automation_device_webhook,
        )
        self.app.router.add_get("/api/sip-endpoints", self.handle_list_sip_endpoints)
        self.app.router.add_post("/api/sip-endpoints", self.handle_create_sip_endpoint)
        self.app.router.add_put("/api/sip-endpoints/{id}", self.handle_update_sip_endpoint)
        self.app.router.add_delete("/api/sip-endpoints/{id}", self.handle_delete_sip_endpoint)

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
        })

    async def handle_status(self, request: web.Request) -> web.Response:
        active = self.call_mgr.active_call
        vps_connected = self.wss_client.connected if self.wss_client else False
        status = {
            "node_id": self.cfg.node_id,
            "account_id": self.cfg.account_id,
            "server_url": self.cfg.server_url,
            "vps_connected": vps_connected,
            "provisioned": bool(self.cfg.install_token),
            "active_call": _call_to_dict(active) if active else None,
        }
        if self.asterisk:
            status["asterisk_connected"] = self.asterisk.connected
        status["availability"] = self.cfg.availability
        status["routing"] = self.cfg.routing_policy
        return web.json_response(status)

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

        logger.info("Settings updated via UI (restart_required=%s)", restart_required)
        return web.json_response({"saved": True, "restart_required": restart_required})

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

    async def handle_create_sip_endpoint(self, request: web.Request) -> web.Response:
        """Create a new SIP endpoint by calling VPS admin API."""
        if not self.cfg.account_id or not self.cfg.admin_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "Not yet provisioned — no account created on VPS"},
                status=400,
            )
        
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        
        # Validate required fields
        if not body.get("extension") or not body.get("username") or not body.get("password"):
            return web.json_response(
                {"error": "extension, username, and password are required"},
                status=400,
            )
        
        http_url = self._ws_to_http_url(self.cfg.server_url)
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{http_url}/admin/accounts/{self.cfg.account_id}/sip-endpoints"
                headers = {
                    "Authorization": f"Bearer {self.cfg.admin_token}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "extension": body.get("extension"),
                    "username": body.get("username"),
                    "password": body.get("password"),
                    "description": body.get("description", ""),
                    "route_to": body.get("route_to", ""),
                    "video_enabled": bool(body.get("video_enabled", False)),
                    "enabled": body.get("enabled", True),
                }
                async with session.post(url, json=payload, headers=headers, ssl=False) as resp:
                    if resp.status in (200, 201):
                        endpoint = await resp.json()
                        logger.info(f"SIP endpoint created: ext={endpoint.get('extension')}")
                        return web.json_response(endpoint, status=resp.status)
                    else:
                        error = await resp.text()
                        logger.error(f"VPS SIP create failed: {resp.status} {error}")
                        return web.json_response(
                            {"error": f"VPS returned {resp.status}: {error}"}, status=resp.status
                        )
        except Exception as e:
            logger.error(f"SIP endpoint create error: {e}")
            return web.json_response({"error": str(e)}, status=500)

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
                        logger.info("SIP endpoint updated: %s", endpoint_id)
                        return web.json_response(endpoint)

                    error = await resp.text()
                    logger.error("VPS SIP update failed: %s %s", resp.status, error)
                    return web.json_response(
                        {"error": f"VPS returned {resp.status}: {error}"},
                        status=resp.status,
                    )
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
                        error = await resp.text()
                        logger.error(f"VPS SIP delete failed: {resp.status} {error}")
                        return web.json_response(
                            {"error": f"VPS returned {resp.status}"}, status=resp.status
                        )
        except Exception as e:
            logger.error(f"SIP endpoint delete error: {e}")
            return web.json_response({"error": str(e)}, status=500)

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

        return await self._initiate_call(body)

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
            trunk = "".join(ch for ch in str(trunk or DEFAULT_PSTN_TRUNK).strip()
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
                        inferred_trunk = "".join(
                            ch for ch in str(trunk or DEFAULT_PSTN_TRUNK).strip()
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
                metadata["target_label"] = remote_label
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
        await self.call_mgr.outgoing_request(call_id, to_node, call_type, routing=routing,
                                             caller_user_id=caller_user_id,
                                             remote_label=remote_label or target_id or to_node)

        try:
            await self.send_fn(msg)
        except Exception as e:
            if self.addon and hasattr(self.addon, "forget_outgoing_call_request"):
                self.addon.forget_outgoing_call_request(msg.get("id", ""))
            await self.call_mgr.update_status(call_id, "failed", "send_failed")
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
            "cooldown_seconds": int(automation.get("cooldown_seconds", 10)),
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
        """Run the only saved door flow for panels using the historic GET URL.

        Early UI versions displayed /api/automation/webhook/{webhook_id} before
        distinguishing POST controllers from GET-only camera panels. Preserve that
        onsite URL safely: it can invoke only one enabled door preset, never an
        arbitrary trigger or destination. Sites with multiple door presets must
        use the explicit /api/automation/device/{webhook_id}/{trigger_id} URL.
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
        logger.warning(
            "Running legacy GET-only camera webhook for saved trigger %s; "
            "regenerate credentials and migrate to the explicit device callback URL",
            trigger_id,
        )
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

        cooldown = max(1, int(automation.get("cooldown_seconds", 10)))
        now = time.time()
        last_run = self._automation_last_run.get(trigger_id, 0)
        if now - last_run < cooldown:
            retry_after = max(1, int(cooldown - (now - last_run)))
            return web.json_response({
                "error": "automation trigger rate limited",
                "retry_after": retry_after,
            }, status=429)

        target_id = str(trigger.get("target_id", "")).strip()
        if not target_id:
            return web.json_response({"error": "automation trigger has no target"}, status=422)

        self._automation_last_run[trigger_id] = now
        logger.info("Running automation trigger %s from %s to target %s", trigger_id, source, target_id)
        if str(trigger.get("mode", "standard")).strip() == "door_station":
            response = await self._initiate_door_station_call(trigger_id, trigger, source)
            if response.status >= 400:
                self._automation_last_run.pop(trigger_id, None)
            return response

        response = await self._initiate_call({
            "target_id": target_id,
            "caller_id": str(trigger.get("caller_id", "")).strip(),
            "caller_user_id": f"automation:{trigger_id}",
        }, source=f"{source}:{trigger_id}")

        if response.status >= 400:
            self._automation_last_run.pop(trigger_id, None)
            return response

        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.fire_event("simson_automation_triggered", {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "target_id": target_id,
                "source": source,
            })
        return response

    async def _initiate_door_station_call(self, trigger_id: str, trigger: dict, source: str) -> web.Response:
        """Start a tenant-scoped native SIP door-camera bridge through the VPS."""
        if not self.cfg.account_id or not self.cfg.node_id or not self.cfg.install_token or not self.cfg.server_url:
            return web.json_response(
                {"error": "door station calls require a provisioned addon node"},
                status=400,
            )
        target_id = str(trigger.get("target_id", "")).strip()
        routing = self.target_dir.resolve_routing(target_id) if self.target_dir else None
        if not routing or routing.target_type not in ("sip", "asterisk"):
            return web.json_response(
                {"error": "door station target must be a saved SIP desk phone"},
                status=422,
            )
        source_extension = str(trigger.get("source_extension", "")).strip()
        target_extension = str(routing.extension or "").strip()
        if not source_extension.isdigit() or not target_extension.isdigit():
            return web.json_response(
                {"error": "door station source and target must be numeric SIP extensions"},
                status=422,
            )

        try:
            timeout_sec = int(trigger.get("timeout", routing.timeout or 30))
        except (TypeError, ValueError):
            return web.json_response({"error": "door station timeout must be an integer"}, status=422)
        if not 5 <= timeout_sec <= 120:
            return web.json_response({"error": "door station timeout must be between 5 and 120 seconds"}, status=422)

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
                        return web.json_response(data, status=resp.status)
        except Exception as exc:
            logger.error("Door station event error: %s", exc)
            return web.json_response({"error": f"door station request failed: {exc}"}, status=502)

        logger.info(
            "Door station trigger %s started native SIP bridge %s -> %s",
            trigger_id,
            source_extension,
            target_extension,
        )
        if self.addon and getattr(self.addon, "ha", None):
            await self.addon.ha.fire_event("simson_automation_triggered", {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "target_id": target_id,
                "source": source,
                "mode": "door_station",
            })
            await self.addon.ha.fire_event("simson_door_station_call", {
                "trigger_id": trigger_id,
                "label": trigger.get("label", trigger_id),
                "source": source,
                "source_extension": source_extension,
                "target_id": target_id,
                "target_extension": target_extension,
                "call_id": data.get("call_id", ""),
                "status": data.get("status", "calling_door_station"),
            })
        return web.json_response(data, status=202)

    async def handle_answer(self, request: web.Request) -> web.Response:
        """Answer an incoming call."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = body.get("call_id", "")
        answered_by_user_id = body.get("answered_by_user_id", "")
        if not call_id:
            # Auto-find incoming call.
            active = self.call_mgr.active_call
            if active and active.state == CallState.INCOMING:
                call_id = active.call_id
            else:
                return web.json_response({"error": "no incoming call"}, status=404)

        call = self.call_mgr.get(call_id)
        if not call or call.state != CallState.INCOMING:
            return web.json_response({"error": "call not found or not incoming"}, status=404)

        msg = make_call_accept(call_id, self.cfg.node_id,
                               answered_by_user_id=answered_by_user_id)
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        return web.json_response({"call_id": call_id, "status": "accepted"})

    async def handle_reject(self, request: web.Request) -> web.Response:
        """Reject an incoming call."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = body.get("call_id", "")
        reason = body.get("reason", "declined")

        if not call_id:
            active = self.call_mgr.active_call
            if active and active.state == CallState.INCOMING:
                call_id = active.call_id
            else:
                return web.json_response({"error": "no incoming call"}, status=404)

        call = self.call_mgr.get(call_id)
        if not call or call.state != CallState.INCOMING:
            return web.json_response({"error": "call not found or not incoming"}, status=404)

        msg = make_call_reject(call_id, self.cfg.node_id, reason)
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        await self.call_mgr.end_call(call_id, reason)
        return web.json_response({"call_id": call_id, "status": "rejected"})

    async def handle_hangup(self, request: web.Request) -> web.Response:
        """Hang up the current call."""
        try:
            body = await request.json()
        except Exception:
            body = {}

        call_id = body.get("call_id", "")

        if not call_id:
            active = self.call_mgr.active_call
            if active:
                call_id = active.call_id
            else:
                return web.json_response({"error": "no active call"}, status=404)

        call = self.call_mgr.get(call_id)
        if not call:
            return web.json_response({"error": "call not found"}, status=404)

        # Some browser SIP bridge failures can produce an automatic /api/hangup
        # immediately after answer. Do not let that helper-leg failure kill the
        # real PSTN/GSM bridge; the explicit Hang Up button can be pressed again
        # after the call is established, and VPS/Asterisk still ends the call
        # when the outside caller really disconnects.
        if (
            call.call_type == "sip"
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
            return web.json_response({"call_id": call_id, "status": "ended"})

        msg = make_call_end(call_id, self.cfg.node_id, "hangup")
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        await self.call_mgr.end_call(call_id, "hangup")
        return web.json_response({"call_id": call_id, "status": "ended"})

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
            return payload
        if isinstance(payload, dict):
            if isinstance(payload.get("endpoints"), list):
                return payload["endpoints"]
            if isinstance(payload.get("items"), list):
                return payload["items"]
        return []

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
        "target_user_id": call.metadata.get("target_user_id", ""),
        "target_user_name": call.metadata.get("target_user_name", ""),
        "caller_user_id": call.caller_user_id,
        "caller_user_name": call.metadata.get("caller_user_name", ""),
        "answered_by_user_id": call.metadata.get("answered_by_user_id", ""),
        "answered_by_user_name": call.metadata.get("answered_by_user_name", ""),
        "forwarded_to": call.metadata.get("forwarded_to", ""),
        "forwarded_extension": call.metadata.get("forwarded_extension", ""),
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
