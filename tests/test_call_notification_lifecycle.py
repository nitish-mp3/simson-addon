"""Regression tests for coherent incoming-call mobile notifications."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from main import SimsonAddon  # noqa: E402


class CallNotificationLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.addon = SimsonAddon.__new__(SimsonAddon)
        self.addon.cfg = SimpleNamespace(node_id="office", node_label="Office", account_id="site-a")
        self.addon.ha = SimpleNamespace(send_notify_message=AsyncMock(return_value=True))
        self.addon._mobile_notify_last = {}
        self.addon._mobile_incoming_calls = {}
        self.settings = {
            "automation": {
                "notify_services": "notify.mobile_app_test_phone",
                "dashboard_path": "/lovelace/calls",
            }
        }

    async def notify(self, payload):
        with patch("main.load_settings", return_value=self.settings):
            await self.addon._notify_call_event(payload)

    async def test_outgoing_call_never_creates_or_replaces_phone_alert(self):
        await self.notify({
            "event": "outgoing",
            "call_id": "out-1",
            "direction": "outgoing",
            "remote_number": "1027",
        })
        await self.notify({
            "event": "ended",
            "call_id": "out-1",
            "direction": "outgoing",
            "remote_number": "1027",
        })

        self.addon.ha.send_notify_message.assert_not_awaited()

    async def test_answered_incoming_call_updates_then_clears_same_alert(self):
        base = {
            "call_id": "incoming-1",
            "direction": "incoming",
            "call_type": "sip",
            "remote_number": "1027",
        }
        await self.notify({**base, "event": "incoming"})
        await self.notify({**base, "event": "active"})
        await self.notify({**base, "event": "ended", "reason": "remote_hangup"})

        calls = self.addon.ha.send_notify_message.await_args_list
        self.assertEqual(len(calls), 4)
        self.assertIn("is calling", calls[0].args[1])
        self.assertEqual(calls[0].kwargs["data"]["channel"], "Simson Incoming Calls v5")
        baseline_actions = calls[0].kwargs["data"]["actions"]
        self.assertEqual([item["title"] for item in baseline_actions], [
            "Answer & Open",
            "Decline",
            "View",
        ])
        self.assertEqual(baseline_actions[0]["action"], "URI")
        self.assertIn("/api/simson/call-action/answer/incoming-1", baseline_actions[0]["uri"])
        self.assertIn("redirect=%2Flovelace%2Fcalls", baseline_actions[0]["uri"])
        self.assertTrue(baseline_actions[1]["action"].startswith("SIMSON_DECLINE::office::incoming-1"))
        actions = calls[1].kwargs["data"]["actions"]
        self.assertEqual([item["title"] for item in actions], [
            "Answer and open call",
            "Decline",
            "Open call screen",
        ])
        self.assertEqual(actions[0]["action"], "URI")
        self.assertIn("/api/simson/call-action/answer/incoming-1", actions[0]["uri"])
        self.assertTrue(actions[1]["action"].startswith("SIMSON_DECLINE::office::incoming-1"))
        self.assertIn("is active", calls[2].args[1])
        self.assertEqual(calls[3].args[1], "clear_notification")
        self.assertEqual(calls[0].kwargs["data"]["tag"], calls[1].kwargs["data"]["tag"])
        self.assertNotIn("incoming-1", self.addon._mobile_incoming_calls)

    async def test_unanswered_remote_hangup_becomes_one_missed_call_update(self):
        base = {
            "call_id": "incoming-2",
            "direction": "incoming",
            "call_type": "sip",
            "remote_name": "Front desk",
        }
        await self.notify({**base, "event": "incoming"})
        await self.notify({**base, "event": "ended", "reason": "remote_hangup"})

        calls = self.addon.ha.send_notify_message.await_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[2].kwargs["title"], "Simson Missed Call")
        self.assertIn("Missed call from Front desk", calls[2].args[1])
        self.assertNotEqual(calls[2].args[1], "clear_notification")
        self.assertNotIn("hung up", calls[2].args[1].lower())


if __name__ == "__main__":
    unittest.main()
