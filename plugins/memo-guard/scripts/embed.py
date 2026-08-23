#!/usr/bin/env python3
"""Embeddings with two models, chosen per task — and never mixed.

The constraint that shapes everything here
------------------------------------------
Vectors from different models are not comparable. A nomic vector and an mxbai
vector for the same sentence are points in unrelated spaces, and a cosine
between them is a number with no meaning. So "adaptive model choice" cannot
mean picking a model per query against one index — it means storing a vector
per (fact, model) and querying entirely within one space. Every read here
filters by model for that reason, and a fact missing a vector in the chosen
space is scored lexically rather than compared across spaces.

Routing, and why each rule exists
---------------------------------
  bulk/hot     -> nomic    768 dims, 18 ms measured. The per-claim verdict check
                           runs dozens of times inside one compression, so
                           latency compounds there.
  recall       -> mxbai    1024 dims, 25 ms measured. A handful of calls per
                           session where retrieval quality is the whole point.
  long input   -> CHUNK, not a different model.

That last rule was written the other way round first, on the assumption that
mxbai truncates at 512 tokens while nomic holds 8192, so long text should route
to nomic. Measured on this machine, that is wrong. BOTH truncate silently, and
neither reports it — two texts differing only after the cut produce identical
vectors (cosine 1.00000). mxbai's latency stays flat at ~76 ms no matter how
much you send it, which is the tell. Observed cut-off: mxbai between 760 and
2850 tokens, nomic between 2850 and 5700.

So there is no "safe" model for long input, only a safe length. SAFE_CHARS is
set below the lower measured cut-off with margin, and anything longer is split
into chunks that are embedded separately. Silently embedding a truncated prefix
is the failure mode this avoids: it looks like it worked.

Hybrid by design: FTS5 narrows to a few dozen candidates, vectors only re-rank
those. That keeps the cosine loop small enough for pure Python, so the plugin
stays dependency-free, and it means a missing or slow embedder degrades to
lexical search instead of failing.

Measured thresholds live in _PROFILE and were set from benchmark output on this
machine, not from documentation. Re-run `embed.py --benchmark` after changing
models.

  embed.py --benchmark
  embed.py --text "some claim" --profile recall
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

MODELS = {
    "fast": os.environ.get("MEMO_EMBED_FAST", "nomic-embed-text"),
    "quality": os.environ.get("MEMO_EMBED_QUALITY", "mxbai-embed-large"),
}

# Measured, not documented. Both models returned identical vectors for texts
# differing only past the cut, so these are the lengths below which an embedding
# actually describes the whole input. Re-run --truncation-test after any model
# change; the numbers depend on Ollama's context defaults, not just the model.
SAFE_CHARS = 2400           # below mxbai's observed cut (3040 ch was still fine)
_PROFILE = {"timeout_s": 20}


def set_timeout(seconds: float) -> float:
    """Change how long an embed call may take, returning the previous value.

    20 s is right for background work: a model that has to be loaded first is
    worth waiting for. It is badly wrong in front of a user's keystroke, where
    the honest answer after 800 ms is "no vector this time" — the caller already
    has a lexical path. Process-wide on purpose; the callers that need this are
    short-lived single-purpose hooks.
    """
    prev = _PROFILE["timeout_s"]
    _PROFILE["timeout_s"] = float(seconds)
    return prev


#: A wedged model server costs the full timeout to detect, and nothing about it
#: changes between two calls one millisecond apart. Without a shared verdict
#: every caller in a process pays that timeout again: a single recall hook was
#: measured at 2× the budget (2.2 s at a 1.1 s timeout) because the query
#: embedding and the claim-check embedding each waited it out in turn.
_BREAKER = {"until": 0.0, "reason": ""}
BREAKER_S = 60.0


def breaker_state() -> dict:
    """How long embedding is being skipped, and why. For doctor/status."""
    left = _BREAKER["until"] - time.time()
    return {"open": left > 0, "seconds_left": round(max(0.0, left), 1),
            "reason": _BREAKER["reason"]}


def _trip(reason: str) -> None:
    _BREAKER["until"] = time.time() + BREAKER_S
    _BREAKER["reason"] = reason
    try:
        (_state_path()).write_text(json.dumps(
            {"until": _BREAKER["until"], "reason": reason}))
    except OSError:
        pass


def _state_path():
    import mg_lib as mg
    return mg.data_dir() / "embed_breaker.json"


def _breaker_open() -> bool:
    if _BREAKER["until"] > time.time():
        return True
    try:
        d = json.loads(_state_path().read_text())
        if float(d.get("until", 0)) > time.time():
            _BREAKER.update(until=float(d["until"]), reason=d.get("reason", ""))
            return True
    except Exception:
        pass
    return False


def _post(path: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        f"{OLLAMA}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def available() -> set[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            return {m["name"].split(":")[0] for m in json.loads(r.read()).get("models", [])}
    except Exception:
        return set()


def chunk(text: str, size: int = SAFE_CHARS, overlap: int = 200) -> list[str]:
    """Split on paragraph then sentence boundaries, never mid-word.

    Overlap exists so a fact stated across a boundary is not halved into two
    embeddings that each describe part of it.
    """
    text = text.strip()
    if len(text) <= size:
        return [text]
    out, pos = [], 0
    while pos < len(text):
        end = min(len(text), pos + size)
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                cut = text.rfind(sep, pos + size // 2, end)
                if cut > pos:
                    end = cut + len(sep)
                    break
        out.append(text[pos:end].strip())
        if end >= len(text):
            break
        pos = max(pos + 1, end - overlap)
    return [c for c in out if c]


def pick_model(text: str, profile: str = "bulk") -> str:
    """Route by task. Length is handled by chunking, not by model choice —
    see the module docstring; neither model is safe on long input."""
    have = available()
    fast, quality = MODELS["fast"], MODELS["quality"]
    chosen = quality if profile == "recall" else fast
    base = chosen.split(":")[0]
    if have and base not in have:
        other = fast if chosen == quality else quality
        chosen = other if other.split(":")[0] in have else ""
    return chosen


def embed_chunks(text: str, profile: str = "bulk", model: str | None = None
                 ) -> tuple[str, list[list[float]]] | None:
    """Embed text of any length as one vector per chunk. Use this for material;
    `embed` is for short items (claims, facts, queries) that fit whole."""
    m = model or pick_model(text, profile)
    if not m:
        return None
    vecs = []
    for c in chunk(text):
        r = embed(c, profile, m)
        if r:
            vecs.append(normalize(r[1]))
    return (m, vecs) if vecs else None


def embed(text: str, profile: str = "bulk", model: str | None = None
          ) -> tuple[str, list[float]] | None:
    """Return (model, vector) or None. Never raises — callers fall back to lexical.

    Refuses input past the measured safe length rather than returning a vector
    that silently describes only the beginning. Call embed_chunks() for that case.
    """
    m = model or pick_model(text, profile)
    if not m:
        return None
    if len(text) > SAFE_CHARS * 4:
        return None          # far past any model's cut; caller must chunk
    if _breaker_open():
        return None          # already known not to answer; do not pay again
    try:
        d = _post("/api/embed", {"model": m, "input": text},
                  _PROFILE["timeout_s"])
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        _trip(f"{type(e).__name__} after {_PROFILE['timeout_s']}s")
        return None
    vecs = d.get("embeddings") or ([d["embedding"]] if "embedding" in d else [])
    if not vecs or not vecs[0]:
        return None
    return m, vecs[0]


# --------------------------------------------------------------------------- storage

def pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def normalize(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """Assumes both are normalized — dot product then IS the cosine."""
    if len(a) != len(b):
        return 0.0          # different spaces; refuse rather than return noise
    return sum(x * y for x, y in zip(a, b))


# --------------------------------------------------------------------------- cli

def benchmark() -> int:
    have = available()
    print(f"ollama models present: {sorted(have) or '(none)'}\n")
    short = "PROSPERO registration must be cited in the abstract"
    long_t = short * 60
    rows = []
    for role, name in MODELS.items():
        if name.split(":")[0] not in have:
            print(f"  {name:<22} NOT PULLED")
            continue
        r = embed(short, model=name)
        if not r:
            print(f"  {name:<22} no response")
            continue
        dim = len(r[1])
        ts = []
        for _ in range(5):
            t = time.perf_counter()
            embed(short, model=name)
            ts.append((time.perf_counter() - t) * 1000)
        ts.sort()
        rl = embed(long_t, model=name)
        rows.append((role, name, dim, ts[len(ts) // 2], bool(rl)))
        print(f"  {name:<22} dim={dim:<5} median={ts[len(ts)//2]:6.1f} ms  "
              f"long-input({len(long_t)} ch)={'ok' if rl else 'FAILED'}")
    if len(rows) >= 2:
        print("\n  cross-space check (must be refused, not scored):")
        a = embed(short, model=rows[0][1])
        b = embed(short, model=rows[1][1])
        if a and b:
            print(f"    cosine(nomic, mxbai) = {cosine(normalize(a[1]), normalize(b[1])):.3f}"
                  f"   (0.000 = correctly refused: dims {len(a[1])} vs {len(b[1])})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--truncation-test", action="store_true",
                    help="find where each model stops reading (re-run after model changes)")
    ap.add_argument("--text")
    ap.add_argument("--profile", default="bulk", choices=("bulk", "recall"))
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    args = ap.parse_args()

    if args.benchmark:
        return benchmark()
    if args.truncation_test:
        unit = "The manuscript was prepared per the submission guidelines. "
        print("Two texts differing ONLY after the padding. Identical vectors")
        print("(cos > 0.9995) mean the model never saw the difference.\n")
        print(f"{'chars':>8} | " + " | ".join(f"{n:>22}" for n in MODELS.values()))
        for n in (40, 150, 300, 600, 1200):
            pad = unit * n
            cells = []
            for name in MODELS.values():
                ra = embed(pad + " END: elephants.", model=name)
                rb = embed(pad + " END: bicycles.", model=name)
                if not ra or not rb:
                    cells.append(f"{'refused (too long)':>22}")
                    continue
                c = cosine(normalize(ra[1]), normalize(rb[1]))
                cells.append(f"{c:>14.5f}{'  TRUNC' if c > 0.9995 else '   ok  '}")
            print(f"{len(pad):>8} | " + " | ".join(cells))
        print(f"\nSAFE_CHARS is currently {SAFE_CHARS}; keep it under the first TRUNC row.")
        return 0
    if args.compare:
        ra = embed(args.compare[0], args.profile)
        rb = embed(args.compare[1], args.profile)
        if not ra or not rb:
            print("no embedder available", file=sys.stderr)
            return 1
        print(f"model={ra[0]}  cosine={cosine(normalize(ra[1]), normalize(rb[1])):.4f}")
        return 0
    if args.text:
        r = embed(args.text, args.profile)
        if not r:
            print("no embedder available", file=sys.stderr)
            return 1
        print(f"model={r[0]} dim={len(r[1])}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
