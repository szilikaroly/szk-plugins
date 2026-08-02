#!/usr/bin/env python3
"""Core memory blocks — the tier that is always in context, and self-edited.

Two tiers, and the difference is the point
------------------------------------------
`memory.py` is archival: many facts, retrieved only when a goal makes them
relevant, costing tokens only when they are fetched. This file is the other
tier: a handful of small labelled blocks that are ALWAYS injected, so they cost
tokens every single turn. That price buys the one thing retrieval cannot give —
the model does not have to know to go looking. User preferences and learned
workflows belong here precisely because nobody thinks to query for them.

Because they are always present, they must stay small. Every block has a hard
char_limit and edits that would overflow it are refused rather than truncated:
a silently truncated memory is a memory that lies.

The three operations are Letta's, with Letta's semantics
--------------------------------------------------------
  memory_replace(label, old_str, new_str)
      Exact string replacement. old_str MUST occur exactly once — zero matches
      or several are both errors, never a guess. This is what makes an edit
      auditable: you named the text you meant.
  memory_insert(label, new_str, line)
      Insert at a line (default: append). For adding without disturbing what is
      already there.
  memory_rethink(label, new_memory)
      Replace the whole block. For when the accumulated text has become a list
      of patches and needs reorganising into something coherent.

Why three and not one general "set": rethink rewrites history wholesale, and
that is occasionally right but usually how a careful record turns into a
confident summary of itself. Making replace and insert the cheap, obvious
operations and rethink the deliberate one is the whole design.

  blocks.py --show
  blocks.py --replace user_preferences --old "prefers tables" --new "prefers prose"
  blocks.py --insert workflows --text "Always run selftest before publishing"
  blocks.py --rethink project_context --text "$(cat new.md)"
  blocks.py --create scratch --limit 800 --description "..."

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS block (
  label       TEXT NOT NULL,
  scope       TEXT NOT NULL DEFAULT 'global',   -- 'global' or a project slug
  content     TEXT NOT NULL DEFAULT '',
  char_limit  INTEGER NOT NULL DEFAULT 1200,
  description TEXT DEFAULT '',
  created_at  REAL,
  updated_at  REAL,
  edits       INTEGER DEFAULT 0,
  PRIMARY KEY (label, scope)
);
CREATE TABLE IF NOT EXISTS block_history (
  id         INTEGER PRIMARY KEY,
  label      TEXT NOT NULL,
  scope      TEXT NOT NULL,
  op         TEXT NOT NULL,
  before     TEXT,
  after      TEXT,
  at         REAL
);
"""

# Created on first use. Deliberately few: every block here is paid for on every
# turn, so the default set has to justify itself without argument.
DEFAULTS = [
    ("user_preferences", "global", 1200,
     "How this user wants to be worked with — style, tools, standing corrections. "
     "Not facts about their projects."),
    ("workflows", "global", 1200,
     "Procedures learned by doing: the sequence that worked, the step that is "
     "always forgotten. Written as instructions to a future session."),
    ("project_context", "project", 1500,
     "What this project is, what stage it is at, what must not be broken. "
     "Scoped to the current project only."),
]


def db_path() -> Path:
    return mg.data_dir() / "memory.db"   # shares the long-term store


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(db_path(), timeout=5.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    try:
        db_path().chmod(0o600)
    except OSError:
        pass
    return db


def ensure_defaults(db: sqlite3.Connection, cwd: str) -> None:
    slug = mg.project_slug(cwd)
    now = time.time()
    for label, kind, limit, desc in DEFAULTS:
        scope = slug if kind == "project" else "global"
        db.execute(
            "INSERT INTO block (label,scope,content,char_limit,description,"
            "created_at,updated_at) VALUES (?,?,'',?,?,?,?)"
            " ON CONFLICT(label,scope) DO NOTHING",
            (label, scope, limit, desc, now, now))
    db.commit()


def _get(db: sqlite3.Connection, label: str, cwd: str) -> tuple[str, str, int] | None:
    """Return (scope, content, char_limit). Project scope wins over global."""
    slug = mg.project_slug(cwd)
    for scope in (slug, "global"):
        row = db.execute(
            "SELECT scope,content,char_limit FROM block WHERE label=? AND scope=?",
            (label, scope)).fetchone()
        if row:
            return row
    return None


def _write(db: sqlite3.Connection, label: str, scope: str, before: str,
           after: str, limit: int, op: str) -> dict:
    if len(after) > limit:
        raise ValueError(
            f"edit would make '{label}' {len(after)} chars, over its {limit} limit. "
            f"Shorten the text, or use --rethink to reorganise the whole block.")
    now = time.time()
    db.execute("UPDATE block SET content=?, updated_at=?, edits=edits+1"
               " WHERE label=? AND scope=?", (after, now, label, scope))
    db.execute("INSERT INTO block_history (label,scope,op,before,after,at)"
               " VALUES (?,?,?,?,?,?)", (label, scope, op, before, after, now))
    db.commit()
    return {"label": label, "scope": scope, "op": op,
            "chars": len(after), "limit": limit}


# --------------------------------------------------------------------------- the three ops

def memory_replace(db: sqlite3.Connection, label: str, old: str, new: str,
                   cwd: str) -> dict:
    """Exact replacement. Refuses ambiguity rather than guessing which one."""
    got = _get(db, label, cwd)
    if not got:
        raise KeyError(f"no block '{label}'")
    scope, content, limit = got
    n = content.count(old)
    if n == 0:
        raise ValueError(
            f"'{old[:60]}' does not appear in '{label}'. Run --show first and "
            f"copy the text exactly; do not include line numbers.")
    if n > 1:
        raise ValueError(
            f"'{old[:60]}' appears {n} times in '{label}'. Extend it with "
            f"surrounding text until it is unique — an ambiguous edit is not "
            f"applied on a guess.")
    return _write(db, label, scope, content, content.replace(old, new, 1),
                  limit, "replace")


def memory_insert(db: sqlite3.Connection, label: str, text: str, cwd: str,
                  line: int = -1) -> dict:
    got = _get(db, label, cwd)
    if not got:
        raise KeyError(f"no block '{label}'")
    scope, content, limit = got
    lines = content.splitlines()
    if line < 0 or line > len(lines):
        lines.append(text)
    else:
        lines.insert(line, text)
    return _write(db, label, scope, content, "\n".join(lines), limit, "insert")


def memory_rethink(db: sqlite3.Connection, label: str, new_memory: str,
                   cwd: str) -> dict:
    got = _get(db, label, cwd)
    if not got:
        raise KeyError(f"no block '{label}'")
    scope, content, limit = got
    return _write(db, label, scope, content, new_memory.strip(), limit, "rethink")


# --------------------------------------------------------------------------- render

def render(db: sqlite3.Connection, cwd: str, max_chars: int = 3000) -> str:
    """The text injected into every fresh context. Empty blocks are omitted —
    an empty heading teaches nothing and still costs tokens."""
    ensure_defaults(db, cwd)
    slug = mg.project_slug(cwd)
    rows = db.execute(
        "SELECT label,scope,content FROM block WHERE (scope=? OR scope='global')"
        " AND TRIM(content)<>'' ORDER BY scope='global' DESC, label", (slug,))
    out, spent = [], 0
    for label, scope, content in rows:
        chunk = f"### {label}" + ("" if scope == "global" else f" ({scope})") \
                + f"\n{content.strip()}"
        if spent + len(chunk) > max_chars:
            break
        out.append(chunk)
        spent += len(chunk)
    return "\n\n".join(out)


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--replace", metavar="LABEL")
    ap.add_argument("--old"), ap.add_argument("--new")
    ap.add_argument("--insert", metavar="LABEL")
    ap.add_argument("--rethink", metavar="LABEL")
    ap.add_argument("--text", default="")
    ap.add_argument("--line", type=int, default=-1)
    ap.add_argument("--create", metavar="LABEL")
    ap.add_argument("--limit", type=int, default=1200)
    ap.add_argument("--description", default="")
    ap.add_argument("--scope", default="")
    ap.add_argument("--history", metavar="LABEL")
    ap.add_argument("--cwd", default=str(Path.cwd()))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = connect()
    ensure_defaults(db, args.cwd)

    try:
        if args.replace:
            if args.old is None or args.new is None:
                print("--replace needs --old and --new", file=sys.stderr)
                return 2
            r = memory_replace(db, args.replace, args.old, args.new, args.cwd)
        elif args.insert:
            r = memory_insert(db, args.insert, args.text, args.cwd, args.line)
        elif args.rethink:
            r = memory_rethink(db, args.rethink, args.text, args.cwd)
        elif args.create:
            scope = args.scope or mg.project_slug(args.cwd)
            now = time.time()
            db.execute("INSERT INTO block (label,scope,content,char_limit,"
                       "description,created_at,updated_at) VALUES (?,?,'',?,?,?,?)"
                       " ON CONFLICT(label,scope) DO NOTHING",
                       (args.create, scope, args.limit, args.description, now, now))
            db.commit()
            r = {"label": args.create, "scope": scope, "op": "create",
                 "limit": args.limit}
        else:
            r = None
    except (KeyError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1

    if r:
        print(json.dumps(r) if args.json else
              f"{r['op']}: {r['label']} [{r['scope']}] "
              f"{r.get('chars', 0)}/{r.get('limit')} chars")
        return 0

    if args.render:
        print(render(db, args.cwd))
        return 0

    if args.history:
        rows = db.execute(
            "SELECT op,at,length(before),length(after) FROM block_history"
            " WHERE label=? ORDER BY at DESC LIMIT 15", (args.history,))
        for op, at, lb, la in rows:
            print(f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(at))}  "
                  f"{op:<8} {lb or 0} -> {la or 0} chars")
        return 0

    slug = mg.project_slug(args.cwd)
    rows = list(db.execute(
        "SELECT label,scope,content,char_limit,description,edits FROM block"
        " WHERE scope=? OR scope='global' ORDER BY scope='global' DESC, label",
        (slug,)))
    if args.json:
        print(json.dumps([{"label": r[0], "scope": r[1], "content": r[2],
                           "limit": r[3], "edits": r[5]} for r in rows], indent=2))
        return 0
    for label, scope, content, limit, desc, edits in rows:
        used = len(content)
        bar = "#" * round(20 * min(1.0, used / limit))
        print(f"\n### {label}  [{scope}]  {used}/{limit} [{bar:<20}] edits={edits}")
        if desc:
            print(f"    ({desc})")
        print(content.strip() or "    (empty)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
