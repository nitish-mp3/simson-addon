"""Regression tests for verified SIP call-behavior saves."""

import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from local_api import _verify_sip_call_behavior_response  # noqa: E402


class SIPBehaviorSaveVerificationTests(unittest.TestCase):
    def setUp(self):
        self.requested = {
            "pre_ring_announcement_text": " Please   wait ",
            "answer_announcement_text": "Call for Amit.",
            "call_duration_rules": {"1025": 15},
        }

    def test_accepts_fresh_committed_response(self):
        committed = {
            "pre_ring_announcement_text": "Please wait",
            "answer_announcement_text": "Call for Amit.",
            "call_duration_rules": '{"1025":15}',
        }

        self.assertEqual(
            _verify_sip_call_behavior_response(committed, self.requested),
            "",
        )

    def test_rejects_outdated_vps_response(self):
        error = _verify_sip_call_behavior_response({}, self.requested)

        self.assertIn("outdated", error)

    def test_rejects_uncommitted_duration_change(self):
        committed = {
            "pre_ring_announcement_text": "Please wait",
            "answer_announcement_text": "Call for Amit.",
            "call_duration_rules": {"1025": 20},
        }

        error = _verify_sip_call_behavior_response(committed, self.requested)

        self.assertIn("did not persist", error)


if __name__ == "__main__":
    unittest.main()
