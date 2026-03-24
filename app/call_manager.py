"""Call state machine — tracks active calls on the addon side."""

import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger("simson.calls")


class CallState(str, Enum):
    IDLE = "idle"
    REQUESTING = "requesting"
    RINGING = "ringing"
    INCOMING = "incoming"
    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"


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


# Type for state-change callback
StateChangeCallback = Callable[[CallInfo], Awaitable[None]]


class CallManager:
    """Manages call state for this node."""

    def __init__(self, node_id: str, on_state_change: StateChangeCallback | None = None):
        self.node_id = node_id
        self._calls: dict[str, CallInfo] = {}
        self._on_state_change = on_state_change

    @property
    def active_call(self) -> CallInfo | None:
        """Return the current active/ringing/incoming call, if any."""
        for c in self._calls.values():
            if c.state in (CallState.REQUESTING, CallState.RINGING,
                           CallState.INCOMING, CallState.ACTIVE):
                return c
        return None

    @property
    def all_calls(self) -> list[CallInfo]:
        return list(self._calls.values())

    def get(self, call_id: str) -> CallInfo | None:
        return self._calls.get(call_id)

    async def outgoing_request(self, call_id: str, to_node_id: str,
                               call_type: str = "voice") -> CallInfo:
        """Register an outgoing call request we just sent."""
        call = CallInfo(
            call_id=call_id,
            remote_node_id=to_node_id,
            call_type=call_type,
            direction="outgoing",
            state=CallState.REQUESTING,
            started_at=time.time(),
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
        to_remove = [
            cid for cid, c in self._calls.items()
            if c.state in (CallState.ENDED, CallState.FAILED)
            and c.ended_at > 0  and (now - c.ended_at) > max_age
        ]
        for cid in to_remove:
            del self._calls[cid]

    async def _notify(self, call: CallInfo):
        if self._on_state_change:
            try:
                await self._on_state_change(call)
            except Exception:
                logger.exception("State change callback error")
