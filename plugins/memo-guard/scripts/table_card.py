#!/usr/bin/env python3
"""Table card: a deterministic memo for a table too large to be worth a model pass.

The decision behind it (2026-10-03). Staged for memo_gen, a 100k-row CSV is 600+
chunks: six GPU-hours at the measured rate. What the 8B model makes of it is
either nothing (Monte Carlo iterations) or worse than nothing. Literature-screening
rows come back as paraphrased titles and author lists, which is the exact shape
of a fabricated reference. The table is already a real SQL table in data.db
(tables.py), where every row can be queried exactly.

What search needs from the memo is a card:
- what the table is, with its columns and its size;
- the range of each numeric column and the common values of each categorical one;
- the first rows;
- which SQL table to query.

All of it is computed, nothing is generated. Every claim is anchored to a literal
snippet of the staged text, the same staging memo_gen would have read, so
verify_anchors checks a card exactly like any other memo. The card replaces the
model's memo under the same name.

  table_card.py --root ROOT --memo-dir DIR [--backup DIR] REL [REL ...]
  table_card.py --root ROOT --chunks REL [REL ...]    # staged size only, nothing written
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg                                   # noqa: E402
import tables                                         # noqa: E402
from ingest import memo_name, prep_text, staged_stem  # noqa: E402

CHUNK_LINES = 160      # memo_gen's MAX_CHUNK_LINES
MIN_CHUNKS = 100       # default threshold: at or above it a table gets a card, not a model pass
CARD_EXT = {".csv", ".tsv"}
MAX_COLS = 15
SAMPLE_ROWS = 3
SNIP = 60

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))


def staged(ab: str) -> tuple[str, str, list[str]]:
    """(staged name, sha256, lines) of the staged text, exactly as memo_gen would read it:
    written by the same prep_text, hashed from the bytes on disk, split the same way."""
    name = staged_stem(ab) + ".txt"
    with tempfile.TemporaryDirectory(prefix="mgtc_") as td:
        dst = os.path.join(td, name)
        prep_text(ab, dst)
        data = open(dst, "rb").read()
    return name, hashlib.sha256(data).hexdigest(), data.decode("utf-8", errors="replace").splitlines()


def chunks(ab: str) -> int:
    return math.ceil(len(staged(ab)[2]) / CHUNK_LINES)


def _line_map(phys: list[str]) -> tuple[list[int | None], int]:
    """For each physical line of the source: the 1-based staged line it starts on (None for a
    blank line prep_text collapsed), and the staged line count. Mirrors prep_text's loop for
    untagged text; build() refuses to anchor anything if the count disagrees with prep_text."""
    out, n, last_blank = [], 0, False
    for ln in phys:
        ln = ln.rstrip()
        if len(ln) > 120:
            w = textwrap.wrap(ln, 120, break_long_words=False, break_on_hyphens=False) or [ln]
            out.append(n + 1)
            n += len(w)
            last_blank = False
        elif ln.strip() or not (n and last_blank):
            out.append(n + 1)
            n += 1
            last_blank = not ln.strip()
        else:
            out.append(None)
    return out, n


def _rows(ab: str):
    """Header, data rows, and for each data row the 0-based physical line it starts on."""
    text = open(ab, "rb").read().decode("utf-8", errors="replace")
    phys = text.splitlines()
    delim = "\t" if ab.lower().endswith(".tsv") else None
    if delim is None:
        try:
            delim = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
        except csv.Error:
            delim = ","
    rd = csv.reader(phys, delimiter=delim)
    rows, starts = [], []
    while True:
        s = rd.line_num
        try:
            r = next(rd)
        except StopIteration:
            break
        if any(c.strip() for c in r):
            rows.append(r)
            starts.append(s)
    if not rows:
        return [], [], [], phys
    return rows[0], rows[1:], starts[1:], phys


def _clean(v: str, n: int = 80) -> str:
    v = re.sub(r"\s+", " ", (v or "").replace("`", "")).strip()
    return v if len(v) <= n else v[: n - 1].rstrip() + "…"


def _fmt(x) -> str:
    # No thousands separator: a year would read "2 010" and an identifier would stop being
    # the string anyone searches for. Counts in the claim text keep theirs.
    if isinstance(x, int) or (isinstance(x, float) and x.is_integer() and abs(x) < 1e15):
        return str(int(x))
    return f"{x:.4g}"


def _n(k: int, word: str) -> str:
    return f"{k:,} {word}" + ("" if k == 1 else "s")


def build(root: Path, rel: str, sql_table: str = "") -> tuple[str, str, dict]:
    """(memo file name, memo text, summary) for one CSV/TSV."""
    ab = str((root / rel).resolve())
    base = os.path.basename(rel.replace("\\", "/"))
    name, digest, slines = staged(ab)
    header, data, starts, phys = _rows(ab)
    lmap, total = _line_map(phys)
    if total != len(slines):
        raise RuntimeError(f"staged line map ({total}) does not match prep_text output ({len(slines)})")
    snip_lines = [l.replace("`", "") for l in slines]

    def anchor_of_phys(i: int) -> tuple[int, str] | None:
        while 0 <= i < len(lmap) and lmap[i] is None:
            i += 1
        if not (0 <= i < len(lmap)):
            return None
        ln = lmap[i]
        s = snip_lines[ln - 1].strip()[:SNIP].strip()
        return (ln, s) if s else None

    width = max([len(header)] + [len(r) for r in data[:5000]]) if header else 0
    heads = tables._headers(header, width) if header else []
    claims = []

    def add(text: str, anchor):
        if anchor:
            claims.append({"text": _clean(text, 400), "line": anchor[0], "snip": anchor[1]})

    shown = heads[:MAX_COLS]
    more = f", and {len(heads) - MAX_COLS} more" if len(heads) > MAX_COLS else ""
    where = f"; the full table is SQL table {sql_table} in the memo-guard table store" if sql_table else ""
    add(f"{base} is a table of {len(data):,} data rows and {len(heads)} columns: "
        f"{', '.join(shown)}{more}{where}", anchor_of_phys(0))

    for ci, h in enumerate(shown):
        col = [(ri, r[ci].strip()) for ri, r in enumerate(data) if ci < len(r) and r[ci].strip()]
        if not col:
            continue
        vals = [(ri, tables._value(v)) for ri, v in col]
        num = [(ri, v) for ri, v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(num) >= 0.9 * len(col):
            lo = min(num, key=lambda t: t[1])
            hi = max(num, key=lambda t: t[1])
            med = statistics.median(v for _, v in num)
            add(f"In {base}, column '{h}' is numeric ({len(num):,} values) and ranges from "
                f"{_fmt(lo[1])} to {_fmt(hi[1])}, median {_fmt(med)}", anchor_of_phys(starts[lo[0]]))
            continue
        cnt = collections.Counter(v for _, v in col)
        top = cnt.most_common(3)
        first_row = {}
        for ri, v in col:
            first_row.setdefault(v, ri)
        if len(cnt) <= 50 or top[0][1] >= 0.05 * len(col):
            add(f"In {base}, column '{h}' has {_n(len(cnt), 'distinct value')}; most frequent: "
                + ", ".join(f"{_clean(v, 60)} ({c:,})" for v, c in top),
                anchor_of_phys(starts[first_row[top[0][0]]]))
        else:
            ri, v = col[0]
            add(f"In {base}, column '{h}' is free text with {len(cnt):,} distinct values, "
                f"e.g. \"{_clean(v, 100)}\"", anchor_of_phys(starts[ri]))

    for k in range(min(SAMPLE_ROWS, len(data))):
        pairs = [f"{heads[i] if i < len(heads) else f'col{i + 1}'}={_clean(v, 40)}"
                 for i, v in enumerate(data[k]) if v.strip()][:8]
        if pairs:
            add(f"In {base}, data row {k + 1}: " + "; ".join(pairs), anchor_of_phys(starts[k]))

    nl = len(slines)
    topic = (f"Table card (computed, no model): {base}, {len(data):,} rows x {len(heads)} columns"
             + (f", SQL table {sql_table}" if sql_table else ""))
    out = ["---", f"source: {name}", f"sha256: {digest}", f"lines: {nl}", "profile: table",
           "generator: table-card", f"cache_key: table-card-{digest[:12]}",
           f"raw_tokens_est: {max(1, sum(len(l) + 1 for l in slines) // 4)}", "verified: pending",
           "---", "", f"# {name}", "", "## Topics", f"- L1-{max(nl, 1)}: {topic}", "", "## Claims", ""]
    for i, c in enumerate(claims, 1):
        out.append(f"- [C{i}] [PENDING] {c['text']} @L{c['line']} `{c['snip']}`")
    out.append("")
    return memo_name(name), "\n".join(out), {"staged": name, "rows": len(data), "cols": len(heads),
                                             "claims": len(claims), "lines": nl}


def sql_tables(root: Path) -> dict[str, str]:
    """posix rel path -> SQL table name, from the data.db registry (empty if there is none)."""
    try:
        db = tables.connect(readonly=True)
        return {p.replace("\\", "/"): (n or f"t{i}") for i, p, n in
                db.execute("SELECT id, path, name FROM tbl WHERE sheet=''")}
    except Exception:
        return {}


def write_cards(root: Path, memo_dir: Path, rels: list[str], ms: Path | None = None,
                backup: Path | None = None, log=print) -> list[dict]:
    """Write a card per table, back up a model memo it replaces, map the staged name to the
    original, then run verify_anchors on the cards against freshly staged text."""
    import ingest
    reg = sql_tables(root)
    smap = memo_dir / "_source_map.tsv"
    known = set()
    if smap.exists():
        known = {l.split("\t", 1)[0] for l in smap.read_text(encoding="utf-8", errors="replace").splitlines()}
    res, names = [], []
    stage = Path(tempfile.mkdtemp(prefix="mgtcv_"))
    try:
        for rel in rels:
            relp = rel.replace("\\", "/")
            mname, text, info = build(root, rel, reg.get(relp, ""))
            mp = memo_dir / mname
            if mp.exists() and backup is not None:
                head = mp.read_text(encoding="utf-8", errors="replace")[:600]
                if "generator: table-card" not in head:
                    backup.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mp, backup / mname)
                    info["backed_up"] = True
            mp.write_text(text, encoding="utf-8", newline="\n")
            if info["staged"] not in known:
                with open(smap, "a", encoding="utf-8", newline="\n") as f:
                    f.write(f"{info['staged']}\t{rel}\tprep\n")
                known.add(info["staged"])
            prep_text(str((root / rel).resolve()), str(stage / info["staged"]))
            names.append(mname)
            info.update({"rel": rel, "memo": mname})
            res.append(info)
            log(f"card: {relp}  {info['rows']:,} rows x {info['cols']} cols, {info['claims']} claims")
        if ms is not None and (ms / "verify_anchors.py").exists():
            ingest._verify(memo_dir, names, stage, ms)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--memo-dir", type=Path)
    ap.add_argument("--backup", type=Path, help="copy a model-written memo here before replacing it")
    ap.add_argument("--chunks", action="store_true", help="only print the staged size in memo_gen chunks")
    ap.add_argument("rels", nargs="+")
    a = ap.parse_args()
    root = a.root.resolve()
    if a.chunks:
        for rel in a.rels:
            print(f"{chunks(str((root / rel).resolve())):>6}  {rel}")
        return 0
    cfg = mg.load_config()
    ms = Path(os.path.expanduser(cfg.get("memo_index_path", ""))) / "scripts"
    res = write_cards(root, a.memo_dir or root / ".memo", a.rels, ms=ms, backup=a.backup)
    print(json.dumps({"cards": len(res), "backed_up": sum(1 for r in res if r.get("backed_up"))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
