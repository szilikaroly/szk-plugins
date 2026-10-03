#!/usr/bin/env python3
"""Every table in the corpus roots as a real SQL table: data_dir()/data.db.

Why: a CSV row is already a fact with columns. Memoizing it through a local LLM costs GPU
hours and yields a paraphrase (2026-09-29: 111 CSVs gave 0 claims; tordelve 13-74 per
file, mostly "trivial/dupe dropped"). As a table it is exact and answers questions like
"which of my corpora contain this DOI" with one SQL query, no model at all.

  - One SQL table per CSV/TSV file and per XLSX sheet, named t<id>; the registry `tbl`
    keeps the source path, sheet, original headers and row count.
  - Cells that are unambiguously numbers are stored as numbers ("33,2" -> 33.2 too: the
    corpus is half Hungarian); everything else stays text exactly as written.
  - rows_fts: one full-text row per data row ("col=value; ...") for tables that are mostly
    text. Numeric-only tables (simulation output, PSA iterations) are imported but not
    full-text indexed: their rows match nothing a person would type.
  - Incremental by (mtime, size), then sha256: unchanged files are not re-read.
  - Queries go through a read-only connection with query_only on; nothing here can write
    to a table through --sql.

  tables.py --sync [--root PATH]
  tables.py --find "text" [--limit N]
  tables.py --sql "SELECT ..."
  tables.py --list [PATTERN]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mg_lib as mg  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
TABLE_EXT = {".csv", ".tsv", ".xlsx"}
SKIP = re.compile(r"(/\.git/|/node_modules/|/__pycache__/|/\.venv/|/venv/|/site-packages/|"
                  r"/\.cache/|/\.memo/|/_stage[^/]*/)", re.I)
NUM = re.compile(r"^[+-]?(\d+|\d{1,3}( \d{3})+)([.,]\d+)?([eE][+-]?\d+)?%?$")
MAX_COLS = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS tbl (
  id INTEGER PRIMARY KEY, root TEXT NOT NULL, path TEXT NOT NULL, sheet TEXT NOT NULL DEFAULT '',
  name TEXT, columns TEXT, nrows INTEGER DEFAULT 0, numeric_share REAL, fts INTEGER DEFAULT 0,
  src_sha TEXT, src_mtime REAL, src_size INTEGER, imported_at REAL, error TEXT,
  UNIQUE(root, path, sheet));
CREATE VIRTUAL TABLE IF NOT EXISTS rows_fts USING fts5(
  text, tbl UNINDEXED, rownum UNINDEXED, tokenize='unicode61 remove_diacritics 2');
"""


def db_path() -> Path:
    return mg.data_dir() / "data.db"


def connect(readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        db = sqlite3.connect(f"file:{db_path().as_posix()}?mode=ro", uri=True, timeout=2.0)
        db.execute("PRAGMA query_only=ON")
        return db
    db = sqlite3.connect(db_path(), timeout=10.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(SCHEMA)
    mg.secure_file(db_path())
    return db


# --------------------------------------------------------------------------- readers

def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_csv(path: Path) -> list[tuple[str, list[list[str]]]]:
    text = _decode(path.read_bytes())
    sample = text[:20000]
    delim = "\t" if path.suffix.lower() == ".tsv" else None
    if delim is None:
        try:
            delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delim = ","
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
    return [("", rows)]


_SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_DOC_RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_xlsx(path: Path) -> list[tuple[str, list[list[str]]]]:
    """Same stdlib reader as doc_ingest._xlsx_text, returning cells instead of markdown."""
    import zipfile
    from xml.etree import ElementTree as ET

    def col(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group(0):
            n = n * 26 + ord(ch) - 64
        return n - 1

    out = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_SS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_SS + "t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(_PKG_REL + "Relationship"):
                t = r.get("Target", "")
                rels[r.get("Id")] = t.lstrip("/") if t.startswith("/") else "xl/" + t
        sheets = []
        if "xl/workbook.xml" in names:
            for s in ET.fromstring(z.read("xl/workbook.xml")).iter(_SS + "sheet"):
                sheets.append((s.get("name"), rels.get(s.get(_DOC_RID))))
        for name, target in sheets:
            if not target or target not in names:
                continue
            rows = []
            for row in ET.fromstring(z.read(target)).iter(_SS + "row"):
                cells = {}
                for c in row.iter(_SS + "c"):
                    t, v = c.get("t"), c.find(_SS + "v")
                    if t == "s" and v is not None:
                        val = shared[int(v.text)]
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(_SS + "t"))
                    elif v is not None:
                        val = v.text or ""
                    else:
                        continue
                    ref = c.get("r")
                    cells[col(ref) if ref else len(cells)] = val
                if any(str(v).strip() for v in cells.values()):
                    width = max(cells) + 1
                    rows.append([cells.get(i, "") for i in range(width)])
            out.append((name or "", rows))
    return out


def _value(cell: str):
    s = (cell or "").strip()
    if s and NUM.match(s) and not (len(s) > 1 and s[0] == "0" and s[1].isdigit()):
        t = s.rstrip("%").replace(" ", "")
        if "," in t and "." not in t:
            t = t.replace(",", ".")
        try:
            return int(t) if re.fullmatch(r"[+-]?\d+", t) else float(t)
        except ValueError:
            return s
    return cell


def _headers(first: list[str], width: int) -> list[str]:
    out, seen = [], {}
    for i in range(width):
        h = re.sub(r"\s+", " ", (first[i] if i < len(first) else "") or "").strip()[:60] or f"col{i + 1}"
        k = h.lower()
        if k in seen:
            seen[k] += 1
            h = f"{h}_{seen[k]}"
        else:
            seen[k] = 1
        out.append(h)
    return out


# --------------------------------------------------------------------------- import

def _drop(db: sqlite3.Connection, tid: int) -> None:
    db.execute(f'DROP TABLE IF EXISTS "t{tid}"')
    db.execute("DELETE FROM rows_fts WHERE tbl=?", (tid,))


def import_file(db: sqlite3.Connection, root: Path, path: Path) -> list[dict]:
    rel = path.relative_to(root).as_posix()
    st = path.stat()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        sheets = read_xlsx(path) if path.suffix.lower() == ".xlsx" else read_csv(path)
        err = None
    except Exception as e:
        sheets, err = [], f"{type(e).__name__}: {str(e)[:160]}"
    old = {r[0]: r[1] for r in db.execute("SELECT sheet, id FROM tbl WHERE root=? AND path=?",
                                           (str(root), rel))}
    for sheet, tid in old.items():
        _drop(db, tid)
    db.execute("DELETE FROM tbl WHERE root=? AND path=?", (str(root), rel))
    if err or not sheets:
        db.execute("INSERT INTO tbl (root, path, sheet, src_sha, src_mtime, src_size, imported_at, error)"
                   " VALUES (?,?,?,?,?,?,?,?)", (str(root), rel, "", sha, st.st_mtime, st.st_size,
                                                 time.time(), err or "no rows"))
        return []
    out = []
    for sheet, rows in sheets:
        if not rows:
            continue
        width = min(MAX_COLS, max(len(r) for r in rows))
        cols = _headers(rows[0], width)
        data = [[_value(r[i]) if i < len(r) else None for i in range(width)] for r in rows[1:]]
        cells = [v for r in data for v in r if v not in (None, "")]
        numeric = (sum(isinstance(v, (int, float)) for v in cells) / len(cells)) if cells else 0.0
        cur = db.execute(
            "INSERT INTO tbl (root, path, sheet, columns, nrows, numeric_share, src_sha, src_mtime,"
            " src_size, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(root), rel, sheet, json.dumps(cols, ensure_ascii=False), len(data),
             round(numeric, 3), sha, st.st_mtime, st.st_size, time.time()))
        tid = cur.lastrowid
        name = f"t{tid}"
        db.execute(f'CREATE TABLE "{name}" ({", ".join(chr(34) + c.replace(chr(34), "") + chr(34) for c in cols)})')
        db.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * width)})', data)
        fts = numeric < 0.8
        if fts:
            db.executemany(
                "INSERT INTO rows_fts (text, tbl, rownum) VALUES (?,?,?)",
                [("; ".join(f"{cols[i]}={v}" for i, v in enumerate(r) if v not in (None, "")), tid, n + 1)
                 for n, r in enumerate(data)])
        db.execute("UPDATE tbl SET name=?, fts=? WHERE id=?", (name, int(fts), tid))
        out.append({"path": rel, "sheet": sheet, "table": name, "rows": len(data),
                    "cols": width, "numeric": round(numeric, 2), "fts": fts})
    return out


def sync_root(root: Path, log=print) -> dict:
    root = Path(os.path.expanduser(str(root))).resolve()
    db = connect()
    t0 = time.time()
    known = {}
    for path, mtime, size in db.execute(
            "SELECT path, MAX(src_mtime), MAX(src_size) FROM tbl WHERE root=? GROUP BY path", (str(root),)):
        known[path] = (mtime, size)
    seen, imported, failed, tables_n = set(), 0, 0, 0
    for dp, dn, fn in os.walk(root):
        dpp = dp.replace("\\", "/") + "/"
        dn[:] = [d for d in dn if not SKIP.search(dpp + d + "/")]
        for f in fn:
            if os.path.splitext(f)[1].lower() not in TABLE_EXT:
                continue
            p = Path(dp) / f
            rel = p.relative_to(root).as_posix()
            seen.add(rel)
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size < 50 or known.get(rel) == (st.st_mtime, st.st_size):
                continue
            res = import_file(db, root, p)
            if res:
                imported += 1; tables_n += len(res)
            else:
                failed += 1
            if (imported + failed) % 50 == 0:
                db.commit()
                log(f"  ... {imported + failed} fajl")
    gone = [p for p in known if p not in seen]
    for rel in gone:
        for (tid,) in db.execute("SELECT id FROM tbl WHERE root=? AND path=?", (str(root), rel)).fetchall():
            _drop(db, tid)
        db.execute("DELETE FROM tbl WHERE root=? AND path=?", (str(root), rel))
    db.commit()
    res = {"root": str(root), "files_imported": imported, "tables": tables_n, "failed": failed,
           "removed": len(gone), "seconds": round(time.time() - t0, 1)}
    mg.append_metrics({"ts": time.time(), **res}, event="tables_sync")
    return res


# --------------------------------------------------------------------------- query

def find(text: str, limit: int = 10) -> list[dict]:
    terms = mg.terms(text, min_len=2)[:10]
    if not terms:
        return []
    db = connect(readonly=True)
    try:
        q = " AND ".join(f'"{t}"' for t in terms)
        out = []
        for tid, rownum, row, b in db.execute(
                "SELECT tbl, rownum, text, bm25(rows_fts) FROM rows_fts WHERE rows_fts MATCH ?"
                " ORDER BY bm25(rows_fts) LIMIT ?", (q, limit)):
            path, sheet, name = db.execute("SELECT path, sheet, name FROM tbl WHERE id=?", (tid,)).fetchone()
            out.append({"table": name, "path": path, "sheet": sheet, "row": rownum, "text": row[:400]})
        return out
    finally:
        db.close()


def sql(query: str, limit: int = 200) -> tuple[list[str], list[tuple]]:
    db = connect(readonly=True)
    try:
        cur = db.execute(query)
        cols = [d[0] for d in cur.description or []]
        return cols, cur.fetchmany(limit)
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--root", action="append")
    ap.add_argument("--find")
    ap.add_argument("--sql")
    ap.add_argument("--list", nargs="?", const="")
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    cfg = mg.load_config()
    if a.sync:
        roots = a.root or cfg.get("corpus_roots") or []
        if not roots:
            print("no corpus_roots configured and no --root given")
            return 1
        for r in roots:
            print(json.dumps(sync_root(Path(r)), ensure_ascii=False))
        return 0
    if a.find:
        for h in find(a.find, a.limit):
            print(f"- {h['table']}  {h['path']}{(' [' + h['sheet'] + ']') if h['sheet'] else ''}  sor {h['row']}\n    {h['text'][:300]}")
        return 0
    if a.sql:
        cols, rows = sql(a.sql, a.limit)
        print("\t".join(cols))
        for r in rows:
            print("\t".join("" if v is None else str(v) for v in r))
        return 0
    if a.list is not None:
        db = connect(readonly=True)
        pat = f"%{a.list}%"
        for name, path, sheet, n, cols in db.execute(
                "SELECT name, path, sheet, nrows, columns FROM tbl WHERE error IS NULL AND path LIKE ?"
                " ORDER BY path LIMIT ?", (pat, a.limit)):
            print(f"{name:7s} {n:7d} sor  {path}{(' [' + sheet + ']') if sheet else ''}\n         {', '.join(json.loads(cols)[:12])}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
