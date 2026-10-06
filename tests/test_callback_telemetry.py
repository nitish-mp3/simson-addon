import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
from call_manager import CallManager
from main import SimsonAddon
from local_api import _call_to_dict


@pytest.mark.asyncio
async def test_callback_status_exposes_the_real_call_id_without_browser_invites():
    with patch.object(CallManager, "_load_history"), patch.object(CallManager, "_save_history"):
        manager = CallManager("office")
        notifications = []
        async def changed(call):
            notifications.append(call.direction)
        manager._on_state_change = changed
        addon = SimsonAddon.__new__(SimsonAddon)
        addon.cfg = SimpleNamespace(node_id="office")
        addon.call_mgr = manager
        addon.ha = SimpleNamespace(fire_event=AsyncMock())
        addon.api = SimpleNamespace(push_sse_event=Mock())
        addon.clear_outgoing_request_for_call = Mock()
        addon._cancel_ring_timer = Mock()
        addon._cancel_sip_route_timer = Mock()
        addon._emit_call_event = AsyncMock()
        payload = {"call_id": "call_one", "status": "ringing", "control_node_id": "office",
            "from_node_id": "sip:3101", "to_node_id": "sip:9123208334", "source_extension": "3101",
            "trunk": "1701", "call_type": "sip", "sip_bridge_id": "bridge-one"}
        await addon._handle_call_status(payload)
        call = manager.get("call_one")
        assert call.direction == "outgoing"
        assert call.metadata["controller_callback"]
        assert manager.active_call_for_user("unrelated-user") is None
        assert notifications and all(direction == "outgoing" for direction in notifications)
        serialized = _call_to_dict(call)
        assert serialized["call_id"] == "call_one"
        assert serialized["source_extension"] == "3101"
        assert serialized["trunk"] == "1701"
        await addon._handle_call_status({**payload, "status": "ended", "reason": "busy"})
        assert manager.active_call is None
