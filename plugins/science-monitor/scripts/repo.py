#!/usr/bin/env python3
"""Shared data repo: the registry and the documents, in git.

The local SQLite store stays the working copy — fast, and the dashboard writes
to it directly. Git holds the shareable truth in a form that actually merges:

    sm-repo.json              schema version + which roles are synced
    projects/<slug>.json      one file per manuscript — project, submissions,
                              checklist, reviews, review points, file index
    documents/<sha2>/<name>   the documents themselves, content-addressed
    README.md .gitignore .gitattributes

One file per project is the whole merge strategy: two co-authors working on
different manuscripts never touch the same file, so git never asks. Within a
file the JSON is sorted and pretty-printed, so a real conflict is readable.

Documents are content-addressed, so the six copies of the same `.docx` that
accumulate in a Downloads folder are stored once.

Files whose role is not synced (figures, datasets, session transcripts) are
recorded with the machine they live on, so a co-author sees "not on this
machine" instead of a path that silently does not exist.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm_lib as L  # noqa: E402

SCHEMA = "science-monitor.data-repo/1"

README = """# Science Monitor — közös nyilvántartás

Ezt a mappát a [science-monitor](https://github.com/) plugin kezeli.
Ne szerkeszd kézzel, hacsak nem konfliktust oldasz fel.

## ⚠ Ez a repo legyen PRIVÁT

Kiadatlan kéziratokat, cover lettereket, bírálói leveleket és folyóirati
azonosítókat tartalmaz. Nyilvános remote-ra soha ne kerüljön.

## Használat

```bash
sm.py repo pull     # git pull, majd a repo betöltése a helyi adatbázisba
sm.py repo push     # a helyi adatbázis kiírása, commit, majd push ha van remote
sm.py repo status   # mi tér el
```

## Szerkezet

| Útvonal | Mit tartalmaz |
|---|---|
| `sm-repo.json` | séma-verzió, szinkronizált szerepek |
| `projects/<slug>.json` | egy kézirat mindene: beadások, checklist, bírálatok, pontok |
| `documents/<hash>/<fájlnév>` | a dokumentumok, tartalom szerint címezve |

Kéziratonként külön fájl, hogy két szerző párhuzamos munkája ne ütközzön.

## Konfliktus

Ha a git egy `projects/*.json`-t megjelöl: a fájl rendezett és tördelt, a
konfliktus emberi szemmel olvasható. Oldd fel, majd `sm.py repo pull`.
"""

GITIGNORE = """.DS_Store
*.tmp
"""

GITATTRIBUTES = """*.json  text eol=lf
*.md    text eol=lf
*.docx  binary
*.pdf   binary
*.doc   binary
*.odt   binary
"""


# --- git ---------------------------------------------------------------------

def git(repo, *args, check=True, quiet=False):
    proc = subprocess.run(["git", "-C", repo, *args],
                          capture_output=True, text=True, encoding="utf-8")
    if check and proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"git {' '.join(args)}: {msg}")
    if not quiet and proc.stdout.strip():
        print(proc.stdout.rstrip())
    return proc


def has_remote(repo):
    return bool(git(repo, "remote", check=False, quiet=True).stdout.strip())


# --- serialisation -----------------------------------------------------------

def _row(row, drop=()):
    return {k: row[k] for k in row.keys() if k not in drop}


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def stash(path, repo, copied):
    """Copy a file into the repo under its content hash; return the rel path."""
    if not path or not os.path.exists(path):
        return ""
    digest = sha256(path)
    rel = os.path.join("documents", digest[:2], digest[2:16], os.path.basename(path))
    dest = os.path.join(repo, rel)
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)
        copied.append(rel)
    return rel.replace(os.sep, "/")


def export_project(conn, p, repo, sync_roles, machine, copied):
    """Serialise one project, copying its synced documents into the repo."""
    doc = {
        "schema": SCHEMA,
        "project": _row(p, drop=("id", "root_path")),
        "submissions": [],
        "files": [],
    }
    # root_path is machine-specific; keep it as a hint, not as truth.
    doc["project"]["root_path_hint"] = {"machine": machine, "path": p["root_path"]}

    for f in L.files_of(conn, p["id"]):
        entry = {"role": f["role"], "label": f["label"],
                 "name": os.path.basename(f["path"])}
        if f["role"] in sync_roles and os.path.exists(f["path"]):
            entry["repo_path"] = stash(f["path"], repo, copied)
        else:
            entry["local"] = {"machine": machine, "path": f["path"]}
        doc["files"].append(entry)
    doc["files"].sort(key=lambda e: (e["role"], e["name"]))

    for s in L.submissions_of(conn, p["id"]):
        sub = _row(s, drop=("id", "project_id"))
        sub["cover_letter_name"] = os.path.basename(s["cover_letter_path"] or "")
        sub.pop("cover_letter_path", None)
        sub["checklist"] = [_row(c, drop=("id", "submission_id"))
                            for c in L.checklist_of(conn, s["id"])]
        sub["reviews"] = []
        for rv in L.all_reviews(conn, s["id"]):
            review = _row(rv, drop=("id", "submission_id", "project_id", "journal",
                                    "slug", "title"))
            # The reviewer letter travels with the review — it is small, it is
            # text, and a co-author cannot answer points without it.
            review["letter_name"] = os.path.basename(rv["letter_path"] or "")
            review["letter_repo_path"] = stash(rv["letter_path"], repo, copied)
            review.pop("letter_path", None)
            review["points"] = [
                _row(pt, drop=("id", "review_id"))
                for pt in conn.execute(
                    "SELECT * FROM review_points WHERE review_id = ? "
                    "ORDER BY reviewer, idx", (rv["id"],))]
            sub["reviews"].append(review)
        doc["submissions"].append(sub)

    doc["events"] = [
        _row(e, drop=("id", "project_id", "submission_id"))
        for e in conn.execute(
            "SELECT * FROM events WHERE project_id = ? ORDER BY at, id", (p["id"],))]
    return doc


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


# --- commands ----------------------------------------------------------------

def cmd_init(conn, path):
    repo = os.path.abspath(os.path.expanduser(path))
    os.makedirs(repo, exist_ok=True)
    if not os.path.isdir(os.path.join(repo, ".git")):
        git(repo, "init", quiet=True)
        print(f"git repo létrehozva: {repo}")
    for name, body in (("README.md", README), (".gitignore", GITIGNORE),
                       (".gitattributes", GITATTRIBUTES)):
        target = os.path.join(repo, name)
        if not os.path.exists(target):
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(body)
    write_json(os.path.join(repo, "sm-repo.json"),
               {"schema": SCHEMA, "sync_roles": L.load_config()["sync_roles"]})
    cfg = L.load_config()
    cfg["data_repo"] = repo
    L.save_config(cfg)
    print(f"beállítva adat-repónak: {repo}")
    print("\n⚠ Ez a repo kiadatlan kéziratokat fog tartalmazni — tartsd privátnak.")
    print("Remote hozzáadása:  git -C '%s' remote add origin <PRIVÁT-URL>" % repo)


def _repo_path(explicit=None):
    repo = explicit or L.load_config().get("data_repo")
    if not repo:
        L.die("nincs beállítva adat-repo — `sm.py repo init ~/science-monitor-data`")
    repo = os.path.abspath(os.path.expanduser(repo))
    if not os.path.isdir(os.path.join(repo, ".git")):
        L.die(f"nem git repo: {repo}")
    return repo


def cmd_push(conn, repo_path=None, message=None, do_push=True):
    repo = _repo_path(repo_path)
    cfg = L.load_config()
    sync_roles = set(cfg["sync_roles"])
    machine = cfg["machine"]

    projects = conn.execute("SELECT * FROM projects ORDER BY slug").fetchall()
    proj_dir = os.path.join(repo, "projects")
    os.makedirs(proj_dir, exist_ok=True)
    wanted = set()
    copied = []
    for p in projects:
        doc = export_project(conn, p, repo, sync_roles, machine, copied)
        name = f"{p['slug']}.json"
        wanted.add(name)
        write_json(os.path.join(proj_dir, name), doc)
    # A project deleted locally should disappear from the repo too.
    for stale in sorted(set(os.listdir(proj_dir)) - wanted):
        if stale.endswith(".json"):
            os.remove(os.path.join(proj_dir, stale))
            print(f"  törölve: projects/{stale}")

    write_json(os.path.join(repo, "sm-repo.json"),
               {"schema": SCHEMA, "sync_roles": sorted(sync_roles)})

    print(f"{len(projects)} kézirat kiírva, {len(copied)} új dokumentum másolva")
    git(repo, "add", "-A", quiet=True)
    status = git(repo, "status", "--porcelain", quiet=True).stdout.strip()
    if not status:
        print("nincs változás — nincs mit commitolni")
        return
    msg = message or f"science-monitor: {len(projects)} kézirat ({machine})"
    git(repo, "commit", "-m", msg, quiet=True)
    print(f"commit: {msg}")
    if do_push and has_remote(repo):
        git(repo, "push")
        print("push kész")
    elif do_push:
        print("nincs remote beállítva — csak helyi commit")


def cmd_pull(conn, repo_path=None, do_fetch=True):
    repo = _repo_path(repo_path)
    if do_fetch and has_remote(repo):
        git(repo, "pull", "--ff-only")

    meta_path = os.path.join(repo, "sm-repo.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        if meta.get("schema") != SCHEMA:
            L.die(f"a repo sémája ({meta.get('schema')}) nem egyezik ({SCHEMA})")

    proj_dir = os.path.join(repo, "projects")
    if not os.path.isdir(proj_dir):
        L.die(f"nincs projects/ mappa itt: {repo}")

    machine = L.load_config()["machine"]
    added = updated = 0
    for name in sorted(os.listdir(proj_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(proj_dir, name), encoding="utf-8") as fh:
            doc = json.load(fh)
        pj = doc["project"]
        slug = pj["slug"]
        hint = pj.pop("root_path_hint", {}) or {}
        root_path = hint.get("path", "") if hint.get("machine") == machine else ""

        row = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
        cols = ("title", "kind", "lang", "notes", "archived", "state", "category")
        vals = [pj.get(c, L.CONFIG_DEFAULTS.get(c, "")) for c in cols]
        if row:
            pid = row["id"]
            conn.execute(
                f"UPDATE projects SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?",
                [*vals, pid])
            updated += 1
        else:
            conn.execute(
                f"INSERT INTO projects (slug, {', '.join(cols)}, root_path, created_at) "
                f"VALUES (?{', ?' * (len(cols) + 2)})",
                [slug, *vals, root_path, pj.get("created_at") or L.now()])
            pid = conn.execute("SELECT id FROM projects WHERE slug = ?",
                               (slug,)).fetchone()["id"]
            added += 1

        # Rebuild the derived rows wholesale: the repo is the truth for them.
        conn.execute("DELETE FROM files WHERE project_id = ?", (pid,))
        for entry in doc.get("files", []):
            if entry.get("repo_path"):
                path = os.path.join(repo, entry["repo_path"])
            elif entry.get("local", {}).get("machine") == machine:
                path = entry["local"]["path"]
            else:
                continue  # lives on someone else's machine
            conn.execute(
                "INSERT OR IGNORE INTO files (project_id, role, path, label, added_at) "
                "VALUES (?,?,?,?,?)",
                (pid, entry["role"], path, entry.get("label", ""), L.now()))

        conn.execute("DELETE FROM submissions WHERE project_id = ?", (pid,))
        for sub in doc.get("submissions", []):
            checklist = sub.pop("checklist", [])
            reviews = sub.pop("reviews", [])
            cover_name = sub.pop("cover_letter_name", "")
            cover_path = ""
            for entry in doc.get("files", []):
                if entry["role"] == "cover_letter" and entry["name"] == cover_name:
                    cover_path = (os.path.join(repo, entry["repo_path"])
                                  if entry.get("repo_path")
                                  else entry.get("local", {}).get("path", ""))
                    break
            keys = [k for k in sub if k != "created_at"]
            conn.execute(
                f"INSERT INTO submissions (project_id, cover_letter_path, created_at, "
                f"{', '.join(keys)}) VALUES (?,?,?{', ?' * len(keys)})",
                [pid, cover_path, sub.get("created_at") or L.now(),
                 *[sub[k] for k in keys]])
            sid = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
            for c in checklist:
                conn.execute(
                    "INSERT OR IGNORE INTO checklist (submission_id, idx, label, done, "
                    "na, note) VALUES (?,?,?,?,?,?)",
                    (sid, c.get("idx", 0), c["label"], c.get("done", 0),
                     c.get("na", 0), c.get("note", "")))
            for rv in reviews:
                points = rv.pop("points", [])
                rv.pop("letter_name", None)
                letter_rel = rv.pop("letter_repo_path", "")
                letter = os.path.join(repo, letter_rel) if letter_rel else ""
                keys = [k for k in rv if k != "created_at"]
                conn.execute(
                    f"INSERT INTO reviews (submission_id, letter_path, created_at, "
                    f"{', '.join(keys)}) VALUES (?,?,?{', ?' * len(keys)})",
                    [sid, letter, rv.get("created_at") or L.now(),
                     *[rv[k] for k in keys]])
                rid = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
                for pt in points:
                    keys = list(pt)
                    conn.execute(
                        f"INSERT INTO review_points (review_id, {', '.join(keys)}) "
                        f"VALUES (?{', ?' * len(keys)})",
                        [rid, *[pt[k] for k in keys]])

        conn.execute("DELETE FROM events WHERE project_id = ?", (pid,))
        for e in doc.get("events", []):
            conn.execute(
                "INSERT INTO events (project_id, at, kind, summary) VALUES (?,?,?,?)",
                (pid, e.get("at") or L.now(), e.get("kind", ""), e.get("summary", "")))

    conn.commit()
    print(f"betöltve: {added} új, {updated} frissített kézirat")
    missing = conn.execute(
        "SELECT COUNT(*) n FROM files WHERE path NOT LIKE ?", (repo + "%",)).fetchone()["n"]
    if missing:
        print(f"{missing} fájl a helyi gépről származik — más gépen nem lesz meg")


def cmd_status(conn, repo_path=None):
    repo = _repo_path(repo_path)
    print(f"adat-repo: {repo}")
    remotes = git(repo, "remote", "-v", check=False, quiet=True).stdout.strip()
    print(f"remote: {remotes.splitlines()[0] if remotes else '— nincs —'}")
    n_local = conn.execute("SELECT COUNT(*) n FROM projects").fetchone()["n"]
    proj_dir = os.path.join(repo, "projects")
    n_repo = len([f for f in os.listdir(proj_dir)
                  if f.endswith(".json")]) if os.path.isdir(proj_dir) else 0
    print(f"kézirat: {n_local} helyben · {n_repo} a repóban")
    docs = os.path.join(repo, "documents")
    if os.path.isdir(docs):
        n = size = 0
        for dirpath, _, names in os.walk(docs):
            for name in names:
                n += 1
                size += os.path.getsize(os.path.join(dirpath, name))
        print(f"dokumentum: {n} db, {size / 1e6:.1f} MB")
    dirty = git(repo, "status", "--porcelain", quiet=True).stdout.strip()
    print(f"munkafa: {'módosítva' if dirty else 'tiszta'}")
    if dirty:
        for line in dirty.splitlines()[:10]:
            print(f"  {line}")
