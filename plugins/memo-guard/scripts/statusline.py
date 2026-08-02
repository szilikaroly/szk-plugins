#!/usr/bin/env python3
"""Optional statusline: shows the live context counter in Claude Code's footer.

Enable in ~/.claude/settings.json (see README):
  "statusLine": {"type": "command",
                 "command": "python3 /path/to/memo-guard/scripts/statusline.py"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    tp = data.get("transcript_path")
    tp = Path(tp) if tp and Path(tp).exists() else mg.find_transcript(
        (data.get("workspace") or {}).get("current_dir"))
    cfg = mg.load_config()
    usage = mg.last_usage(tp) if tp else None
    model = ((data.get("model") or {}).get("display_name")
             or (data.get("model") or {}).get("id") or "")
    if not usage:
        print(f"ctx --% | {model}".strip(" |"))
        return 0
    pct, window, _wsrc = mg.context_pct(usage, cfg)
    mark = "!" if pct >= max(cfg["checkpoints"] or [80]) else (
        "*" if pct >= min(cfg["checkpoints"] or [70]) else "")
    print(f"ctx {pct:.0f}%{mark} ({usage['context_tokens'] // 1000}k/"
          f"{window // 1000}k) | {model}".strip(" |"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
