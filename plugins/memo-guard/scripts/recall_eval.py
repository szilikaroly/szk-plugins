#!/usr/bin/env python3
"""Measure the recall stack against a labelled corpus, and calibrate its floor.

Two claims in this plugin were, until now, assertions:

  1. `SEMANTIC_FLOOR = 0.48` "sits in a measured gap" — measured on a handful of
     facts, by hand, once.
  2. Injecting memory into every prompt is worth its tokens.

Neither can be settled by looking at what the retriever returned; both need the
scores of the facts it did *not* return, and the behaviour on queries where the
correct answer is silence. So this builds an isolated store from a labelled
corpus and scores four query kinds separately:

  lexical     the query shares words with its fact — the easy case
  paraphrase  it shares almost none — this is the case embeddings are for, and
              the only place they can justify their latency
  gated       the one relevant fact lives in ANOTHER project. With no goal
              stated the correct answer is nothing, so a "hit" here is a
              privacy failure, not a success
  noise       nothing in the store answers it. Anything returned is pure cost

The headline number is not recall. It is the **false-injection rate**: how often
a prompt that needed nothing was charged for something anyway. Recall is paid
for once per useful answer; noise is paid for on every turn forever.

    recall_eval.py                     # measure, both modes if an embedder is up
    recall_eval.py --calibrate         # sweep SEMANTIC_FLOOR, show the gap
    recall_eval.py --corpus mine.json --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DEFAULT_CORPUS = Path(__file__).parent.parent / "eval" / "recall_corpus.json"
FLOOR_SWEEP = [0.30, 0.34, 0.38, 0.42, 0.46, 0.48, 0.50, 0.54, 0.58, 0.62, 0.66]


def build_store(corpus: dict, home: Path, sem_up: bool):
    """A throwaway store, because evaluating against the real one would both
    pollute it and score whatever happened to be in it.

    `promote()` embeds each fact twice. With a healthy server that is fast; with
    a stalled one it is 20 s per call by default, so seeding 20 facts becomes 13
    minutes of a harness that appears to have hung. The timeout is therefore
    bound to what the health probe just found — the same discipline recall.py
    applies in the hook, for the same reason.
    """
    os.environ["MEMO_GUARD_HOME"] = str(home)
    for mod in ("mg_lib", "memory", "embed", "recall"):
        sys.modules.pop(mod, None)
    import embed
    embed.set_timeout(20.0 if sem_up else 0.4)
    import memory
    db = memory.connect()
    ids = {}
    for f in corpus["facts"]:
        cwd = corpus["projects"][f["project"]]
        r = memory.promote(db, f["text"], cwd, kind=f.get("kind", "finding"),
                           utility=0.5)
        ids[f["id"]] = r["id"]
    return db, ids


def run_queries(db, corpus: dict, ids: dict, allow_semantic: bool,
                floor: float | None = None, cfg_over: dict | None = None
                ) -> list[dict]:
    import memory
    import recall as R
    import mg_lib as mg
    if floor is not None:
        memory.SEMANTIC_FLOOR = floor
    cfg = dict(mg.load_config())
    cfg.update(cfg_over or {})
    rev = {v: k for k, v in ids.items()}
    out = []
    for q in corpus["queries"]:
        cwd = corpus["projects"][q["project"]]
        dbg: dict = {}
        t0 = time.time()
        res = memory.recall(db, q["q"], cwd, goal=None, budget_tokens=1200,
                            limit=12, allow_semantic=allow_semantic, debug=dbg)
        # Score what the hook would ACTUALLY inject, not the candidate list.
        _, chosen, spent = R.select(res["facts"], cfg)
        got = [rev.get(i, f"?{i}") for i in chosen]
        want = set(q["relevant"])
        sem_scores = list(dbg.get("semantic", {}).values())
        out.append({
            "q": q["q"], "kind": q["kind"], "want": sorted(want), "got": got,
            "tokens": spent, "ms": round((time.time() - t0) * 1000, 1),
            "hit": bool(want & set(got)),
            "silent": not got,
            "best_sem": max(sem_scores) if sem_scores else None,
            "cross_project": sum(1 for f in res["facts"]
                                 if f["id"] in chosen and not f["same_project"]),
            "rank": next((i + 1 for i, g in enumerate(got) if g in want), 0),
        })
    return out


def summarise(rows: list[dict]) -> dict:
    def sub(kind):
        return [r for r in rows if r["kind"] == kind]
    answerable = [r for r in rows if r["want"]]
    silent_should = [r for r in rows if not r["want"]]
    hits = [r for r in answerable if r["hit"]]
    injected = sum(len(r["got"]) for r in rows)
    correct = sum(len(set(r["got"]) & set(r["want"])) for r in rows)
    return {
        "queries": len(rows),
        "recall": len(hits) / max(1, len(answerable)),
        "precision": correct / max(1, injected),
        "mrr": sum(1 / r["rank"] for r in hits) / max(1, len(answerable)),
        "recall_lexical": (sum(r["hit"] for r in sub("lexical"))
                           / max(1, len(sub("lexical")))),
        "recall_paraphrase": (sum(r["hit"] for r in sub("paraphrase"))
                              / max(1, len(sub("paraphrase")))),
        "false_injection_rate": (sum(not r["silent"] for r in silent_should)
                                 / max(1, len(silent_should))),
        # A gated query that returns an unrelated fact from its OWN project is
        # noise, not a breach. Conflating the two hides the only failure here
        # that is a privacy problem rather than a cost problem.
        "gate_breaches": sum(r["cross_project"] for r in rows),
        "gated_silent": (sum(r["silent"] for r in sub("gated"))
                         / max(1, len(sub("gated")))),
        "noise_silent": (sum(r["silent"] for r in sub("noise"))
                         / max(1, len(sub("noise")))),
        "mean_tokens_per_prompt": sum(r["tokens"] for r in rows) / max(1, len(rows)),
        "mean_ms": sum(r["ms"] for r in rows) / max(1, len(rows)),
    }


def print_report(label: str, s: dict, rows: list[dict], verbose: bool) -> None:
    print(f"\n=== {label} ===")
    print(f"  recall            {s['recall']:.0%}   "
          f"(lexical {s['recall_lexical']:.0%}, paraphrase {s['recall_paraphrase']:.0%})")
    print(f"  precision         {s['precision']:.0%}")
    print(f"  MRR               {s['mrr']:.2f}")
    print(f"  FALSE INJECTION   {s['false_injection_rate']:.0%}   "
          f"(gated silent {s['gated_silent']:.0%}, noise silent "
          f"{s['noise_silent']:.0%})")
    print(f"  cross-project leaks {s['gate_breaches']}   "
          f"(must be 0 — no goal was stated)")
    print(f"  cost              ~{s['mean_tokens_per_prompt']:.0f} tok/prompt, "
          f"{s['mean_ms']:.0f} ms/query")
    if verbose:
        for r in rows:
            mark = ("hit " if r["hit"] else
                    ("ok  " if (not r["want"] and r["silent"]) else "MISS"))
            print(f"    {mark} [{r['kind']:10}] {r['q'][:58]:58} -> "
                  f"{','.join(r['got']) or '(silent)'}")


def calibrate(db, corpus: dict, ids: dict) -> int:
    """Where should the floor sit? Show the two distributions, then the sweep.

    A single recommended number hides the thing worth seeing: whether there is a
    gap at all. If the relevant and the nonsense scores overlap, no threshold
    fixes it and the honest move is to stop trusting the semantic path — which
    is exactly what a printed recommendation would conceal.
    """
    rows = run_queries(db, corpus, ids, allow_semantic=True, floor=0.0)
    rel = [r["best_sem"] for r in rows if r["want"] and r["best_sem"] is not None]
    noi = [r["best_sem"] for r in rows
           if not r["want"] and r["best_sem"] is not None]
    if not rel or not noi:
        print("\nNo semantic scores available — the embedder did not answer. "
              "Calibration needs it; nothing to report.")
        return 1
    rel.sort(); noi.sort()
    print("\n=== score distributions (best semantic score per query) ===")
    print(f"  relevant queries  n={len(rel):2}  min {min(rel):.3f}  "
          f"median {rel[len(rel)//2]:.3f}  max {max(rel):.3f}")
    print(f"  should-be-silent  n={len(noi):2}  min {min(noi):.3f}  "
          f"median {noi[len(noi)//2]:.3f}  max {max(noi):.3f}")
    gap_lo, gap_hi = max(noi), min(rel)
    if gap_hi > gap_lo:
        print(f"  GAP               {gap_lo:.3f} .. {gap_hi:.3f}  "
              f"(width {gap_hi - gap_lo:.3f}) -> a floor here separates them cleanly")
        rec = round((gap_lo + gap_hi) / 2, 2)
    else:
        print(f"  OVERLAP           noise reaches {gap_lo:.3f}, relevant starts "
              f"at {gap_hi:.3f} — no threshold separates these two sets. "
              f"Pick by which error you prefer, not by a gap that is not there.")
        rec = None

    print("\n=== sweep ===")
    print(f"  {'floor':>6} {'recall':>7} {'false-inj':>10} {'tok/prompt':>11}")
    best = None
    for f in FLOOR_SWEEP:
        s = summarise(run_queries(db, corpus, ids, allow_semantic=True, floor=f))
        print(f"  {f:6.2f} {s['recall']:7.0%} {s['false_injection_rate']:10.0%} "
              f"{s['mean_tokens_per_prompt']:11.0f}")
        score = s["recall"] - s["false_injection_rate"]
        if best is None or score > best[1]:
            best = (f, score)
    print(f"\n  recommended floor : {rec if rec is not None else best[0]:.2f}"
          f"   (export MEMO_SEMANTIC_FLOOR to use it)")
    import memory
    print(f"  current floor     : {memory.SEMANTIC_FLOOR:.2f}")
    return 0


def sweep_floors(db, corpus: dict, ids: dict, sem_up: bool) -> int:
    """Pick the injection floors from the corpus instead of from taste.

    Recall and false injection move in opposite directions, so there is no
    single best row — the choice is which error you would rather pay. For a hook
    that fires on every prompt the asymmetry is real: a miss costs one answer
    you could still ask for, a false injection costs tokens on every turn and
    teaches you to ignore the block.
    """
    print("\n=== injection-floor sweep ===")
    print(f"  {'abs':>5} {'rel':>5} {'recall':>7} {'precis':>7} "
          f"{'false-inj':>10} {'tok/prompt':>11}")
    rows = []
    for absf in (0.0, 0.30, 0.35, 0.40, 0.45):
        for relf in (0.0, 0.45, 0.55, 0.65, 0.75):
            s = summarise(run_queries(
                db, corpus, ids, allow_semantic=sem_up,
                cfg_over={"recall_min_relevance": absf,
                          "recall_relative_floor": relf}))
            rows.append((absf, relf, s))
            print(f"  {absf:5.2f} {relf:5.2f} {s['recall']:7.0%} "
                  f"{s['precision']:7.0%} {s['false_injection_rate']:10.0%} "
                  f"{s['mean_tokens_per_prompt']:11.0f}")
    base = rows[0][2]
    # Rank by recall kept minus twice the false injection, because the two are
    # not paid at the same rate: recall is paid once per useful answer, noise on
    # every turn forever.
    # Ties are common and not meaningless: among rows that keep the same recall
    # and the same noise rate, the one that injects fewer tokens is strictly
    # better, so precision breaks the tie rather than row order doing it.
    best = max(rows, key=lambda r: (round(r[2]["recall"]
                                          - 2 * r[2]["false_injection_rate"], 4),
                                    round(r[2]["precision"], 4),
                                    -r[2]["mean_tokens_per_prompt"]))
    print(f"\n  baseline (0,0)  recall {base['recall']:.0%}  "
          f"precision {base['precision']:.0%}  "
          f"false-inj {base['false_injection_rate']:.0%}")
    print(f"  best            abs={best[0]:.2f} rel={best[1]:.2f}  "
          f"recall {best[2]['recall']:.0%}  precision {best[2]['precision']:.0%}  "
          f"false-inj {best[2]['false_injection_rate']:.0%}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--mode", choices=("lexical", "semantic", "both"),
                    default="both")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="sweep the two injection floors and show the tradeoff")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-embed", action="store_true",
                    help="force the lexical path and make seeding instant, by "
                         "pointing the embedder at a closed port. A refused "
                         "connection fails in microseconds; a SLOW server costs "
                         "the timeout per fact, which is what turns a 2-second "
                         "regression check into a 16-second one.")
    a = ap.parse_args()

    if a.no_embed:
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"
        a.mode = "lexical"
    corpus = json.loads(a.corpus.read_text())
    home = Path(tempfile.mkdtemp(prefix="mg-eval-"))
    try:
        # Probe BEFORE seeding: the answer decides how long seeding is allowed
        # to take, and seeding is where a stalled server does its damage.
        import broker
        sem_up = False
        try:
            sem_up = broker.healthy(timeout=3.0, strict=True)
        except Exception:
            sem_up = False
        t_seed = time.time()
        db, ids = build_store(corpus, home, sem_up)
        if not a.json:
            print(f"corpus: {len(corpus['facts'])} facts, "
                  f"{len(corpus['queries'])} queries; embedder "
                  f"{'up' if sem_up else 'DOWN (lexical only)'}; "
                  f"seeded in {time.time() - t_seed:.1f}s")

        if a.sweep:
            return sweep_floors(db, corpus, ids, sem_up)
        if a.calibrate:
            if not sem_up:
                print("The embedder is not answering (broker.healthy strict). "
                      "Calibration is meaningless without it — fix the model "
                      "server first: broker.py --diagnose")
                return 1
            return calibrate(db, corpus, ids)

        modes = []
        if a.mode in ("lexical", "both"):
            modes.append(("lexical only", False))
        if a.mode in ("semantic", "both"):
            if sem_up:
                modes.append(("lexical + semantic", True))
            else:
                print("(semantic mode skipped: the embedder is not answering)")

        results = {}
        for label, allow in modes:
            rows = run_queries(db, corpus, ids, allow_semantic=allow)
            s = summarise(rows)
            results[label] = s
            if not a.json:
                print_report(label, s, rows, a.verbose)
        if a.json:
            print(json.dumps({"corpus": corpus.get("name"),
                              "facts": len(corpus["facts"]),
                              "modes": results}, indent=2))
        elif len(results) == 2:
            l, sm = results["lexical only"], results["lexical + semantic"]
            print("\n=== what the embedder buys ===")
            print(f"  paraphrase recall  {l['recall_paraphrase']:.0%} -> "
                  f"{sm['recall_paraphrase']:.0%}")
            print(f"  false injection    {l['false_injection_rate']:.0%} -> "
                  f"{sm['false_injection_rate']:.0%}")
            print(f"  latency            {l['mean_ms']:.0f} -> {sm['mean_ms']:.0f} ms")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
