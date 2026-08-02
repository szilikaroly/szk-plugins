#!/usr/bin/env python3
"""memo-guard monitor — runs on PostToolUse and UserPromptSubmit.

Fast path first: below the lowest checkpoint it does one tail-read of the
transcript and exits silently, so it adds no perceptible latency to tool calls.

At each checkpoint (default 70% and 80%):
  1. archive the ORIGINAL context window losslessly (gzipped transcript copy)
  2. spawn compressor.py in the background (never blocks the session)
  3. tell the user via systemMessage

At advise_at (default 85%), on UserPromptSubmit only, inject a small
additionalContext so Claude itself recommends /compact at a natural break —
a hook cannot run /compact; that is the user's action.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402


def main() -> int:
    data = mg.read_stdin_json()
    tp = data.get("transcript_path")
    if not tp or not Path(tp).exists():
        return 0
    tp = Path(tp)
    sid = data.get("session_id") or "unknown"
    cwd = data.get("cwd") or str(Path.cwd())
    event = data.get("hook_event_name", "")

    cfg = mg.load_config()
    usage = mg.last_usage(tp)
    if not usage:
        return 0
    pct, window, _wsrc = mg.context_pct(usage, cfg)

    st = mg.load_state(sid)
    fired = set(st.get("fired", []))

    # After /compact or /clear the measured % collapses; reset the checkpoints
    # so the next climb archives again.
    low = min(cfg["checkpoints"]) if cfg["checkpoints"] else 70
    if fired and pct < low - 15:
        fired = set()
        st["advised"] = False
        st["suggested"] = False
        st["floor_fired"] = False

    out: dict = {}

    due = [c for c in cfg["checkpoints"] if pct >= c and c not in fired]

    # Adaptive (A-MEM style): the model decides when a memory write is worth
    # making, because it knows whether the last 20 minutes were one coherent
    # piece of work or three false starts — a percentage cannot know that.
    # hard_floor stays unconditional: judgement is allowed to be wrong, but
    # never allowed to lose the session.
    adaptive = bool(cfg.get("adaptive"))
    floor = float(cfg.get("hard_floor", 90))
    # Tracked outside `fired` on purpose: that set is checkpoint percentages,
    # and mixing a sentinel string into it breaks sorted() when state is saved.
    forced = pct >= floor and not st.get("floor_fired")

    if due and adaptive and not forced:
        due = []
        if event == "UserPromptSubmit" and not st.get("suggested"):
            st["suggested"] = True
            out.setdefault("hookSpecificOutput", {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    f"[memo-guard] Context is at {pct:.0f}%. Adaptive mode is on, "
                    f"so nothing has been archived yet — you decide. If the work "
                    f"since the last archive is worth preserving as a memory, run "
                    f"/memo-guard:compress at the next natural break. If it was "
                    f"exploration you would not want resurrected, skip it and say "
                    f"so briefly. A hard archive happens automatically at {floor:.0f}%."
                ),
            })

    if due or forced:
        cp = max(due) if due else int(floor)
        arc = mg.archive_transcript(tp, sid, cwd, f"cp{cp}", usage, cfg)
        mg.spawn_background(Path(__file__).parent / "compressor.py",
                            ["--archive", str(arc), "--session", sid,
                             "--cwd", cwd])
        fired |= set(due)
        if forced:
            st["floor_fired"] = True
        out["systemMessage"] = (
            f"memo-guard ▸ context {pct:.0f}% "
            f"({usage['context_tokens']:,}/{window:,} tok). "
            f"Original context archived ({arc.name}); compressed memo is "
            f"building in the background. After /compact or /clear the resume "
            f"index is injected automatically. Details: /memo-guard:status"
        )

    if (event == "UserPromptSubmit" and pct >= cfg["advise_at"]
            and not st.get("advised")):
        st["advised"] = True
        out.setdefault("hookSpecificOutput", {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f"[memo-guard] The context window is at {pct:.0f}%. A "
                f"compressed memo of this session is already prepared on disk "
                f"and will be auto-injected after compaction. When the current "
                f"step reaches a natural break, recommend that the user run "
                f"/compact. From now on avoid re-reading large files or "
                f"re-fetching long outputs; work from what is already in "
                f"context."
            ),
        })

    st.update({"fired": sorted(fired), "pct": round(pct, 1),
               "tokens": usage["context_tokens"], "cwd": cwd})
    mg.save_state(sid, st)

    if out:
        mg.emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
