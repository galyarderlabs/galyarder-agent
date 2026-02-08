#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${G_AGENT_REPO_URL:-https://github.com/galyarderlabs/galyarder-agent.git}"
INSTALL_DIR="${G_AGENT_INSTALL_DIR:-$HOME/galyarder-agent}"
DATA_DIR="${G_AGENT_DATA_DIR:-$HOME/.g-agent}"
SKIP_PACMAN="${G_AGENT_SKIP_PACMAN:-0}"
SKIP_SERVICES="${G_AGENT_SKIP_SERVICES:-0}"
AUTO_START_SERVICES="${G_AGENT_AUTO_START_SERVICES:-1}"

log() {
  printf '\033[1;36m[install]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$*"
}

fail() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

detect_arch_like() {
  if [[ "${OSTYPE:-}" != linux* ]]; then
    fail "This installer targets Linux (Arch-based) environments."
  fi
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    case "${ID:-}" in
      arch|manjaro|endeavouros) return 0 ;;
    esac
    case "${ID_LIKE:-}" in
      *arch*) return 0 ;;
    esac
  fi
  warn "Non-Arch distro detected. Continuing, but package install step may fail."
}

install_packages() {
  if [[ "$SKIP_PACMAN" == "1" ]]; then
    warn "Skipping pacman dependency install (G_AGENT_SKIP_PACMAN=1)."
    return 0
  fi
  require_cmd sudo
  require_cmd pacman
  log "Installing dependencies via pacman..."
  sudo pacman -S --noconfirm --needed \
    git \
    python \
    python-pipx \
    nodejs \
    npm \
    jq \
    curl
}

ensure_pipx() {
  if ! command -v pipx >/dev/null 2>&1; then
    log "pipx not found in PATH, installing via pip --user..."
    require_cmd python
    python -m pip install --user pipx
  fi

  python -m pipx ensurepath >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:$PATH"

  command -v pipx >/dev/null 2>&1 || fail "pipx is still unavailable in PATH."
}

sync_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Updating existing repo at $INSTALL_DIR..."
    git -C "$INSTALL_DIR" fetch origin main
    git -C "$INSTALL_DIR" checkout main
    git -C "$INSTALL_DIR" pull --ff-only
    return 0
  fi

  if [[ -e "$INSTALL_DIR" ]]; then
    fail "Install dir exists but is not a git repo: $INSTALL_DIR"
  fi

  log "Cloning repo to $INSTALL_DIR..."
  git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
}

install_agent() {
  local pkg_dir="$INSTALL_DIR/backend/agent"
  [[ -f "$pkg_dir/pyproject.toml" ]] || fail "Backend package not found at $pkg_dir"

  log "Installing g-agent with pipx..."
  pipx install --force "$pkg_dir"
  export PATH="$HOME/.local/bin:$PATH"

  command -v g-agent >/dev/null 2>&1 || fail "g-agent command not found after install."
}

bootstrap_config() {
  if [[ -f "$DATA_DIR/config.json" ]]; then
    log "Config already exists at $DATA_DIR/config.json (keeping existing config)."
    return 0
  fi
  log "Initializing fresh config/workspace at $DATA_DIR..."
  G_AGENT_DATA_DIR="$DATA_DIR" g-agent onboard </dev/null
}

setup_bridge() {
  local src="$INSTALL_DIR/backend/agent/bridge"
  local dst="$DATA_DIR/bridge"
  [[ -f "$src/package.json" ]] || fail "Bridge source missing: $src/package.json"

  log "Setting up WhatsApp bridge at $dst..."
  mkdir -p "$DATA_DIR"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp -a "$src"/. "$dst"/
  rm -rf "$dst/node_modules" "$dst/dist"

  npm --prefix "$dst" install
  npm --prefix "$dst" run build
}

install_user_services() {
  if [[ "$SKIP_SERVICES" == "1" ]]; then
    warn "Skipping systemd user service setup (G_AGENT_SKIP_SERVICES=1)."
    return 0
  fi

  require_cmd systemctl
  mkdir -p "$HOME/.config/systemd/user"

  local gateway_unit="$HOME/.config/systemd/user/g-agent-gateway.service"
  local bridge_unit="$HOME/.config/systemd/user/g-agent-wa-bridge.service"

  cat >"$gateway_unit" <<EOF
[Unit]
Description=g-agent Gateway
After=network-online.target
Wants=network-online.target g-agent-wa-bridge.service

[Service]
Type=simple
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin
Environment=G_AGENT_DATA_DIR=$DATA_DIR
ExecStart=%h/.local/bin/g-agent gateway
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

  cat >"$bridge_unit" <<EOF
[Unit]
Description=g-agent WhatsApp Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin
Environment=G_AGENT_DATA_DIR=$DATA_DIR
ExecStart=/usr/bin/env bash -lc 'exec npm --prefix "$DATA_DIR/bridge" start'
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable g-agent-wa-bridge.service g-agent-gateway.service

  if [[ "$AUTO_START_SERVICES" == "1" ]]; then
    systemctl --user restart g-agent-wa-bridge.service g-agent-gateway.service || true
  fi
}

print_next_steps() {
  cat <<EOF

✅ g-agent install complete.

Paths:
- Repo: $INSTALL_DIR
- Data: $DATA_DIR

Next steps:
1) Configure model/provider + allowlists:
   nano $DATA_DIR/config.json

2) Pair WhatsApp once (QR flow):
   G_AGENT_DATA_DIR="$DATA_DIR" g-agent channels login

3) Check status:
   G_AGENT_DATA_DIR="$DATA_DIR" g-agent status
   G_AGENT_DATA_DIR="$DATA_DIR" g-agent doctor --network

4) Check services:
   systemctl --user status g-agent-wa-bridge.service g-agent-gateway.service

Tips:
- If needed, enable user linger for true 24/7:
  sudo loginctl enable-linger "\$USER"
- Run ops scripts:
  $INSTALL_DIR/deploy/ops/healthcheck.sh
  $INSTALL_DIR/deploy/ops/backup.sh
EOF
}

main() {
  detect_arch_like
  install_packages
  ensure_pipx
  sync_repo
  install_agent
  bootstrap_config
  setup_bridge
  install_user_services
  print_next_steps
}

main "$@"
