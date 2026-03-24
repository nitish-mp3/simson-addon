"""Persistent WebSocket client with reconnect, heartbeat, and message dispatch."""

import asyncio
import json
import logging
import ssl
import time
from typing import Callable, Awaitable

import websockets
import websockets.exceptions

from protocol import (
    make_hello, make_heartbeat, sign_envelope,
    TYPE_AUTH_RESULT, TYPE_HEARTBEAT_ACK, TYPE_CALL_INVITE,
    TYPE_CALL_STATUS, TYPE_ERROR,
)
from config import Config

logger = logging.getLogger("simson.wss")

# Callback type: async function that receives a parsed envelope dict.
MessageHandler = Callable[[dict], Awaitable[None]]


class WSSClient:
    """Maintains a persistent WSS connection to the Simson VPS."""

    def __init__(self, cfg: Config, on_message: MessageHandler):
        self.cfg = cfg
        self.on_message = on_message
        self._ws = None
        self._authenticated = False
        self._heartbeat_interval: int = 30
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False
        self._reconnect_delay: float = 1.0
        self._max_reconnect_delay: float = 60.0

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._authenticated

    async def start(self):
        """Start the connection loop. Runs forever with reconnect."""
        self._running = True
        while self._running:
            try:
                await self._connect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Connection failed: %s", e)

            if not self._running:
                break

            logger.info(
                "Reconnecting in %.0fs...", self._reconnect_delay
            )
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2, self._max_reconnect_delay
            )

    async def stop(self):
        """Gracefully disconnect."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._ws:
            await self._ws.close()

    async def send(self, envelope: dict):
        """Send a signed envelope to the VPS."""
        if not self._ws:
            raise ConnectionError("Not connected")
        signed = sign_envelope(envelope, self.cfg.install_token)
        data = json.dumps(signed)
        await self._ws.send(data)
        logger.debug("Sent: %s", envelope.get("type"))

    async def _connect(self):
        """Single connection attempt — authenticate, then read loop."""
        logger.info("Connecting to %s", self.cfg.server_url)

        ssl_ctx = ssl.create_default_context() if self.cfg.server_url.startswith("wss://") else None

        async with websockets.connect(
            self.cfg.server_url,
            ssl=ssl_ctx,
            ping_interval=None,  # We handle our own heartbeats.
            close_timeout=10,
            max_size=65536,
        ) as ws:
            self._ws = ws
            self._authenticated = False

            # Send hello.
            hello = make_hello(
                node_id=self.cfg.node_id,
                account_id=self.cfg.account_id,
                install_token=self.cfg.install_token,
                capabilities=self.cfg.capabilities,
            )
            signed = sign_envelope(hello, self.cfg.install_token)
            await ws.send(json.dumps(signed))
            logger.debug("Sent hello")

            # Wait for auth result.
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            env = json.loads(raw)

            if env.get("type") == TYPE_ERROR:
                payload = env.get("payload", {})
                logger.error(
                    "Auth rejected: [%s] %s",
                    payload.get("code"), payload.get("message"),
                )
                return

            if env.get("type") != TYPE_AUTH_RESULT:
                logger.error("Unexpected first response: %s", env.get("type"))
                return

            payload = env.get("payload", {})
            if not payload.get("ok"):
                logger.error("Auth failed: %s", payload.get("reason"))
                return

            self._authenticated = True
            self._heartbeat_interval = payload.get("heartbeat_sec", 30)
            self._reconnect_delay = 1.0  # Reset on success.
            logger.info(
                "Authenticated. Server v%s, protocol v%s, heartbeat %ds",
                payload.get("server_version"),
                payload.get("protocol_version"),
                self._heartbeat_interval,
            )

            # Start heartbeat task.
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Read loop.
            try:
                async for raw_msg in ws:
                    try:
                        env = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON, ignoring")
                        continue

                    msg_type = env.get("type", "")
                    logger.debug("Received: %s", msg_type)

                    if msg_type == TYPE_HEARTBEAT_ACK:
                        continue  # Already handled implicitly.

                    # Dispatch to handler.
                    try:
                        await self.on_message(env)
                    except Exception:
                        logger.exception("Error handling message type %s", msg_type)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("Connection closed: %s", e)
            finally:
                self._authenticated = False
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    self._heartbeat_task = None
                self._ws = None

    async def _heartbeat_loop(self):
        """Send heartbeats at the server-specified interval."""
        try:
            while self._running and self._ws:
                await asyncio.sleep(self._heartbeat_interval)
                if self._ws and self._authenticated:
                    hb = make_heartbeat(self.cfg.node_id)
                    signed = sign_envelope(hb, self.cfg.install_token)
                    await self._ws.send(json.dumps(signed))
                    logger.debug("Heartbeat sent")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Heartbeat error: %s", e)
