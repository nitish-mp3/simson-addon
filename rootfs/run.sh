#!/usr/bin/with-contenv bashio
# Simson Addon — Entry point
set -e

CONFIG_PATH=/data/options.json

bashio::log.info "Starting Simson Call Relay addon v1.0.0"

# Export config as environment variables for the Python process
export SIMSON_SERVER_URL=$(bashio::config 'server_url')
export SIMSON_ACCOUNT_ID=$(bashio::config 'account_id')
export SIMSON_NODE_ID=$(bashio::config 'node_id')
export SIMSON_INSTALL_TOKEN=$(bashio::config 'install_token')
export SIMSON_LOG_LEVEL=$(bashio::config 'log_level')

# Validate required config
if [ -z "$SIMSON_SERVER_URL" ] || [ -z "$SIMSON_ACCOUNT_ID" ] || [ -z "$SIMSON_NODE_ID" ] || [ -z "$SIMSON_INSTALL_TOKEN" ]; then
    bashio::log.error "Missing required configuration. Please set server_url, account_id, node_id, and install_token."
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
