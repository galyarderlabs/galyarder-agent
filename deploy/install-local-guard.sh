#!/usr/bin/env bash
set -euo pipefail

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "install-local-guard: run this inside the galyarder-agent git repo"
  exit 1
fi
cd "$repo_root"

if [[ ! -f ".githooks/pre-push" ]]; then
  echo "install-local-guard: missing .githooks/pre-push"
  exit 1
fi

git config core.hooksPath .githooks
chmod +x .githooks/pre-push

echo "install-local-guard: installed"
echo "  core.hooksPath=$(git config --get core.hooksPath)"
echo "  hook=.githooks/pre-push (executable)"
echo
echo "Bypass once (if needed):"
echo "  G_AGENT_SKIP_PRE_PUSH=1 git push origin main"
