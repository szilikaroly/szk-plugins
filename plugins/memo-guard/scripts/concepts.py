#!/usr/bin/env python3
"""Concept formation over the corpus store: embeddings -> clusters -> labelled concepts.

Why: a claim is one sentence from one file. What a reader (or Claude) needs to reason with
is the concept behind many of them - the same finding restated across a manuscript's
versions, the same trial cited by four reviews, the same number that changed between two
drafts. Lexical search cannot see that ("elhizas" never matches "obesity"); a concept card
can, and it costs a few dozen tokens instead of the claims it stands for.

  1. --embed    nomic-embed-text ("search_document: " prefix, its trained task prefix),
                truncated to 256 dims (Matryoshka) and stored as float16: 512 bytes a claim.
                Only CONFIRMED/DRIFTED claims with real content; resumable, batched.
  2. --cluster  mini-batch k-means (numpy, cosine on unit vectors), ~150 claims a concept.
  3. --label    deterministic: the concept's most distinctive keywords (in-cluster
                frequency against corpus frequency). --llm adds a short name and a
                one-sentence summary from the local model, when the GPU is free.
  4. --conflicts  near-identical claims (cosine >= 0.93) inside a concept whose numbers
                differ: "33,2% elhizas-prevalencia" vs "22%-os elhizas-prevalencia".
                Stored as `conflict` edges for review, never resolved automatically.
  5. --search   query embedding ("search_query: ") -> nearest concepts -> their best
                verified claims.

Embedding calls do not use embed.py's shared breaker on purpose: a recall-hook timeout
there would silence this bulk job, and this job's load would trip the hook's breaker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg  # noqa: E402
import store  # noqa: E402

MODEL = os.environ.get("MEMO_CONCEPT_EMBED", "nomic-embed-text")
DIM = 256
GOOD = ("CONFIRMED", "DRIFTED")

SCHEMA = """
CREATE TABLE IF NOT EXISTS emb (claim_id INTEGER PRIMARY KEY, model TEXT, dim INTEGER, vec BLOB);
CREATE TABLE IF NOT EXISTS concept (
  id INTEGER PRIMARY KEY, label TEXT, keywords TEXT, summary TEXT, size INTEGER,
  projects TEXT, centroid BLOB, model TEXT, dim INTEGER, updated_at REAL);
CREATE TABLE IF NOT EXISTS concept_member (
  concept_id INTEGER NOT NULL, claim_id INTEGER NOT NULL, score REAL,
  PRIMARY KEY (concept_id, claim_id));
CREATE INDEX IF NOT EXISTS cm_claim ON concept_member(claim_id);
CREATE TABLE IF NOT EXISTS edge (
  src INTEGER NOT NULL, dst INTEGER NOT NULL, kind TEXT NOT NULL, weight REAL, note TEXT,
  created_at REAL, PRIMARY KEY (src, dst, kind));
CREATE INDEX IF NOT EXISTS edge_dst ON edge(dst);
-- A claim's vector, memberships and conflict edges go with it. The store re-imports a changed
-- memo by deleting its claims, and claim ids are INTEGER PRIMARY KEY without AUTOINCREMENT:
-- a vector left behind is an orphan in every clustering, and when its id is reused it is read
-- as the NEXT claim's vector. Measured 2026-10-04: 167 of the first 256 vectors were orphans.
CREATE TRIGGER IF NOT EXISTS claim_concept_ad AFTER DELETE ON claim BEGIN
  DELETE FROM emb WHERE claim_id = old.id;
  DELETE FROM concept_member WHERE claim_id = old.id;
  DELETE FROM edge WHERE src = old.id OR dst = old.id;
END;
"""


def _sha(text: str) -> str:
    """What a vector was computed from. A claim whose text no longer hashes to it is
    re-embedded, and its old vector never takes part in a clustering."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def connect():
    db = store.connect()
    db.executescript(SCHEMA)
    if "sha" not in {r[1] for r in db.execute("PRAGMA table_info(emb)")}:
        db.execute("ALTER TABLE emb ADD COLUMN sha TEXT")   # older rows: NULL = re-embed
        db.commit()
    return db


def _prune(db) -> dict:
    """Drop what the trigger could not have caught: rows left from before it existed."""
    out = {}
    for table, cond in (("emb", "claim_id NOT IN (SELECT id FROM claim)"),
                        ("concept_member", "claim_id NOT IN (SELECT id FROM claim)"),
                        ("edge", "src NOT IN (SELECT id FROM claim) OR dst NOT IN (SELECT id FROM claim)")):
        out[table] = db.execute(f"DELETE FROM {table} WHERE {cond}").rowcount
    db.commit()
    return out


def _np():
    import numpy as np
    return np


def _post_embed(texts: list[str], prefix: str, timeout: float):
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    body = json.dumps({"model": MODEL, "input": [prefix + t[:2000] for t in texts],
                       "truncate": True}).encode()
    req = urllib.request.Request(f"{host}/api/embed", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["embeddings"]


def embed_batch(texts: list[str], prefix: str, timeout: float = 120.0, retries: int = 3):
    """Batched /api/embed. Under GPU contention the scheduler can evict the embedding
    runner mid-request and the server answers 400 (2026-10-03: 1 of 3 batches, while 14
    generation workers held the card). Retry with backoff; a batch that keeps failing is
    split in half, so one bad input cannot sink the other 255."""
    np = _np()
    for attempt in range(retries):
        try:
            vecs = _post_embed(texts, prefix, timeout)
            break
        except Exception:
            if attempt == retries - 1:
                if len(texts) == 1:
                    raise
                h = len(texts) // 2
                return np.vstack([embed_batch(texts[:h], prefix, timeout, retries),
                                  embed_batch(texts[h:], prefix, timeout, retries)])
            time.sleep(2 * (attempt + 1))
    a = np.asarray(vecs, dtype=np.float32)[:, :DIM]
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-9
    return a


def _content_ok_sql() -> str:
    # Same junk rule as store.search: not anchor-only, not a bare heading.
    return ("length(c.text) >= 15 AND c.text NOT LIKE '@L%' AND"
            " (length(c.text) - length(replace(c.text, ' ', ''))) >= 2")


def build_embeddings(limit: int | None = None, batch: int = 256, log=print) -> dict:
    np = _np()
    db = connect()
    pruned = _prune(db)
    todo = [(cid, t) for cid, t, sha in db.execute(
        f"SELECT c.id, c.text, e.sha FROM claim c LEFT JOIN emb e ON e.claim_id = c.id"
        f" WHERE c.status IN {GOOD} AND {_content_ok_sql()}") if sha != _sha(t)]
    if limit:
        todo = todo[:int(limit)]
    t0, done = time.time(), 0
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        vec = embed_batch([t for _, t in part], "search_document: ")
        db.executemany("INSERT OR REPLACE INTO emb (claim_id, model, dim, vec, sha) VALUES (?,?,?,?,?)",
                       [(cid, MODEL, DIM, vec[j].astype(np.float16).tobytes(), _sha(t))
                        for j, (cid, t) in enumerate(part)])
        done += len(part)
        if (i // batch) % 20 == 0:
            db.commit()
            el = time.time() - t0
            log(f"  {done}/{len(todo)}  ({done / max(el, 1e-9):.0f} claim/s)")
    db.commit()
    return {"embedded": done, "pruned": pruned, "seconds": round(time.time() - t0, 1)}


def _load_vectors(db):
    """Vectors of the claims a concept may stand for: still CONFIRMED/DRIFTED, and still the
    text the vector was computed from."""
    np = _np()
    ids, blobs = [], []
    for cid, blob, sha, text in db.execute(
            f"SELECT e.claim_id, e.vec, e.sha, c.text FROM emb e JOIN claim c ON c.id = e.claim_id"
            f" WHERE e.dim=? AND c.status IN {GOOD}", (DIM,)):
        if sha == _sha(text):
            ids.append(cid)
            blobs.append(blob)
    X = np.frombuffer(b"".join(blobs), dtype=np.float16).reshape(-1, DIM).astype(np.float32)
    return np.asarray(ids), X


def cluster(k: int | None = None, iters: int = 25, batch: int = 20000, seed: int = 7,
            log=print) -> dict:
    np = _np()
    db = connect()
    _prune(db)
    ids, X = _load_vectors(db)
    n = len(ids)
    if n < 50:
        return {"skipped": f"only {n} embedded claims"}
    k = k or int(min(4000, max(50, n // 150)))
    rng = np.random.default_rng(seed)
    C = X[rng.choice(n, k, replace=False)].copy()
    counts = np.zeros(k)
    t0 = time.time()
    for it in range(iters):                       # mini-batch k-means (Sculley 2010)
        idx = rng.choice(n, min(batch, n), replace=False)
        B = X[idx]
        a = np.argmax(B @ C.T, axis=1)
        for j in np.unique(a):
            m = B[a == j]
            counts[j] += len(m)
            eta = len(m) / counts[j]
            C[j] = (1 - eta) * C[j] + eta * m.mean(axis=0)
        C /= np.linalg.norm(C, axis=1, keepdims=True) + 1e-9
    assign = np.empty(n, dtype=np.int64)
    score = np.empty(n, dtype=np.float32)
    for i in range(0, n, 50000):                  # final full assignment
        S = X[i:i + 50000] @ C.T
        assign[i:i + 50000] = np.argmax(S, axis=1)
        score[i:i + 50000] = S[np.arange(len(S)), assign[i:i + 50000]]
    db.execute("DELETE FROM concept_member")
    db.execute("DELETE FROM concept")
    now = time.time()
    used = np.unique(assign)
    remap = {int(j): r + 1 for r, j in enumerate(used)}
    db.executemany("INSERT INTO concept (id, size, centroid, model, dim, updated_at) VALUES (?,?,?,?,?,?)",
                   [(remap[int(j)], int((assign == j).sum()), C[j].astype(np.float16).tobytes(),
                     MODEL, DIM, now) for j in used])
    db.executemany("INSERT INTO concept_member VALUES (?,?,?)",
                   [(remap[int(assign[i])], int(ids[i]), float(score[i])) for i in range(n)])
    db.commit()
    return {"claims": n, "concepts": len(used), "seconds": round(time.time() - t0, 1)}


def label(log=print) -> dict:
    """Deterministic labels: keywords frequent inside the concept, rare outside it."""
    db = connect()
    df = Counter()
    members: dict[int, list[str]] = {}
    projects: dict[int, Counter] = {}
    for cid, kws, proj in db.execute(
            "SELECT m.concept_id, c.keywords, d.project FROM concept_member m"
            " JOIN claim c ON c.id = m.claim_id JOIN doc d ON d.id = c.doc_id"):
        words = set(w for w in (kws or "").split() if len(w) > 2 and not w.isdigit())
        df.update(words)
        members.setdefault(cid, []).extend(words)
        projects.setdefault(cid, Counter())[proj] += 1
    N = sum(1 for _ in db.execute("SELECT 1 FROM concept_member"))
    import math
    rows = []
    for cid, words in members.items():
        tf = Counter(words)
        size = sum(projects[cid].values())
        top = sorted(tf, key=lambda w: -(tf[w] / size) * math.log((N + 1) / (df[w] + 1)))[:6]
        rows.append((" / ".join(top[:3]), " ".join(top),
                     json.dumps(dict(projects[cid].most_common(5)), ensure_ascii=False), cid))
    db.executemany("UPDATE concept SET label=?, keywords=?, projects=? WHERE id=?", rows)
    db.commit()
    return {"labelled": len(rows)}


NUMS = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?%?")


def conflicts(threshold: float = 0.93, max_per_concept: int = 2000, log=print) -> dict:
    """Pairs of near-identical claims in one concept whose numbers differ."""
    np = _np()
    db = connect()
    db.execute("DELETE FROM edge WHERE kind='conflict'")
    found = 0
    concepts = [r[0] for r in db.execute("SELECT id FROM concept WHERE size >= 2")]
    for cid in concepts:
        rows = db.execute(
            "SELECT c.id, c.text, e.vec FROM concept_member m JOIN claim c ON c.id = m.claim_id"
            f" JOIN emb e ON e.claim_id = c.id WHERE m.concept_id=? AND c.status IN {GOOD} LIMIT ?",
            (cid, max_per_concept)).fetchall()
        nums = [set(NUMS.findall(t)) for _, t, _ in rows]
        keep = [i for i, s in enumerate(nums) if s]
        if len(keep) < 2:
            continue
        V = np.frombuffer(b"".join(rows[i][2] for i in keep), dtype=np.float16).reshape(-1, DIM).astype(np.float32)
        S = V @ V.T
        np.fill_diagonal(S, 0)
        a, b = np.where(np.triu(S) >= threshold)
        edges = []
        for x, y in zip(a, b):
            i, j = keep[x], keep[y]
            if nums[i] != nums[j] and mg.fold(rows[i][1]) != mg.fold(rows[j][1]):
                note = f"{sorted(nums[i])[:4]} vs {sorted(nums[j])[:4]}"
                edges.append((rows[i][0], rows[j][0], "conflict", float(S[x, y]), note, time.time()))
        if edges:
            db.executemany("INSERT OR REPLACE INTO edge VALUES (?,?,?,?,?,?)", edges)
            found += len(edges)
    db.commit()
    return {"conflict_edges": found}


def _centroids(db):
    np = _np()
    rows = db.execute("SELECT id, centroid FROM concept WHERE dim=? ORDER BY id", (DIM,)).fetchall()
    if not rows:
        return None, None
    C = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float16).reshape(-1, DIM).astype(np.float32)
    return np.asarray([r[0] for r in rows]), C


def search(query: str, top: int = 3, claims_per: int = 3, db=None, timeout: float = 3.0) -> list[dict]:
    np = _np()
    own = db is None
    db = db or store.connect(readonly=True, timeout=1.0)
    try:
        ids, C = _centroids(db)
        if ids is None:
            return []
        q = embed_batch([query], "search_query: ", timeout=timeout)[0]
        sims = C @ q
        order = np.argsort(-sims)[:top]
        out = []
        for o in order:
            cid = int(ids[o])
            lab, kws, summ, size, projs = db.execute(
                "SELECT label, keywords, summary, size, projects FROM concept WHERE id=?", (cid,)).fetchone()
            # A member verified away since the clustering (UNSUPPORTED, REFUTED) is no answer.
            mem = db.execute(
                "SELECT c.id, c.text, c.status, d.path, c.anchor_line, e.vec FROM concept_member m"
                " JOIN claim c ON c.id = m.claim_id JOIN doc d ON d.id = c.doc_id"
                f" JOIN emb e ON e.claim_id = c.id WHERE m.concept_id=? AND c.status IN {GOOD}"
                " ORDER BY m.score DESC LIMIT 400", (cid,)).fetchall()
            if mem:
                V = np.frombuffer(b"".join(m[5] for m in mem), dtype=np.float16).reshape(-1, DIM).astype(np.float32)
                best = np.argsort(-(V @ q))[:claims_per]
                claims = [{"id": mem[i][0], "text": mem[i][1], "status": mem[i][2], "path": mem[i][3],
                           "line": mem[i][4], "sim": round(float(V[i] @ q), 3)} for i in best]
            else:
                claims = []
            out.append({"concept": cid, "sim": round(float(sims[o]), 3), "label": lab, "keywords": kws,
                        "summary": summ, "size": size, "projects": json.loads(projs or "{}"),
                        "claims": claims})
        return out
    finally:
        if own:
            db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cluster", action="store_true")
    ap.add_argument("--k", type=int)
    ap.add_argument("--label", action="store_true")
    ap.add_argument("--conflicts", action="store_true")
    ap.add_argument("--search")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.embed:
        print(json.dumps(build_embeddings(a.limit)))
    if a.cluster:
        print(json.dumps(cluster(a.k)))
    if a.label:
        print(json.dumps(label()))
    if a.conflicts:
        print(json.dumps(conflicts()))
    if a.search:
        for c in search(a.search):
            print(f"## [{c['sim']}] {c['label']}  ({c['size']} claim; {', '.join(list(c['projects'])[:3])})")
            for cl in c["claims"]:
                print(f"   - {cl['text'][:160]}  — {cl['path']}:{cl['line'] or '?'}  ({cl['sim']})")
    if a.stats:
        db = connect()
        live = sum(1 for _, t, sha in db.execute(
            f"SELECT e.claim_id, c.text, e.sha FROM emb e JOIN claim c ON c.id = e.claim_id"
            f" WHERE c.status IN {GOOD}") if sha == _sha(t))
        print(json.dumps({
            "embedded": db.execute("SELECT COUNT(*) FROM emb").fetchone()[0],
            "embedded_current": live,
            "concepts": db.execute("SELECT COUNT(*) FROM concept").fetchone()[0],
            "conflict_edges": db.execute("SELECT COUNT(*) FROM edge WHERE kind='conflict'").fetchone()[0],
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
