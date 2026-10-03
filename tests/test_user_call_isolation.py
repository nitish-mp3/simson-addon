import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
from call_manager import CallManager


@pytest.mark.asyncio
async def test_automation_does_not_block_unrelated_user():
    with patch.object(CallManager, "_load_history"):
        manager = CallManager("office")
    await manager.outgoing_request("automation", "sip:1701")
    assert manager.active_call_for_user("third-user") is None
    await manager.outgoing_request("user-call", "studio", caller_user_id="caller")
    assert manager.active_call_for_user("caller").call_id == "user-call"
    assert manager.active_call_for_user("third-user") is None


@pytest.mark.asyncio
async def test_local_user_call_preserves_both_participants():
    with patch.object(CallManager, "_load_history"):
        manager = CallManager("office")
    await manager.outgoing_request("one", "office", caller_user_id="caller")
    await manager.incoming_invite("one", "office", "Office", "video",
        {"caller_user_id": "caller", "target_user_id": "recipient", "local_user_call": True})
    assert manager.active_call_for_user("caller").call_id == "one"
    assert manager.active_call_for_user("recipient").call_id == "one"
    assert manager.active_call_for_user("third-user") is None
