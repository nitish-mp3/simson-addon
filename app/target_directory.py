"""Target directory — provides the list of callable targets from addon config."""

import logging
from config import Config
from call_manager import RoutingIntent

logger = logging.getLogger("simson.targets")


class TargetDirectory:
    """Loads call targets from addon config and resolves routing intents."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._targets: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load targets from config into an indexed map."""
        self._targets.clear()
        for t in self.cfg.call_targets:
            tid = t.get("id", "")
            if not tid:
                logger.warning("Skipping call_target with no id: %s", t)
                continue
            self._targets[tid] = t
        logger.info("Loaded %d call targets", len(self._targets))

    def reload(self):
        """Re-read targets from config (after config change)."""
        self._load()

    def all_targets(self) -> list[dict]:
        """Return all targets as a list suitable for the API."""
        return list(self._targets.values())

    def get(self, target_id: str) -> dict | None:
        """Get a single target by id."""
        return self._targets.get(target_id)

    def resolve_routing(self, target_id: str) -> RoutingIntent | None:
        """Build a RoutingIntent from a target id."""
        t = self._targets.get(target_id)
        if not t:
            return None
        return RoutingIntent(
            target_type=t.get("type", "node"),
            target_id=t.get("id", ""),
            target_label=t.get("label", ""),
            extension=t.get("extension", ""),
            context=t.get("context", ""),
            trunk=t.get("trunk", ""),
            caller_id=t.get("caller_id", ""),
            timeout=t.get("timeout", 30),
            fallback_targets=t.get("fallback_targets", []),
        )

    def resolve_node_id(self, target_id: str) -> str:
        """Return the node_id for a target (for VPS routing).

        For node/device types, returns the configured node_id.
        For asterisk/queue types, returns this node's own id (local Asterisk).
        """
        t = self._targets.get(target_id)
        if not t:
            return target_id  # fallback: treat target_id as a raw node_id
        ttype = t.get("type", "node")
        if ttype in ("node", "device"):
            return t.get("node_id", "") or target_id
        # asterisk/queue targets route to local Asterisk on this node
        return self.cfg.node_id
