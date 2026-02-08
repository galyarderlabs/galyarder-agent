#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${G_AGENT_REPO_URL:-https://github.com/galyarderlabs/galyarder-agent.git}"
INSTALL_DIR="${G_AGENT_INSTALL_DIR:-$HOME/galyarder-agent}"
DATA_DIR="${G_AGENT_DATA_DIR:-$HOME/.g-agent}"
SKIP_BREW="${G_AGENT_SKIP_BREW:-0}"
SETUP_LAUNCHD="${G_AGENT_SETUP_LAUNCHD:-0}"
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

detect_macos() {
  [[ "$(uname -s)" == "Darwin" ]] || fail "This installer targets macOS only."
}

install_packages() {
  if [[ "$SKIP_BREW" == "1" ]]; then
    warn "Skipping Homebrew dependency install (G_AGENT_SKIP_BREW=1)."
    return 0
  fi
  require_cmd brew
  log "Installing dependencies via Homebrew..."
  brew update
  brew install git python pipx node jq
}

ensure_pipx() {
  if ! command -v pipx >/dev/null 2>&1; then
    log "pipx not found in PATH, installing via pip --user..."
    require_cmd python3
    python3 -m pip install --user pipx
  fi
  python3 -m pipx ensurepath >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
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
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

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

setup_launchd() {
  if [[ "$SETUP_LAUNCHD" != "1" ]]; then
    warn "Skipping launchd setup. Set G_AGENT_SETUP_LAUNCHD=1 to install LaunchAgents."
    return 0
  fi

  require_cmd launchctl
  local uid
  uid="$(id -u)"
  local agents_dir="$HOME/Library/LaunchAgents"
  mkdir -p "$agents_dir"

  local g_agent_bin="${G_AGENT_BIN:-$(command -v g-agent || true)}"
  [[ -n "$g_agent_bin" ]] || fail "Unable to resolve g-agent executable path."

  local gateway_plist="$agents_dir/com.galyarder.g-agent.gateway.plist"
  local bridge_plist="$agents_dir/com.galyarder.g-agent.wa-bridge.plist"

  cat >"$gateway_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.galyarder.g-agent.gateway</string>
    <key>ProgramArguments</key>
    <array>
      <string>$g_agent_bin</string>
      <string>gateway</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
      <key>G_AGENT_DATA_DIR</key><string>$DATA_DIR</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$DATA_DIR/gateway.log</string>
    <key>StandardErrorPath</key><string>$DATA_DIR/gateway.err.log</string>
  </dict>
</plist>
EOF

  cat >"$bridge_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.galyarder.g-agent.wa-bridge</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>-lc</string>
      <string>exec npm --prefix "$DATA_DIR/bridge" start</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
      <key>G_AGENT_DATA_DIR</key><string>$DATA_DIR</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$DATA_DIR/wa-bridge.log</string>
    <key>StandardErrorPath</key><string>$DATA_DIR/wa-bridge.err.log</string>
  </dict>
</plist>
EOF

  launchctl bootout "gui/$uid/com.galyarder.g-agent.gateway" >/dev/null 2>&1 || true
  launchctl bootout "gui/$uid/com.galyarder.g-agent.wa-bridge" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$uid" "$bridge_plist"
  launchctl bootstrap "gui/$uid" "$gateway_plist"

  if [[ "$AUTO_START_SERVICES" == "1" ]]; then
    launchctl kickstart -k "gui/$uid/com.galyarder.g-agent.wa-bridge" || true
    launchctl kickstart -k "gui/$uid/com.galyarder.g-agent.gateway" || true
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

4) Run ops scripts:
   $INSTALL_DIR/deploy/ops/healthcheck.sh
   $INSTALL_DIR/deploy/ops/backup.sh

Notes:
- launchd setup is optional. Enable with: G_AGENT_SETUP_LAUNCHD=1
- If launchd enabled, logs go to:
  $DATA_DIR/gateway.log
  $DATA_DIR/wa-bridge.log
EOF
}

main() {
  detect_macos
  install_packages
  ensure_pipx
  sync_repo
  install_agent
  bootstrap_config
  setup_bridge
  setup_launchd
  print_next_steps
}

main "$@"
