---
description: List archived context windows / expand a detail from a memo without re-reading originals
argument-hint: [search term]
allowed-tools: Bash, Read
---
If "$ARGUMENTS" is empty: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status.py"` with Bash and show the user the archives and resumes sections.

If "$ARGUMENTS" contains a search term: find the answer cheap-first, stopping at the first level that answers it —
1. If a `.memo/index.db` exists for the newest session under the memo-guard data dir, query it:
   `python3 ~/.claude/skills/memo-index/scripts/memo_query.py --memo-dir <session>/.memo --root <session> '$ARGUMENTS'`
2. Otherwise grep the distilled sources: `grep -rn -i '$ARGUMENTS' <session>/distilled/`
3. Only for exact ground truth: `gunzip -c '<newest archive>.jsonl.gz' | grep -n -i '$ARGUMENTS' | head -40`

Never load a whole archive or whole original file into context; quote only the matching lines.
