"""Asterisk Manager Interface (AMI) adapter for local Asterisk control."""

import asyncio
import logging
import time

from config import Config

logger = logging.getLogger("simson.asterisk")

_DEVICE_CACHE_TTL = 30.0  # seconds


class AsteriskAMI:
    """Minimal async AMI client for originating and managing calls."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._action_id = 0
        self._lock = asyncio.Lock()  # prevents concurrent AMI send/read
        self._device_cache: list[dict] = []
        self._device_cache_time: float = 0.0

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self):
        """Connect and authenticate to Asterisk AMI."""
        if not self.cfg.asterisk_enabled:
            logger.info("Asterisk integration disabled")
            return

        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.cfg.asterisk_host, self.cfg.asterisk_ami_port
            )
            # Read the AMI greeting.
            greeting = await asyncio.wait_for(self._reader.readline(), timeout=5)
            logger.debug("AMI greeting: %s", greeting.decode().strip())

            # Login.
            resp = await self._send_action({
                "Action": "Login",
                "Username": self.cfg.asterisk_ami_user,
                "Secret": self.cfg.asterisk_ami_secret,
            })

            if "Success" in resp:
                self._connected = True
                logger.info("Connected to Asterisk AMI at %s:%d",
                            self.cfg.asterisk_host, self.cfg.asterisk_ami_port)
            else:
                logger.warning("AMI login failed: %s", resp)
                await self.disconnect()

        except Exception as e:
            logger.warning("Failed to connect to Asterisk AMI: %s", e)
            self._connected = False

    async def disconnect(self):
        """Disconnect from AMI."""
        if self._writer:
            try:
                await self._send_action({"Action": "Logoff"})
            except Exception:
                pass
            self._writer.close()
        self._connected = False
        self._reader = None
        self._writer = None
        logger.info("Disconnected from Asterisk AMI")

    async def originate_call(self, extension: str, caller_id: str = "Simson",
                             variables: dict | None = None) -> bool:
        """Originate a call via Asterisk.

        Args:
            extension: The extension/number to call.
            caller_id: Caller ID string.
            variables: Optional channel variables.
        """
        if not self._connected:
            logger.error("Cannot originate — not connected to AMI")
            return False

        action = {
            "Action": "Originate",
            "Channel": f"PJSIP/{extension}",
            "Context": self.cfg.asterisk_context,
            "Exten": f"{self.cfg.asterisk_ext_prefix}{extension}",
            "Priority": "1",
            "CallerID": f'"{caller_id}" <{extension}>',
            "Account": variables.get("SIMSON_CALL_ID", "") if variables else "",
            "Async": "true",
        }

        if variables:
            var_str = ",".join(f"{k}={v}" for k, v in variables.items())
            action["Variable"] = var_str

        async with self._lock:
            resp = await self._send_action(action)
        success = "Success" in resp
        if success:
            logger.info("Originated call to %s", extension)
        else:
            logger.error("Originate failed: %s", resp)
        return success

    async def hangup_channel(self, channel: str) -> bool:
        """Hangup a specific channel."""
        if not self._connected:
            return False

        async with self._lock:
            resp = await self._send_action({
                "Action": "Hangup",
                "Channel": channel,
            })
        return "Success" in resp

    async def get_channels(self) -> str:
        """Get active channels (for debugging)."""
        if not self._connected:
            return ""
        async with self._lock:
            return await self._send_action({"Action": "CoreShowChannels"})

    async def get_registered_devices(self, force_refresh: bool = False) -> list[dict]:
        """Auto-discover registered SIP/PJSIP devices from Asterisk AMI.

        Returns a list of target dicts (type=asterisk) suitable for the
        target directory.  Results are cached for _DEVICE_CACHE_TTL seconds.
        """
        if not self._connected:
            return []

        now = time.monotonic()
        if not force_refresh and self._device_cache and (now - self._device_cache_time) < _DEVICE_CACHE_TTL:
            return list(self._device_cache)

        devices: list[dict] = []

        async with self._lock:
            # Try PJSIP endpoints first.
            try:
                events = await self._send_action_events(
                    {"Action": "PJSIPShowEndpoints"},
                    complete_event="EndpointListComplete",
                )
                for ev in events:
                    if ev.get("Event") == "EndpointList":
                        ext = ev.get("ObjectName", "").strip()
                        if ext and ext not in ("anonymous", ""):
                            devices.append({
                                "type": "asterisk",
                                "id": f"asterisk_{ext}",
                                "label": ext,
                                "extension": ext,
                                "icon": "\U0001f4de",
                            })
                logger.debug("PJSIP discovery: found %d endpoints", len(devices))
            except Exception as e:
                logger.warning("PJSIPShowEndpoints failed (%s), trying SIPpeers", e)
                # Fallback: legacy chan_sip peers.
                try:
                    events = await self._send_action_events(
                        {"Action": "SIPpeers"},
                        complete_event="PeerlistComplete",
                    )
                    for ev in events:
                        if ev.get("Event") == "PeerEntry":
                            peer = (ev.get("ObjectName") or ev.get("Peer", "")).strip()
                            if peer:
                                devices.append({
                                    "type": "asterisk",
                                    "id": f"asterisk_{peer}",
                                    "label": peer,
                                    "extension": peer,
                                    "icon": "\U0001f4de",
                                })
                    logger.debug("SIPpeers discovery: found %d peers", len(devices))
                except Exception as e2:
                    logger.warning("SIPpeers also failed: %s", e2)

        self._device_cache = devices
        self._device_cache_time = now
        return list(devices)

    async def hangup_by_call_id(self, simson_call_id: str) -> bool:
        """Hang up the channel that was originated for the given Simson call ID.

        This works by listing active channels and checking each one for a
        SIMSON_CALL_ID channel variable that matches.
        """
        if not self._connected:
            return False

        async with self._lock:
            # Get active channels list (multi-event response).
            try:
                events = await self._send_action_events(
                    {"Action": "CoreShowChannels"},
                    complete_event="CoreShowChannelsComplete",
                    timeout=6.0,
                )
            except Exception as e:
                logger.warning("CoreShowChannels failed: %s", e)
                return False

            for ev in events:
                if ev.get("Event") == "CoreShowChannel":
                    channel = ev.get("Channel", "")
                    if not channel:
                        continue
                    # Channel variable is embedded in the event if Asterisk
                    # passes it; otherwise we'd need GetVar per channel.
                    # Use channel description / Account field we set.
                    account = ev.get("AccountCode", "")
                    if account == simson_call_id:
                        # Hang up this channel.
                        try:
                            resp = await self._send_action({"Action": "Hangup", "Channel": channel})
                            logger.info("Hung up channel %s for call %s", channel, simson_call_id)
                            return "Success" in resp
                        except Exception as e:
                            logger.warning("Hangup failed for channel %s: %s", channel, e)
                            return False

        logger.debug("No active channel found for call ID %s", simson_call_id)
        return False

    async def _send_action(self, action: dict) -> str:
        """Send an AMI action and read the single response block.

        Caller is responsible for holding self._lock when needed.
        """
        if not self._writer or not self._reader:
            raise ConnectionError("Not connected to AMI")

        self._action_id += 1
        action["ActionID"] = str(self._action_id)

        # Format AMI message: "Key: Value\r\n" terminated by blank line.
        msg = ""
        for key, value in action.items():
            msg += f"{key}: {value}\r\n"
        msg += "\r\n"

        self._writer.write(msg.encode())
        await self._writer.drain()

        # Read response until blank line.
        response_lines = []
        while True:
            line = await asyncio.wait_for(self._reader.readline(), timeout=10)
            decoded = line.decode().strip()
            if decoded == "":
                break
            response_lines.append(decoded)

        return "\n".join(response_lines)

    async def _send_action_events(
        self, action: dict, complete_event: str, timeout: float = 10.0
    ) -> list[dict]:
        """Send an AMI list action and collect all events until the complete event.

        Parses each event block (separated by blank lines) into a dict.
        Stops when an event with Event==complete_event or EventList==Complete
        is received, or when timeout expires.

        Caller is responsible for holding self._lock.
        """
        if not self._writer or not self._reader:
            raise ConnectionError("Not connected to AMI")

        self._action_id += 1
        action["ActionID"] = str(self._action_id)

        msg = ""
        for key, value in action.items():
            msg += f"{key}: {value}\r\n"
        msg += "\r\n"

        self._writer.write(msg.encode())
        await self._writer.drain()

        events: list[dict] = []
        current_lines: list[str] = []
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("_send_action_events timed out for action %s", action.get("Action"))
                break

            try:
                line = await asyncio.wait_for(self._reader.readline(), timeout=min(remaining, 5.0))
            except asyncio.TimeoutError:
                break

            decoded = line.decode().strip()

            if decoded == "":
                if current_lines:
                    ev: dict = {}
                    for l in current_lines:
                        if ":" in l:
                            k, _, v = l.partition(":")
                            ev[k.strip()] = v.strip()
                    events.append(ev)
                    current_lines = []

                    # Check for completion.
                    if (
                        ev.get("EventList") == "Complete"
                        or ev.get("Event", "") == complete_event
                    ):
                        break
            else:
                current_lines.append(decoded)

        # Return data events only (exclude the initial Response block and the
        # completion event).
        return [
            e for e in events
            if e.get("Event")  # must have an Event key
            and e.get("Event") != complete_event
            and e.get("EventList") != "Complete"
        ]
