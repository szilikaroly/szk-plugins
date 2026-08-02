#!/usr/bin/env python3
"""Archive the original context window right now, then compress in background.

Called three ways:
  - PreCompact hook   -> tag "precompact"  (safety net: nothing is ever lost
                         to compaction, even if no checkpoint fired)
  - SessionEnd hook   -> tag "end"         (tomorrow's session can resume from
                         the memo for a few hundred tokens)
  - manually / by the /memo-guard:compress command with --now
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

TAGS = {"PreCompact": "precompact", "SessionEnd": "end"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true",
                    help="manual mode: discover the transcript, print paths")
    args = ap.parse_args()

    if args.now:
        tp = mg.find_transcript()
        if not tp:
            print("memo-guard: no session transcript found under "
                  "~/.claude/projects")
            return 1
        sid, cwd, tag = tp.stem, str(Path.cwd()), "manual"
    else:
        data = mg.read_stdin_json()
        tp = data.get("transcript_path")
        if not tp or not Path(tp).exists():
            return 0
        tp = Path(tp)
        sid = data.get("session_id") or tp.stem
        cwd = data.get("cwd") or str(Path.cwd())
        tag = TAGS.get(data.get("hook_event_name", ""), "manual")

    cfg = mg.load_config()
    usage = mg.last_usage(tp)
    arc = mg.archive_transcript(tp, sid, cwd, tag, usage, cfg)
    mg.spawn_background(Path(__file__).parent / "compressor.py",
                        ["--archive", str(arc), "--session", sid,
                         "--cwd", cwd])

    if args.now:
        pct = mg.context_pct(usage, cfg)[0] if usage else 0
        print(f"archived : {arc}")
        print(f"context  : {usage['context_tokens']:,} tok ({pct:.0f}%)"
              if usage else "context  : (no usage data yet)")
        print("memo     : building in background "
              f"(log: {mg.data_dir() / 'logs' / 'compressor.log'})")
        print(f"resume   : {mg.sessions_dir() / sid / 'RESUME.md'} "
              "(auto-injected after /compact, /clear or resume)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
