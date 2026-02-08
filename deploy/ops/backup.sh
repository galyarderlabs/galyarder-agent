#!/usr/bin/env bash
set -Eeuo pipefail

DATA_DIR="${G_AGENT_DATA_DIR:-$HOME/.g-agent}"
BACKUP_DIR="${1:-${G_AGENT_BACKUP_DIR:-$HOME/.g-agent-backups}}"
STAMP="$(date +%F-%H%M%S)"
ARCHIVE="$BACKUP_DIR/g-agent-$STAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

INCLUDE_ITEMS=()
for rel in config.json workspace/memory cron; do
  if [[ -e "$DATA_DIR/$rel" ]]; then
    INCLUDE_ITEMS+=("$rel")
  fi
done

if [[ ${#INCLUDE_ITEMS[@]} -eq 0 ]]; then
  echo "[error] Nothing to back up from $DATA_DIR (missing config/memory/cron)." >&2
  exit 1
fi

tar -C "$DATA_DIR" -czf "$ARCHIVE" "${INCLUDE_ITEMS[@]}"
echo "Backup created: $ARCHIVE"
