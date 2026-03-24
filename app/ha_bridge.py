"""Home Assistant event bridge — fires events to HA via the Supervisor API."""

import logging
import aiohttp
from config import Config

logger = logging.getLogger("simson.ha_bridge")

HA_API_BASE = "http://supervisor/core/api"


class HABridge:
    """Communicates with Home Assistant via the Supervisor REST API."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._session: aiohttp.ClientSession | None = None
        self._headers = {
            "Authorization": f"Bearer {cfg.supervisor_token}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def fire_event(self, event_type: str, data: dict):
        """Fire a Home Assistant event."""
        url = f"{HA_API_BASE}/events/{event_type}"
        try:
            session = await self._get_session()
            async with session.post(
                url, json=data, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    logger.debug("Fired HA event: %s", event_type)
                else:
                    body = await resp.text()
                    logger.warning(
                        "Failed to fire HA event %s: %d %s",
                        event_type, resp.status, body,
                    )
        except Exception as e:
            logger.warning("HA event fire error: %s", e)

    async def set_state(self, entity_id: str, state: str, attributes: dict | None = None):
        """Set an entity state in HA."""
        url = f"{HA_API_BASE}/states/{entity_id}"
        payload = {"state": state}
        if attributes:
            payload["attributes"] = attributes
        try:
            session = await self._get_session()
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status in (200, 201):
                    logger.debug("Set HA state: %s = %s", entity_id, state)
                else:
                    body = await resp.text()
                    logger.warning(
                        "Failed to set HA state %s: %d %s",
                        entity_id, resp.status, body,
                    )
        except Exception as e:
            logger.warning("HA state set error: %s", e)

    async def call_service(self, domain: str, service: str, data: dict | None = None):
        """Call a Home Assistant service."""
        url = f"{HA_API_BASE}/services/{domain}/{service}"
        try:
            session = await self._get_session()
            async with session.post(
                url, json=data or {}, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.debug("Called HA service: %s.%s", domain, service)
                else:
                    body = await resp.text()
                    logger.warning(
                        "Failed to call service %s.%s: %d %s",
                        domain, service, resp.status, body,
                    )
        except Exception as e:
            logger.warning("HA service call error: %s", e)
