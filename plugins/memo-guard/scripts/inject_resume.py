#!/usr/bin/env python3
"""SessionStart hook — put the compressed session knowledge back into context.

Claude Code adds SessionStart stdout to the model's context, so this is the
one legitimate place to restore what compaction (or /clear) threw away.

  source = compact | clear | resume  -> inject the full RESUME.md
  source = startup | fork            -> inject a 3-line pointer only, and only
                                        when a fresh RESUME (<48h) exists for
                                        THIS project. A pointer costs ~80 tok;
                                        the model Reads the file only if the
                                        user actually resumes that work.

Hook stdout is capped at 10,000 chars by Claude Code; RESUME.md is built to
fit well under that.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402


def newest_resume_for(cwd: str, sid: str, max_age_h: float):
    """Prefer this session's RESUME; else the freshest one from this project."""
    exact = mg.sessions_dir() / sid / "RESUME.md"
    if exact.exists():
        return exact
    best, best_m = None, 0.0
    for st in mg.sessions_dir().glob("*/STATE.json"):
        try:
            d = json.loads(st.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("phase") != "done":
            continue
        if cwd and d.get("cwd") and d["cwd"] != cwd:
            continue
        r = st.parent / "RESUME.md"
        if r.exists() and r.stat().st_mtime > best_m:
            best, best_m = r, r.stat().st_mtime
    if best and (time.time() - best_m) <= max_age_h * 3600:
        return best
    return None


def main() -> int:
    data = mg.read_stdin_json()
    source = data.get("source", "")
    sid = data.get("session_id") or ""
    cwd = data.get("cwd") or ""
    cfg = mg.load_config()

    # Core memory goes in first and unconditionally. It is not a summary of past
    # work, so it must not depend on past work existing — a preference or a
    # learned workflow applies to a brand new session too.
    if cfg.get("core_memory", True):
        try:
            import blocks
            core = blocks.render(blocks.connect(), cwd,
                                 int(cfg.get("core_memory_max_chars", 2000)))
            if core.strip():
                print("=== memo-guard: core memory (edit with /memo-guard:remember) ===")
                print(core)
                print("=== end core memory ===")
        except Exception:
            pass

    resume = newest_resume_for(cwd, sid, cfg["startup_max_age_h"])
    if not resume:
        return 0

    if source in ("compact", "clear", "resume"):
        body = resume.read_text(encoding="utf-8")[:9500]
        print("=== memo-guard: compressed context restored ===")
        print(body)
        print("=== end memo-guard resume ===")
    elif source in ("startup", "fork") and cfg.get("inject_on_startup", True):
        try:
            st = json.loads((resume.parent / "STATE.json").read_text(encoding="utf-8"))
        except Exception:
            st = {}
        age_h = (time.time() - resume.stat().st_mtime) / 3600
        print(f"[memo-guard] A compressed memo of a previous session in this "
              f"project exists ({age_h:.0f}h old, "
              f"~{st.get('resume_tokens_est', '?')} tok vs "
              f"~{st.get('raw_tokens_est', '?')} tok original): {resume}")
        print("Read it ONLY if the user resumes that work; otherwise ignore "
              "it. Do not re-read the archived originals.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
