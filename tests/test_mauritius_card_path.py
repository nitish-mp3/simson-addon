import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
from call_manager import CallManager
from local_api import LocalAPI

spec = importlib.util.spec_from_file_location("simson_api_client_test", Path(__file__).parents[2] / "integration/custom_components/simson/api.py")
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)


@pytest.mark.asyncio
@pytest.mark.parametrize("number", ["59330025", "+23059330025", "23059330025"])
async def test_card_service_payload_reaches_vps_protocol_with_explicit_6202(number):
    with patch.object(CallManager, "_load_history"):
        manager = CallManager("office")
    sent = AsyncMock()
    api = LocalAPI(SimpleNamespace(node_id="office", node_label="Office", routing_policy={},
        asterisk_context="from-simson-node"), manager, sent)
    client = client_module.SimsonApiClient("http://mock-addon")

    async def local_post(paths, body):
        assert paths[0] == "/api/call"
        response = await api._initiate_call(body)
        assert response.status == 201
        return json.loads(response.body)

    client._post_first = local_post
    result = await client.make_call(call_type="sip", phone_number=number, trunk="6202", caller_user_id="caller")
    payload = sent.call_args.args[0]["payload"]
    digits = number.lstrip("+")
    assert payload["to_node_id"] == f"sip:{digits}"
    assert payload["metadata"]["trunk"] == "6202"
    assert payload["metadata"]["extension"] == digits
    assert payload["metadata"]["caller_user_id"] == "caller"
    assert manager.get(result["call_id"]).routing.trunk == "6202"
    assert manager.active_call_for_user("observer") is None
    conflict = await api._initiate_call({"phone_number": number, "trunk": "6202", "caller_user_id": "caller"})
    assert conflict.status == 409
    assert sent.await_count == 1
