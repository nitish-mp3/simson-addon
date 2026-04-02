"""Auto-provisioning — creates account + node on the VPS if credentials are missing."""

import json
import logging
import os
import re
import socket

import aiohttp

logger = logging.getLogger("simson.provision")

CREDENTIALS_FILE = "/data/credentials.json"


def _sanitize_id(raw: str) -> str:
    """Turn an arbitrary string into a safe ID (lowercase alphanum + underscore)."""
    s = raw.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:64] or "default"


def load_saved_credentials() -> dict | None:
    """Load previously-saved credentials from persistent storage. Returns None if not found."""
    if not os.path.isfile(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE, "r") as f:
            data = json.load(f)
        if data.get("account_id") and data.get("node_id") and data.get("install_token"):
            logger.info("Loaded saved credentials from %s", CREDENTIALS_FILE)
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read saved credentials: %s", e)
    return None


def clear_saved_credentials() -> None:
    """Delete persisted credentials so the setup wizard runs again."""
    try:
        if os.path.isfile(CREDENTIALS_FILE):
            os.remove(CREDENTIALS_FILE)
            logger.info("Cleared saved credentials from %s", CREDENTIALS_FILE)
    except OSError as e:
        logger.warning("Could not clear credentials file: %s", e)


def _save_credentials(account_id: str, node_id: str, install_token: str,
                      node_label: str = "", capabilities: list | None = None) -> None:
    """Persist credentials so they survive addon restarts."""
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump({
            "account_id": account_id,
            "node_id": node_id,
            "install_token": install_token,
            "node_label": node_label,
            "capabilities": capabilities or ["haos", "voice"],
        }, f, indent=2)
    os.chmod(CREDENTIALS_FILE, 0o600)
    logger.info("Saved credentials to %s", CREDENTIALS_FILE)


def _admin_url(server_url: str) -> str:
    """Convert wss://host/ws to https://host for admin API calls."""
    url = server_url.replace("wss://", "https://").replace("ws://", "http://")
    url = url.rstrip("/")
    if url.endswith("/ws"):
        url = url[:-3]
    return url


async def auto_provision(server_url: str, admin_token: str,
                         node_label: str = "", account_id: str = "",
                         capabilities: list[str] | None = None) -> dict:
    """Create account + node on VPS, return {account_id, node_id, install_token}.

    Args:
        account_id: If provided, reuse this account (lets multiple nodes share one account).
                    If empty, auto-generates from hostname.
    Raises on failure.
    """
    base = _admin_url(server_url)
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    hostname = socket.gethostname() or "ha"
    if not account_id:
        account_id = _sanitize_id(f"ha_{hostname}")
    node_id = _sanitize_id(node_label or hostname)
    caps = capabilities or ["haos", "voice"]

    logger.info("Auto-provisioning: account=%s  node=%s  vps=%s", account_id, node_id, base)

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        # --- Create account (ignore 409 = already exists) ---
        async with session.post(
            f"{base}/admin/accounts",
            headers=headers,
            json={"id": account_id, "name": f"Auto-provisioned ({hostname})"},
        ) as resp:
            if resp.status == 201:
                logger.info("Account '%s' created", account_id)
            elif resp.status == 409:
                logger.info("Account '%s' already exists, reusing", account_id)
            else:
                body = await resp.text()
                raise RuntimeError(f"Failed to create account: HTTP {resp.status} — {body}")

        # --- Create node ---
        async with session.post(
            f"{base}/admin/accounts/{account_id}/nodes",
            headers=headers,
            json={
                "id": node_id,
                "label": node_label or node_id,
                "node_type": "haos",
                "capabilities": caps,
            },
        ) as resp:
            if resp.status == 201:
                data = await resp.json()
                install_token = data["install_token"]
                logger.info("Node '%s' created, install_token obtained", node_id)
            elif resp.status == 409:
                # Node already exists — we can't get the token again.
                # User must either revoke+recreate or provide token manually.
                raise RuntimeError(
                    f"Node '{node_id}' already exists on this account. "
                    f"Either delete it via the admin API and restart, "
                    f"or manually enter the install_token in the addon config."
                )
            else:
                body = await resp.text()
                raise RuntimeError(f"Failed to create node: HTTP {resp.status} — {body}")

    _save_credentials(account_id, node_id, install_token, node_label, caps)
    return {"account_id": account_id, "node_id": node_id, "install_token": install_token}
