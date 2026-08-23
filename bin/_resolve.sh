# Shared resolution for the szk-plugins launchers. Sourced, not executed.
#
# Always target the real SOURCE .py, in this order:
#   1. the git working copy      — source of truth, editable, what you just changed
#   2. the marketplace clone     — what `claude plugin update` pulled
#   3. the newest install cache  — what a session is actually running
#
# The order matters: a launcher that preferred the install cache would keep
# running yesterday's code while you edit the repo and wonder why nothing changes.
szk_resolve() {   # szk_resolve <plugin> <script-relative-path>
  local plugin="$1" rel="$2" cache_base latest p
  local candidates=(
    "$HOME/Documents/claude/szk-plugins/plugins/$plugin/$rel"
    "$HOME/.claude/plugins/marketplaces/szk-plugins/plugins/$plugin/$rel"
  )
  cache_base="$HOME/.claude/plugins/cache/szk-plugins/$plugin"
  if [[ -d "$cache_base" ]]; then
    latest="$(ls -1 "$cache_base" 2>/dev/null | sort -V | tail -1 || true)"
    [[ -n "${latest:-}" ]] && candidates+=("$cache_base/$latest/$rel")
  fi
  for p in "${candidates[@]}"; do
    if [[ -f "$p" ]]; then printf '%s\n' "$p"; return 0; fi
  done
  return 1
}

szk_run() {       # szk_run <plugin> <script-relative-path> [args...]
  local plugin="$1" rel="$2"; shift 2
  local path
  if ! path="$(szk_resolve "$plugin" "$rel")"; then
    echo "$plugin: could not find $rel in the repo, marketplace clone, or install cache." >&2
    echo "  Install it with:  claude plugin install $plugin@szk-plugins" >&2
    exit 1
  fi
  exec "${SZK_PYTHON:-python3}" "$path" "$@"
}
