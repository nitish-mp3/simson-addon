import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
from ice_config import merge_ice_servers


def test_remote_stun_config_does_not_erase_local_turn():
    local = [{"urls": "turn:local-relay:3478", "username": "user", "credential": "test"}, {"urls": "stun:example"}]
    remote = [{"urls": "stun:example"}]
    merged = merge_ice_servers(local, remote)
    assert merged == [remote[0], local[0]]
    assert local[0]["credential"] == "test"
