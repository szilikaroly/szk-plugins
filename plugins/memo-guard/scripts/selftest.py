#!/usr/bin/env python3
"""End-to-end self-test on a synthetic transcript. No Claude Code needed.

Builds a fake session (big tool outputs + real dialogue), drives the hooks the
way Claude Code would, and prints the MEASURED reduction. Run it after any
change to the compressor:

    python3 scripts/selftest.py                       # fresh sandbox each run
    MEMO_GUARD_SELFTEST_HOME=/tmp/mg-test python3 scripts/selftest.py
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
    # NEVER the production data directory.
    #
    # This used to read MEMO_GUARD_HOME — the variable the plugin's own
    # installer PINS to ~/.claude/memo-guard. So in any shell that had the
    # plugin installed, the "sandbox" was the live store, and the test's
    # fixtures were written into the user's real long-term memory: an invented
    # PROSPERO registration number, an invented rejection reason, and a REFUTED
    # claim about a cohort's sample size. Recall then served them to real
    # sessions as facts the user had established.
    #
    # A self test must not be able to reach production by inheriting an
    # environment. It gets its own directory, and an override that cannot be set
    # by accident.
    home = Path(os.environ.get("MEMO_GUARD_SELFTEST_HOME")
                or tempfile.mkdtemp(prefix="mg-selftest-"))
    os.environ["MEMO_GUARD_HOME"] = str(home)
    mg.assert_not_production("the self test")
    os.environ.setdefault("MEMO_CTX_WINDOW", "200000")
    # local model isn't present in a test box; force the honest fallback
    os.environ["MEMO_GUARD_USE_LOCAL_MODEL"] = "false"
    print(f"data dir: {home}  (sandbox — never the production store)\n")

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

    # THIS run's compression row, selected by session id and event type.
    # Reading the last line of a shared, multi-event, append-only file meant the
    # numbers printed here belonged to whatever session wrote last — a real
    # 8.1-million-token window was once reported as this synthetic test's
    # result, complete with a PASS. Position is not identity.
    rows = mg.read_metrics(event=mg.COMPRESS, session=sid,
                           path=home / "metrics.jsonl")
    if not rows:
        print("\n4) MEASURED — FAIL: the compressor wrote no metrics row for "
              f"session {sid}. Nothing was measured; the numbers below would "
              "have been someone else's.")
        return 1
    row = rows[-1]
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

    ap_ok = check_autopilot(home)
    cv_ok = check_calibration_converges()
    sb_ok = check_stub_visible(home)
    rc_ok = check_recall(home)
    ev_ok = check_recall_quality()
    mr_ok = check_map_reduce(home)
    dr_ok = check_doctor(home)
    dg_ok = check_degradation(home)
    bw_ok = check_busy_vs_wedged()
    return 0 if (ok and hit and ap_ok and cv_ok and sb_ok and rc_ok and ev_ok
                 and mr_ok and dr_ok and dg_ok and bw_ok) else 1


def check_doctor(home: Path) -> bool:
    """The two destructive operations, on a sandbox that looks like the real one.

    `--fix` edits the user's settings.json and `--clean-handoffs` deletes files.
    Both are narrow by design, and "narrow by design" is worth exactly as much
    as a test that the blast radius really is what the design says.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    cfgdir = home / "doctor-claude"
    cfgdir.mkdir(parents=True, exist_ok=True)
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
    import autopilot, doctor
    importlib.reload(autopilot)
    importlib.reload(doctor)

    (cfgdir / "settings.json").write_text(json.dumps({
        "env": {"KEEP": "1"},
        "theme": "dark",
        "hooks": {
            "UserPromptSubmit": [{"hooks": [
                {"type": "command",
                 "command": "bash $HOME/.claude/skills/memo-index/scripts/hook_gate.sh"}]}],
            "PostToolUse": [{"matcher": "*", "hooks": [
                {"type": "command",
                 "command": "python3 $HOME/.claude/skills/memo-index/scripts/ctx_watch.py --hook"},
                {"type": "command", "command": "echo someone-elses-hook"}]}],
        },
    }, indent=2))

    doctor.apply_fix()
    got = json.loads((cfgdir / "settings.json").read_text())
    post = got.get("hooks", {}).get("PostToolUse", [])
    remaining = [h["command"] for g in post for h in g["hooks"]]

    # Running it again must be a no-op, not a second round of edits.
    before = (cfgdir / "settings.json").read_text()
    doctor.apply_fix()
    idempotent = (cfgdir / "settings.json").read_text() == before

    # Handoff litter: one unfilled template, one someone actually wrote in.
    root = home / "litter"
    (root / "a" / ".memo").mkdir(parents=True, exist_ok=True)
    (root / "b" / ".memo").mkdir(parents=True, exist_ok=True)
    (root / "a" / ".memo" / "HANDOFF.md").write_text(
        "# Handoff\n<!-- Fill this in before /clear: the question -->\n")
    (root / "b" / ".memo" / "HANDOFF.md").write_text(
        "# Handoff\nWe decided to switch module_13 to exponential backoff.\n")
    doctor.clean_handoffs(root)

    print("\n11) DOCTOR")
    checks = {
        "ctx_watch hook removed":
            not any("ctx_watch" in c for c in remaining),
        "an unrelated hook in the same group survives":
            any("someone-elses-hook" in c for c in remaining),
        "MEMO_CTX_THRESHOLD raised above 100":
            float(got["env"].get("MEMO_CTX_THRESHOLD", 0)) > 100,
        "unrelated settings untouched":
            got.get("theme") == "dark" and got["env"].get("KEEP") == "1",
        "running --fix twice changes nothing": idempotent,
        "unfilled handoff deleted":
            not (root / "a" / ".memo" / "HANDOFF.md").exists(),
        "a handoff someone wrote in is kept":
            (root / "b" / ".memo" / "HANDOFF.md").exists(),
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


STUB_MEMO_GEN = """#!/usr/bin/env python3
import argparse, os, pathlib, sys, time
a = argparse.ArgumentParser(); a.add_argument("--root"); a.add_argument("--include",
    action="append"); a.add_argument("--memo-dir"); a.add_argument("--profile")
n = a.parse_args()
name = n.include[0].split("/")[-1]
if name in os.environ.get("STUB_FAIL", "").split(","):
    sys.stderr.write("stub: refusing " + name); sys.exit(1)
if name in os.environ.get("STUB_SLOW", "").split(","):
    time.sleep(30)
d = pathlib.Path(n.memo_dir); d.mkdir(parents=True, exist_ok=True)
(d / (name + ".memo.md")).write_text("stub memo for " + name)
pathlib.Path(os.environ["STUB_ORDER"]).open("a").write(name + "\\n")
"""


def check_map_reduce(home: Path) -> bool:
    """Does the model path survive one bad source?

    The old shape ran `memo_gen` once over every source with a single timeout,
    read the kill as total failure, and fell back to deterministic — discarding
    memos it had already written. This checks the replacement without needing a
    model: a stub generator that fails on demand, sleeps on demand, and records
    the order it was called in. What is being tested is the control flow, which
    is the part that was wrong.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import compressor
    importlib.reload(compressor)

    wd = home / "mapreduce"
    (wd / "sources").mkdir(parents=True, exist_ok=True)
    # Deliberately out of size order, so "smallest first" is visible and
    # conversation.md jumping the queue is not an accident of the filesystem.
    for name, size in [("conversation.md", 5000), ("aaa_big.md", 9000),
                       ("bbb_small.md", 100), ("ccc_mid.md", 2000),
                       ("ddd_tiny.md", 50)]:
        (wd / "sources" / name).write_text("x" * size)
    skill = home / "stubskill"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "memo_gen.py").write_text(STUB_MEMO_GEN)

    order_file = home / "stub_order.txt"

    def run(fail="", slow="", total=900.0, step=240.0):
        order_file.write_text("")
        for f in (wd / ".memo").glob("*"):
            f.unlink()
        os.environ.update({"STUB_FAIL": fail, "STUB_SLOW": slow,
                           "STUB_ORDER": str(order_file)})
        done, failed = compressor.map_sources(wd, skill, step, total,
                                              lambda m: None)
        seen = order_file.read_text().split()
        return done, failed, seen

    done, failed, seen = run()
    ordering = seen[:1] == ["conversation.md"] and seen[1:] == [
        "ddd_tiny.md", "bbb_small.md", "ccc_mid.md", "aaa_big.md"]

    d2, f2, s2 = run(fail="ccc_mid.md")
    isolated = "ccc_mid.md" in f2 and len(d2) == 4 and "aaa_big.md" in d2

    d3, f3, _ = run(slow="bbb_small.md", step=2.0)
    slow_ok = "bbb_small.md" in f3 and len(d3) == 4

    d4, f4, _ = run(total=0.0)
    deadline_ok = d4 == [] and len(f4) == 5

    print("\n10) MODEL PATH ON A BIG TRANSCRIPT (stub generator)")
    checks = {
        "conversation first, then smallest-first": ordering,
        "a failing source skips one file, not the run": isolated,
        "a source that times out is skipped, run continues": slow_ok,
        "the total deadline stops it and names what was dropped": deadline_ok,
        "every source is accounted for (done + failed)":
            all(len(d) + len(f) == 5 for d, f in
                [(done, failed), (d2, f2), (d3, f3), (d4, f4)]),
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_recall_quality() -> bool:
    """Guard the retrieval numbers, not just the plumbing.

    Section 8 proves the hook fires and stays quiet in the right places. It says
    nothing about whether what comes back is any good — and every knob in the
    retriever (the relevance floor, the coverage damping, the score blend) is
    one edit away from quietly trading precision for recall. The floors below
    are the measured values with a margin, so a real regression trips them and
    normal drift does not.

    Run as a subprocess on purpose: the harness rebuilds MEMO_GUARD_HOME and
    drops modules from sys.modules, which would pull the store out from under
    the rest of this file.
    """
    r = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "recall_eval.py"),
         "--no-embed", "--json"], capture_output=True, text=True, timeout=120)
    print("\n9) RECALL QUALITY (bundled corpus, lexical only)")
    try:
        m = json.loads(r.stdout)["modes"]["lexical only"]
    except Exception:
        print(f"   FAIL harness did not produce JSON: "
              f"{(r.stderr or r.stdout)[:200]}")
        return False
    checks = {
        f"recall >= 65%  (got {m['recall']:.0%})": m["recall"] >= 0.65,
        f"lexical recall = 100%  (got {m['recall_lexical']:.0%})":
            m["recall_lexical"] >= 0.99,
        f"precision >= 85%  (got {m['precision']:.0%})": m["precision"] >= 0.85,
        f"false injection <= 5%  (got {m['false_injection_rate']:.0%})":
            m["false_injection_rate"] <= 0.05,
        f"zero cross-project leaks  (got {m['gate_breaches']})":
            m["gate_breaches"] == 0,
        f"<= 30 tok/prompt  (got {m['mean_tokens_per_prompt']:.0f})":
            m["mean_tokens_per_prompt"] <= 30,
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    # Not a pass/fail line: paraphrase recall is the honest weak spot of the
    # lexical path and the number the semantic path has to justify itself
    # against. Printing it keeps that visible instead of comfortable.
    print(f"   ..  paraphrase recall {m['recall_paraphrase']:.0%} "
          f"(lexical path only — this is what embeddings are for)")
    return all(checks.values())


def check_calibration_converges() -> bool:
    """Does the correction loop actually land on the target?

    This runs the loop against a transcription of Claude Code's own arithmetic
    (2.1.237: `min(floor(effWin * pct/100), effWin - 13000)`, with
    `effWin = window - min(reserve, 20000)`). It therefore proves the loop
    converges *given that formula* — it cannot prove the formula is still the
    product's. That is the honest scope: it catches a regression in the
    correction maths, not a change upstream.
    """
    import importlib, math
    sys.path.insert(0, str(Path(__file__).parent))
    import autopilot
    importlib.reload(autopilot)

    def fires_at(window, override, reserve=20000):
        eff = window - min(reserve, 20000)
        return min(math.floor(eff * override / 100.0), eff - 13000)

    cases = [("1M / autoCompactWindow 800k", 1_000_000, 800_000),
             ("1M / no override window", 1_000_000, 1_000_000),
             ("200k window", 200_000, 200_000)]
    target, results = 70.0, {}
    for label, real, cc in cases:
        autopilot.save_state({})
        autopilot.cmd_enable(target)
        measured, rounds = None, 0
        for rounds in range(6):
            ov = float(autopilot.load_state()["override"])
            measured = 100.0 * fires_at(cc, ov) / real
            if abs(measured - target) <= autopilot.TOLERANCE_PCT:
                break
            autopilot.record_firing(measured, mg.load_config())
        results[f"{label}: {measured:.1f}% after {rounds} correction(s)"] = (
            abs(measured - target) <= autopilot.TOLERANCE_PCT and rounds <= 2)
    print("\n6) CALIBRATION")
    for name, val in results.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(results.values())


def check_stub_visible(home: Path) -> bool:
    """A session that ended at "stub" must still be findable — and must never
    outrank a real memo."""
    sd = home / "sessions"

    def mk(name, phase, cwd, age_h, body):
        d = sd / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "RESUME.md").write_text(body)
        (d / "STATE.json").write_text(json.dumps(
            {"phase": phase, "cwd": cwd, "resume_tokens_est": 400,
             "raw_tokens_est": 80000}))
        t = time.time() - age_h * 3600
        os.utime(d / "RESUME.md", (t, t))

    mk("zz-stub", "stub", "/stubproj", 1, "STUBBODY pointing at the archive\n" * 8)
    _, out1 = hook("inject_resume.py", {"session_id": "n1", "cwd": "/stubproj",
                                        "source": "startup",
                                        "hook_event_name": "SessionStart"})
    mk("zz-done", "done", "/stubproj", 5, "DONEBODY the real memo\n" * 8)
    _, out2 = hook("inject_resume.py", {"session_id": "n2", "cwd": "/stubproj",
                                        "source": "startup",
                                        "hook_event_name": "SessionStart"})
    _, out3 = hook("inject_resume.py", {"session_id": "n3", "cwd": "/elsewhere",
                                        "source": "startup",
                                        "hook_event_name": "SessionStart"})
    checks = {
        "a stub-only project is still pointed at": "zz-stub" in out1,
        "a real memo outranks a newer stub": "zz-done" in out2,
        "no pointer leaks to another project": "zz-" not in out3,
    }
    print("\n7) STUB FALLBACK")
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_recall_stays_offline() -> bool:
    """`allow_semantic=False` has to mean no model call, all the way down.

    A stopwatch cannot assert this. The model server on a developer's machine
    answers, so a stray embed costs milliseconds here and seconds on a machine
    where the embed model is missing or wedged — the timing check passes and the
    user waits 2.3 s per keystroke. Count the calls instead: none is none on
    every machine.

    Both short-circuits that hid the original regression are removed first — a
    verdict vector is planted, so claims.py cannot decline before embedding.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import claims, embed, memory
    importlib.reload(memory)

    db = memory.connect()
    memory.promote(db, "The PMOS review protocol was registered before "
                       "screening began", "/offline-probe", kind="reference")
    cdb = claims.connect()
    claims.record(cdb, "The PMOS cohort enrolled 412 participants", "REFUTED",
                  note="recount gave 389")
    fp = cdb.execute("SELECT fp FROM verdict LIMIT 1").fetchone()
    if not fp:
        return False
    cdb.execute("INSERT OR REPLACE INTO verdict_vec (fp,model,dim,data)"
                " VALUES (?,?,?,?)",
                (fp[0], "stub-embed", 3, embed.pack([1.0, 0.0, 0.0])))
    cdb.commit()

    calls: list[str] = []
    real = embed.embed

    def counted(*a, **k):
        calls.append(str(a[:1]))
        return None

    embed.embed = counted
    try:
        memory.recall(db, "When was the PMOS review protocol registered?",
                      "/offline-probe", goal=None, allow_semantic=False)
    finally:
        embed.embed = real
    if calls:
        print(f"   (recall made {len(calls)} embed call(s) with the semantic "
              "path switched off)")
    return not calls


def check_recall(home: Path) -> bool:
    """The recall hook is judged on what it stays silent about.

    Injecting a relevant fact is the easy half. The half that decides whether
    this is worth having on every prompt is the three cases where it must
    produce nothing at all — and the latency, because this runs in front of a
    keystroke.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import embed
    # The model server may be slow or wedged on the machine running this; the
    # test is about the hook's behaviour, not the server's.
    embed.set_timeout(0.5)
    import memory, claims
    importlib.reload(memory)

    db = memory.connect()
    memory.promote(db, "The PROSPERO registration number for the PMOS review "
                       "is CRD42024518822", "/repo", kind="reference",
                   utility=0.8)
    memory.promote(db, "The rosacea review was rejected for AI-fabricated "
                       "references", "/repo", kind="decision", utility=0.8)
    claims.record(claims.connect(),
                  "The sample size in the PMOS cohort was 412 participants",
                  "REFUTED", note="recount gave 389")

    def run(prompt: str, sid: str) -> tuple[str, float]:
        t = time.time()
        rc, out = hook("recall.py", {"prompt": prompt, "cwd": "/repo",
                                     "session_id": sid,
                                     "hook_event_name": "UserPromptSubmit"})
        return out.strip(), (time.time() - t) * 1000

    # First call pays for the model-server health probe (0.6 s against a wedged
    # server) and caches the verdict for a minute. Timing that one would measure
    # the probe, not the hook; timing only the warm one would hide it. Both.
    _, cold_ms = run("A first prompt that warms the health probe cache only",
                     "rc0")
    hit_out, hit_ms = run("What was the PROSPERO registration number we used "
                          "for the PMOS review?", "rc1")
    again, _ = run("Remind me of the PROSPERO registration number for PMOS",
                   "rc1")
    short, _ = run("ok go", "rc2")
    slash, _ = run("/memo-guard:status plus several more words to pass length",
                   "rc2")
    off, _ = run("Can you refactor the pagination logic in the checkout "
                 "service please?", "rc3")
    warn, _ = run("I think the sample size in the PMOS cohort was 412 "
                  "participants, right?", "rc4")

    # The budget below is a behaviour assertion, not a stopwatch on this box.
    # Measured on this machine, 12 warm calls each, subprocess round trip
    # included (bare `python3 -c pass` is ~27 ms of that):
    #   sandbox fixture, 2 facts        min 42  median 46   max 61 ms
    #   copy of a real store, 46 facts  min 88  median 127  max 135 ms
    # So 400 ms is not a tight budget for the lexical path — it is roughly 3x
    # the real-corpus median, and anything that breaches it has stopped being
    # the lexical path. That is exactly what happened: memory._refuted() called
    # claims.match() without passing `allow_semantic` down, so each candidate
    # fact took an embed round trip after the caller had already decided the
    # model server was unaffordable — 2.3 s per prompt on a store with verdict
    # vectors. The fixture here cannot reproduce that (no embedder, so no
    # verdict vectors, so claims.py short-circuits before embedding), which is
    # why the timing check is backed by the no-network assertion below.
    #
    # Not covered by either: recall_deadline_s is advisory. Nothing interrupts
    # a call that has already started; the deadline only gates whether the
    # semantic path is attempted at all.
    no_net = check_recall_stays_offline()

    print("\n8) RECALL")
    checks = {
        "relevant prompt recalls the fact": "CRD42024518822" in hit_out,
        "same fact not injected twice in a session": again == "",
        "short prompt stays silent": short == "",
        "slash command stays silent": slash == "",
        "unrelated prompt stays silent": off == "",
        "refuted claim is flagged": "REFUTED" in warn,
        "marked as data, not instructions": "not instructions" in hit_out,
        f"warm latency under 400 ms (was {hit_ms:.0f} ms, "
        f"cold {cold_ms:.0f} ms incl. interpreter start)": hit_ms < 400,
        "lexical-only recall makes no model call": no_net,
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_busy_vs_wedged() -> bool:
    """A server serving somebody else must never be diagnosed as broken.

    The two states are identical at the socket: a request goes out, nothing
    comes back. The prescriptions are opposite — wedged wants a restart, busy
    wants patience — so getting this wrong is not a cosmetic error. It happened
    here: a memo-index run held the only slot (`-np 1`) for twenty minutes
    while /api/tags answered in 3 ms, the doctor called it wedged, and the fix
    it printed would have killed the job.
    """
    print("\n[busy is not wedged]")
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import broker
    importlib.reload(broker)
    import doctor
    importlib.reload(doctor)

    checks = {}

    checks["ps TIME mm:ss.ff parses"] = abs(broker._cpu_seconds("12:34.56") - 754.56) < 0.01
    checks["ps TIME hh:mm:ss parses"] = broker._cpu_seconds("1:02:03") == 3723
    checks["ps TIME dd-hh:mm:ss parses"] = broker._cpu_seconds("2-03:04:05") == 183845
    checks["an unparseable TIME field is 0, not a crash"] = broker._cpu_seconds("??") == 0.0

    real_cpu = broker.runner_cpu_ms
    real_sleep = broker.time.sleep
    try:
        broker.time.sleep = lambda _s: None
        ticks = iter([1000.0, 1400.0])
        broker.runner_cpu_ms = lambda: next(ticks)
        ev = broker.busy_evidence(sample_s=1.0)
        checks["a runner burning CPU reads as busy"] = ev["busy"] and ev["cpu_ms"] == 400

        ticks = iter([1000.0, 1000.0])
        broker.runner_cpu_ms = lambda: next(ticks)
        checks["an idle runner does not read as busy"] = not broker.busy_evidence(1.0)["busy"]

        broker.runner_cpu_ms = lambda: None
        ev = broker.busy_evidence(1.0)
        checks["unmeasurable is not silently 'idle'"] = (not ev["known"]) and not ev["busy"]
    finally:
        broker.runner_cpu_ms = real_cpu
        broker.time.sleep = real_sleep

    # The verdicts, with the server stubbed out entirely.
    real = (broker.healthy, broker.port_up, broker.busy_evidence,
            broker.loaded_models, broker.probe_hardware)
    try:
        broker.healthy = lambda *a, **k: False
        broker.loaded_models = lambda: [{"name": "m", "size_mb": 1, "on_gpu": 1.0}]
        broker.probe_hardware = lambda: {}

        broker.port_up = lambda *a, **k: False
        checks["nothing listening reads as DOWN, not wedged"] = (
            broker.diagnose()["verdict"] == "DOWN")

        broker.port_up = lambda *a, **k: True
        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": True,
                                                "cpu_ms": 400, "why": "w"}
        busy = broker.diagnose()
        checks["port up + runner computing reads as BUSY"] = busy["verdict"] == "BUSY"
        checks["the BUSY fix never says restart"] = not any(
            w in busy["fix"].lower() for w in ("restart", "level 3", "kill"))

        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": False,
                                                "cpu_ms": 0, "why": "w"}
        wedged = broker.diagnose()
        checks["port up + nothing computing still reads as WEDGED"] = (
            wedged["verdict"] == "WEDGED")
        checks["the WEDGED fix does say level 3"] = "level 3" in wedged["fix"]
    finally:
        (broker.healthy, broker.port_up, broker.busy_evidence,
         broker.loaded_models, broker.probe_hardware) = real

    # The doctor has to carry the distinction through, not re-derive it.
    real_d = (broker.healthy, broker.diagnose)
    try:
        broker.healthy = lambda *a, **k: False
        broker.diagnose = lambda *a, **k: {
            "verdict": "BUSY", "why": "another client holds the slot",
            "fix": "wait", "loaded": []}
        f = doctor.check_model_server()
        checks["the doctor reports BUSY as info, not a warning"] = (
            len(f) == 1 and f[0].level == "info")
        checks["the doctor's BUSY text never advises a restart"] = not any(
            w in (f[0].detail + f[0].fix).lower()
            for w in ("--recover --level 3", "restarts the model server"))

        broker.diagnose = lambda *a, **k: {
            "verdict": "WEDGED", "why": "no runner is computing",
            "fix": "recover --level 2, then --level 3", "loaded": []}
        f = doctor.check_model_server()
        checks["the doctor still warns, and offers level 3, when truly wedged"] = (
            f[0].level == "warn" and "level 3" in f[0].fix)
    finally:
        broker.healthy, broker.diagnose = real_d

    # Level 3 says "restart". Killing and not starting is not a restart.
    real_r = (broker._run, broker._spawn_server, broker.busy_evidence,
              broker.loaded_models, broker.healthy, broker.diagnose,
              broker.probe_hardware, broker.time.sleep)
    try:
        killed, spawned = [], []
        broker._run = lambda cmd, **k: killed.append(cmd)
        broker._spawn_server = lambda: spawned.append(True)
        broker.loaded_models = lambda: []
        broker.healthy = lambda *a, **k: True
        broker.diagnose = lambda *a, **k: {"verdict": "OK"}
        broker.probe_hardware = lambda: {}
        broker.time.sleep = lambda _s: None

        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": False,
                                                "cpu_ms": 0, "why": "idle"}
        r = broker.recover(3)
        checks["level 3 kills the server"] = bool(killed)
        checks["level 3 also starts one again"] = spawned == [True]
        checks["an idle level 3 does not cry wolf"] = not any(
            "WARNING" in a for a in r["actions"])

        killed, spawned = [], []
        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": True,
                                                "cpu_ms": 400, "why": "w"}
        r = broker.recover(3)
        checks["level 3 says out loud that it aborted a live request"] = any(
            "WARNING" in a for a in r["actions"])
    finally:
        (broker._run, broker._spawn_server, broker.busy_evidence,
         broker.loaded_models, broker.healthy, broker.diagnose,
         broker.probe_hardware, broker.time.sleep) = real_r

    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_degradation(home: Path) -> bool:
    """What memo-guard does when the model server is up but does not answer.

    This is the failure mode that hides: /api/tags replies in a millisecond
    while /api/embed never returns, so every health check that asks "is the
    server there" says yes and every prompt pays the full embed timeout. Both
    findings below were live on the machine this was written on.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import embed, broker, recall as R
    importlib.reload(embed)

    checks = {}

    # 1) A lock whose owner died must not disable the semantic path forever.
    #    lock_status reports `stale`; the caller used to throw the whole dict at
    #    a truthiness test, so a compressor that crashed holding the model lock
    #    switched semantic recall off permanently and said nothing.
    real = broker.lock_status
    try:
        broker.lock_status = lambda name: {"owner": "compressor/dead",
                                           "age_s": 900.0, "stale": True}
        # The assertion has to be that the LOCK stops being the veto, not that
        # the whole gate opens — the health probe may still, correctly, close
        # it. So: with a stale lock present, the probe must be reached at all.
        # (An earlier version of this check was `x is not False or True`, which
        # cannot fail and therefore tested nothing.)
        seen = {}
        R._cached_health(lambda: seen.setdefault("probed", True) or True, ttl=0)
        checks["a stale lock lets the health probe run at all"] = bool(seen)

        broker.lock_status = lambda name: {"owner": "compressor/alive",
                                           "age_s": 3.0, "stale": False}
        checks["a live lock still stands the hook down"] = (
            R.semantic_affordable(99) is False)
    finally:
        broker.lock_status = real

    # 2) A server that times out must be paid for once, not once per call.
    #    Measured before the breaker: one recall cost 2x the embed budget,
    #    because the query embedding and the claim check each waited it out.
    embed._BREAKER.update(until=0.0, reason="")
    try:
        (embed._state_path()).unlink()
    except OSError:
        pass
    calls = {"n": 0}

    def _hang(path, payload, timeout):
        calls["n"] += 1
        raise TimeoutError("wedged")

    real_post = embed._post
    try:
        embed._post = _hang
        embed.set_timeout(0.2)
        embed.embed("first call trips the breaker")
        first = calls["n"]
        embed.embed("second call must not reach the server")
        embed.embed("nor the third")
        checks["a wedged server is contacted once, not once per call"] = (
            first == 1 and calls["n"] == 1)
        st = embed.breaker_state()
        checks["the breaker says why it is open"] = (
            st["open"] and "Timeout" in st["reason"])
    finally:
        embed._post = real_post
        embed._BREAKER.update(until=0.0, reason="")
        try:
            (embed._state_path()).unlink()
        except OSError:
            pass

    # 3) metrics.jsonl is multi-event; readers must select by type, not position.
    mg.append_metrics({"session": "sX", "raw_tokens_est": 10}, event=mg.COMPRESS)
    mg.append_metrics({"session": "sX", "ms": 1.0}, event="recall")
    comp = mg.read_metrics(event=mg.COMPRESS, session="sX")
    checks["a recall row is never read as a compression row"] = (
        len(comp) == 1 and "raw_tokens_est" in comp[-1])

    print("\n12) DEGRADED-MODEL BEHAVIOUR")
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_autopilot(home: Path) -> bool:
    """Autopilot edits the user's own settings.json, so the test that matters is
    not "did it write the key" but "did it leave everything else alone"."""
    import importlib
    cfgdir = home / "fake-claude"
    cfgdir.mkdir(parents=True, exist_ok=True)
    keep = {"env": {"KEEP_ME": "1"}, "hooks": {"X": []}, "theme": "dark"}
    (cfgdir / "settings.json").write_text(json.dumps(keep, indent=2))
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)

    sys.path.insert(0, str(Path(__file__).parent))
    import autopilot
    importlib.reload(autopilot)

    print("\n5) AUTOPILOT")
    autopilot.cmd_enable(70.0)
    got = json.loads((cfgdir / "settings.json").read_text())
    wrote = got.get("env", {}).get(autopilot.ENV_KEY) == "70"
    kept = (got.get("theme") == "dark" and got.get("hooks") == {"X": []}
            and got.get("env", {}).get("KEEP_ME") == "1")

    # A compaction that fired at 88.6% of a 70% target must pull the override
    # DOWN, not up. Getting this sign wrong would drive the threshold to the
    # ceiling and compaction would stop happening at all.
    autopilot.record_firing(88.6, mg.load_config())
    after = float(json.loads((cfgdir / "settings.json").read_text())
                  ["env"][autopilot.ENV_KEY])
    direction = after < 70

    # Inside tolerance nothing should move.
    autopilot.record_firing(70.0 + autopilot.TOLERANCE_PCT / 2, mg.load_config())
    stable = float(json.loads((cfgdir / "settings.json").read_text())
                   ["env"][autopilot.ENV_KEY]) == after

    autopilot.cmd_disable()
    final = json.loads((cfgdir / "settings.json").read_text())
    removed = autopilot.ENV_KEY not in final.get("env", {})
    restored = (final.get("theme") == "dark"
                and final.get("env", {}).get("KEEP_ME") == "1")

    checks = {"override written": wrote, "other settings kept": kept,
              "over-target correction goes down": direction,
              "in-tolerance firing changes nothing": stable,
              "disable removes only its own key": removed and restored}
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


if __name__ == "__main__":
    sys.exit(main())
