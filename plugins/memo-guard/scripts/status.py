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
    mf = mg.data_dir() / "metrics.jsonl"
    rows = []
    if mf.exists():
        for ln in mf.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    if not rows:
        return {"runs": 0}
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

    print(f"\narchives ({slug}): {len(archives)} total")
    for a in archives[-5:]:
        print(f"  {a.name}  {a.stat().st_size // 1024:>6} KB")

    print(f"\nresumes ready: {len(resumes)}")
    for r in resumes[:5]:
        try:
            st = json.loads((r.parent / "STATE.json").read_text(encoding="utf-8"))
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
