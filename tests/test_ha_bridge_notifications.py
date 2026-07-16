"""Regression tests for actionable Companion-app notification delivery."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from ha_bridge import HABridge  # noqa: E402


class HABridgeNotificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge = HABridge.__new__(HABridge)
        self.bridge.cfg = SimpleNamespace()
        self.bridge.call_service = AsyncMock(return_value=True)
        self.bridge.discover_notify_targets = AsyncMock(return_value=[
            {
                "ref": "notify.mobile_app_23090ra98i",
                "label": "Pixel",
                "kind": "service",
                "rich_actions": True,
            },
            {
                "ref": "notify.23090ra98i",
                "label": "Pixel",
                "kind": "entity",
                "rich_actions": False,
            },
        ])

    async def test_action_notification_prefers_discovered_mobile_service(self):
        ok = await self.bridge.send_notify_message(
            "notify.23090ra98i",
            "Caller is ringing",
            title="Incoming call",
            data={
                "actions": [{"action": "ANSWER", "title": "Answer"}],
                "persistent": True,
            },
        )

        self.assertTrue(ok)
        self.bridge.call_service.assert_awaited_once()
        args = self.bridge.call_service.await_args.args
        self.assertEqual(args[:2], ("notify", "mobile_app_23090ra98i"))
        self.assertEqual(args[2]["data"]["actions"][0]["action"], "ANSWER")

    async def test_plain_entity_remains_supported_without_mobile_service(self):
        self.bridge.discover_notify_targets.return_value = [{
            "ref": "notify.front_desk",
            "label": "Front desk",
            "kind": "entity",
            "rich_actions": False,
        }]

        ok = await self.bridge.send_notify_message(
            "notify.front_desk",
            "Test message",
        )

        self.assertTrue(ok)
        self.bridge.call_service.assert_awaited_once_with(
            "notify",
            "send_message",
            {"entity_id": "notify.front_desk", "message": "Test message"},
        )

    async def test_explicit_mobile_service_is_not_rewritten(self):
        ok = await self.bridge.send_notify_message(
            "notify.mobile_app_23090ra98i",
            "Caller is ringing",
            data={"actions": [{"action": "DECLINE", "title": "Decline"}]},
        )

        self.assertTrue(ok)
        self.bridge.call_service.assert_awaited_once()
        self.assertEqual(
            self.bridge.call_service.await_args.args[:2],
            ("notify", "mobile_app_23090ra98i"),
        )

    async def test_retries_reduced_rich_payload_before_losing_actions(self):
        self.bridge.call_service.side_effect = [False, True]
        ok = await self.bridge.send_notify_message(
            "notify.mobile_app_23090ra98i",
            "Caller is ringing",
            title="Incoming call",
            data={
                "actions": [{"action": "ANSWER", "title": "Answer"}],
                "persistent": True,
                "simson": {"call_id": "call-1"},
                "tag": "simson-call-1",
            },
        )

        self.assertTrue(ok)
        self.assertEqual(self.bridge.call_service.await_count, 2)
        retry = self.bridge.call_service.await_args_list[1].args[2]
        self.assertIn("actions", retry["data"])
        self.assertNotIn("persistent", retry["data"])
        self.assertNotIn("simson", retry["data"])

    async def test_action_notification_never_falls_back_to_plain_same_tag(self):
        self.bridge.call_service.side_effect = [False, False]
        ok = await self.bridge.send_notify_message(
            "notify.mobile_app_23090ra98i",
            "Caller is ringing",
            title="Incoming call",
            data={
                "actions": [{"action": "ANSWER", "title": "Answer"}],
                "persistent": True,
            },
        )

        self.assertFalse(ok)
        self.assertEqual(self.bridge.call_service.await_count, 2)
        for call in self.bridge.call_service.await_args_list:
            body = call.args[2]
            self.assertIn("actions", body["data"])


if __name__ == "__main__":
    unittest.main()
