"""Call state machine — tracks active calls on the addon side."""

import json
import logging
import os
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger("simson.calls")

HISTORY_FILE = "/data/call_history.json"
MAX_HISTORY = 200


class CallState(str, Enum):
    IDLE = "idle"
    REQUESTING = "requesting"
    RINGING = "ringing"
    INCOMING = "incoming"
    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"
    MISSED = "missed"
    DECLINED = "declined"
    TIMEOUT = "timeout"


@dataclass
class RoutingIntent:
    """Describes where a call should be routed."""
    target_type: str = "node"       # node | device | asterisk | queue
    target_id: str = ""             # node_id, device extension, or queue id
    target_label: str = ""          # human-readable name
    extension: str = ""             # Asterisk extension (asterisk/queue types)
    context: str = ""               # Asterisk dial context
    trunk: str = ""                 # SIP trunk for external calls
    caller_id: str = ""             # outbound caller ID
    timeout: int = 30               # ring timeout in seconds
    fallback_targets: list = field(default_factory=list)  # list of target_id strings


@dataclass
class CallInfo:
    call_id: str
    remote_node_id: str
    remote_label: str = ""
    call_type: str = "voice"
    direction: str = "outgoing"  # "outgoing" or "incoming"
    state: CallState = CallState.IDLE
    started_at: float = 0.0
    answered_at: float = 0.0
    ended_at: float = 0.0
    end_reason: str = ""
    metadata: dict = field(default_factory=dict)
    routing: RoutingIntent | None = None
    fallback_attempt: int = 0       # which fallback target we're on (0 = primary)
    caller_user_id: str = ""        # hass user.id of whoever placed the outgoing call


# Type for state-change callback
StateChangeCallback = Callable[[CallInfo], Awaitable[None]]


class CallManager:
    """Manages call state for this node."""

    def __init__(self, node_id: str, on_state_change: StateChangeCallback | None = None):
        self.node_id = node_id
        self._calls: dict[str, CallInfo] = {}
        self._on_state_change = on_state_change
        self._history: list[dict] = []
        self._load_history()

    @property
    def active_call(self) -> CallInfo | None:
        """Return the current active/ringing/incoming call, if any."""
        for c in self._calls.values():
            if c.state in (CallState.REQUESTING, CallState.RINGING,
                           CallState.INCOMING, CallState.ACTIVE):
                return c
        return None

    def active_call_for_user(self, user_id: str) -> "CallInfo | None":
        """Return active call owned by user_id. Falls back to any active call if user_id blank."""
        if not user_id:
            return self.active_call
        for c in self._calls.values():
            if c.state in (CallState.REQUESTING, CallState.RINGING,
                           CallState.INCOMING, CallState.ACTIVE):
                if not c.caller_user_id or c.caller_user_id == user_id:
                    return c
        return None

    @property
    def all_calls(self) -> list[CallInfo]:
        return list(self._calls.values())

    def get(self, call_id: str) -> CallInfo | None:
        return self._calls.get(call_id)

    async def outgoing_request(self, call_id: str, to_node_id: str,
                               call_type: str = "voice",
                               routing: RoutingIntent | None = None,
                               caller_user_id: str = "",
                               remote_label: str = "") -> CallInfo:
        """Register an outgoing call request we just sent."""
        call = CallInfo(
            call_id=call_id,
            remote_node_id=to_node_id,
            remote_label=remote_label,
            call_type=call_type,
            direction="outgoing",
            state=CallState.REQUESTING,
            started_at=time.time(),
            routing=routing,
            caller_user_id=caller_user_id,
        )
        self._calls[call_id] = call
        await self._notify(call)
        return call

    async def incoming_invite(self, call_id: str, from_node_id: str,
                              from_label: str, call_type: str,
                              metadata: dict | None = None) -> CallInfo:
        """Register an incoming call invite from VPS."""
        call = CallInfo(
            call_id=call_id,
            remote_node_id=from_node_id,
            remote_label=from_label,
            call_type=call_type,
            direction="incoming",
            state=CallState.INCOMING,
            started_at=time.time(),
            metadata=metadata or {},
        )
        self._calls[call_id] = call
        await self._notify(call)
        return call

    async def update_status(self, call_id: str, status: str,
                            reason: str = "") -> CallInfo | None:
        """Update call state from a call.status message."""
        call = self._calls.get(call_id)
        if not call:
            return None

        prev = call.state
        if status == "ringing":
            call.state = CallState.RINGING
        elif status == "active":
            call.state = CallState.ACTIVE
            call.answered_at = time.time()
        elif status == "ended":
            call.state = CallState.ENDED
            call.ended_at = time.time()
            call.end_reason = reason
        elif status == "failed":
            call.state = CallState.FAILED
            call.ended_at = time.time()
            call.end_reason = reason
        elif status == "missed":
            call.state = CallState.MISSED
            call.ended_at = time.time()
            call.end_reason = reason or "missed"
        elif status == "declined":
            call.state = CallState.DECLINED
            call.ended_at = time.time()
            call.end_reason = reason or "declined"
        elif status == "timeout":
            call.state = CallState.TIMEOUT
            call.ended_at = time.time()
            call.end_reason = reason or "timeout"

        if call.state != prev:
            logger.info("Call %s: %s -> %s", call_id, prev.value, call.state.value)
            await self._notify(call)

        return call

    async def end_call(self, call_id: str, reason: str = "hangup") -> CallInfo | None:
        """Mark a call as ended locally."""
        call = self._calls.get(call_id)
        if not call:
            return None
        call.state = CallState.ENDED
        call.ended_at = time.time()
        call.end_reason = reason
        await self._notify(call)
        return call

    def cleanup(self, max_age: float = 300):
        """Remove ended calls older than max_age seconds."""
        now = time.time()
        terminal_states = (
            CallState.ENDED, CallState.FAILED,
            CallState.MISSED, CallState.DECLINED, CallState.TIMEOUT,
        )
        to_remove = [
            cid for cid, c in self._calls.items()
            if c.state in terminal_states
            and c.ended_at > 0  and (now - c.ended_at) > max_age
        ]
        for cid in to_remove:
            # Archive to history before removing.
            call = self._calls[cid]
            self._archive_call(call)
            del self._calls[cid]

    def _archive_call(self, call: CallInfo):
        """Add a completed call to persistent history."""
        entry = {
            "call_id": call.call_id,
            "remote_node_id": call.remote_node_id,
            "remote_label": call.remote_label,
            "call_type": call.call_type,
            "direction": call.direction,
            "state": call.state.value,
            "started_at": call.started_at,
            "answered_at": call.answered_at,
            "ended_at": call.ended_at,
            "end_reason": call.end_reason,
            "duration": (call.ended_at - call.answered_at) if call.answered_at and call.ended_at else 0,
        }
        # Avoid duplicates.
        if any(h["call_id"] == call.call_id for h in self._history):
            return
        self._history.insert(0, entry)
        self._history = self._history[:MAX_HISTORY]
        self._save_history()

    def get_history(self, limit: int = 50) -> list[dict]:
        """Return call history, most recent first."""
        return self._history[:limit]

    def _load_history(self):
        """Load call history from disk."""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r") as f:
                    self._history = json.load(f)
                logger.info("Loaded %d history entries", len(self._history))
        except Exception as e:
            logger.warning("Failed to load call history: %s", e)
            self._history = []

    def _save_history(self):
        """Save call history to disk."""
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, "w") as f:
                json.dump(self._history, f)
        except Exception as e:
            logger.warning("Failed to save call history: %s", e)

    async def _notify(self, call: CallInfo):
        if self._on_state_change:
            try:
                await self._on_state_change(call)
            except Exception:
                logger.exception("State change callback error")
