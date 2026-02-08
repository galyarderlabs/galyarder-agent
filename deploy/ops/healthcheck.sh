#!/usr/bin/env bash
set -Eeuo pipefail

DATA_DIR="${G_AGENT_DATA_DIR:-$HOME/.g-agent}"
export G_AGENT_DATA_DIR="$DATA_DIR"

if ! command -v g-agent >/dev/null 2>&1; then
  echo "[error] g-agent command not found in PATH." >&2
  exit 1
fi

echo "== g-agent healthcheck =="
echo "Data dir: $DATA_DIR"
echo

echo "-- Version --"
g-agent --version
echo

echo "-- Status --"
g-agent status || true
echo

echo "-- Doctor (network) --"
g-agent doctor --network || true
echo

if command -v systemctl >/dev/null 2>&1; then
  echo "-- systemd user units --"
  systemctl --user --no-pager --full status \
    g-agent-gateway.service \
    g-agent-wa-bridge.service || true
  echo
fi

if command -v journalctl >/dev/null 2>&1; then
  echo "-- recent logs (last 80 lines) --"
  journalctl --user \
    -u g-agent-gateway.service \
    -u g-agent-wa-bridge.service \
    -n 80 \
    --no-pager || true
fi
