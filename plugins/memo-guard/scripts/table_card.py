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
CARD_EXT = {".csv", ".tsv", ".xlsx"}
MAX_COLS = 15
SAMPLE_ROWS = 3
ROW_CLAIMS_MAX = 60    # a table this small gets every row as a claim (the no-claims fallback)
SNIP = 60

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))


def _memo_index_scripts() -> Path:
    return Path(os.path.expanduser(mg.load_config().get("memo_index_path", ""))) / "scripts"


def _stage_into(ab: str, outdir: str) -> str:
    """Write the staged text exactly as the batch runs do: prep_text for CSV/TSV, memo-index's
    doc_ingest for a workbook (one markdown table per sheet). Returns the staged file path."""
    name = staged_stem(ab) + ".txt"
    if ab.lower().endswith(".xlsx"):
        import subprocess
        subprocess.run([sys.executable, str(_memo_index_scripts() / "doc_ingest.py"), "--outdir",
                        outdir, "--no-images", ab], capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONUTF8="1"), timeout=1800)
    else:
        prep_text(ab, os.path.join(outdir, name))
    return os.path.join(outdir, name)


def staged(ab: str) -> tuple[str, str, list[str]]:
    """(staged name, sha256, lines) of the staged text, exactly as memo_gen would read it:
    written by the same staging, hashed from the bytes on disk, split the same way."""
    name = staged_stem(ab) + ".txt"
    with tempfile.TemporaryDirectory(prefix="mgtc_") as td:
        dst = _stage_into(ab, td)
        if not os.path.exists(dst):
            raise RuntimeError(f"staging produced nothing for {ab}")
        data = open(dst, "rb").read()
    return name, hashlib.sha256(data).hexdigest(), data.decode("utf-8", errors="replace").splitlines()


def chunks(ab: str) -> int:
    return math.ceil(len(staged(ab)[2]) / CHUNK_LINES)


def file_chunks(path) -> int:
    """memo_gen chunks in an already staged file, split as memo_gen splits it (splitlines,
    not file iteration: the two disagree on a stray \\r or \\x0c)."""
    with open(path, "rb") as fh:
        return math.ceil(len(fh.read().decode("utf-8", errors="replace").splitlines()) / CHUNK_LINES)


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
    if len(v) <= n:
        return v
    cut = v[: n - 1]
    # End on a whole token: a PMID list cut mid-number ("4239616…") reads as a different
    # identifier. Only a word that fills the whole window is cut hard.
    sp = cut.rfind(" ")
    return (cut[:sp] if sp >= n // 2 else cut).rstrip() + "…"


def _fmt(x) -> str:
    # No thousands separator: a year would read "2 010" and an identifier would stop being
    # the string anyone searches for. Counts in the claim text keep theirs.
    if isinstance(x, int) or (isinstance(x, float) and x.is_integer() and abs(x) < 1e15):
        return str(int(x))
    return f"{x:.4g}"


def _n(k: int, word: str) -> str:
    return f"{k:,} {word}" + ("" if k == 1 else "s")


def _row_range(nrows: int) -> range:
    """Which data rows become claims: all of a small table (a result table's rows ARE its
    findings), the first SAMPLE_ROWS of a big one."""
    return range(nrows if nrows <= ROW_CLAIMS_MAX else SAMPLE_ROWS)


def _pairs(heads: list[str], row: list[str], nrows: int) -> list[str]:
    """'column=value' for a row's non-empty cells; a small table's rows keep every column
    and longer values, since such a row is usually one finding read across."""
    small = nrows <= ROW_CLAIMS_MAX
    return [f"{heads[i] if i < len(heads) else f'col{i + 1}'}={_clean(v, 80 if small else 40)}"
            for i, v in enumerate(row) if v.strip()][:MAX_COLS if small else 8]


_SEP_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?$")
# '## name' (doc_ingest's stdlib reader), '=== name (N rows) ===' (doc-tools' xlstotext -f md,
# which names sheets only when there are several), or any other '#' heading.
_SHEET_HEAD_RE = re.compile(r"^(?:#{1,6}\s+(?P<h>.+?)|===\s*(?P<x>.*?)\s*\(\d+ rows\)\s*===)\s*$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _md_sheets(slines: list[str]) -> list[dict]:
    """The markdown tables of a staged workbook: header, separator, then one data row per
    line up to the next blank line. Two dialects reach here: doc_ingest's stdlib reader
    ('| a | b |', '|---|---|'; '|' in a cell already turned into '/') and, where doc-tools
    is on PATH, xlstotext ('a | b', '--- | ---'). A sheet's name is the heading just above
    its table, '' when there is none. Line numbers are 1-based staged lines, so a row's
    anchor is its own line."""
    out, i, n = [], 0, len(slines)
    while i < n:
        if slines[i].strip() and i + 1 < n and _SEP_RE.match(slines[i + 1].strip()):
            name = ""
            for k in range(i - 1, max(-1, i - 3), -1):
                if slines[k].strip():
                    m = _SHEET_HEAD_RE.match(slines[k].strip())
                    name = (m.group("h") or m.group("x") or "").strip() if m else ""
                    break
            sh = {"name": name, "head_line": i + 1, "header": _cells(slines[i]), "rows": [], "lines": []}
            j = i + 2
            while j < n and slines[j].strip():
                sh["rows"].append(_cells(slines[j]))
                sh["lines"].append(j + 1)
                j += 1
            out.append(sh)
            i = j
        else:
            i += 1
    return out


def _column_claims(base: str, heads: list[str], data: list[list[str]], anchor_row, add) -> None:
    """Range/median for a numeric column, frequent values for a categorical one, an example
    for free text; each anchored to the row it speaks about."""
    for ci, h in enumerate(heads[:MAX_COLS]):
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
                f"{_fmt(lo[1])} to {_fmt(hi[1])}, median {_fmt(med)}", anchor_row(lo[0]))
            continue
        cnt = collections.Counter(v for _, v in col)
        top = cnt.most_common(3)
        first_row = {}
        for ri, v in col:
            first_row.setdefault(v, ri)
        if top[0][1] == 1 and len(cnt) <= 50:
            # a small table's label column: "most frequent: x (1), y (1)" would say nothing
            ri, v = col[0]
            add(f"In {base}, column '{h}' has {_n(len(cnt), 'distinct value')}, each once, "
                f"e.g. \"{_clean(v, 100)}\"", anchor_row(ri))
        elif len(cnt) <= 50 or top[0][1] >= 0.05 * len(col):
            add(f"In {base}, column '{h}' has {_n(len(cnt), 'distinct value')}; most frequent: "
                + ", ".join(f"{_clean(v, 60)} ({c:,})" for v, c in top),
                anchor_row(first_row[top[0][0]]))
        else:
            ri, v = col[0]
            add(f"In {base}, column '{h}' is free text with {len(cnt):,} distinct values, "
                f"e.g. \"{_clean(v, 100)}\"", anchor_row(ri))


def build_xlsx(root: Path, rel: str, sql: dict) -> tuple[str, str, dict]:
    """Card for a workbook: per sheet its size and columns, column statistics and first rows
    of the largest sheet, every claim anchored to its own markdown row in the staged text."""
    ab = str((root / rel).resolve())
    base = os.path.basename(rel.replace("\\", "/"))
    name, digest, slines = staged(ab)
    sheets = _md_sheets(slines)
    if not sheets:
        raise RuntimeError("no markdown table found in the staged workbook")
    snip = [l.replace("`", "") for l in slines]
    claims = []

    def add(text, anchor):
        if anchor:
            claims.append({"text": _clean(text, 400), "line": anchor[0], "snip": anchor[1]})

    def at(line):
        s = snip[line - 1].strip()[:SNIP].strip()
        return (line, s) if s else None

    for k, sh in enumerate(sheets, 1):
        # xlstotext leaves a lone sheet unnamed: say "sheet 1" rather than invent a name
        sh["label"] = f"sheet '{sh['name']}'" if sh["name"] else f"sheet {k}"
    for sh in sheets[:8]:
        heads = tables._headers(sh["header"], max([len(sh["header"])] + [len(r) for r in sh["rows"][:5000]]))
        tname = sql.get(sh["name"], "") if sh["name"] else \
            (next(iter(sql.values())) if len(sql) == 1 and len(sheets) == 1 else "")
        add(f"{base}, {sh['label']}, is a table of {len(sh['rows']):,} data rows and {len(heads)} "
            f"columns: {', '.join(heads[:MAX_COLS])}"
            + (f", and {len(heads) - MAX_COLS} more" if len(heads) > MAX_COLS else "")
            + (f"; the full sheet is SQL table {tname} in the memo-guard table store" if tname else ""),
            at(sh["head_line"]))
    big = max(sheets, key=lambda s: len(s["rows"]))
    heads = tables._headers(big["header"], max([len(big["header"])] + [len(r) for r in big["rows"][:5000]]))
    _column_claims(f"{base} ({big['label']})", heads, big["rows"], lambda ri: at(big["lines"][ri]), add)
    for k in _row_range(len(big["rows"])):
        pairs = _pairs(heads, big["rows"][k], len(big["rows"]))
        if pairs:
            add(f"In {base} ({big['label']}), data row {k + 1}: " + "; ".join(pairs), at(big["lines"][k]))
    nl = len(slines)
    nrows = sum(len(s["rows"]) for s in sheets)
    topic = f"Table card (computed, no model): {base}, {len(sheets)} sheet(s), {nrows:,} rows"
    return memo_name(name), _render(name, digest, slines, topic, claims), {
        "staged": name, "rows": nrows, "cols": len(heads), "claims": len(claims), "lines": nl}


def _render(name: str, digest: str, slines: list[str], topic: str, claims: list[dict]) -> str:
    nl = len(slines)
    out = ["---", f"source: {name}", f"sha256: {digest}", f"lines: {nl}", "profile: table",
           "generator: table-card", f"cache_key: table-card-{digest[:12]}",
           f"raw_tokens_est: {max(1, sum(len(l) + 1 for l in slines) // 4)}", "verified: pending",
           "---", "", f"# {name}", "", "## Topics", f"- L1-{max(nl, 1)}: {topic}", "", "## Claims", ""]
    for i, c in enumerate(claims, 1):
        out.append(f"- [C{i}] [PENDING] {c['text']} @L{c['line']} `{c['snip']}`")
    out.append("")
    return "\n".join(out)


def build(root: Path, rel: str, sql_table="") -> tuple[str, str, dict]:
    """(memo file name, memo text, summary) for one CSV/TSV, or a workbook (sql_table is then
    a {sheet: table} dict)."""
    if rel.lower().endswith(".xlsx"):
        return build_xlsx(root, rel, sql_table if isinstance(sql_table, dict) else {})
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

    _column_claims(base, heads, data, lambda ri: anchor_of_phys(starts[ri]), add)

    for k in _row_range(len(data)):
        pairs = _pairs(heads, data[k], len(data))
        if pairs:
            add(f"In {base}, data row {k + 1}: " + "; ".join(pairs), anchor_of_phys(starts[k]))

    nl = len(slines)
    topic = (f"Table card (computed, no model): {base}, {len(data):,} rows x {len(heads)} columns"
             + (f", SQL table {sql_table}" if sql_table else ""))
    return memo_name(name), _render(name, digest, slines, topic, claims), {
        "staged": name, "rows": len(data), "cols": len(heads), "claims": len(claims), "lines": nl}


def sql_tables(root: Path) -> dict:
    """posix rel path -> SQL table name for a CSV/TSV, or {sheet: name} for a workbook, from
    the data.db registry (empty if there is none)."""
    out: dict = {}
    try:
        db = tables.connect(readonly=True)
        for i, p, sheet, n in db.execute("SELECT id, path, sheet, name FROM tbl"):
            key = p.replace("\\", "/")
            if sheet:
                out.setdefault(key, {})[sheet] = n or f"t{i}"
            else:
                out[key] = n or f"t{i}"
    except Exception:
        pass
    return out


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
            mname, text, info = build(root, rel, reg.get(relp, {} if relp.lower().endswith(".xlsx") else ""))
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
                    mode = "ingest" if relp.lower().endswith(".xlsx") else "prep"
                    f.write(f"{info['staged']}\t{rel}\t{mode}\n")
                known.add(info["staged"])
            _stage_into(str((root / rel).resolve()), str(stage))
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
