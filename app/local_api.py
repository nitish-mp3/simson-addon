"""Local HTTP API — exposed via HA ingress for the integration to talk to."""

import asyncio
import copy
import json
import logging
from urllib.parse import urlsplit, urlunsplit
from aiohttp import web

from call_manager import CallManager, CallState, RoutingIntent
from config import Config
from protocol import make_call_request, make_call_accept, make_call_reject, make_call_end, make_webrtc_signal
from provisioner import auto_provision, clear_saved_credentials
from settings import load_settings, save_settings, validate_settings
from settings_ui import INGRESS_UI_HTML
from target_directory import TargetDirectory

ADDON_VERSION = "3.8.0"

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
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.handle_ingress)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/calls", self.handle_list_calls)
        self.app.router.add_post("/api/call", self.handle_make_call)
        self.app.router.add_post("/api/answer", self.handle_answer)
        self.app.router.add_post("/api/reject", self.handle_reject)
        self.app.router.add_post("/api/hangup", self.handle_hangup)
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
        return web.json_response({
            "node_id": self.cfg.node_id,
            "account_id": self.cfg.account_id,
            "server_url": self.cfg.server_url,
            "vps_connected": vps_connected,
            "provisioned": bool(self.cfg.install_token),
            "active_call": _call_to_dict(active) if active else None,
            "asterisk_connected": self.asterisk.connected if self.asterisk else False,
        })

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

    async def handle_make_call(self, request: web.Request) -> web.Response:
        """Initiate a call to another node or configured target."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        target_id = body.get("target_id", "")
        to_node = body.get("target_node_id", "") or body.get("to_node_id", "")
        call_type = body.get("call_type", "voice")
        target_user_id = body.get("target_user_id", "")
        target_user_name = body.get("target_user_name", "")
        caller_user_id = body.get("caller_user_id", "")

        routing = None

        # If target_id is given, resolve from directory.
        if target_id and self.target_dir:
            routing = self.target_dir.resolve_routing(target_id)
            if not routing:
                # Auto-discovered Asterisk targets have id format "asterisk_{ext}"
                # but aren't stored in the directory.  Build a synthetic routing.
                if target_id.startswith("asterisk_"):
                    ext = target_id[len("asterisk_"):]
                    routing = RoutingIntent(
                        target_type="asterisk",
                        target_id=target_id,
                        target_label=ext,
                        extension=ext,
                        context=self.cfg.asterisk_context,
                        timeout=60,
                    )
                else:
                    return web.json_response({"error": f"unknown target: {target_id}"}, status=404)

            if routing.target_type == "asterisk":
                call_type = "sip"
                ext = (routing.extension or "").strip()
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
            if routing.target_type == "asterisk" and str(to_node).startswith("sip:"):
                # Always send a caller_id so the SIP phone shows a useful callback number.
                metadata["caller_id"] = (
                    routing.caller_id
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

        return web.json_response({"targets": targets, "total": len(targets)})

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
            "enabled": bool(self.cfg.sip_enabled and sip_ready),
            "ws_url": sip_ws_url,
            "username": sip_username,
            "password": sip_password,
            "domain": sip_domain,
        }

        return web.json_response({
            "ice_servers": ice_servers,
            "sip": sip_config,
        })

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
        "end_reason": call.end_reason,
        "fallback_attempt": call.fallback_attempt,
        "sip_bridge_id": call.metadata.get("sip_bridge_id", ""),
        "target_user_id": call.metadata.get("target_user_id", ""),
        "target_user_name": call.metadata.get("target_user_name", ""),
        "caller_user_id": call.caller_user_id,
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
