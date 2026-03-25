"""Simson protocol constants and helpers — mirrors VPS protocol/messages.go."""

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone

PROTOCOL_VERSION = "1.0.0"
ADDON_VERSION = "1.0.0"

# Message types
TYPE_HELLO = "hello"
TYPE_AUTH_RESULT = "auth.result"
TYPE_HEARTBEAT = "heartbeat"
TYPE_HEARTBEAT_ACK = "heartbeat.ack"
TYPE_CALL_REQUEST = "call.request"
TYPE_CALL_INVITE = "call.invite"
TYPE_CALL_ACCEPT = "call.accept"
TYPE_CALL_REJECT = "call.reject"
TYPE_CALL_END = "call.end"
TYPE_CALL_STATUS = "call.status"
TYPE_ERROR = "error"

# Error codes
ERR_BAD_REQUEST = 4000
ERR_UNAUTHORIZED = 4001
ERR_FORBIDDEN = 4003
ERR_NODE_OFFLINE = 4004
ERR_RATE_LIMITED = 4029
ERR_INTERNAL = 5000


def make_envelope(msg_type: str, payload: dict) -> dict:
    """Create a protocol envelope.

    Timestamp must use Z suffix (not +00:00) to match Go's time.RFC3339Nano
    which always uses Z for UTC offsets when re-computing the HMAC.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    return {
        "type": msg_type,
        "id": str(uuid.uuid4()),
        "ts": ts,
        "payload": payload,
    }


def sign_envelope(envelope: dict, secret: str) -> dict:
    """Sign an envelope with HMAC-SHA256."""
    nonce = os.urandom(16).hex()
    envelope["nonce"] = nonce
    message = envelope["id"] + envelope["type"] + nonce + envelope["ts"]
    sig = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    envelope["signature"] = sig
    return envelope


def make_hello(node_id: str, account_id: str, install_token: str,
               capabilities: list[str], fingerprint: str = "") -> dict:
    """Create a hello message."""
    return make_envelope(TYPE_HELLO, {
        "node_id": node_id,
        "account_id": account_id,
        "install_token": install_token,
        "addon_version": ADDON_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": capabilities,
        "fingerprint": fingerprint,
    })


def make_heartbeat(node_id: str) -> dict:
    """Create a heartbeat message."""
    return make_envelope(TYPE_HEARTBEAT, {"node_id": node_id})


def make_call_request(from_node: str, to_node: str,
                      call_type: str = "voice",
                      metadata: dict | None = None) -> dict:
    """Create a call request message."""
    call_id = f"call_{uuid.uuid4()}"
    return make_envelope(TYPE_CALL_REQUEST, {
        "call_id": call_id,
        "from_node_id": from_node,
        "to_node_id": to_node,
        "call_type": call_type,
        "metadata": metadata or {},
    })


def make_call_accept(call_id: str, node_id: str) -> dict:
    """Create a call accept message."""
    return make_envelope(TYPE_CALL_ACCEPT, {
        "call_id": call_id,
        "node_id": node_id,
    })


def make_call_reject(call_id: str, node_id: str,
                     reason: str = "declined") -> dict:
    """Create a call reject message."""
    return make_envelope(TYPE_CALL_REJECT, {
        "call_id": call_id,
        "node_id": node_id,
        "reason": reason,
    })


def make_call_end(call_id: str, node_id: str,
                  reason: str = "hangup") -> dict:
    """Create a call end message."""
    return make_envelope(TYPE_CALL_END, {
        "call_id": call_id,
        "node_id": node_id,
        "reason": reason,
    })
