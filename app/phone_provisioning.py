"""Guarded, vendor-specific SIP phone account provisioning.

Phone administration APIs are not part of SIP.  This module therefore exposes
an adapter boundary instead of guessing endpoints on an arbitrary LAN device.
The first adapter implements Grandstream's documented GSC36xx HTTP API.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import secrets
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

from aiohttp import ClientSession, ClientTimeout, CookieJar


class ProvisioningError(Exception):
    """An expected provisioning failure safe to return to the settings UI."""

    def __init__(self, message: str, *, status: int = 400, code: str = "provisioning_error"):
        super().__init__(message)
        self.status = status
        self.code = code


def private_ipv4(value: object) -> str:
    """Accept a literal RFC1918 IPv4 address and nothing DNS/SSRF-sensitive."""
    text = str(value or "").strip()
    try:
        address = ipaddress.ip_address(text)
    except ValueError as exc:
        raise ProvisioningError(
            "Phone address must be a literal private IPv4 address, for example 192.168.1.80",
            code="invalid_phone_ip",
        ) from exc
    private_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    if address.version != 4 or not any(address in network for network in private_networks):
        raise ProvisioningError(
            "Phone address must be on a private LAN (10.x, 172.16-31.x, or 192.168.x)",
            code="unsafe_phone_ip",
        )
    return str(address)


def _xml_values(text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ProvisioningError(
            "The device replied, but not with the expected Grandstream API response",
            status=502,
            code="unexpected_device_response",
        ) from exc
    return {child.tag: (child.text or "").strip() for child in root.iter() if child is not root}


@dataclass(slots=True)
class DeviceConnection:
    ip: str
    scheme: str
    port: int
    admin_username: str
    admin_password: str
    verify_tls: bool

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.ip}:{self.port}"


@dataclass(slots=True)
class DiscoverySession:
    session_id: str
    profile: str
    connection: DeviceConnection
    allowed_slots: tuple[int, ...]
    expires_at: float


class GrandstreamGSC36xxAdapter:
    """Grandstream GSC3610/GSC3615/GSC3620 account configuration adapter."""

    profile = "grandstream_gsc36xx"
    display_name = "Grandstream GSC36xx door/camera station"
    _AUTH_SALT = "GSC36XXlZpRsFzCbM"
    _SLOTS = {
        1: {"active": "P271", "registered": "P210", "name": "P3", "server": "P47", "user": "P35", "auth": "P36", "password": "P34", "transport": "P130"},
        2: {"active": "P401", "registered": "P499", "name": "P407", "server": "P402", "user": "P404", "auth": "P405", "password": "P406", "transport": "P448"},
        3: {"active": "P501", "registered": "P599", "name": "P507", "server": "P502", "user": "P504", "auth": "P505", "password": "P506", "transport": "P548"},
        4: {"active": "P601", "registered": "P699", "name": "P607", "server": "P602", "user": "P604", "auth": "P605", "password": "P606", "transport": "P648"},
    }
    _TRANSPORT = {"udp": "0", "tcp": "1", "tls": "2"}

    def __init__(self, connection: DeviceConnection):
        self.connection = connection

    def _request_options(self) -> dict:
        return {
            "ssl": self.connection.verify_tls if self.connection.scheme == "https" else None,
            "allow_redirects": False,
        }

    async def _login(self, session: ClientSession) -> None:
        login_url = f"{self.connection.base_url}/goform/login"
        opts = self._request_options()
        try:
            async with session.post(
                login_url,
                data={"cmd": "login", "user": self.connection.admin_username, "type": "0"},
                **opts,
            ) as response:
                if response.status != 200:
                    raise ProvisioningError(
                        f"Phone management login returned HTTP {response.status}",
                        status=502,
                        code="device_login_failed",
                    )
                challenge_values = _xml_values(await response.text())
        except ProvisioningError:
            raise
        except asyncio.TimeoutError as exc:
            raise ProvisioningError(
                "Timed out connecting to the phone management interface",
                status=504,
                code="device_timeout",
            ) from exc
        except Exception as exc:
            raise ProvisioningError(
                "Could not connect to the phone management interface",
                status=502,
                code="device_unreachable",
            ) from exc

        challenge = challenge_values.get("ChallengeCode", "")
        if challenge_values.get("ResCode") != "0" or not challenge:
            raise ProvisioningError(
                "This device did not provide a valid Grandstream GSC36xx login challenge",
                status=422,
                code="unsupported_device",
            )
        digest = hashlib.md5(
            f"{challenge}:{self._AUTH_SALT}:{self.connection.admin_password}".encode("utf-8")
        ).hexdigest()
        try:
            async with session.post(
                login_url,
                data={
                    "cmd": "login",
                    "user": self.connection.admin_username,
                    "authcode": digest,
                    "type": "0",
                },
                **opts,
            ) as response:
                values = _xml_values(await response.text()) if response.status == 200 else {}
                if response.status != 200 or values.get("ResCode") != "0":
                    raise ProvisioningError(
                        "Phone administrator username or password was rejected",
                        status=401,
                        code="invalid_device_credentials",
                    )
        except ProvisioningError:
            raise
        except asyncio.TimeoutError as exc:
            raise ProvisioningError(
                "Timed out while authenticating to the phone management interface",
                status=504,
                code="device_timeout",
            ) from exc
        except Exception as exc:
            raise ProvisioningError(
                "The phone management connection failed during authentication",
                status=502,
                code="device_login_failed",
            ) from exc

    async def _sip_values(self, session: ClientSession) -> dict[str, str]:
        url = f"{self.connection.base_url}/goform/config"
        async with session.get(
            url,
            params={"cmd": "get", "type": "sip"},
            **self._request_options(),
        ) as response:
            if response.status != 200:
                raise ProvisioningError(
                    f"Phone SIP account query returned HTTP {response.status}",
                    status=502,
                    code="device_query_failed",
                )
            values = _xml_values(await response.text())
            if values.get("ResCode") != "0":
                raise ProvisioningError(
                    "The device rejected the SIP account query",
                    status=502,
                    code="device_query_failed",
                )
            return values

    async def discover(self) -> dict:
        timeout = ClientTimeout(total=8, connect=3, sock_read=5)
        async with ClientSession(timeout=timeout, cookie_jar=CookieJar(unsafe=True)) as session:
            await self._login(session)
            values = await self._sip_values(session)

        slots = []
        available = []
        for number, params in self._SLOTS.items():
            active = values.get(params["active"], "0") == "1"
            username = values.get(params["user"], "")
            server = values.get(params["server"], "")
            occupied = active or bool(username or server)
            if not occupied:
                available.append(number)
            slots.append({
                "slot": number,
                "available": not occupied,
                "active": active,
                "registered": values.get(params["registered"], "0") == "1",
                "account_name": values.get(params["name"], ""),
                "sip_user": username,
                "sip_server": server,
            })
        return {"device_name": self.display_name, "slots": slots, "available_slots": available}

    async def apply(self, slot: int, sip: dict) -> None:
        if slot not in self._SLOTS:
            raise ProvisioningError("Selected phone account slot is invalid", code="invalid_slot")
        transport = str(sip.get("transport", "tcp")).lower()
        if transport not in self._TRANSPORT:
            raise ProvisioningError("SIP transport must be TCP, UDP, or TLS", code="invalid_transport")
        params = self._SLOTS[slot]
        form = {
            "cmd": "set",
            params["active"]: "1",
            params["name"]: str(sip.get("label") or sip["extension"])[:64],
            params["server"]: str(sip["server"]),
            params["user"]: str(sip["username"]),
            params["auth"]: str(sip["username"]),
            params["password"]: str(sip["password"]),
            params["transport"]: self._TRANSPORT[transport],
        }
        timeout = ClientTimeout(total=10, connect=3, sock_read=7)
        async with ClientSession(timeout=timeout, cookie_jar=CookieJar(unsafe=True)) as session:
            await self._login(session)
            url = f"{self.connection.base_url}/goform/config"
            async with session.post(url, data=form, **self._request_options()) as response:
                values = _xml_values(await response.text()) if response.status == 200 else {}
                if response.status != 200 or values.get("ResCode") != "0":
                    raise ProvisioningError(
                        "The phone rejected the SIP account update",
                        status=502,
                        code="device_update_failed",
                    )
            updated = await self._sip_values(session)
        expected = {
            params["active"]: "1",
            params["server"]: str(sip["server"]),
            params["user"]: str(sip["username"]),
            params["auth"]: str(sip["username"]),
            params["transport"]: self._TRANSPORT[transport],
        }
        if any(updated.get(key, "") != value for key, value in expected.items()):
            raise ProvisioningError(
                "The phone accepted the request but did not persist the selected SIP account",
                status=502,
                code="device_verification_failed",
            )


class PhoneProvisioningService:
    """Short-lived discovery sessions and serialized writes per LAN phone."""

    SESSION_TTL_SECONDS = 300

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._sessions: dict[str, DiscoverySession] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def profiles() -> list[dict]:
        return [
            {
                "id": GrandstreamGSC36xxAdapter.profile,
                "name": GrandstreamGSC36xxAdapter.display_name,
                "account_slots": 4,
                "mode": "direct_management",
                "automatic_write": True,
                "help": "Direct, verified account-slot setup through the documented GSC36xx management API.",
            },
            {
                "id": "fanvil_linkvil_provisioning",
                "name": "Fanvil / LINKVIL phone (provisioning server)",
                "account_slots": 0,
                "mode": "provisioning_server",
                "automatic_write": False,
                "help": "Fanvil and LINKVIL use SIP PnP, DHCP, or an HTTP/HTTPS provisioning server; they do not share the GSC direct-management API.",
            },
            {
                "id": "grandstream_xml_provisioning",
                "name": "Grandstream desk phone (XML provisioning)",
                "account_slots": 0,
                "mode": "provisioning_server",
                "automatic_write": False,
                "help": "Standard Grandstream desk phones use Grandstream XML provisioning. Select the exact documented model workflow instead of writing guessed web-form fields.",
            },
        ]

    @classmethod
    def _profile(cls, profile_id: str) -> dict | None:
        return next((profile for profile in cls.profiles() if profile["id"] == profile_id), None)

    def _connection(self, payload: dict) -> tuple[str, DeviceConnection]:
        profile = str(payload.get("profile", "")).strip()
        profile_meta = self._profile(profile)
        if not profile_meta:
            raise ProvisioningError(
                "Unsupported phone profile. Select the exact supported model family.",
                status=422,
                code="unsupported_profile",
            )
        if not profile_meta.get("automatic_write"):
            raise ProvisioningError(
                f"{profile_meta['name']} uses vendor provisioning rather than a documented direct account API. "
                "Use the phone's SIP PnP/DHCP/static provisioning workflow or configure the SIP account manually; "
                "Simson will not guess private web-form endpoints.",
                status=422,
                code="provisioning_server_required",
            )
        scheme = str(payload.get("scheme", "https")).strip().lower()
        if scheme not in {"http", "https"}:
            raise ProvisioningError("Management protocol must be HTTP or HTTPS", code="invalid_scheme")
        try:
            port = int(payload.get("port") or (443 if scheme == "https" else 80))
        except (TypeError, ValueError) as exc:
            raise ProvisioningError("Management port must be a number", code="invalid_port") from exc
        if not 1 <= port <= 65535:
            raise ProvisioningError("Management port must be between 1 and 65535", code="invalid_port")
        username = str(payload.get("admin_username", "")).strip()
        password = str(payload.get("admin_password", ""))
        if not username or not password:
            raise ProvisioningError(
                "Phone IP, administrator username, and administrator password are all required",
                code="incomplete_device_credentials",
            )
        return profile, DeviceConnection(
            ip=private_ipv4(payload.get("ip")),
            scheme=scheme,
            port=port,
            admin_username=username,
            admin_password=password,
            verify_tls=bool(payload.get("verify_tls", False)),
        )

    def _prune(self) -> None:
        now = self._clock()
        self._sessions = {key: value for key, value in self._sessions.items() if value.expires_at > now}

    async def discover(self, payload: dict) -> dict:
        self._prune()
        profile, connection = self._connection(payload)
        lock = self._locks.setdefault(connection.ip, asyncio.Lock())
        async with lock:
            result = await GrandstreamGSC36xxAdapter(connection).discover()
        available = tuple(int(value) for value in result.get("available_slots", []))
        if not available:
            raise ProvisioningError(
                "The phone is reachable, but all four SIP account slots are already in use",
                status=409,
                code="no_available_slots",
            )
        session_id = secrets.token_urlsafe(24)
        expires_at = self._clock() + self.SESSION_TTL_SECONDS
        self._sessions[session_id] = DiscoverySession(
            session_id=session_id,
            profile=profile,
            connection=connection,
            allowed_slots=available,
            expires_at=expires_at,
        ) 
        return {
            "session_id": session_id,
            "expires_in": self.SESSION_TTL_SECONDS,
            "profile": profile,
            "device_name": result["device_name"],
            "phone_ip": connection.ip,
            "slots": result["slots"],
        }

    async def apply(self, session_id: str, slot: object, sip: dict) -> dict:
        self._prune()
        session = self._sessions.get(str(session_id or ""))
        if not session:
            raise ProvisioningError(
                "Phone test expired. Test the connection again before creating the SIP account.",
                status=410,
                code="discovery_expired",
            )
        try:
            slot_number = int(slot)
        except (TypeError, ValueError) as exc:
            raise ProvisioningError("Select an available phone account slot", code="invalid_slot") from exc
        if slot_number not in session.allowed_slots:
            raise ProvisioningError(
                "That phone account slot was not available during the connection test",
                status=409,
                code="slot_not_available",
            )
        lock = self._locks.setdefault(session.connection.ip, asyncio.Lock())
        try:
            async with lock:
                await GrandstreamGSC36xxAdapter(session.connection).apply(slot_number, sip)
        finally:
            self._sessions.pop(session.session_id, None)
        return {"phone_ip": session.connection.ip, "profile": session.profile, "slot": slot_number}
