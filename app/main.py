"""Simson Addon — Main entry point.

Orchestrates: WSS client, call manager, Asterisk AMI, local API, HA bridge.
"""

import asyncio
import logging
import signal
import sys

from config import Config
from provisioner import auto_provision, load_saved_credentials
from protocol import (
    TYPE_CALL_INVITE, TYPE_CALL_STATUS, TYPE_ERROR, TYPE_WEBRTC_SIGNAL,
    make_call_request, make_call_end,
)
from wss_client import WSSClient
from call_manager import CallManager, CallInfo, CallState
from asterisk_ami import AsteriskAMI
from local_api import LocalAPI
from ha_bridge import HABridge
from target_directory import TargetDirectory

# --- Logging setup ---


def setup_logging(level: str):
    log_level = getattr(logging, level, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


# --- Main orchestrator ---


class SimsonAddon:
    """Main addon process that wires all components together."""

    def __init__(self):
        self.cfg = Config()
        self.ha = HABridge(self.cfg)
        self.call_mgr = CallManager(
            node_id=self.cfg.node_id,
            on_state_change=self._on_call_state_change,
        )
        self.wss = WSSClient(self.cfg, on_message=self._on_vps_message)
        self.asterisk = AsteriskAMI(self.cfg) if self.cfg.asterisk_enabled else None
        self.target_dir = TargetDirectory(self.cfg)
        self.api = LocalAPI(
            cfg=self.cfg,
            call_mgr=self.call_mgr,
            send_fn=self.wss.send,
            asterisk=self.asterisk,
            wss_client=self.wss,
            target_dir=self.target_dir,
        )
        self._background_tasks: list[asyncio.Task] = []
        self._ring_timers: dict[str, asyncio.Task] = {}  # call_id -> timeout task

    async def run(self):
        """Start all components and run forever."""
        logger = logging.getLogger("simson.main")

        # ── 1. Start local API first so the ingress panel is always reachable ──
        await self.api.start()
        logger.info("Local API listening on port %d", self.cfg.local_api_port)

        # ── 2. Auto-provision if admin_token is set but credentials are missing ──
        if self.cfg.needs_provisioning():
            logger.info("No credentials found — auto-provisioning via admin API...")
            try:
                creds = await auto_provision(
                    self.cfg.server_url,
                    self.cfg.admin_token,
                    self.cfg.node_label,
                    self.cfg.account_id,
                    self.cfg.capabilities,
                )
                self.cfg.account_id = creds["account_id"]
                self.cfg.node_id = creds["node_id"]
                self.cfg.install_token = creds["install_token"]
                self.call_mgr.node_id = self.cfg.node_id
                logger.info("Auto-provisioned: account=%s node=%s",
                            self.cfg.account_id, self.cfg.node_id)
            except Exception as e:
                logger.error("Auto-provisioning failed: %s", e)

        # ── 3. If still no credentials, wait for setup via ingress panel ──
        if not self.cfg.install_token:
            logger.warning(
                "No credentials configured. Open the Simson panel in "
                "Home Assistant to set up, or add account_id / node_id / "
                "install_token in the addon configuration."
            )
            await self._wait_for_credentials()
            self.call_mgr.node_id = self.cfg.node_id
            logger.info("Credentials loaded: account=%s node=%s",
                        self.cfg.account_id, self.cfg.node_id)

        # ── 4. Validate config ──
        errors = self.cfg.validate()
        if errors:
            for e in errors:
                logger.error("Config error: %s", e)
            sys.exit(1)

        logger.info("Simson addon starting")
        logger.info("Node: %s, Account: %s", self.cfg.node_id, self.cfg.account_id)

        # Connect to Asterisk if enabled.
        if self.asterisk:
            try:
                await self.asterisk.connect()
            except Exception as e:
                logger.warning("Asterisk connection failed (continuing): %s", e)

        # Set initial HA state.
        await self.ha.set_state(
            f"sensor.simson_{self.cfg.node_id}_status",
            "connecting",
            {
                "friendly_name": f"Simson {self.cfg.node_id}",
                "node_id": self.cfg.node_id,
                "account_id": self.cfg.account_id,
                "icon": "mdi:phone-voip",
            },
        )

        # Periodic tasks.
        self._background_tasks.append(asyncio.create_task(self._periodic_cleanup()))
        self._background_tasks.append(asyncio.create_task(self._connection_state_updater()))

        # Start WSS (blocks with reconnect loop).
        try:
            await self.wss.start()
        finally:
            await self.shutdown()

    async def _wait_for_credentials(self):
        """Block until credentials appear (provisioned via ingress panel)."""
        logger = logging.getLogger("simson.main")
        while not self.cfg.install_token:
            await asyncio.sleep(2)
            saved = load_saved_credentials()
            if saved:
                self.cfg.account_id = saved["account_id"]
                self.cfg.node_id = saved["node_id"]
                self.cfg.install_token = saved["install_token"]

    async def shutdown(self):
        """Gracefully stop all components."""
        logger = logging.getLogger("simson.main")
        logger.info("Shutting down...")

        # Cancel background tasks.
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # Stop WSS.
        await self.wss.stop()

        # Disconnect Asterisk.
        if self.asterisk:
            await self.asterisk.disconnect()

        # Stop local API.
        await self.api.stop()

        # Close HA session.
        await self.ha.close()

    async def _on_vps_message(self, env: dict):
        """Handle a message received from the VPS."""
        logger = logging.getLogger("simson.dispatch")
        msg_type = env.get("type", "")
        payload = env.get("payload", {})

        if msg_type == TYPE_CALL_INVITE:
            await self._handle_invite(payload)

        elif msg_type == TYPE_CALL_STATUS:
            await self._handle_call_status(payload)

        elif msg_type == TYPE_ERROR:
            code = payload.get("code", 0)
            message = payload.get("message", "")
            logger.warning("VPS error [%d]: %s", code, message)
            await self.ha.fire_event("simson_error", {
                "code": code,
                "message": message,
                "ref": payload.get("ref", ""),
            })

        elif msg_type == TYPE_WEBRTC_SIGNAL:
            sig_payload = {
                "call_id": payload.get("call_id", ""),
                "from_node_id": payload.get("from_node_id", ""),
                "signal_type": payload.get("signal_type", ""),
                "data": payload.get("data"),
            }
            logger.info(
                "WebRTC signal IN: %s from %s (call %s)",
                sig_payload["signal_type"],
                sig_payload["from_node_id"],
                sig_payload["call_id"],
            )
            # Fire as HA event — card subscribes via hass.connection.subscribeEvents
            # (works through HTTPS WebSocket, no mixed-content issues).
            await self.ha.fire_event("simson_webrtc_signal", sig_payload)
            # Also push to SSE as fallback for plain-HTTP setups.
            self.api.push_sse_event({"type": "webrtc_signal", **sig_payload})

        else:
            logger.debug("Unhandled message type: %s", msg_type)

    async def _handle_invite(self, payload: dict):
        """Handle an incoming call invite."""
        logger = logging.getLogger("simson.invite")

        call_id = payload.get("call_id", "")
        from_node = payload.get("from_node_id", "")
        from_label = payload.get("from_label", "")
        call_type = payload.get("call_type", "voice")
        metadata = payload.get("metadata", {})

        logger.info(
            "Incoming call %s from %s (%s), type=%s",
            call_id, from_node, from_label, call_type,
        )

        # Register the incoming call.
        call = await self.call_mgr.incoming_invite(
            call_id, from_node, from_label, call_type, metadata
        )

        # Fire HA event for automations / UI.
        await self.ha.fire_event("simson_incoming_call", {
            "call_id": call_id,
            "from_node_id": from_node,
            "from_label": from_label,
            "call_type": call_type,
        })

        # Create a persistent notification so the user sees the call even
        # when the Lovelace card is not visible.
        await self.ha.create_notification(
            notification_id=f"simson_call_{call_id[:12]}",
            title="Incoming Call",
            message=f"📞 {from_label or from_node} is calling ({call_type})",
        )

        # Push to SSE so the Lovelace card shows incoming call immediately.
        self.api.push_sse_event({
            "type": "incoming_call",
            "call_id": call_id,
            "from_node_id": from_node,
            "from_label": from_label,
            "call_type": call_type,
        })

        # If Asterisk is enabled and call type is voice/sip, trigger it.
        if self.asterisk and self.asterisk.connected and call_type in ("voice", "sip"):
            ext = metadata.get("extension", "s")
            await self.asterisk.originate_call(
                extension=ext,
                caller_id=from_label or from_node,
                variables={"SIMSON_CALL_ID": call_id},
            )

    async def _handle_call_status(self, payload: dict):
        """Handle a call status update."""
        call_id = payload.get("call_id", "")
        status = payload.get("status", "")
        reason = payload.get("reason", "")

        call = await self.call_mgr.update_status(call_id, status, reason)
        if not call:
            return

        # Cancel ring timer if call is no longer ringing.
        if status not in ("ringing", "requesting"):
            self._cancel_ring_timer(call_id)

        # Fire HA event.
        await self.ha.fire_event("simson_call_status", {
            "call_id": call_id,
            "status": status,
            "reason": reason,
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
        })

        # Push to SSE so the Lovelace card reacts immediately.
        self.api.push_sse_event({
            "type": "call_status",
            "call_id": call_id,
            "status": status,
            "reason": reason,
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
        })

        # Start ring timer when outgoing call starts ringing.
        if status == "ringing" and call.direction == "outgoing" and call.routing:
            self._start_ring_timer(call)

        # Attempt fallback on declined/failed for outgoing calls with routing.
        if status in ("ended", "failed") and call.direction == "outgoing":
            if reason in ("declined", "rejected", "timeout", "busy", "no_answer"):
                await self._attempt_fallback(call, reason)

    async def _on_call_state_change(self, call: CallInfo):
        """Update HA entity state when call state changes."""
        state = call.state.value
        attrs = {
            "friendly_name": f"Simson {self.cfg.node_id}",
            "node_id": self.cfg.node_id,
            "icon": "mdi:phone-voip",
            "call_id": call.call_id,
            "call_state": state,
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
            "remote_label": call.remote_label,
            "call_type": call.call_type,
        }

        # Map call state to sensor state.
        if state in ("requesting", "ringing", "incoming"):
            sensor_state = "ringing"
        elif state == "active":
            sensor_state = "in_call"
        else:
            sensor_state = "idle"
            # Dismiss persistent notification when call ends.
            await self.ha.dismiss_notification(f"simson_call_{call.call_id[:12]}")

        await self.ha.set_state(
            f"sensor.simson_{self.cfg.node_id}_status",
            sensor_state,
            attrs,
        )

    async def _connection_state_updater(self):
        """Periodically update HA with connection state."""
        logger = logging.getLogger("simson.state")
        was_connected = False
        while True:
            await asyncio.sleep(5)
            is_connected = self.wss.connected

            if is_connected != was_connected:
                state = "connected" if is_connected else "disconnected"
                # Only set to connected/disconnected if no active call.
                if not self.call_mgr.active_call:
                    await self.ha.set_state(
                        f"sensor.simson_{self.cfg.node_id}_status",
                        state,
                        {
                            "friendly_name": f"Simson {self.cfg.node_id}",
                            "node_id": self.cfg.node_id,
                            "icon": "mdi:phone-voip",
                        },
                    )
                was_connected = is_connected

    # ── Ring timeout & fallback routing ─────────────────────────────────

    def _start_ring_timer(self, call: CallInfo):
        """Start a timer that fires if the remote doesn't answer in time."""
        timeout = 30
        if call.routing:
            timeout = call.routing.timeout
        self._cancel_ring_timer(call.call_id)
        self._ring_timers[call.call_id] = asyncio.create_task(
            self._ring_timeout_task(call.call_id, timeout)
        )

    def _cancel_ring_timer(self, call_id: str):
        """Cancel an active ring timer."""
        task = self._ring_timers.pop(call_id, None)
        if task and not task.done():
            task.cancel()

    async def _ring_timeout_task(self, call_id: str, timeout: int):
        """Wait for timeout, then end the call and attempt fallback."""
        logger = logging.getLogger("simson.timeout")
        try:
            await asyncio.sleep(timeout)
        except asyncio.CancelledError:
            return

        call = self.call_mgr.get(call_id)
        if not call or call.state not in (CallState.RINGING, CallState.REQUESTING):
            return

        logger.info("Call %s timed out after %ds", call_id, timeout)

        # Send call.end to VPS.
        msg = make_call_end(call_id, self.cfg.node_id, "timeout")
        try:
            await self.wss.send(msg)
        except Exception as e:
            logger.warning("Failed to send timeout end: %s", e)

        await self.call_mgr.update_status(call_id, "timeout", "timeout")

        # Fire HA events.
        await self.ha.fire_event("simson_call_status", {
            "call_id": call_id,
            "status": "timeout",
            "reason": "timeout",
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
        })
        self.api.push_sse_event({
            "type": "call_status",
            "call_id": call_id,
            "status": "timeout",
            "reason": "timeout",
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
        })

        await self._attempt_fallback(call, "timeout")

    async def _attempt_fallback(self, call: CallInfo, reason: str):
        """Try the next fallback target if available."""
        logger = logging.getLogger("simson.fallback")
        if not call.routing or not call.routing.fallback_targets:
            return

        next_idx = call.fallback_attempt + 1
        if next_idx > len(call.routing.fallback_targets):
            logger.info("No more fallback targets for call %s", call.call_id)
            await self.ha.fire_event("simson_call_status", {
                "call_id": call.call_id,
                "status": "failed",
                "reason": f"all_fallbacks_exhausted ({reason})",
                "direction": call.direction,
                "remote_node_id": call.remote_node_id,
            })
            return

        fallback_id = call.routing.fallback_targets[next_idx - 1]
        logger.info(
            "Call %s fallback attempt %d → target %s (reason: %s)",
            call.call_id, next_idx, fallback_id, reason,
        )

        # Resolve the fallback target.
        fallback_routing = self.target_dir.resolve_routing(fallback_id)
        fallback_node = self.target_dir.resolve_node_id(fallback_id)

        if not fallback_node:
            logger.warning("Fallback target %s could not be resolved", fallback_id)
            return

        # Build metadata.
        metadata = {}
        if fallback_routing:
            metadata["routing"] = {
                "target_type": fallback_routing.target_type,
                "target_id": fallback_routing.target_id,
                "extension": fallback_routing.extension,
                "context": fallback_routing.context,
                "trunk": fallback_routing.trunk,
                "caller_id": fallback_routing.caller_id,
                "timeout": fallback_routing.timeout,
            }
            metadata["fallback_from"] = call.call_id

        call_type = "sip" if fallback_routing and fallback_routing.target_type == "asterisk" else "voice"
        msg = make_call_request(self.cfg.node_id, fallback_node, call_type, metadata=metadata or None)
        new_call_id = msg["payload"]["call_id"]

        try:
            await self.wss.send(msg)
        except Exception as e:
            logger.error("Fallback call send failed: %s", e)
            return

        # Register the new call with updated fallback state.
        new_routing = call.routing
        new_call = await self.call_mgr.outgoing_request(
            new_call_id, fallback_node, call_type, routing=new_routing
        )
        new_call.fallback_attempt = next_idx

        # Fire fallback-redirected event.
        await self.ha.fire_event("simson_call_status", {
            "call_id": new_call_id,
            "status": "fallback-redirected",
            "reason": reason,
            "direction": "outgoing",
            "remote_node_id": fallback_node,
            "fallback_from": call.call_id,
            "fallback_target": fallback_id,
            "fallback_attempt": next_idx,
        })
        self.api.push_sse_event({
            "type": "call_status",
            "call_id": new_call_id,
            "status": "fallback-redirected",
            "reason": reason,
            "direction": "outgoing",
            "remote_node_id": fallback_node,
            "fallback_from": call.call_id,
            "fallback_target": fallback_id,
        })

    async def _periodic_cleanup(self):
        """Clean up ended calls periodically."""
        while True:
            await asyncio.sleep(60)
            self.call_mgr.cleanup(max_age=300)


# --- Entry point ---

def main():
    cfg = Config()
    setup_logging(cfg.log_level)
    addon = SimsonAddon()

    loop = asyncio.new_event_loop()

    def _signal_handler():
        logging.getLogger("simson.main").info("Signal received, stopping...")
        loop.create_task(addon.wss.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        loop.run_until_complete(addon.run())
    except KeyboardInterrupt:
        logging.getLogger("simson.main").info("Interrupted, shutting down")
        loop.run_until_complete(addon.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
