"""Simson Standalone Agent — runs on Raspberry Pi (or any Linux box).

Drop-in replacement for the Home Assistant addon when HAOS is not available.
Reads config from simson-agent.json, connects to the VPS, handles calls via
Asterisk AMI, and serves a local web UI on port 8799.

Usage:
  python standalone.py [--config /path/to/simson-agent.json]

The agent exposes the same HTTP API as the addon (port configurable), so the
same Lovelace card works when pointed at the agent's IP — no HA required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import web

from call_manager import CallManager, CallInfo, CallState
from asterisk_ami import AsteriskAMI
from asterisk_setup import setup_asterisk
from wss_client import WSSClient
from target_directory import TargetDirectory
from protocol import (
    TYPE_CALL_INVITE, TYPE_CALL_STATUS, TYPE_ERROR, TYPE_WEBRTC_SIGNAL,
    TYPE_USERS_LIST,
    make_call_request, make_call_end, make_call_accept, make_call_reject,
    make_webrtc_signal,
)
from local_api import LocalAPI

logger = logging.getLogger("simson.standalone")

# ── Config locations searched in order ───────────────────────────────────────
_CONFIG_SEARCH = [
    Path("simson-agent.json"),
    Path(os.path.expanduser("~/.config/simson/agent.json")),
    Path("/etc/simson/agent.json"),
    Path("/data/simson-agent.json"),
]


# ── Minimal no-op HA bridge (so LocalAPI still works without HAOS) ───────────

class NullHABridge:
    """Drop-in replacement for HABridge when HA is not present."""

    async def fire_event(self, *a, **kw): pass
    async def set_state(self, *a, **kw): pass
    async def call_service(self, *a, **kw): pass
    async def create_notification(self, *a, **kw): pass
    async def dismiss_notification(self, *a, **kw): pass
    async def close(self): pass


# ── Standalone config (reads from JSON, not /data/options.json) ──────────────

class StandaloneConfig:
    """Configuration for standalone (non-HAOS) operation."""

    def __init__(self, data: dict):
        # Credentials
        self.account_id: str = data.get("account_id", "")
        self.node_id: str = data.get("node_id", "")
        self.install_token: str = data.get("install_token", "")
        self.node_label: str = data.get("node_label", self.node_id)
        self.capabilities: list[str] = data.get("capabilities", ["standalone", "voice"])

        # VPS
        self.server_url: str = data.get("server_url", os.environ.get("SIMSON_SERVER_URL", ""))
        self.admin_token: str = data.get("admin_token", "")

        # Asterisk
        ast = data.get("asterisk", {})
        self.asterisk_enabled: bool = ast.get("enabled", False)
        self.asterisk_host: str = ast.get("host", "127.0.0.1")
        self.asterisk_ami_port: int = int(ast.get("ami_port", 5038))
        self.asterisk_ami_user: str = ast.get("ami_user", "simson")
        self.asterisk_ami_secret: str = ast.get("ami_secret", "")
        self.asterisk_context: str = ast.get("context", "from-simson")
        self.asterisk_ext_prefix: str = ast.get("extension_prefix", "9")
        self.asterisk_auto_configure: bool = ast.get("auto_configure", False)

        # API
        self.local_api_port: int = int(data.get("port", 8799))
        self.log_level: str = data.get("log_level", "info").upper()

        # Internal (used by LocalAPI / provisioner)
        self.supervisor_token: str = ""  # no supervisor in standalone mode

    def needs_provisioning(self) -> bool:
        return not self.install_token and bool(self.admin_token)

    def validate(self) -> list[str]:
        errors = []
        if not self.server_url:
            errors.append("server_url is required")
        if not self.account_id:
            errors.append("account_id is required (run provisioner or add manually)")
        if not self.node_id:
            errors.append("node_id is required")
        if not self.install_token:
            errors.append("install_token is required")
        return errors


def load_config(config_path: str | None = None) -> tuple[StandaloneConfig, Path]:
    search = [Path(config_path)] if config_path else _CONFIG_SEARCH
    for path in search:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            logger.info("Loaded config from %s", path)
            return StandaloneConfig(data), path
    raise FileNotFoundError(
        f"Config file not found. Searched: {[str(p) for p in search]}\n"
        "Create one using: simson-agent --generate-config"
    )


def generate_sample_config(dest: Path):
    """Write a sample simson-agent.json to dest."""
    sample = {
        "server_url": "wss://simson-vps.niti.life/ws",
        "account_id": "",
        "node_id": "my-pi",
        "node_label": "My Pi",
        "install_token": "",
        "admin_token": "",
        "port": 8799,
        "log_level": "info",
        "asterisk": {
            "enabled": False,
            "host": "127.0.0.1",
            "ami_port": 5038,
            "ami_user": "simson",
            "ami_secret": "changeme",
            "context": "from-simson",
            "extension_prefix": "9",
            "auto_configure": False
        }
    }
    dest.write_text(json.dumps(sample, indent=2))
    print(f"Sample config written to {dest}")
    print("Edit it, then run: simson-agent")


# ── Standalone orchestrator ───────────────────────────────────────────────────

class StandaloneAgent:
    """Full Simson agent without Home Assistant."""

    def __init__(self, cfg: StandaloneConfig):
        self.cfg = cfg
        self.ha = NullHABridge()  # type: ignore[assignment]
        self.call_mgr = CallManager(
            node_id=cfg.node_id,
            on_state_change=self._on_call_state_change,
        )
        self.wss = WSSClient(cfg, on_message=self._on_vps_message)  # type: ignore[arg-type]
        self.asterisk = AsteriskAMI(cfg) if cfg.asterisk_enabled else None  # type: ignore[arg-type]
        self.target_dir = TargetDirectory(cfg)  # type: ignore[arg-type]
        self.api = LocalAPI(
            cfg=cfg,  # type: ignore[arg-type]
            call_mgr=self.call_mgr,
            send_fn=self.wss.send,
            asterisk=self.asterisk,
            wss_client=self.wss,
            target_dir=self.target_dir,
            addon=self,
            standalone_mode=True,
        )
        self._background_tasks: list[asyncio.Task] = []
        self._ring_timers: dict[str, asyncio.Task] = {}
        self._online_users: dict[str, dict] = {}

    async def run(self):
        logger.info("Simson standalone agent starting")
        logger.info("Node: %s  Account: %s  VPS: %s",
                    self.cfg.node_id, self.cfg.account_id, self.cfg.server_url)

        await self.api.start()
        logger.info("Local API on port %d", self.cfg.local_api_port)

        if self.asterisk:
            if self.cfg.asterisk_auto_configure:
                try:
                    await setup_asterisk(
                        ami_user=self.cfg.asterisk_ami_user,
                        ami_secret=self.cfg.asterisk_ami_secret,
                        context=self.cfg.asterisk_context,
                        ext_prefix=self.cfg.asterisk_ext_prefix,
                    )
                except Exception as e:
                    logger.warning("Asterisk auto-configure failed (continuing): %s", e)
            try:
                await self.asterisk.connect()
            except Exception as e:
                logger.warning("Asterisk connection failed (continuing): %s", e)

        self._background_tasks.append(asyncio.create_task(self._periodic_cleanup()))
        if self.asterisk:
            self._background_tasks.append(asyncio.create_task(self._asterisk_reconnect_loop()))

        try:
            await self.wss.start()
        finally:
            await self._shutdown()

    async def _shutdown(self):
        logger.info("Shutting down standalone agent...")
        for t in self._background_tasks:
            t.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        await self.wss.stop()
        if self.asterisk:
            await self.asterisk.disconnect()
        await self.api.stop()

    # ── VPS message dispatch ──────────────────────────────────────────────────

    async def _on_vps_message(self, env: dict):
        msg_type = env.get("type", "")
        payload = env.get("payload", {})

        if msg_type == TYPE_CALL_INVITE:
            await self._handle_invite(payload)
        elif msg_type == TYPE_CALL_STATUS:
            await self._handle_call_status(payload)
        elif msg_type == TYPE_WEBRTC_SIGNAL:
            self.api.push_sse_event({"type": "webrtc_signal", **payload})
        elif msg_type == TYPE_USERS_LIST:
            await self._handle_users_list(payload)

    async def _handle_invite(self, payload: dict):
        call_id = payload.get("call_id", "")
        from_node = payload.get("from_node_id", "")
        from_label = payload.get("from_label", from_node)
        call_type = payload.get("call_type", "voice")
        metadata = payload.get("metadata") or {}
        target_user_id = metadata.get("target_user_id", "")

        logger.info("Incoming call from %s (call_id=%s)", from_node, call_id)

        call = await self.call_mgr.incoming_invite(
            call_id, from_node, from_label, call_type, metadata=metadata
        )

        self.api.push_sse_event({
            "type": "incoming_call",
            "call_id": call_id,
            "from_node_id": from_node,
            "from_label": from_label,
            "call_type": call_type,
            "target_user_id": target_user_id,
        })

        if self.asterisk and self.asterisk.connected and call_type == "sip":
            ext = metadata.get("extension", "")
            if ext:
                await self.asterisk.originate_call(
                    extension=ext,
                    caller_id=from_label,
                    variables={"SIMSON_CALL_ID": call_id},
                )

        self._start_ring_timer(call)

    async def _handle_call_status(self, payload: dict):
        call_id = payload.get("call_id", "")
        status = payload.get("status", "")
        reason = payload.get("reason", "")

        call = await self.call_mgr.update_status(call_id, status, reason)
        if not call:
            return

        if status not in ("ringing", "requesting"):
            self._cancel_ring_timer(call_id)

        self.api.push_sse_event({
            "type": "call_status",
            "call_id": call_id,
            "status": status,
            "reason": reason,
            "direction": call.direction,
            "remote_node_id": call.remote_node_id,
            "target_user_id": call.metadata.get("target_user_id", ""),
            "caller_user_id": call.caller_user_id,
        })

        if status == "ringing" and call.direction == "outgoing":
            self._start_ring_timer(call)

    async def _handle_users_list(self, payload: dict):
        node_id = payload.get("node_id", "")
        users = payload.get("users", [])
        self.api.push_sse_event({
            "type": "remote_users",
            "node_id": node_id,
            "users": users,
        })

    async def _on_call_state_change(self, call: CallInfo):
        state = call.state.value
        logger.info("Call state: %s → %s (remote=%s)", call.call_id[:8], state, call.remote_node_id)

        # Push SSE for local web UI.
        is_ami = call.remote_node_id.startswith("asterisk:")
        if is_ami:
            self.api.push_sse_event({
                "type": "call_status",
                "call_id": call.call_id,
                "status": state,
                "reason": call.end_reason,
                "direction": call.direction,
                "remote_node_id": call.remote_node_id,
                "target_user_id": call.metadata.get("target_user_id", ""),
                "caller_user_id": call.caller_user_id,
            })

    # ── Ring timer ────────────────────────────────────────────────────────────

    def _start_ring_timer(self, call: CallInfo):
        timeout = 30
        if call.routing:
            timeout = call.routing.timeout or 30

        async def _timeout():
            await asyncio.sleep(timeout)
            if self.call_mgr.get(call.call_id) and \
               self.call_mgr.get(call.call_id).state in (CallState.RINGING, CallState.INCOMING, CallState.REQUESTING):
                logger.info("Ring timeout for call %s", call.call_id[:8])
                await self.call_mgr.update_status(call.call_id, "ended", "timeout")
                try:
                    await self.wss.send(make_call_end(call.call_id, self.cfg.node_id, "timeout"))
                except Exception:
                    pass

        task = asyncio.create_task(_timeout())
        if call.call_id in self._ring_timers:
            self._ring_timers[call.call_id].cancel()
        self._ring_timers[call.call_id] = task

    def _cancel_ring_timer(self, call_id: str):
        task = self._ring_timers.pop(call_id, None)
        if task:
            task.cancel()

    # ── Asterisk reconnect loop ───────────────────────────────────────────────

    async def _asterisk_reconnect_loop(self):
        while True:
            await asyncio.sleep(30)
            if self.asterisk and not self.asterisk.connected:
                logger.info("Reconnecting to Asterisk AMI...")
                try:
                    await self.asterisk.connect()
                except Exception as e:
                    logger.warning("Asterisk reconnect failed: %s", e)

    # ── Periodic cleanup ──────────────────────────────────────────────────────

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(300)
            cutoff = time.time() - 3600
            for cid in list(self.call_mgr._calls):
                c = self.call_mgr._calls[cid]
                if c.state == CallState.IDLE and c.ended_at < cutoff:
                    del self.call_mgr._calls[cid]

    # ── User presence stubs (used by LocalAPI) ────────────────────────────────

    def register_user(self, user_id: str, user_name: str):
        self._online_users[user_id] = {"user_name": user_name, "last_seen": time.time()}

    def unregister_user(self, user_id: str):
        self._online_users.pop(user_id, None)

    def get_online_users(self) -> list[dict]:
        return [
            {"user_id": uid, "user_name": v["user_name"]}
            for uid, v in self._online_users.items()
        ]


# ── Entry point ───────────────────────────────────────────────────────────────

def _setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


async def _amain(config_path: str | None):
    cfg, cfg_file = load_config(config_path)
    _setup_logging(cfg.log_level)

    errors = cfg.validate()
    if errors:
        for e in errors:
            logger.error("Config error: %s", e)
        sys.exit(1)

    agent = StandaloneAgent(cfg)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(agent._shutdown()))
        except NotImplementedError:
            pass  # Windows

    await agent.run()


def main():
    parser = argparse.ArgumentParser(description="Simson standalone agent")
    parser.add_argument("--config", "-c", help="Path to simson-agent.json")
    parser.add_argument(
        "--generate-config", "-g",
        metavar="PATH",
        help="Generate a sample config file at PATH and exit",
    )
    args = parser.parse_args()

    if args.generate_config:
        generate_sample_config(Path(args.generate_config))
        return

    asyncio.run(_amain(args.config))


if __name__ == "__main__":
    main()
