"""Configuration loader — reads from /data/options.json (written by HA Supervisor).

Node credentials (account_id, node_id, install_token) are NEVER read from options.json.
They live exclusively in /data/credentials.json, managed by the setup wizard and
auto-provisioner. This prevents stale addon-config values from causing auth failures.
"""

import json
import os

from provisioner import load_saved_credentials

OPTIONS_FILE = "/data/options.json"


def _load_options() -> dict:
    """Load addon options written by HA Supervisor before container start."""
    try:
        with open(OPTIONS_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


class Config:
    """Addon configuration.

    Infrastructure options (server_url, admin_token, log_level, port, asterisk)
    come from /data/options.json set via the HA addon configuration UI.

    Node credentials (account_id, node_id, install_token) come ONLY from
    /data/credentials.json, written by the setup wizard or auto-provisioner.
    They are never read from options.json so the addon config UI cannot accidentally
    corrupt them.
    """

    def __init__(self):
        opts = _load_options()

        # ── Infrastructure options (from addon config UI) ──────────────────
        self.server_url: str = opts.get("server_url", os.environ.get("SIMSON_SERVER_URL", ""))
        self.admin_token: str = opts.get("admin_token", os.environ.get("SIMSON_ADMIN_TOKEN", ""))
        self.log_level: str = opts.get("log_level", os.environ.get("SIMSON_LOG_LEVEL", "info")).upper()

        # ── Node credentials (from /data/credentials.json ONLY) ───────────
        # Do not read account_id / node_id / install_token from options.json.
        # The HA addon config UI cannot reliably manage these — any stale value
        # there would cause 4001 auth failures on restart.
        self.account_id: str = ""
        self.node_id: str = ""
        self.install_token: str = ""
        self.node_label: str = ""
        self.capabilities: list[str] = ["haos", "voice"]

        saved = load_saved_credentials()
        if saved:
            self.account_id = saved["account_id"]
            self.node_id = saved["node_id"]
            self.install_token = saved["install_token"]
            self.node_label = saved.get("node_label", "")
            if saved.get("capabilities"):
                self.capabilities = saved["capabilities"]

        # ── Asterisk (nested dict in options.json) ─────────────────────────
        ast = opts.get("asterisk", {})
        self.asterisk_enabled: bool = ast.get(
            "enabled", os.environ.get("SIMSON_ASTERISK_ENABLED", "false").lower() in ("true", "1", "yes")
        )
        self.asterisk_host: str = ast.get("host", os.environ.get("SIMSON_ASTERISK_HOST", "127.0.0.1"))
        self.asterisk_ami_port: int = int(ast.get("ami_port", os.environ.get("SIMSON_ASTERISK_AMI_PORT", 5038)))
        self.asterisk_ami_user: str = ast.get("ami_user", os.environ.get("SIMSON_ASTERISK_AMI_USER", "simson"))
        self.asterisk_ami_secret: str = ast.get("ami_secret", os.environ.get("SIMSON_ASTERISK_AMI_SECRET", ""))
        self.asterisk_context: str = ast.get("context", os.environ.get("SIMSON_ASTERISK_CONTEXT", "from-simson"))
        self.asterisk_ext_prefix: str = ast.get(
            "extension_prefix", os.environ.get("SIMSON_ASTERISK_EXT_PREFIX", "9")
        )

        # Ingress / local API
        self.local_api_port: int = int(opts.get("local_api_port", os.environ.get("SIMSON_LOCAL_API_PORT", 8799)))

        # HA Supervisor token (always from env — not in options.json)
        self.supervisor_token: str = os.environ.get("SUPERVISOR_TOKEN", "")

    def needs_provisioning(self) -> bool:
        """True if credentials are missing but admin_token is available."""
        return bool(self.admin_token) and not self.install_token

    def validate(self) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        errors = []
        if not self.server_url:
            errors.append("server_url is required")
        if self.server_url and not self.server_url.startswith(("ws://", "wss://")):
            errors.append("server_url must start with ws:// or wss://")
        # Credentials can be missing if we have an admin_token (auto-provision).
        if not self.needs_provisioning():
            if not self.account_id:
                errors.append("No credentials found. Open the Simson panel and complete setup.")
            if not self.node_id:
                errors.append("node_id missing — open the Simson panel to set up this node.")
            if not self.install_token:
                errors.append("install_token missing — open the Simson panel to set up this node.")
        if self.asterisk_enabled and not self.asterisk_ami_secret:
            errors.append("asterisk ami_secret is required when asterisk is enabled")
        return errors
