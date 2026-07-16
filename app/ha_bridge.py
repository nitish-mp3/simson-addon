"""Home Assistant event bridge — fires events to HA via the Supervisor API."""

import logging
import os
import time
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
        self._notify_targets_cache: list[dict] = []
        self._notify_targets_cached_at = 0.0
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

    async def discover_notify_targets(self, force: bool = False) -> list[dict]:
        """Return notify entities and services currently exposed by Home Assistant."""
        now = time.monotonic()
        if not force and self._notify_targets_cache and now - self._notify_targets_cached_at < 60:
            return [dict(item) for item in self._notify_targets_cache]

        targets: dict[str, dict] = {}
        session = await self._get_session()
        try:
            async with session.get(
                f"{HA_API_BASE}/states", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    for state in await resp.json():
                        entity_id = str(state.get("entity_id") or "")
                        if not entity_id.startswith("notify."):
                            continue
                        attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
                        targets[entity_id] = {
                            "ref": entity_id,
                            "label": str(attrs.get("friendly_name") or entity_id),
                            "kind": "entity",
                            "rich_actions": False,
                        }
                else:
                    logger.warning("HA notify entity discovery failed: %d %s", resp.status, await resp.text())
        except Exception as exc:
            logger.warning("HA notify entity discovery error: %s", exc)

        try:
            async with session.get(
                f"{HA_API_BASE}/services", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    for domain in await resp.json():
                        if domain.get("domain") != "notify":
                            continue
                        services = domain.get("services") if isinstance(domain.get("services"), dict) else {}
                        for service, definition in services.items():
                            if service == "send_message":
                                continue
                            ref = f"notify.{service}"
                            fields = definition if isinstance(definition, dict) else {}
                            targets[ref] = {
                                "ref": ref,
                                "label": str(fields.get("name") or fields.get("description") or ref),
                                "kind": "service",
                                "rich_actions": service.startswith("mobile_app_"),
                            }
                else:
                    logger.warning("HA notify service discovery failed: %d %s", resp.status, await resp.text())
        except Exception as exc:
            logger.warning("HA notify service discovery error: %s", exc)

        result = sorted(
            targets.values(),
            key=lambda item: (not item["rich_actions"], item["label"].lower(), item["ref"]),
        )
        self._notify_targets_cache = [dict(item) for item in result]
        self._notify_targets_cached_at = now
        return result

    async def _mobile_notify_service_for(self, ref: str) -> str:
        """Resolve a modern notify entity to its Companion mobile_app service."""
        if ref.startswith("notify.mobile_app_"):
            return ref
        if not ref.startswith("notify."):
            return ""
        suffix = ref.split(".", 1)[1]
        expected = f"notify.mobile_app_{suffix}"
        targets = await self.discover_notify_targets()
        services = {
            str(item.get("ref") or "")
            for item in targets
            if item.get("kind") == "service"
        }
        if expected in services:
            return expected
        normalized = suffix.lower().replace("-", "_").replace(" ", "_")
        matches = sorted(
            service for service in services
            if service.removeprefix("notify.mobile_app_").lower() == normalized
        )
        return matches[0] if len(matches) == 1 else ""

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

        # Companion versions and Android vendors do not all accept the same
        # optional notification fields. Keep call actions, sound and deep-link
        # data for a compatibility retry before falling back to plain text.
        compatible_payload = {"message": message}
        if title:
            compatible_payload["title"] = title
        if isinstance(data, dict):
            safe_keys = {
                "actions", "channel", "clickAction", "group", "importance",
                "notification_icon", "priority", "push", "sticky", "tag",
                "timeout", "ttl", "url", "vibrationPattern",
            }
            compatible_data = {key: value for key, value in data.items() if key in safe_keys}
            if compatible_data:
                compatible_payload["data"] = compatible_data

        basic_payload = {"message": message}
        if title:
            basic_payload["title"] = title

        actions = data.get("actions") if isinstance(data, dict) else None
        has_actions = bool(actions)
        clearing_only = message == "clear_notification" and not has_actions

        async def call_notify_service(service_ref: str, body: dict) -> bool:
            if "." not in service_ref:
                return False
            domain, service = service_ref.split(".", 1)
            if domain != "notify":
                return False
            return await self.call_service(domain, service, body)

        async def call_notify_entity(body: dict) -> bool:
            return await self.call_service("notify", "send_message", {"entity_id": ref, **body})

        async def deliver_mobile(service_ref: str) -> bool:
            if await call_notify_service(service_ref, payload):
                return True
            if compatible_payload != payload and await call_notify_service(service_ref, compatible_payload):
                logger.warning("Notification %s required the compatible rich payload", service_ref)
                return True
            if not clearing_only and await call_notify_service(service_ref, basic_payload):
                logger.warning("Notification %s was delivered without call controls", service_ref)
                return True
            return False

        if ref.startswith("notify."):
            service = ref.split(".", 1)[1]
            if service.startswith("mobile_app_"):
                if await deliver_mobile(ref):
                    logger.info("Delivered rich notification through %s", ref)
                    return True
            else:
                # Generic notify entities can accept a message while silently
                # dropping Companion call actions. Prefer the discovered mobile
                # service for action-bearing notifications.
                mobile_service = await self._mobile_notify_service_for(ref) if (has_actions or data) else ""
                if mobile_service and await deliver_mobile(mobile_service):
                    logger.info("Delivered rich notification for %s through %s", ref, mobile_service)
                    return True
                if await call_notify_entity(payload):
                    logger.info("Delivered notification through entity %s", ref)
                    return True
                if compatible_payload != payload and await call_notify_entity(compatible_payload):
                    logger.warning("Notification entity %s required the compatible payload", ref)
                    return True
                if not clearing_only and await call_notify_entity(basic_payload):
                    logger.warning("Notification entity %s was delivered without call controls", ref)
                    return True
                guessed = f"notify.mobile_app_{service}"
                if guessed != mobile_service and await deliver_mobile(guessed):
                    logger.info("Delivered notification for %s through compatibility service %s", ref, guessed)
                    return True

            if clearing_only:
                return False

            return False

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
