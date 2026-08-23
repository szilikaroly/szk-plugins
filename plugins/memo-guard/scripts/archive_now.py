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
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

TAGS = {"PreCompact": "precompact", "SessionEnd": "end"}

# PreCompact's hook timeout is 60 s. The fast pass gets most of it but not all:
# a hook that is killed mid-write leaves a half-written RESUME, which is worse
# than one that ran out of time and said so.
FAST_BUDGET_S = 40


def fast_pass(script_dir: Path, arc: Path, sid: str, cwd: str) -> bool:
    """Build a deterministic memo synchronously, before the context vanishes.

    The background compressor is right for a checkpoint: nothing is about to be
    lost, so it can take four minutes and use the local model. PreCompact is the
    opposite situation. The summary replaces the window seconds from now, and
    SessionStart fires immediately after — so a memo that is still building is a
    memo that is not there when it is read. A lossier one, finished, beats it.
    """
    try:
        r = subprocess.run(
            [sys.executable, str(script_dir / "compressor.py"), "--fast",
             "--archive", str(arc), "--session", sid, "--cwd", cwd],
            timeout=FAST_BUDGET_S, capture_output=True)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def record_calibration(pct: float) -> None:
    """Tell autopilot where compaction actually landed. Never let it matter."""
    try:
        import autopilot
        autopilot.record_firing(pct, mg.load_config())
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true",
                    help="manual mode: discover the transcript, print paths")
    args = ap.parse_args()

    data: dict = {}
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

    here = Path(__file__).parent
    if tag == "precompact":
        # Only an *automatic* compaction says anything about where the threshold
        # sits. A manual /compact is the user picking a moment, so calibrating
        # on it would teach autopilot the user's habits instead of the product's
        # arithmetic.
        if data.get("trigger") == "auto" and usage:
            record_calibration(mg.context_pct(usage, cfg)[0])
        # Stub first, then try to do better. The fast pass is bounded by a
        # timeout, and a timeout is the one case where we would otherwise hand
        # the next context nothing at all — precisely on the largest sessions,
        # where losing the pointer to the archive costs the most.
        try:
            import compressor
            compressor.write_stub(mg.sessions_dir() / sid, sid, arc, cwd)
        except Exception:
            pass
        fast_pass(here, arc, sid, cwd)

    mg.spawn_background(here / "compressor.py",
                        ["--archive", str(arc), "--session", sid,
                         "--cwd", cwd])

    # Session end is the only moment the machine is reliably idle and the store
    # is reliably complete, so it is where maintenance belongs. It rate-limits
    # itself to once a day and reports rather than deletes — a scheduled job
    # that removes things is the one component nobody is watching.
    if tag == "end":
        mg.spawn_background(here / "doctor.py", ["--maintain-if-due"])

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
