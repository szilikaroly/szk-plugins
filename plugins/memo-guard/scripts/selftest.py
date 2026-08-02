#!/usr/bin/env python3
"""End-to-end self-test on a synthetic transcript. No Claude Code needed.

Builds a fake session (big tool outputs + real dialogue), drives the hooks the
way Claude Code would, and prints the MEASURED reduction. Run it after any
change to the compressor:

    MEMO_GUARD_HOME=/tmp/mg-test python3 scripts/selftest.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import mg_lib as mg  # noqa: E402


def build_transcript(path: Path, big_files=14, lines_each=900) -> None:
    """A realistic shape: a few huge Read results, some bash noise, dialogue."""
    recs = []
    ctx = 0
    for i in range(big_files):
        tid = f"toolu_{i:03d}"
        recs.append({"type": "assistant", "message": {"content": [
            {"type": "text", "text": f"Reading source file {i}."},
            {"type": "tool_use", "id": tid, "name": "Read",
             "input": {"file_path": f"/repo/src/module_{i}.py"}}],
            "usage": {"input_tokens": ctx, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 50}}})
        body = "\n".join(
            (f"def handler_{i}_{n}(request):" if n % 90 == 0 else
             f"ERROR: retry {n} failed for module {i}" if n % 150 == 0 else
             f"    value_{n} = compute({n}) * factor  # filler line {n}")
            for n in range(lines_each))
        recs.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid,
             "content": [{"type": "text", "text": body}]}]}})
        ctx += len(body) // 4
        recs.append({"type": "user", "message": {"content":
                    f"Now explain what module_{i} does and why retries fail."}})
        recs.append({"type": "assistant", "message": {"content": [
            {"type": "text",
             "text": f"Module {i} handles request routing; retries fail "
                     f"because the backoff resets on each 5xx. Decision: "
                     f"switch module_{i} to exponential backoff."}],
            "usage": {"input_tokens": ctx, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 120}}})
    path.write_text("\n".join(json.dumps(r) for r in recs))


def hook(script: str, payload: dict) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(HERE / script)],
                       input=json.dumps(payload), capture_output=True,
                       text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    home = Path(os.environ.get("MEMO_GUARD_HOME", tempfile.mkdtemp()))
    os.environ["MEMO_GUARD_HOME"] = str(home)
    os.environ.setdefault("MEMO_CTX_WINDOW", "200000")
    # local model isn't present in a test box; force the honest fallback
    os.environ["MEMO_GUARD_USE_LOCAL_MODEL"] = "false"
    print(f"data dir: {home}\n")

    tdir = home / "fake-projects"
    tdir.mkdir(parents=True, exist_ok=True)
    tp = tdir / "11112222-3333-4444-5555-666677778888.jsonl"
    build_transcript(tp)
    raw_kb = tp.stat().st_size // 1024
    print(f"synthetic transcript: {raw_kb} KB "
          f"(~{mg.est_tokens(tp.read_bytes()):,} tok)")

    sid = tp.stem
    payload = {"session_id": sid, "transcript_path": str(tp),
               "cwd": "/repo", "hook_event_name": "PostToolUse"}

    rc, out = hook("ctx_monitor.py", payload)
    print(f"\n1) PostToolUse monitor rc={rc}")
    if out.strip():
        msg = json.loads(out).get("systemMessage", "")
        print("   " + msg[:160])
    assert rc == 0

    # wait for the background compressor
    wd = home / "sessions" / sid
    for _ in range(120):
        st = wd / "STATE.json"
        if st.exists() and json.loads(st.read_text()).get("phase") in (
                "done", "error"):
            break
        time.sleep(0.5)
    state = json.loads((wd / "STATE.json").read_text())
    print(f"\n2) compressor phase={state.get('phase')} "
          f"mode={state.get('mode')}")
    if state.get("phase") != "done":
        print("   ERROR:", state)
        return 1

    rc, out = hook("inject_resume.py",
                   {"session_id": sid, "cwd": "/repo", "source": "compact",
                    "hook_event_name": "SessionStart"})
    print(f"\n3) SessionStart(compact) injection rc={rc}, "
          f"{len(out)} chars (cap 10,000)")
    print("   ---- injected into the fresh context ----")
    for ln in out.splitlines()[:14]:
        print("   " + ln)
    print("   ...")

    row = json.loads((home / "metrics.jsonl").read_text().splitlines()[-1])
    print("\n4) MEASURED")
    print(f"   raw window            ~{row['raw_tokens_est']:,} tok")
    print(f"   distilled working set ~{row['kept_tokens_est']:,} tok "
          f"({row['reduction_kept_pct']}% smaller)")
    print(f"   RESUME injected       ~{row['resume_tokens_est']:,} tok "
          f"({row['reduction_resume_pct']}% smaller)")
    print(f"   sources={row['sources']} turns={row['turns']} "
          f"in {row['duration_s']}s")

    # Best case (resume only) flatters the design. Price a REALISTIC resumed
    # session: the injected resume plus several real lookups.
    probes = ["exponential backoff", "handler_3", "retry 150",
              "module_7", "ERROR"]
    lookup_tok = 0
    for q in probes:
        g = subprocess.run(["grep", "-rn", "-i", q, str(wd / "distilled")],
                           capture_output=True, text=True).stdout
        lookup_tok += mg.est_tokens("\n".join(g.splitlines()[:8]))
    realistic = row["resume_tokens_est"] + lookup_tok
    red = 100 - 100 * realistic / row["raw_tokens_est"]
    print(f"   realistic session     ~{realistic:,} tok "
          f"(resume + {len(probes)} lookups) = {red:.2f}% smaller")

    ok = row["reduction_resume_pct"] >= 95 and red >= 95
    print(f"\n   >=95% target (best case AND realistic): "
          f"{'PASS' if ok else 'FAIL'}")

    # the compression must not lose the decisions
    resume = (wd / "RESUME.md").read_text()
    hit = subprocess.run(
        ["grep", "-ril", "exponential backoff", str(wd / "sources")],
        capture_output=True, text=True).stdout.strip()
    print(f"   decision recoverable from compressed sources: "
          f"{'yes' if hit else 'NO'}")
    print(f"   archive path in RESUME: "
          f"{'yes' if '.jsonl.gz' in resume else 'NO'}")
    return 0 if ok and hit else 1


if __name__ == "__main__":
    sys.exit(main())
