"""Asterisk Manager Interface (AMI) adapter for local Asterisk control."""

import asyncio
import logging

from config import Config

logger = logging.getLogger("simson.asterisk")


class AsteriskAMI:
    """Minimal async AMI client for originating and managing calls."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._action_id = 0

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
                logger.error("AMI login failed: %s", resp)
                await self.disconnect()

        except Exception as e:
            logger.error("Failed to connect to Asterisk AMI: %s", e)
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
            "Async": "true",
        }

        if variables:
            var_str = ",".join(f"{k}={v}" for k, v in variables.items())
            action["Variable"] = var_str

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

        resp = await self._send_action({
            "Action": "Hangup",
            "Channel": channel,
        })
        return "Success" in resp

    async def get_channels(self) -> str:
        """Get active channels (for debugging)."""
        if not self._connected:
            return ""
        return await self._send_action({"Action": "CoreShowChannels"})

    async def _send_action(self, action: dict) -> str:
        """Send an AMI action and read the response."""
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
