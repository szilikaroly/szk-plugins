#!/usr/bin/env bash
# Publish this marketplace to GitHub in one shot.
#
#   ./publish.sh <github-user> [repo-name] [public|private]
#
# Requires the GitHub CLI, authenticated:  gh auth login
# Uses YOUR git identity — nothing is committed under anyone else's name.
set -euo pipefail

USER_NAME="${1:?usage: ./publish.sh <github-user> [repo-name] [public|private]}"
REPO="${2:-szk-plugins}"
VIS="${3:-public}"
cd "$(dirname "$0")"

command -v gh >/dev/null || { echo "gh CLI not found: https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "run: gh auth login"; exit 1; }
git config --get user.name  >/dev/null || { echo 'set: git config --global user.name "Your Name"'; exit 1; }
git config --get user.email >/dev/null || { echo 'set: git config --global user.email "you@example.com"'; exit 1; }

echo "==> sanity checks"
python3 -c "import json;json.load(open('.claude-plugin/marketplace.json'))"
python3 -c "import json;json.load(open('plugins/memo-guard/.claude-plugin/plugin.json'))"
python3 -c "import json;json.load(open('plugins/memo-guard/hooks/hooks.json'))"
python3 -m py_compile plugins/memo-guard/scripts/*.py
MEMO_GUARD_HOME="$(mktemp -d)" python3 plugins/memo-guard/scripts/selftest.py >/dev/null \
  && echo "    selftest PASS"
command -v claude >/dev/null && claude plugin validate . || \
  echo "    (claude CLI not on PATH — skipping plugin validate)"

echo "==> git"
[ -d .git ] || git init -q -b main
git add -A
git diff --cached --quiet || git commit -q -m "memo-guard: context-window monitor, lossless archive at 70/80%, memo compression"

echo "==> guard: no session data staged"
if git ls-files | grep -Eq '\.jsonl(\.gz)?$|^(archive|sessions)/'; then
  echo "REFUSING: transcript/archive files are staged. They contain full session"
  echo "content including any secrets. Remove them and re-run."; exit 1
fi

echo "==> pushing to github.com/$USER_NAME/$REPO"
gh repo view "$USER_NAME/$REPO" >/dev/null 2>&1 \
  && git remote get-url origin >/dev/null 2>&1 \
  || gh repo create "$USER_NAME/$REPO" "--$VIS" --source=. --remote=origin \
       --description "Claude Code plugins: memo-guard context-window compression"
git push -u origin main

cat <<EOF

Done. Install it anywhere with:

  /plugin marketplace add $USER_NAME/$REPO
  /plugin install memo-guard@szk-plugins
  /reload-plugins
  /memo-guard:status
EOF
