#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="${G_AGENT_INSTALL_DIR:-$HOME/galyarder-agent}"
DATA_DIR="${G_AGENT_DATA_DIR:-$HOME/.g-agent}"
REMOVE_SERVICES="${G_AGENT_REMOVE_SERVICES:-1}"
REMOVE_REPO="${G_AGENT_REMOVE_REPO:-0}"
WIPE_DATA="${G_AGENT_WIPE_DATA:-0}"

log() {
  printf '\033[1;36m[uninstall]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$*"
}

remove_systemd_user_services() {
  [[ "$REMOVE_SERVICES" == "1" ]] || {
    warn "Skipping systemd user service removal (G_AGENT_REMOVE_SERVICES=0)."
    return 0
  }

  if ! command -v systemctl >/dev/null 2>&1; then
    warn "systemctl not found; skipping user service removal."
    return 0
  fi

  log "Stopping/disabling g-agent systemd user services..."
  systemctl --user stop g-agent-gateway.service g-agent-wa-bridge.service >/dev/null 2>&1 || true
  systemctl --user disable g-agent-gateway.service g-agent-wa-bridge.service >/dev/null 2>&1 || true

  rm -f \
    "$HOME/.config/systemd/user/g-agent-gateway.service" \
    "$HOME/.config/systemd/user/g-agent-wa-bridge.service"

  systemctl --user daemon-reload >/dev/null 2>&1 || true
}

uninstall_pipx_package() {
  if ! command -v pipx >/dev/null 2>&1; then
    warn "pipx not found; skipping pipx uninstall."
  else
    log "Removing pipx package..."
    pipx uninstall galyarder-agent >/dev/null 2>&1 || true
    pipx uninstall g-agent >/dev/null 2>&1 || true
  fi

  rm -f "$HOME/.local/bin/g-agent"
}

cleanup_data_dir() {
  if [[ ! -d "$DATA_DIR" ]]; then
    warn "Data dir not found: $DATA_DIR"
    return 0
  fi

  if [[ "$WIPE_DATA" == "1" ]]; then
    log "Removing full data dir: $DATA_DIR"
    rm -rf "$DATA_DIR"
    return 0
  fi

  log "Keeping memory/config data. Removing runtime bridge artifacts only."
  rm -rf "$DATA_DIR/bridge"
  rm -f "$DATA_DIR"/gateway.log "$DATA_DIR"/gateway.err.log "$DATA_DIR"/wa-bridge.log "$DATA_DIR"/wa-bridge.err.log
}

cleanup_repo() {
  [[ "$REMOVE_REPO" == "1" ]] || {
    warn "Keeping repo dir (set G_AGENT_REMOVE_REPO=1 to remove): $INSTALL_DIR"
    return 0
  }

  if [[ -d "$INSTALL_DIR" ]]; then
    log "Removing repo dir: $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
  else
    warn "Repo dir not found: $INSTALL_DIR"
  fi
}

print_done() {
  cat <<EOF

✅ g-agent uninstall flow complete.

Removed:
- pipx package/binary (if present)
- systemd user units (if enabled)
- bridge runtime artifacts

Kept by default:
- $DATA_DIR/config.json
- $DATA_DIR/workspace/memory
- $DATA_DIR/cron
- repo directory: $INSTALL_DIR

To fully wipe everything, run with:
G_AGENT_WIPE_DATA=1 G_AGENT_REMOVE_REPO=1 bash deploy/arch/uninstall.sh
EOF
}

main() {
  remove_systemd_user_services
  uninstall_pipx_package
  cleanup_data_dir
  cleanup_repo
  print_done
}

main "$@"
