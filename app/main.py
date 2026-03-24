"""Simson Addon — Main entry point.

Orchestrates: WSS client, call manager, Asterisk AMI, local API, HA bridge.
"""

import asyncio
import logging
import signal
import sys

from config import Config
from protocol import (
    TYPE_CALL_INVITE, TYPE_CALL_STATUS, TYPE_ERROR,
)
from wss_client import WSSClient
from call_manager import CallManager, CallInfo, CallState
from asterisk_ami import AsteriskAMI
from local_api import LocalAPI
from ha_bridge import HABridge

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
        self.api = LocalAPI(
            cfg=self.cfg,
            call_mgr=self.call_mgr,
            send_fn=self.wss.send,
            asterisk=self.asterisk,
            wss_client=self.wss,
        )
        self._background_tasks: list[asyncio.Task] = []

    async def run(self):
        """Start all components and run forever."""
        logger = logging.getLogger("simson.main")

        # Validate config.
        errors = self.cfg.validate()
        if errors:
            for e in errors:
                logger.error("Config error: %s", e)
            sys.exit(1)

        logger.info("Simson addon starting")
        logger.info("Node: %s, Account: %s", self.cfg.node_id, self.cfg.account_id)

        # Start local API.
        await self.api.start()

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

        # Fire HA event.
        await self.ha.fire_event("simson_call_status", {
            "call_id": call_id,
            "status": status,
            "reason": reason,
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
        })

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
