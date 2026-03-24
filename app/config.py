"""Configuration loader — reads from environment (set by run.sh from HA options)."""

import os


def _safe_int(env_key: str, default: int) -> int:
    """Parse an integer from env, falling back to default on bad input."""
    raw = os.environ.get(env_key, str(default))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


class Config:
    """Addon configuration from environment variables."""

    def __init__(self):
        self.server_url: str = os.environ.get("SIMSON_SERVER_URL", "")
        self.account_id: str = os.environ.get("SIMSON_ACCOUNT_ID", "")
        self.node_id: str = os.environ.get("SIMSON_NODE_ID", "")
        self.install_token: str = os.environ.get("SIMSON_INSTALL_TOKEN", "")
        self.log_level: str = os.environ.get("SIMSON_LOG_LEVEL", "info").upper()

        caps = os.environ.get("SIMSON_CAPABILITIES", "haos,voice")
        self.capabilities: list[str] = [c.strip() for c in caps.split(",") if c.strip()]

        # Asterisk
        self.asterisk_enabled: bool = os.environ.get(
            "SIMSON_ASTERISK_ENABLED", "false"
        ).lower() in ("true", "1", "yes")
        self.asterisk_host: str = os.environ.get("SIMSON_ASTERISK_HOST", "127.0.0.1")
        self.asterisk_ami_port: int = _safe_int("SIMSON_ASTERISK_AMI_PORT", 5038)
        self.asterisk_ami_user: str = os.environ.get("SIMSON_ASTERISK_AMI_USER", "simson")
        self.asterisk_ami_secret: str = os.environ.get("SIMSON_ASTERISK_AMI_SECRET", "")
        self.asterisk_context: str = os.environ.get("SIMSON_ASTERISK_CONTEXT", "from-simson")
        self.asterisk_ext_prefix: str = os.environ.get("SIMSON_ASTERISK_EXT_PREFIX", "9")

        # Ingress / local API
        self.local_api_port: int = _safe_int("SIMSON_LOCAL_API_PORT", 8099)

        # HA Supervisor
        self.supervisor_token: str = os.environ.get("SUPERVISOR_TOKEN", "")

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        errors = []
        if not self.server_url:
            errors.append("server_url is required")
        if not self.server_url.startswith(("ws://", "wss://")):
            errors.append("server_url must start with ws:// or wss://")
        if not self.account_id:
            errors.append("account_id is required")
        if not self.node_id:
            errors.append("node_id is required")
        if not self.install_token:
            errors.append("install_token is required")
        if self.asterisk_enabled and not self.asterisk_ami_secret:
            errors.append("asterisk ami_secret is required when asterisk is enabled")
        return errors
