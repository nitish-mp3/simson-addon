#!/usr/bin/with-contenv bashio
# Simson Addon — Entry point (called by s6-overlay)
set -e

bashio::log.info "Starting Simson Call Relay addon v1.0.1"

# Export config as environment variables for the Python process
export SIMSON_SERVER_URL=$(bashio::config 'server_url')
export SIMSON_ACCOUNT_ID=$(bashio::config 'account_id')
export SIMSON_NODE_ID=$(bashio::config 'node_id')
export SIMSON_INSTALL_TOKEN=$(bashio::config 'install_token')
export SIMSON_LOG_LEVEL=$(bashio::config 'log_level')

# Validate required config — give clear instructions if missing
if [ -z "$SIMSON_ACCOUNT_ID" ] || [ -z "$SIMSON_NODE_ID" ] || [ -z "$SIMSON_INSTALL_TOKEN" ]; then
    bashio::log.error "---------------------------------------------"
    bashio::log.error "CONFIGURATION REQUIRED"
    bashio::log.error ""
    bashio::log.error "Go to the addon Configuration tab and fill in:"
    bashio::log.error "  - account_id"
    bashio::log.error "  - node_id"
    bashio::log.error "  - install_token"
    bashio::log.error ""
    bashio::log.error "Get these from your VPS admin API:"
    bashio::log.error ""
    bashio::log.error "  1. Create an account:"
    bashio::log.error "     curl -X POST https://simson-vps.niti.life/admin/accounts \\"
    bashio::log.error "       -H 'Authorization: Bearer YOUR_ADMIN_TOKEN' \\"
    bashio::log.error "       -H 'Content-Type: application/json' \\"
    bashio::log.error "       -d '{\"id\":\"home\",\"name\":\"My Home\"}'"
    bashio::log.error ""
    bashio::log.error "  2. Create a node:"
    bashio::log.error "     curl -X POST https://simson-vps.niti.life/admin/accounts/home/nodes \\"
    bashio::log.error "       -H 'Authorization: Bearer YOUR_ADMIN_TOKEN' \\"
    bashio::log.error "       -H 'Content-Type: application/json' \\"
    bashio::log.error "       -d '{\"id\":\"living_room\",\"label\":\"Living Room\"}'"
    bashio::log.error ""
    bashio::log.error "  The response will contain the install_token."
    bashio::log.error "  Use the account id as account_id, node id as node_id."
    bashio::log.error "---------------------------------------------"
    # Sleep briefly so the log is visible, then exit
    sleep 5
    exit 1
fi

# Capabilities (comma-separated)
export SIMSON_CAPABILITIES=$(bashio::config 'capabilities' | tr -d '[]"' | tr ',' ',')

# Asterisk config
export SIMSON_ASTERISK_ENABLED=$(bashio::config 'asterisk.enabled')
export SIMSON_ASTERISK_HOST=$(bashio::config 'asterisk.host')
export SIMSON_ASTERISK_AMI_PORT=$(bashio::config 'asterisk.ami_port')
export SIMSON_ASTERISK_AMI_USER=$(bashio::config 'asterisk.ami_user')
export SIMSON_ASTERISK_AMI_SECRET=$(bashio::config 'asterisk.ami_secret')
export SIMSON_ASTERISK_CONTEXT=$(bashio::config 'asterisk.context')
export SIMSON_ASTERISK_EXT_PREFIX=$(bashio::config 'asterisk.extension_prefix')

# HA Supervisor token for API access
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

bashio::log.info "Connecting to ${SIMSON_SERVER_URL} as node ${SIMSON_NODE_ID}"

exec python3 /app/main.py
