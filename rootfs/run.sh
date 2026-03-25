#!/bin/bash
# Simson Addon — Entry point (PID 1, bypasses s6-overlay)
# HA Supervisor writes addon options to /data/options.json before starting.
# SUPERVISOR_TOKEN is injected automatically by HA as an env var.
set -e

echo "Starting Simson Call Relay..."
exec python3 /app/main.py
