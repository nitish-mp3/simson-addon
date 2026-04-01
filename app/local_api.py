"""Local HTTP API — exposed via HA ingress for the integration to talk to."""

import logging
from aiohttp import web

from call_manager import CallManager, CallState
from config import Config
from protocol import make_call_request, make_call_accept, make_call_reject, make_call_end

logger = logging.getLogger("simson.api")


class LocalAPI:
    """HTTP API running inside the addon for HA integration communication."""

    def __init__(self, cfg: Config, call_mgr: CallManager,
                 send_fn, asterisk=None, wss_client=None):
        """
        Args:
            cfg: Addon config.
            call_mgr: Call state manager.
            send_fn: Async callable to send protocol messages to VPS.
            asterisk: Optional AsteriskAMI instance.
            wss_client: Optional WSSClient for connection status.
        """
        self.cfg = cfg
        self.call_mgr = call_mgr
        self.send_fn = send_fn
        self.asterisk = asterisk
        self.wss_client = wss_client
        self.app = web.Application()
        self._runner = None
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
        """Serve the ingress web panel."""
        vps_connected = self.wss_client.connected if self.wss_client else False
        active = self.call_mgr.active_call
        status_class = "ok" if vps_connected else "err"
        status_text = "Connected" if vps_connected else "Disconnected"
        call_html = ""
        if active:
            call_html = (
                f'<div class="card">'
                f'<h2>Active Call</h2>'
                f'<p><b>Call ID:</b> {active.call_id[:8]}...</p>'
                f'<p><b>With:</b> {active.remote_label or active.remote_node_id}</p>'
                f'<p><b>Direction:</b> {active.direction}</p>'
                f'<p><b>State:</b> {active.state.value}</p>'
                f'</div>'
            )
        else:
            call_html = '<div class="card"><h2>Calls</h2><p>No active call</p></div>'

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simson Call Relay</title>
<style>
  body{{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:20px;background:#1c1c1c;color:#e1e1e1}}
  h1{{color:#03a9f4;margin-bottom:4px}} .sub{{color:#888;font-size:14px;margin-bottom:24px}}
  .card{{background:#2a2a2a;border-radius:12px;padding:16px 20px;margin-bottom:16px}}
  .card h2{{margin:0 0 8px;font-size:16px;color:#aaa}}
  .card p{{margin:4px 0;font-size:14px}}
  .badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:13px;font-weight:600}}
  .ok{{background:#1b5e20;color:#a5d6a7}} .err{{background:#b71c1c;color:#ef9a9a}}
  .row{{display:flex;gap:12px;flex-wrap:wrap}}
  .row .card{{flex:1;min-width:200px}}
</style></head><body>
<h1>Simson Call Relay</h1>
<p class="sub">Node: <b>{self.cfg.node_id}</b> &middot; Account: <b>{self.cfg.account_id}</b></p>
<div class="row">
  <div class="card"><h2>VPS Connection</h2><p><span class="badge {status_class}">{status_text}</span></p>
    <p>Server: {self.cfg.server_url}</p></div>
  {call_html}
</div>
<div class="card"><h2>API Endpoints</h2>
  <p>GET <code>/api/health</code> — health check</p>
  <p>GET <code>/api/status</code> — connection &amp; call status</p>
  <p>GET <code>/api/calls</code> — call history</p>
  <p>POST <code>/api/call</code> — initiate call</p>
  <p>POST <code>/api/answer</code> — answer incoming</p>
  <p>POST <code>/api/reject</code> — reject incoming</p>
  <p>POST <code>/api/hangup</code> — end call</p>
</div>
<script>setTimeout(()=>location.reload(),10000)</script>
</body></html>"""
        return web.Response(text=html, content_type="text/html")

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok",
            "addon_version": "1.0.0",
            "node_id": self.cfg.node_id,
        })

    async def handle_status(self, request: web.Request) -> web.Response:
        active = self.call_mgr.active_call
        vps_connected = self.wss_client.connected if self.wss_client else False
        return web.json_response({
            "node_id": self.cfg.node_id,
            "account_id": self.cfg.account_id,
            "vps_connected": vps_connected,
            "active_call": _call_to_dict(active) if active else None,
            "asterisk_connected": self.asterisk.connected if self.asterisk else False,
        })

    async def handle_list_calls(self, request: web.Request) -> web.Response:
        calls = self.call_mgr.all_calls
        active = self.call_mgr.active_call
        return web.json_response({
            "active_call": _call_to_dict(active) if active else None,
            "calls": [_call_to_dict(c) for c in calls],
            "total": len(calls),
        })

    async def handle_make_call(self, request: web.Request) -> web.Response:
        """Initiate a call to another node."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        to_node = body.get("target_node_id", "") or body.get("to_node_id", "")
        call_type = body.get("call_type", "voice")

        if not to_node:
            return web.json_response({"error": "target_node_id required"}, status=400)

        # Check no active call.
        if self.call_mgr.active_call:
            return web.json_response({"error": "already in a call"}, status=409)

        # Build and send call.request.
        msg = make_call_request(self.cfg.node_id, to_node, call_type)
        call_id = msg["payload"]["call_id"]

        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        # Register locally.
        call = await self.call_mgr.outgoing_request(call_id, to_node, call_type)

        return web.json_response({
            "call_id": call_id,
            "status": "requesting",
        }, status=201)

    async def handle_answer(self, request: web.Request) -> web.Response:
        """Answer an incoming call."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        call_id = body.get("call_id", "")
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

        msg = make_call_accept(call_id, self.cfg.node_id)
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

        msg = make_call_end(call_id, self.cfg.node_id, "hangup")
        try:
            await self.send_fn(msg)
        except Exception as e:
            return web.json_response({"error": f"send failed: {e}"}, status=502)

        await self.call_mgr.end_call(call_id, "hangup")
        return web.json_response({"call_id": call_id, "status": "ended"})


def _call_to_dict(call) -> dict:
    """Serialise a CallInfo to a JSON-safe dict."""
    return {
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
    }
