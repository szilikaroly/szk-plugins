#!/usr/bin/env python3
"""Import a Claude Science work-unit export into the store.

The export (`00_MANIFEST.json`, schema `claude-science.work-unit-export-manifest/v2`)
is one markdown + json transcript per work unit. Each unit becomes a project,
or — where a `--map` says so — gets attached to a project that already exists,
so a manuscript already being tracked does not gain a duplicate.

Every unit is imported as a full, active entry. The tooling/specialist-config
units and the platform's own example units are marked by `category`
(`eszkoz` / `pelda` / `kutatas`) rather than hidden, so nothing disappears from
the record while the research work stays filterable.
"""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm_lib as L  # noqa: E402

# The manifest's own category, refined: these origin projects are the Claude
# Science demo content shipped with the platform, not the user's research.
EXAMPLE_ORIGINS = {"proj_example"}


def classify_unit(unit):
    """-> (kind, category, why).

    Every unit is imported as a full, active entry — the category keeps the
    tooling and demo work distinguishable without hiding it.
    """
    if unit.get("origin_project_id") in EXAMPLE_ORIGINS:
        return "article", "pelda", "platform példaprojekt, nem saját kutatás"
    if unit.get("category") == "tooling":
        return "tooling", "eszkoz", "eszköz-/specialista-konfiguráció, nem kézirat"
    return "article", "kutatas", ""


def short_title(title, n=90):
    title = " ".join(str(title).split())
    return title if len(title) <= n else title[: n - 1].rstrip() + "…"


def load(manifest_path):
    with open(manifest_path, encoding="utf-8") as fh:
        man = json.load(fh)
    if not str(man.get("schema", "")).startswith("claude-science.work-unit-export-manifest"):
        L.die(f"ismeretlen manifest séma: {man.get('schema')}")
    return man


def plan(conn, man, root, mapping):
    """Decide, per unit, whether it links to an existing project or makes a new one."""
    rows = []
    for unit in man["work_units"]:
        seq = str(unit["seq"])
        kind, category, why = classify_unit(unit)
        files = [os.path.join(root, unit["files"][k])
                 for k in ("markdown", "json") if unit["files"].get(k)]
        missing = [f for f in files if not os.path.exists(f)]

        target = mapping.get(seq)
        existing = None
        if target:
            try:
                existing = L.get_project(conn, target)
            except L.NotFound:
                L.die(f"a --map a(z) {seq}. egységhez ismeretlen kéziratot ad meg: {target}")

        slug = f"sci-{seq}-{L.slugify(short_title(unit['title'], 40))}"
        already = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()

        rows.append({
            "seq": seq, "unit": unit, "kind": kind, "category": category, "why": why,
            "files": files, "missing": missing, "slug": slug,
            "action": "link" if existing else ("skip" if already else "create"),
            "existing": existing, "already": already,
        })
    return rows


def artifacts_by_root(db_path):
    """Every work unit's produced files, keyed by root frame id.

    The export's markdown holds the transcript; the real deliverables — the
    .docx, the figures, the tables — only exist in the app's own store, keyed
    by the same root_frame_id the manifest uses. Opened read-only.
    """
    db_path = os.path.abspath(os.path.expanduser(db_path))
    art_root = os.path.join(os.path.dirname(db_path), "artifacts")
    src = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    src.row_factory = sqlite3.Row
    out = {}
    try:
        rows = src.execute(
            "SELECT a.root_frame_id, a.filename, a.is_user_upload, v.storage_path "
            "FROM artifacts a JOIN artifact_versions v ON v.id = a.latest_version_id "
            "WHERE COALESCE(a.is_ephemeral, 0) = 0 AND v.storage_path IS NOT NULL"
        ).fetchall()
    finally:
        src.close()
    for r in rows:
        path = os.path.join(art_root, r["storage_path"])
        if os.path.exists(path):
            out.setdefault(r["root_frame_id"], []).append(
                (path, r["filename"], bool(r["is_user_upload"])))
    return out


def describe(unit):
    return (f"{unit.get('messages', 0)} üzenet · {unit.get('artifacts', 0)} artifact"
            f" · {unit.get('sub_sessions', 0)} al-munkamenet"
            f" · {unit.get('started_utc', '')[:10]}–{unit.get('last_activity_utc', '')[:10]}"
            f" · eredeti projekt: {unit.get('origin_project_name', '—')}")


def run(conn, manifest_path, apply_changes, mapping, root=None, artifacts_db=None):
    manifest_path = os.path.abspath(os.path.expanduser(manifest_path))
    root = root or os.path.dirname(manifest_path)
    man = load(manifest_path)
    rows = plan(conn, man, root, mapping)
    arts = artifacts_by_root(artifacts_db) if artifacts_db else {}
    if artifacts_db:
        n = sum(len(v) for v in arts.values())
        covered = sum(1 for r in rows if arts.get(r["unit"]["root_frame_id"]))
        print(f"Artifact-forrás: {n} fájl, {covered}/{len(rows)} munkaegységhez\n")

    t = man.get("totals", {})
    print(f"CLAUDE SCIENCE EXPORT — {man.get('exported_at_utc', '')[:10]}")
    print(f"{t.get('work_units', len(rows))} munkaegység "
          f"({t.get('research_units', '?')} kutatás, {t.get('tooling_units', '?')} eszköz) "
          f"· {t.get('messages', '?')} üzenet\n")

    for r in rows:
        if r["action"] == "link":
            head = f"→ csatolás ide: [{r['existing']['slug']}]"
        elif r["action"] == "skip":
            head = f"· már felvéve [{r['slug']}]"
        else:
            head = f"+ új ({r['category']}) [{r['slug']}]"
        print(f"{r['seq']}. {head}")
        print(f"    {short_title(r['unit']['title'])}")
        print(f"    {describe(r['unit'])}")
        if r["why"]:
            print(f"    ok: {r['why']}")
        if r["missing"]:
            print(f"    ⚠ hiányzó fájl: {', '.join(os.path.basename(m) for m in r['missing'])}")

    n_new = sum(1 for r in rows if r["action"] == "create")
    n_link = sum(1 for r in rows if r["action"] == "link")
    n_skip = sum(1 for r in rows if r["action"] == "skip")
    cats = {}
    for r in rows:
        if r["action"] == "create":
            cats[r["category"]] = cats.get(r["category"], 0) + 1
    breakdown = ", ".join(f"{v} {k}" for k, v in sorted(cats.items())) or "—"
    print(f"\nÖsszesen: {n_new} új ({breakdown}), {n_link} csatolás, "
          f"{n_skip} változatlan.")

    if not apply_changes:
        print("\nEz csak javaslat. Végrehajtás: ugyanez `--apply` kapcsolóval.")
        return

    import sm  # for the same role heuristics `sm.py scan` uses

    created = linked = attached = 0
    for r in rows:
        unit = r["unit"]
        note = (f"Claude Science munkaegység #{r['seq']} · {describe(unit)}"
                + (f" · {r['why']}" if r["why"] else ""))
        if r["action"] == "skip":
            pid = r["already"]["id"]
        elif r["action"] == "link":
            pid = r["existing"]["id"]
            existing_note = r["existing"]["notes"]
            if note not in existing_note:
                conn.execute("UPDATE projects SET notes = ? WHERE id = ?",
                             ((existing_note + "\n" if existing_note else "") + note, pid))
            L.log_event(conn, pid, "science_export_linked", f"munkaegység #{r['seq']}")
            linked += 1
        elif r["action"] == "create":
            conn.execute(
                "INSERT INTO projects (slug, title, kind, root_path, lang, notes, "
                "archived, category, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (r["slug"], " ".join(unit["title"].split()), r["kind"], root, "en",
                 note, 0, r["category"], L.now()))
            pid = conn.execute("SELECT id FROM projects WHERE slug = ?",
                               (r["slug"],)).fetchone()["id"]
            L.log_event(conn, pid, "science_export_imported", f"munkaegység #{r['seq']}")
            created += 1

        for path in r["files"]:
            if os.path.exists(path):
                conn.execute(
                    "INSERT OR IGNORE INTO files (project_id, role, path, label, added_at) "
                    "VALUES (?,?,?,?,?)",
                    (pid, "session", path, f"munkaegység #{r['seq']} átirat", L.now()))

        for path, filename, uploaded in arts.get(unit["root_frame_id"], []):
            # Classify by the artifact's own name, not the storage path — the
            # store keeps files under an opaque version-hash filename.
            role = sm.classify(os.path.join(os.path.dirname(path), filename))
            label = f"#{r['seq']} {filename}" + (" (feltöltés)" if uploaded else "")
            conn.execute(
                "INSERT OR IGNORE INTO files (project_id, role, path, label, added_at) "
                "VALUES (?,?,?,?,?)", (pid, role, path, label, L.now()))
            attached += 1
    conn.commit()
    print(f"\nKész: {created} új kézirat, {linked} meglévőhöz csatolt átirat, "
          f"{attached} artifact-fájl bekötve.")
