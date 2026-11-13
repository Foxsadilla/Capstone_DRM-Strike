# Name: registry.py
# Nodes: server (/opt/acme/acme/)
# Purpose: server-side device registry
# Notes:
#   - Creates one row per each serial issued: roles, model, status and timestamps.
#   - Devices become reigstered from its cert after verification from the cert first
#   - The registry will never trust an unsigned list
# ===================================================================