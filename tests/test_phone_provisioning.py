"""Security and workflow tests for optional LAN phone provisioning."""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from phone_provisioning import (  # noqa: E402
    DeviceConnection,
    GrandstreamGSC36xxAdapter,
    PhoneProvisioningService,
    ProvisioningError,
    private_ipv4,
)


class PrivateAddressTests(unittest.TestCase):
    def test_accepts_rfc1918_literal(self):
        self.assertEqual(private_ipv4("192.168.4.212"), "192.168.4.212")
        self.assertEqual(private_ipv4("10.20.30.40"), "10.20.30.40")

    def test_rejects_public_dns_and_loopback(self):
        for value in ("simson-vps.vipsy.in", "8.8.8.8", "127.0.0.1", "169.254.1.2", "192.0.2.1"):
            with self.subTest(value=value), self.assertRaises(ProvisioningError):
                private_ipv4(value)


class GrandstreamDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_only_empty_slots_as_available(self):
        connection = DeviceConnection("192.168.1.80", "http", 80, "admin", "secret", False)
        adapter = GrandstreamGSC36xxAdapter(connection)
        adapter._login = AsyncMock()
        adapter._sip_values = AsyncMock(return_value={
            "P271": "1", "P210": "1", "P3": "Door", "P47": "pbx.local", "P35": "1602",
            "P401": "0", "P499": "0", "P407": "", "P402": "", "P404": "",
            "P501": "0", "P599": "0", "P507": "", "P502": "", "P504": "",
            "P601": "0", "P699": "0", "P607": "", "P602": "", "P604": "",
        })

        result = await adapter.discover()

        self.assertEqual(result["available_slots"], [2, 3, 4])
        self.assertFalse(result["slots"][0]["available"])
        self.assertEqual(result["slots"][0]["sip_user"], "1602")


class ProvisioningSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 100.0
        self.service = PhoneProvisioningService(clock=lambda: self.now)
        self.payload = {
            "profile": "grandstream_gsc36xx",
            "ip": "192.168.1.80",
            "scheme": "http",
            "port": 80,
            "admin_username": "admin",
            "admin_password": "device-secret",
            "verify_tls": False,
        }
        self.discovery = {
            "device_name": "Grandstream GSC36xx door/camera station",
            "available_slots": [2],
            "slots": [
                {"slot": 1, "available": False, "sip_user": "1602"},
                {"slot": 2, "available": True, "sip_user": ""},
            ],
        }

    async def test_credentials_are_not_returned_and_selected_slot_is_one_time(self):
        with patch.object(GrandstreamGSC36xxAdapter, "discover", AsyncMock(return_value=self.discovery)):
            result = await self.service.discover(self.payload)

        self.assertNotIn("admin_password", result)
        self.assertNotIn("admin_username", result)
        with patch.object(GrandstreamGSC36xxAdapter, "apply", AsyncMock()) as apply_mock:
            applied = await self.service.apply(result["session_id"], 2, {
                "extension": "1027",
                "username": "1027",
                "password": "sip-secret",
                "label": "Kitchen",
                "server": "simson-vps.vipsy.in",
                "transport": "tcp",
            })
        self.assertEqual(applied["slot"], 2)
        apply_mock.assert_awaited_once()
        with self.assertRaises(ProvisioningError):
            await self.service.apply(result["session_id"], 2, {})

    async def test_expired_discovery_cannot_modify_phone(self):
        with patch.object(GrandstreamGSC36xxAdapter, "discover", AsyncMock(return_value=self.discovery)):
            result = await self.service.discover(self.payload)
        self.now += self.service.SESSION_TTL_SECONDS + 1

        with self.assertRaises(ProvisioningError) as caught:
            await self.service.apply(result["session_id"], 2, {})

        self.assertEqual(caught.exception.code, "discovery_expired")

    async def test_occupied_slot_is_rejected(self):
        with patch.object(GrandstreamGSC36xxAdapter, "discover", AsyncMock(return_value=self.discovery)):
            result = await self.service.discover(self.payload)

        with self.assertRaises(ProvisioningError) as caught:
            await self.service.apply(result["session_id"], 1, {})

        self.assertEqual(caught.exception.code, "slot_not_available")


if __name__ == "__main__":
    unittest.main()
