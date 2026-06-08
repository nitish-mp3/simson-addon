"""Home Assistant event bridge — fires events to HA via the Supervisor API."""

import logging
import os
import aiohttp
from config import Config

logger = logging.getLogger("simson.ha_bridge")

# With host_network:true the Docker internal "supervisor" hostname may not
# resolve. HA Supervisor always sets SUPERVISOR_URL; fall back to the known
# internal supervisor IP used by HA OS.
_supervisor_host = (
    os.environ.get("SUPERVISOR_URL", "").rstrip("/")
    or os.environ.get("HASSIO_TOKEN", "") and "http://supervisor"  # token present → DNS works
    or "http://172.30.32.2"
)
HA_API_BASE = f"{_supervisor_host}/core/api"


def _entity_safe(value: str) -> str:
    """Return a Home Assistant entity-id safe fragment."""
    safe = []
    for ch in str(value or "").lower():
        safe.append(ch if ch.isalnum() else "_")
    collapsed = "_".join(part for part in "".join(safe).split("_") if part)
    return collapsed or "node"


class HABridge:
    """Communicates with Home Assistant via the Supervisor REST API."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._session: aiohttp.ClientSession | None = None
        self.last_call_event: dict = {}
        self.last_automation_event: dict = {}
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

    async def publish_call_event(self, payload: dict):
        """Expose the latest call event as both an HA event and state sensor."""
        self.last_call_event = dict(payload or {})
        await self.fire_event("simson_call_event", payload)
        attrs = dict(payload)
        attrs.setdefault("friendly_name", "Simson Last Call Event")
        attrs.setdefault("icon", "mdi:phone-in-talk")
        event_state = str(payload.get("event") or payload.get("status") or "unknown")[:255]
        await self.set_state("sensor.simson_last_call_event", event_state, attrs)

        node_fragment = _entity_safe(payload.get("node_id", self.cfg.node_id))
        await self.set_state(
            f"sensor.simson_{node_fragment}_last_call_event",
            event_state,
            attrs,
        )

    async def publish_automation_event(self, event_type: str, payload: dict):
        """Expose the latest automation/door event for HA automations."""
        self.last_automation_event = {"event_type": event_type, **dict(payload or {})}
        await self.fire_event(event_type, payload)
        attrs = dict(payload)
        attrs.setdefault("friendly_name", "Simson Last Automation Event")
        attrs.setdefault("icon", "mdi:lightning-bolt")
        event_state = str(payload.get("status") or payload.get("event") or event_type)[:255]
        await self.set_state("sensor.simson_last_automation_event", event_state, attrs)

    async def call_service(self, domain: str, service: str, data: dict | None = None) -> bool:
        """Call a Home Assistant service."""
        url = f"{HA_API_BASE}/services/{domain}/{service}"
        try:
            session = await self._get_session()
            async with session.post(
                url, json=data or {}, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status in (200, 201):
                    logger.debug("Called HA service: %s.%s", domain, service)
                    return True
                else:
                    body = await resp.text()
                    logger.warning(
                        "Failed to call service %s.%s: %d %s",
                        domain, service, resp.status, body,
                    )
                    return False
        except Exception as e:
            logger.warning("HA service call error: %s", e)
            return False

    async def send_notify_message(
        self,
        notify_ref: str,
        message: str,
        title: str = "",
        data: dict | None = None,
    ) -> bool:
        """Send a push notification to a Home Assistant notify entity/service.

        Supports both modern notify entities, e.g. notify.23090ra98i via
        notify.send_message, and legacy services such as notify.mobile_app_x.
        """
        ref = str(notify_ref or "").strip()
        if not ref or "." not in ref:
            return False

        payload = {"message": message}
        if title:
            payload["title"] = title
        if data:
            payload["data"] = data

        # Modern HA notify entities use action notify.send_message with a
        # target entity_id. The REST API accepts entity_id in service data.
        if ref.startswith("notify."):
            if await self.call_service("notify", "send_message", {"entity_id": ref, **payload}):
                return True
            if (title or data) and await self.call_service(
                "notify",
                "send_message",
                {"entity_id": ref, "message": message},
            ):
                return True
            if await self.call_service("notify", "send_message", {
                "target": {"entity_id": ref},
                "data": payload,
            }):
                return True

        domain, service = ref.split(".", 1)
        return await self.call_service(domain, service, payload)

    async def create_notification(self, notification_id: str, title: str, message: str):
        """Create a persistent notification in HA."""
        await self.call_service(
            "persistent_notification", "create",
            {
                "notification_id": notification_id,
                "title": title,
                "message": message,
            },
        )

    async def dismiss_notification(self, notification_id: str):
        """Dismiss a persistent notification in HA."""
        await self.call_service(
            "persistent_notification", "dismiss",
            {"notification_id": notification_id},
        )
