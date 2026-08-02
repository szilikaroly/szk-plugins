#!/usr/bin/env bash
# Install and activate memo-guard on THIS machine.
#
#   ./install.sh                      # install from this local directory
#   ./install.sh <github-user>/<repo> # install from GitHub after publishing
#
# Uses the non-interactive `claude plugin` subcommands, so no clicking required.
set -euo pipefail

SOURCE="${1:-}"
cd "$(dirname "$0")"
MARKET="szk-plugins"
PLUGIN="memo-guard"

command -v claude >/dev/null || {
  echo "The 'claude' CLI is not on PATH."
  echo "Install Claude Code first: https://code.claude.com/docs/en/overview"
  exit 1
}
command -v python3 >/dev/null || { echo "python3 is required."; exit 1; }

echo "==> validating"
claude plugin validate . || { echo "marketplace validation failed"; exit 1; }
claude plugin validate ./plugins/$PLUGIN || { echo "plugin validation failed"; exit 1; }

echo "==> selftest (measures the >=95% reduction target)"
MEMO_GUARD_HOME="$(mktemp -d)" python3 plugins/$PLUGIN/scripts/selftest.py | tail -8

if [ -z "$SOURCE" ]; then
  SOURCE="$(pwd)"
  echo "==> adding marketplace from local path: $SOURCE"
else
  echo "==> adding marketplace from GitHub: $SOURCE"
fi

# Re-adding replaces an existing marketplace of the same name, so this is
# safe to re-run after you push changes.
claude plugin marketplace add "$SOURCE"
claude plugin install "$PLUGIN@$MARKET"

cat <<'EOF'

Installed. Two things left, both inside a Claude Code session:

  /reload-plugins      activate it now, without restarting
  /memo-guard:status   confirm it is live and see the context counter

Optional live counter in the footer — add to ~/.claude/settings.json:

  { "statusLine": { "type": "command",
    "command": "python3 <cache-path>/scripts/statusline.py" } }

Run /memo-guard:status once; it prints the concrete cache path to use.

Note: installing COPIES the plugin into ~/.claude/plugins/cache. Editing this
directory afterwards changes nothing in the installed copy. After you edit and
push, run:  /plugin marketplace update szk-plugins  &&  /plugin update memo-guard
EOF
