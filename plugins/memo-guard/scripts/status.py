#!/usr/bin/env python3
"""memo-guard status: live context %, archives, memo state, measured savings."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402


def metrics_summary() -> dict:
    # metrics.jsonl holds compression rows AND recall rows. Counting them all as
    # "runs" inflated the number, and `rows[-1]` showed a recall event as the
    # last compression — the same positional read that made the self test print
    # another session's figures as its own.
    rows = mg.read_metrics(event=mg.COMPRESS)
    recalls = mg.read_metrics(event="recall")
    if not rows:
        return {"runs": 0, "recall_events": len(recalls)}
    res = [r["reduction_resume_pct"] for r in rows
           if "reduction_resume_pct" in r]
    kept = [r["reduction_kept_pct"] for r in rows if "reduction_kept_pct" in r]
    return {
        "runs": len(rows),
        "avg_reduction_resume_pct": round(sum(res) / len(res), 2) if res else None,
        "min_reduction_resume_pct": round(min(res), 2) if res else None,
        "avg_reduction_kept_pct": round(sum(kept) / len(kept), 2) if kept else None,
        "modes": {m: sum(1 for r in rows if r.get("mode") == m)
                  for m in {r.get("mode") for r in rows}},
        "last": rows[-1],
        "recall_events": len(recalls),
        "recall_injected": sum(1 for r in recalls if r.get("injected")),
        "recall_p50_ms": (sorted(r["ms"] for r in recalls if "ms" in r)
                          [len(recalls) // 2] if recalls else None),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cfg = mg.load_config()
    tp = mg.find_transcript()
    usage = mg.last_usage(tp) if tp else None
    pct, window, wsrc = mg.context_pct(usage, cfg)
    if not usage:
        pct = None

    slug = mg.project_slug(str(Path.cwd()))
    arc_dir = mg.data_dir() / "archive" / slug
    archives = sorted(arc_dir.glob("*.jsonl.gz")) if arc_dir.exists() else []
    resumes = sorted(mg.sessions_dir().glob("*/RESUME.md"),
                     key=lambda p: -p.stat().st_mtime)
    ms = metrics_summary()

    if args.json:
        print(json.dumps({
            "context_pct": pct, "usage": usage, "window": window,
            "window_source": wsrc,
            "checkpoints": cfg["checkpoints"],
            "archives": [str(a) for a in archives[-5:]],
            "resumes": [str(r) for r in resumes[:5]],
            "metrics": ms, "data_dir": str(mg.data_dir()),
        }, indent=2))
        return 0

    print("memo-guard status")
    print("-----------------")
    if usage:
        bar = "#" * round(30 * min(1.0, pct / 100))
        print(f"context   : {usage['context_tokens']:,} / {window:,} "
              f"tok = {pct:.1f}%   [{bar:<30}]")
        print(f"window    : {wsrc}")
    else:
        print("context   : (no transcript with usage found from this cwd)")
    try:
        import broker
        hw = broker.probe_hardware()
        st = broker.lock_status()
        print(f"hardware  : {hw['vendor']} {hw.get('device','')} — {hw['backend']}, "
              f"{hw['vram_mb']:,} MB usable, {broker.capacity(hw)} model slot(s)")
        slot = "free" if not st else (
            f"held {st['age_s']:.0f}s by {st.get('owner', '?')}"
            + ("  [STALE]" if st["stale"] else ""))
        srv = "responding" if broker.healthy() else "NOT RESPONDING"
        print(f"model svr : {srv}   slot: {slot}")
        for m in broker.loaded_models():
            if m["on_gpu"] < 0.95:
                print(f"  warning : {m['name']} is only {m['on_gpu']:.0%} on GPU "
                      f"— roughly 20x slower than it looks")
    except Exception:
        pass
    print(f"checkpoints: archive+compress at {cfg['checkpoints']}% ; "
          f"advise /compact at {cfg['advise_at']}%")
    print(f"data dir  : {mg.data_dir()}")

    # Autopilot is the one setting that lives outside this plugin's data dir —
    # it edits settings.json — so status has to read the real thing rather than
    # report what it once wrote.
    try:
        import autopilot
        ast_ = autopilot.load_state()
        if ast_.get("enabled"):
            written = (autopilot.read_settings().get("env") or {}).get(
                autopilot.ENV_KEY)
            print(f"autopilot : ON, compaction targeted at "
                  f"{float(ast_.get('target', 70)):g}% "
                  f"(override {written or '(missing!)'}, "
                  f"{'calibrated' if ast_.get('calibrated') else 'still learning'})")
            for b in autopilot.blockers():
                print(f"  ! {b}")
        else:
            print("autopilot : off  (/memo-guard:autopilot to let compaction "
                  "fire on its own)")
    except Exception:
        pass

    print(f"\narchives ({slug}): {len(archives)} total")
    for a in archives[-5:]:
        print(f"  {a.name}  {a.stat().st_size // 1024:>6} KB")

    print(f"\nresumes ready: {len(resumes)}")
    for r in resumes[:5]:
        try:
            st = json.loads((r.parent / "STATE.json").read_text())
            print(f"  {r.parent.name[:8]}  mode={st.get('mode', '?'):13} "
                  f"~{st.get('resume_tokens_est', '?')} tok "
                  f"(raw ~{st.get('raw_tokens_est', '?')})")
        except Exception:
            print(f"  {r.parent.name[:8]}")

    print("\nmeasured savings (metrics.jsonl)")
    if ms["runs"]:
        print(f"  runs                       : {ms['runs']}")
        print(f"  avg reduction, RESUME vs raw window : "
              f"{ms['avg_reduction_resume_pct']}%   "
              f"(target >= 95%; min {ms['min_reduction_resume_pct']}%)")
        print(f"  avg reduction, full distilled set   : "
              f"{ms['avg_reduction_kept_pct']}%")
        print(f"  modes: {ms['modes']}")
    else:
        print("  no compression runs yet")

    if ms.get("recall_events"):
        inj = ms.get("recall_injected", 0)
        print(f"  recall hook                : {ms['recall_events']} prompts, "
              f"{inj} injected ({100 * inj // max(1, ms['recall_events'])}%), "
              f"median {ms.get('recall_p50_ms')} ms")

    # The semantic path failing is invisible from the outside: recall keeps
    # working on the lexical index and simply stops finding paraphrases. Say so.
    try:
        import embed
        br = embed.breaker_state()
        if br["open"]:
            print(f"  embedding                  : SKIPPED for another "
                  f"{br['seconds_left']}s — {br['reason']}. Recall is lexical "
                  f"only: exact words still match, paraphrases do not.")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
