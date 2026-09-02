"""Regression coverage for stale HA-originated gateway calls."""

import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from call_manager import CallInfo, CallState, RoutingIntent  # noqa: E402
from main import SimsonAddon  # noqa: E402


class GatewayCallRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_stale_gateway_call_is_ended_and_released(self):
        addon = SimsonAddon.__new__(SimsonAddon)
        addon.cfg = SimpleNamespace(node_id="office")
        addon.wss = SimpleNamespace(send=AsyncMock())
        addon._handle_call_status = AsyncMock()
        call = CallInfo(
            call_id="call-stale-gateway",
            remote_node_id="sip:9123208334",
            call_type="sip",
            direction="outgoing",
            state=CallState.ACTIVE,
            started_at=time.time() - 331,
            routing=RoutingIntent(trunk="7016"),
        )
        addon.call_mgr = SimpleNamespace(all_calls=[call])

        await addon.reconcile_call_state()

        addon.wss.send.assert_awaited_once()
        addon._handle_call_status.assert_awaited_once_with({
            "call_id": "call-stale-gateway",
            "status": "ended",
            "reason": "stale_gateway_outbound",
        })


if __name__ == "__main__":
    unittest.main()
