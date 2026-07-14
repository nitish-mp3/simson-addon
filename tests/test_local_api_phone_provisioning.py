"""Transactional tests for SIP endpoint creation plus phone provisioning."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from local_api import LocalAPI  # noqa: E402
from phone_provisioning import ProvisioningError  # noqa: E402


class FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


class FakeProvisioningService:
    def __init__(self):
        self.apply = AsyncMock()

    @staticmethod
    def profiles():
        return []


class LocalAPIProvisioningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.provisioning = FakeProvisioningService()
        cfg = SimpleNamespace(
            account_id="site-1",
            admin_token="admin-token",
            server_url="wss://simson-vps.vipsy.in/ws",
            sip_domain="simson-vps.vipsy.in",
        )
        self.api = LocalAPI(
            cfg,
            call_mgr=None,
            send_fn=AsyncMock(),
            phone_provisioning=self.provisioning,
        )
        self.api._create_vps_sip_endpoint = AsyncMock(return_value=(201, {
            "id": "endpoint-1",
            "extension": "1027",
        }))
        self.api._rollback_vps_sip_endpoint = AsyncMock(return_value=True)
        self.base_body = {
            "extension": "1027",
            "username": "1027",
            "password": "sip-secret",
            "description": "Kitchen",
        }

    async def test_manual_create_does_not_touch_phone_provisioner(self):
        response = await self.api.handle_create_sip_endpoint(FakeRequest(self.base_body))

        self.assertEqual(response.status, 201)
        self.provisioning.apply.assert_not_awaited()
        self.api._rollback_vps_sip_endpoint.assert_not_awaited()

    async def test_successful_phone_create_returns_slot_result(self):
        self.provisioning.apply.return_value = {
            "phone_ip": "192.168.1.80",
            "profile": "grandstream_gsc36xx",
            "slot": 2,
        }
        body = dict(self.base_body, phone_provisioning={
            "session_id": "test-session",
            "slot": 2,
            "transport": "tcp",
        })

        response = await self.api.handle_create_sip_endpoint(FakeRequest(body))
        payload = json.loads(response.text)

        self.assertEqual(response.status, 201)
        self.assertEqual(payload["phone_provisioning"]["slot"], 2)
        configured = self.provisioning.apply.await_args.args[2]
        self.assertEqual(configured["server"], "simson-vps.vipsy.in")
        self.assertEqual(configured["transport"], "tcp")

    async def test_phone_failure_rolls_back_new_vps_endpoint(self):
        self.provisioning.apply.side_effect = ProvisioningError(
            "phone rejected update",
            status=502,
            code="device_update_failed",
        )
        body = dict(self.base_body, phone_provisioning={
            "session_id": "test-session",
            "slot": 2,
            "transport": "tcp",
        })

        response = await self.api.handle_create_sip_endpoint(FakeRequest(body))
        payload = json.loads(response.text)

        self.assertEqual(response.status, 502)
        self.assertTrue(payload["sip_endpoint_rolled_back"])
        self.assertFalse(payload["manual_cleanup_required"])
        self.api._rollback_vps_sip_endpoint.assert_awaited_once_with("endpoint-1")


if __name__ == "__main__":
    unittest.main()
