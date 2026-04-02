"""Local HTTP API — exposed via HA ingress for the integration to talk to."""

import asyncio
import json
import logging
from aiohttp import web

from call_manager import CallManager, CallState
from config import Config
from protocol import make_call_request, make_call_accept, make_call_reject, make_call_end, make_webrtc_signal
from provisioner import auto_provision, clear_saved_credentials

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
        self.app.router.add_post("/api/provision", self.handle_provision)
        self.app.router.add_post("/api/reset", self.handle_reset)
        self.app.router.add_get("/api/events", self.handle_sse)
        self.app.router.add_post("/api/webrtc/signal", self.handle_webrtc_signal)

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
        """Serve the ingress web panel — setup wizard or dashboard."""
        provisioned = bool(self.cfg.install_token)
        vps_connected = self.wss_client.connected if self.wss_client else False
        active = self.call_mgr.active_call

        # Determine status badge.
        if not provisioned:
            badge_cls, badge_txt = "badge-setup", "Setup Required"
        elif vps_connected:
            badge_cls, badge_txt = "badge-ok", "Connected"
        else:
            badge_cls, badge_txt = "badge-err", "Disconnected"

        # Active call section (dashboard only).
        call_html = ""
        if provisioned and active:
            call_html = (
                f'<div class="card">'
                f'<div class="card-title">Active Call</div>'
                f'<div class="info-row"><span class="info-label">Call ID</span>'
                f'<span class="info-value">{active.call_id[:12]}…</span></div>'
                f'<div class="info-row"><span class="info-label">With</span>'
                f'<span class="info-value">{active.remote_label or active.remote_node_id}</span></div>'
                f'<div class="info-row"><span class="info-label">Direction</span>'
                f'<span class="info-value">{active.direction}</span></div>'
                f'<div class="info-row"><span class="info-label">State</span>'
                f'<span class="info-value">{active.state.value}</span></div>'
                f'</div>'
            )
        elif provisioned:
            call_html = '<div class="card"><div class="card-title">Calls</div><p class="muted">No active call</p></div>'

        # Node info section (dashboard only).
        node_html = ""
        if provisioned:
            vps_dot = "dot-ok" if vps_connected else "dot-err"
            vps_label = "Connected" if vps_connected else "Disconnected"
            node_html = (
                f'<div class="card">'
                f'<div class="card-title">Node Info</div>'
                f'<div class="info-row"><span class="info-label">Node ID</span>'
                f'<span class="info-value">{self.cfg.node_id}</span></div>'
                f'<div class="info-row"><span class="info-label">Account</span>'
                f'<span class="info-value">{self.cfg.account_id}</span></div>'
                f'<div class="info-row"><span class="info-label">Server</span>'
                f'<span class="info-value">{self.cfg.server_url}</span></div>'
                f'<div class="info-row"><span class="info-label">VPS</span>'
                f'<span class="info-value"><span class="dot {vps_dot}"></span>{vps_label}</span></div>'
                f'</div>'
            )

        # Escape braces for f-string safety in CSS/JS — use doubled braces.
        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simson Call Relay</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,sans-serif;background:#111;color:#e1e1e1;min-height:100vh}}
.container{{max-width:600px;margin:0 auto;padding:24px 16px}}
.header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}}
.header h1{{font-size:20px;display:flex;align-items:center;gap:10px}}
.header h1 span{{color:#03a9f4}}
.badge{{font-size:11px;font-weight:700;padding:3px 10px;border-radius:10px;text-transform:uppercase;letter-spacing:.5px}}
.badge-ok{{background:#1b5e2088;color:#a5d6a7;border:1px solid #a5d6a740}}
.badge-err{{background:#b71c1c88;color:#ef9a9a;border:1px solid #ef9a9a40}}
.badge-setup{{background:#e6510088;color:#ffcc80;border:1px solid #ffcc8040}}
.card{{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:20px;margin-bottom:16px}}
.card-title{{font-size:13px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:14px;font-weight:600}}
.info-row{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #222}}
.info-row:last-child{{border-bottom:none}}
.info-label{{color:#888;font-size:13px}}
.info-value{{font-size:13px;font-weight:500;display:flex;align-items:center;gap:6px}}
.dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.dot-ok{{background:#4caf50}} .dot-err{{background:#f44336}}
p.muted{{color:#666;font-size:14px}}
.field{{margin-bottom:16px}}
.field label{{display:block;font-size:13px;color:#aaa;margin-bottom:6px;font-weight:500}}
.field input{{width:100%;background:#222;border:1px solid #333;border-radius:8px;padding:10px 14px;color:#e1e1e1;font-size:14px;outline:none;transition:border-color .2s}}
.field input:focus{{border-color:#03a9f4}}
.field .hint{{font-size:12px;color:#555;margin-top:5px;line-height:1.4}}
.btn-primary{{display:inline-flex;align-items:center;gap:8px;background:#03a9f4;color:#fff;border:none;border-radius:8px;padding:12px 28px;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s,transform .1s;margin-top:4px}}
.btn-primary:hover{{background:#0288d1}}
.btn-primary:active{{transform:scale(.97)}}
.btn-primary:disabled{{opacity:.5;cursor:not-allowed;transform:none}}
.alert{{padding:12px 16px;border-radius:8px;font-size:13px;margin-top:16px;line-height:1.5}}
.alert-success{{background:#1b5e2044;border:1px solid #4caf5033;color:#a5d6a7}}
.alert-error{{background:#b71c1c33;border:1px solid #f4433633;color:#ef9a9a}}
.alert-info{{background:#0d47a133;border:1px solid #2196f333;color:#90caf9}}
.step{{display:flex;gap:12px;align-items:flex-start;margin-bottom:20px}}
.step-num{{width:28px;height:28px;background:#03a9f422;color:#03a9f4;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;flex-shrink:0;margin-top:2px}}
.step-text{{font-size:14px;color:#bbb;line-height:1.5}}
.step-text b{{color:#e1e1e1}}
.divider{{height:1px;background:#222;margin:20px 0}}
details{{margin-top:16px}} details summary{{cursor:pointer;color:#03a9f4;font-size:13px;font-weight:500}}
details summary:hover{{text-decoration:underline}}
</style>
</head><body>
<div class="container">
  <div class="header">
    <h1>📞 <span>Simson Call Relay</span></h1>
    <span class="badge {badge_cls}">{badge_txt}</span>
  </div>

  {"" if provisioned else '''
  <div class="card" id="setup-card">
    <div class="card-title">Quick Setup</div>
    <div class="step">
      <div class="step-num">1</div>
      <div class="step-text">Enter your <b>VPS admin token</b> — the one from deployment.</div>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <div class="step-text">Choose a <b>node label</b> (e.g. "Living Room"). This identifies this HA instance.</div>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <div class="step-text"><b>Calling between two HA instances?</b> Both must share the same Account ID. Copy the Account ID shown on your first instance's Simson panel and paste it in the Account ID field below. Leave it empty for a brand-new standalone setup.</div>
    </div>
    <div class="divider"></div>
    <div class="field">
      <label>Admin Token</label>
      <input type="password" id="f-token" placeholder="Paste your admin token" autocomplete="off" />
    </div>
    <div class="field">
      <label>Account ID <span style="color:#03a9f4;font-weight:500;font-size:12px">— required for calling between instances</span></label>
      <input type="text" id="f-account" placeholder="e.g. haos203 — leave empty for first setup" />
      <div class="hint" style="color:#e6a817;background:#2a1e00;border:1px solid #e6a81733;border-radius:6px;padding:8px 10px;margin-top:6px">
        ⚠ To call between two HA instances, both <b>must use the same Account ID</b>.<br>
        On your first instance's Simson panel, copy the Account ID from the Node Info card and paste it here.
      </div>
    </div>
    <div class="field">
      <label>Node Label</label>
      <input type="text" id="f-label" placeholder="e.g. Living Room, Office, Kitchen" />
      <div class="hint">A friendly name for this HA instance. Used to generate the node ID.</div>
    </div>
    <button class="btn-primary" id="btn-setup" onclick="doSetup()">Set Up Node</button>
    <div id="setup-result"></div>
  </div>
  '''}

  {node_html}
  {call_html}

  {"" if not provisioned else f'''
  <div class="card">
    <div class="card-title">Add Another HA Instance</div>
    <p style="color:#bbb;font-size:13px;margin-bottom:14px;line-height:1.6">
      To call between this node and another HA instance, install the Simson addon on the second HA,
      open its Simson panel, and use the values below during setup.
    </p>
    <div class="info-row">
      <span class="info-label">Use this Account ID</span>
      <span class="info-value" style="display:flex;align-items:center;gap:8px">
        <code style="background:#222;padding:2px 8px;border-radius:5px;font-size:13px">{self.cfg.account_id}</code>
        <button onclick="navigator.clipboard.writeText('{self.cfg.account_id}');this.textContent='Copied!';setTimeout(()=>this.textContent='Copy',2000)"
          style="background:#03a9f422;color:#03a9f4;border:1px solid #03a9f433;border-radius:6px;padding:3px 10px;cursor:pointer;font-size:12px;font-weight:600">Copy</button>
      </span>
    </div>
    <div class="info-row" style="border-bottom:none">
      <span class="info-label">Use a different Node Label</span>
      <span class="info-value" style="color:#888">e.g. Office, Kitchen, Bedroom…</span>
    </div>
  </div>

  <div class="card" style="border-color:#b71c1c44">
    <div class="card-title" style="color:#ef9a9a">Danger Zone</div>
    <p style="color:#888;font-size:13px;margin-bottom:14px">
      Reset credentials to re-run the setup wizard. Use this if this node is on the wrong account.
    </p>
    <button class="btn-primary" style="background:#b71c1c;font-size:13px;padding:9px 20px" onclick="doReset()">Reset Setup</button>
    <div id="reset-result"></div>
  </div>
  '''}
</div>

<script>
async function doReset() {{
  if (!confirm('This will clear saved credentials and show the setup wizard. Continue?')) return;
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Resetting…';
  try {{
    await fetch('api/reset', {{ method: 'POST' }});
    document.getElementById('reset-result').innerHTML =
      '<div class="alert alert-success">Reset complete. Reloading…</div>';
    setTimeout(() => location.reload(), 1500);
  }} catch(e) {{
    document.getElementById('reset-result').innerHTML =
      '<div class="alert alert-error">Reset failed: ' + e.message + '</div>';
    btn.disabled = false;
    btn.textContent = 'Reset Setup';
  }}
}}
async function doSetup() {{
  const btn = document.getElementById('btn-setup');
  const result = document.getElementById('setup-result');
  const token = document.getElementById('f-token').value.trim();
  const label = document.getElementById('f-label').value.trim();
  const account = document.getElementById('f-account').value.trim();

  if (!token) {{ result.innerHTML = '<div class="alert alert-error">Admin token is required.</div>'; return; }}
  if (!label) {{ result.innerHTML = '<div class="alert alert-error">Node label is required.</div>'; return; }}

  btn.disabled = true;
  btn.textContent = 'Setting up…';
  result.innerHTML = '<div class="alert alert-info">Creating account and node on VPS…</div>';

  try {{
    const resp = await fetch('api/provision', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ admin_token: token, node_label: label, account_id: account }}),
    }});
    const data = await resp.json();
    if (resp.ok) {{
      result.innerHTML =
        '<div class="alert alert-success">' +
        '✓ Setup complete!<br>' +
        '<b>Account:</b> ' + data.account_id + '<br>' +
        '<b>Node:</b> ' + data.node_id + '<br>' +
        '<small>Credentials saved. Reloading in 3 seconds…</small>' +
        '</div>';
      setTimeout(() => location.reload(), 3000);
    }} else {{
      result.innerHTML = '<div class="alert alert-error">✗ ' + (data.error || 'Setup failed') + '</div>';
      btn.disabled = false;
      btn.textContent = 'Set Up Node';
    }}
  }} catch (e) {{
    result.innerHTML = '<div class="alert alert-error">✗ Network error: ' + e.message + '</div>';
    btn.disabled = false;
    btn.textContent = 'Set Up Node';
  }}
}}
{"" if provisioned else ""}
</script>
{"<script>setTimeout(()=>location.reload(),10000)</script>" if provisioned else ""}
</body></html>"""
        return web.Response(text=html, content_type="text/html")

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok",
            "addon_version": "2.1.0",
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

        admin_token = body.get("admin_token", "").strip()
        node_label = body.get("node_label", "").strip()
        account_id = body.get("account_id", "").strip()

        if not admin_token:
            return web.json_response({"error": "admin_token is required"}, status=400)
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
