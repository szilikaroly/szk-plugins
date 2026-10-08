#!/usr/bin/env python3
"""End-to-end self-test on a synthetic transcript. No Claude Code needed.

Builds a fake session (big tool outputs + real dialogue), drives the hooks the
way Claude Code would, and prints the MEASURED reduction. Run it after any
change to the compressor:

    python3 scripts/selftest.py                       # fresh sandbox each run
    MEMO_GUARD_SELFTEST_HOME=/tmp/mg-test python3 scripts/selftest.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import mg_lib as mg  # noqa: E402


def build_transcript(path: Path, big_files=14, lines_each=900) -> None:
    """A realistic shape: a few huge Read results, some bash noise, dialogue."""
    recs = []
    ctx = 0
    for i in range(big_files):
        tid = f"toolu_{i:03d}"
        recs.append({"type": "assistant", "message": {"content": [
            {"type": "text", "text": f"Reading source file {i}."},
            {"type": "tool_use", "id": tid, "name": "Read",
             "input": {"file_path": f"/repo/src/module_{i}.py"}}],
            "usage": {"input_tokens": ctx, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 50}}})
        body = "\n".join(
            (f"def handler_{i}_{n}(request):" if n % 90 == 0 else
             f"ERROR: retry {n} failed for module {i}" if n % 150 == 0 else
             f"    value_{n} = compute({n}) * factor  # filler line {n}")
            for n in range(lines_each))
        recs.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid,
             "content": [{"type": "text", "text": body}]}]}})
        ctx += len(body) // 4
        recs.append({"type": "user", "message": {"content":
                    f"Now explain what module_{i} does and why retries fail."}})
        recs.append({"type": "assistant", "message": {"content": [
            {"type": "text",
             "text": f"Module {i} handles request routing; retries fail "
                     f"because the backoff resets on each 5xx. Decision: "
                     f"switch module_{i} to exponential backoff."}],
            "usage": {"input_tokens": ctx, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0, "output_tokens": 120}}})
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")


def hook(script: str, payload: dict) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(HERE / script)],
                       input=json.dumps(payload), capture_output=True,
                       text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    # NEVER the production data directory.
    #
    # This used to read MEMO_GUARD_HOME — the variable the plugin's own
    # installer PINS to ~/.claude/memo-guard. So in any shell that had the
    # plugin installed, the "sandbox" was the live store, and the test's
    # fixtures were written into the user's real long-term memory: an invented
    # PROSPERO registration number, an invented rejection reason, and a REFUTED
    # claim about a cohort's sample size. Recall then served them to real
    # sessions as facts the user had established.
    #
    # A self test must not be able to reach production by inheriting an
    # environment. It gets its own directory, and an override that cannot be set
    # by accident.
    home = Path(os.environ.get("MEMO_GUARD_SELFTEST_HOME")
                or tempfile.mkdtemp(prefix="mg-selftest-"))
    os.environ["MEMO_GUARD_HOME"] = str(home)
    mg.assert_not_production("the self test")
    os.environ.setdefault("MEMO_CTX_WINDOW", "200000")
    # local model isn't present in a test box; force the honest fallback
    os.environ["MEMO_GUARD_USE_LOCAL_MODEL"] = "false"
    print(f"data dir: {home}  (sandbox — never the production store)\n")

    tdir = home / "fake-projects"
    tdir.mkdir(parents=True, exist_ok=True)
    tp = tdir / "11112222-3333-4444-5555-666677778888.jsonl"
    build_transcript(tp)
    raw_kb = tp.stat().st_size // 1024
    print(f"synthetic transcript: {raw_kb} KB "
          f"(~{mg.est_tokens(tp.read_bytes()):,} tok)")

    sid = tp.stem
    payload = {"session_id": sid, "transcript_path": str(tp),
               "cwd": "/repo", "hook_event_name": "PostToolUse"}

    rc, out = hook("ctx_monitor.py", payload)
    print(f"\n1) PostToolUse monitor rc={rc}")
    if out.strip():
        msg = json.loads(out).get("systemMessage", "")
        print("   " + msg[:160])
    assert rc == 0

    # wait for the background compressor
    wd = home / "sessions" / sid
    for _ in range(120):
        st = wd / "STATE.json"
        if st.exists() and json.loads(st.read_text(encoding="utf-8")).get("phase") in (
                "done", "error"):
            break
        time.sleep(0.5)
    state = json.loads((wd / "STATE.json").read_text(encoding="utf-8"))
    print(f"\n2) compressor phase={state.get('phase')} "
          f"mode={state.get('mode')}")
    if state.get("phase") != "done":
        print("   ERROR:", state)
        return 1

    rc, out = hook("inject_resume.py",
                   {"session_id": sid, "cwd": "/repo", "source": "compact",
                    "hook_event_name": "SessionStart"})
    print(f"\n3) SessionStart(compact) injection rc={rc}, "
          f"{len(out)} chars (cap 10,000)")
    print("   ---- injected into the fresh context ----")
    for ln in out.splitlines()[:14]:
        print("   " + ln)
    print("   ...")

    # THIS run's compression row, selected by session id and event type.
    # Reading the last line of a shared, multi-event, append-only file meant the
    # numbers printed here belonged to whatever session wrote last — a real
    # 8.1-million-token window was once reported as this synthetic test's
    # result, complete with a PASS. Position is not identity.
    rows = mg.read_metrics(event=mg.COMPRESS, session=sid,
                           path=home / "metrics.jsonl")
    if not rows:
        print("\n4) MEASURED — FAIL: the compressor wrote no metrics row for "
              f"session {sid}. Nothing was measured; the numbers below would "
              "have been someone else's.")
        return 1
    row = rows[-1]
    print("\n4) MEASURED")
    print(f"   raw window            ~{row['raw_tokens_est']:,} tok")
    print(f"   distilled working set ~{row['kept_tokens_est']:,} tok "
          f"({row['reduction_kept_pct']}% smaller)")
    print(f"   RESUME injected       ~{row['resume_tokens_est']:,} tok "
          f"({row['reduction_resume_pct']}% smaller)")
    print(f"   sources={row['sources']} turns={row['turns']} "
          f"in {row['duration_s']}s")

    # Best case (resume only) flatters the design. Price a REALISTIC resumed
    # session: the injected resume plus several real lookups.
    probes = ["exponential backoff", "handler_3", "retry 150",
              "module_7", "ERROR"]
    lookup_tok = 0
    for q in probes:
        g = subprocess.run(["grep", "-rn", "-i", q, str(wd / "distilled")],
                           capture_output=True, text=True).stdout
        lookup_tok += mg.est_tokens("\n".join(g.splitlines()[:8]))
    realistic = row["resume_tokens_est"] + lookup_tok
    red = 100 - 100 * realistic / row["raw_tokens_est"]
    print(f"   realistic session     ~{realistic:,} tok "
          f"(resume + {len(probes)} lookups) = {red:.2f}% smaller")

    ok = row["reduction_resume_pct"] >= 95 and red >= 95
    print(f"\n   >=95% target (best case AND realistic): "
          f"{'PASS' if ok else 'FAIL'}")

    # the compression must not lose the decisions
    resume = (wd / "RESUME.md").read_text(encoding="utf-8")
    hit = subprocess.run(
        ["grep", "-ril", "exponential backoff", str(wd / "sources")],
        capture_output=True, text=True).stdout.strip()
    print(f"   decision recoverable from compressed sources: "
          f"{'yes' if hit else 'NO'}")
    print(f"   archive path in RESUME: "
          f"{'yes' if '.jsonl.gz' in resume else 'NO'}")

    ap_ok = check_autopilot(home)
    cv_ok = check_calibration_converges()
    co_ok = check_calibration_outlier(home)
    sb_ok = check_stub_visible(home)
    rc_ok = check_recall(home)
    ev_ok = check_recall_quality()
    mr_ok = check_map_reduce(home)
    dr_ok = check_doctor(home)
    dg_ok = check_degradation(home)
    bw_ok = check_busy_vs_wedged()
    cp_ok = check_corpus(home)
    st_ok = check_sync_tombstones(home)
    tc_ok = check_table_cards(home)
    tx_ok = check_table_cards_xlsx(home)
    tf_ok = check_table_card_fallback(home)
    tb_ok = check_table_card_bibliographic(home)
    dm_ok = check_db_maint(home)
    cc_ok = check_concepts(home)
    en_ok = check_text_encoding()
    return 0 if (ok and hit and ap_ok and cv_ok and co_ok and sb_ok and rc_ok
                 and ev_ok and mr_ok and dr_ok and dg_ok and bw_ok and cp_ok
                 and st_ok and tc_ok and tx_ok and tf_ok and tb_ok and dm_ok and cc_ok
                 and en_ok) else 1


def check_db_maint(home: Path) -> bool:
    """16) The store's search index holds only answerable claims, and maintenance keeps it sound.

    v2 indexes claim_live (REFUTED/STALE excluded) through triggers whose WHEN clauses must
    mirror the view. An external-content FTS5 'delete' of a row that was never indexed
    corrupts the index without failing, so the integrity-check after the status flips is the
    real assertion here. Also: a v1 store migrates in place, the pair fallback answers a
    question no single claim fully matches without dragging in single-word noise, and the
    daily heavy pass runs clean.
    """
    import sqlite3
    import store
    import dbmaint
    print("\n16) store index v2 + db maintenance")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    saved = os.environ["MEMO_GUARD_HOME"]
    os.environ["MEMO_GUARD_HOME"] = str(home / "dbm")
    try:
        p = store.db_path()
        v1 = sqlite3.connect(p)
        v1.executescript(store.SCHEMA.replace("content='claim_live'", "content='claim'")
                         .replace("CREATE VIEW IF NOT EXISTS claim_live AS\n  SELECT id, text, keywords"
                                  " FROM claim WHERE status NOT IN ('REFUTED', 'STALE');", ""))
        v1.executescript("""
CREATE TRIGGER claim_ai AFTER INSERT ON claim BEGIN
  INSERT INTO claim_fts(rowid, text, keywords) VALUES (new.id, new.text, new.keywords); END;
INSERT INTO meta (k,v) VALUES ('schema_version','1');
INSERT INTO root (id, path, memo_dir) VALUES (1, '/r', '/r/.memo');
INSERT INTO doc (id, root_id, memo, path, project) VALUES (1, 1, 'm.memo.md', 'kutatas/p/a.md', 'kutatas/p');
INSERT INTO claim (doc_id, cid, text, status, utility) VALUES
  (1, 'C1', 'Alpha beta findings were reported in the cohort study', 'CONFIRMED', 0.8),
  (1, 'C2', 'Alpha beta gamma delta was refuted by the source text', 'REFUTED', 0.8),
  (1, 'C3', 'Gamma appears alone in this unrelated noise claim', 'CONFIRMED', 0.8);
""")
        v1.commit()
        v1.close()
        db = store.connect()
        ver = db.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()[0]
        n_idx = db.execute("SELECT count(*) FROM claim_fts_docsize").fetchone()[0]
        chk(ver == store.SCHEMA_VERSION and n_idx == 2, f"a v1 store migrates; the index holds {n_idx} of 3 claims")
        db.execute("UPDATE claim SET status='REFUTED' WHERE cid='C3'")
        db.execute("UPDATE claim SET status='CONFIRMED' WHERE cid='C2'")
        db.execute("INSERT INTO claim (doc_id, cid, text, status) VALUES (1, 'C4', 'Stale words here x', 'STALE')")
        db.execute("DELETE FROM claim WHERE cid IN ('C1', 'C4')")
        db.commit()
        try:
            db.execute("INSERT INTO claim_fts(claim_fts, rank) VALUES('integrity-check', 1)")
            fine = True
        except sqlite3.DatabaseError:
            fine = False
        chk(fine and db.execute("SELECT count(*) FROM claim_fts_docsize").fetchone()[0] == 1,
            "status flips, inserts and deletes keep the index exactly in step with claim_live")
        db.execute("UPDATE claim SET status='CONFIRMED' WHERE cid='C3'")
        db.execute("INSERT INTO claim (doc_id, cid, text, status, utility) VALUES"
                   " (1, 'C5', 'Alpha beta findings were reported in the cohort study', 'CONFIRMED', 0.8)")
        db.commit()
        db.close()
        hits = store.search("alpha beta gamma cohort")
        texts = " | ".join(h["text"] for h in hits)
        chk("cohort study" in texts and "unrelated noise" not in texts,
            "the pair fallback finds the claim sharing two terms, not single-word noise")
        res = dbmaint.heavy_all(["memo"])
        chk(res and not res[0].get("error") and "claim_fts: integrity ok" in res[0].get("steps", []),
            "the daily heavy pass checks, optimizes and analyzes without error")

        # A project whose directory moved keeps its facts recallable after --move-project.
        import memory
        mdb = memory.connect()
        old = "/Users/someone/Documents/claude/thesis_proj"
        memory.promote(mdb, "Thesis rule: every table carries its source and year", old,
                       kind="decision", utility=0.8)
        memory.promote(mdb, "Thesis rule: abbreviations are defined at first use", old,
                       kind="decision", utility=0.8)
        new_dir = home / "dbm" / "kutatas" / "thesis_proj"
        new_dir.mkdir(parents=True, exist_ok=True)
        before = memory.recall(mdb, "thesis rule table source year", str(new_dir), None)
        r = memory.move_project(mdb, mg.project_slug(old), str(new_dir))
        after = memory.recall(mdb, "thesis rule table source year", str(new_dir), None)
        txt = json.dumps(after, ensure_ascii=False)
        chk(r["moved"] == 2 and "every table carries its source" in txt
            and "every table carries its source" not in json.dumps(before, ensure_ascii=False),
            "after --move-project the moved project's facts are recalled at the new path")
    finally:
        os.environ["MEMO_GUARD_HOME"] = saved
    return ok


def check_table_cards(home: Path) -> bool:
    """15) A big table gets a computed card, never a model pass.

    The 2026-10-03 decision: a CSV of 100+ memo_gen chunks costs GPU-hours, the 8B model
    paraphrases screening-list titles and authors, and tables.py already holds every row.
    Checked: every card claim's snippet is literally on the staged line it names (so
    verify_anchors confirms it), the computed numbers are right, the card covers the whole
    file (no false "partial memo"), and the ingest worker writes it without starting a
    model -- even with the pause flag set, because a card needs no GPU.
    """
    import re as _re
    import ingest
    import table_card
    print("\n15) table cards")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    root = home / "card-root"
    (root / "data").mkdir(parents=True, exist_ok=True)
    rel = "data/sim.csv"
    rows = ["iter;arm;cost;note"] + [f"{i};{'A' if i % 3 else 'B'};{1000 + (i * 37) % 5000};run {i}"
                                     for i in range(1, 17001)]
    (root / rel).write_text("\n".join(rows) + "\n", encoding="utf-8")
    ab = str((root / rel).resolve())
    chk(table_card.chunks(ab) >= 100, "the fixture is big enough to get a card")
    mname, text, info = table_card.build(root, rel, "t7")
    _, _, slines = table_card.staged(ab)
    claims = _re.findall(r"^- \[C\d+\] \[PENDING\] (.*) @L(\d+) `([^`]*)`$", text, _re.M)
    chk(claims and all(s and s in slines[int(n) - 1].replace("`", "") for _, n, s in claims),
        f"every one of {len(claims)} claims is anchored to a literal snippet on its line")
    chk(f"- L1-{len(slines)}:" in text, "the card covers the whole staged file")
    chk("'cost' is numeric (17,000 values) and ranges from 1000 to 5999" in text,
        "a numeric column's range is computed, not guessed")
    chk("'arm' has 2 distinct values; most frequent: A (11,334), B (5,666)" in text,
        "a categorical column's counts are exact")
    chk("17,000 data rows and 4 columns" in text and "SQL table t7" in text,
        "the card names its size and the SQL table to query")

    cfg = {"corpus_roots": [str(root)], "memo_index_path": "", "table_card_min_chunks": 100,
           "corpus_tables": False}
    small = root / "data" / "small.csv"
    small.write_text("a;b\n1;2\n", encoding="utf-8")
    chk(ingest._is_card(root / rel, ".csv", cfg) and not ingest._is_card(small, ".csv", cfg)
        and not ingest._is_card(root / rel, ".csv", dict(cfg, table_card_min_chunks=0)),
        "only the big table is carded, and 0 turns cards off")

    # The size is memo_gen's own chunk plan, not lines / 160 (2026-10-08). Ten long floats
    # a row is ~100 tokens: 2,401 lines are 16 chunks by lines and far more by token budget.
    if table_card._memo_gen() is not None:
        dense = root / "data" / "psa.csv"
        dense.write_text("\n".join(["iter," + ",".join(f"p{j}" for j in range(9))] + [
            ",".join([str(i)] + [f"{((i * 7919 + j * 104729) % 1000003) / 7.0:.15f}" for j in range(9)])
            for i in range(1, 2401)]) + "\n", encoding="utf-8")
        why = table_card.card_reason(str(dense.resolve()), 100, False)
        chk(why.endswith(" chunks") and int(why.split()[0]) >= 100,
            f"a dense numeric table is sized by memo_gen's chunk plan ({why or 'no card'}, "
            f"not {-(-2401 // table_card.CHUNK_LINES)} by lines)")
    else:
        print("   skip dense-table size: memo-index's memo_gen is not installed")
    calls = []
    real_run = ingest.subprocess.run

    def no_model(*a, **k):
        calls.append(a)
        raise RuntimeError("no model in this test")

    ingest.subprocess.run = no_model
    flag = ingest.qdir() / "paused"
    flag.write_text("selftest", encoding="utf-8")
    try:
        ingest.enqueue(root / rel, "test", cfg)
        done = ingest.work(cfg, debounce=0, idle_exit=0)
        mp = root / ".memo" / mname
        chk(done.get("cards") == 1 and not done.get("deferred") and not calls,
            "the worker writes the card while paused, without starting memo_gen")
        chk(mp.exists() and "generator: table-card" in mp.read_text(encoding="utf-8"),
            "the card sits where memo_gen's memo would have")
    finally:
        ingest.subprocess.run = real_run
        flag.unlink(missing_ok=True)
    return ok


def _write_xlsx(path: Path, sheets: list) -> None:
    """A minimal real workbook -- inline strings, numbers as <v> -- written with the stdlib,
    so the test needs no openpyxl."""
    import zipfile
    from xml.sax.saxutils import escape, quoteattr

    def ref(ci: int, ri: int) -> str:
        s, ci = "", ci + 1
        while ci:
            ci, r = divmod(ci - 1, 26)
            s = chr(65 + r) + s
        return f"{s}{ri}"

    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    ct = ("application/vnd.openxmlformats-officedocument.spreadsheetml.")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"><Default Extension="rels" ContentType="application/'
                   'vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" '
                   'ContentType="application/xml"/><Override PartName="/xl/workbook.xml" '
                   f'ContentType="{ct}sheet.main+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{k}.xml" ContentType="{ct}'
                             f'worksheet+xml"/>' for k in range(1, len(sheets) + 1)) + "</Types>")
        z.writestr("_rels/.rels", f'<Relationships xmlns="{pkg_ns}"><Relationship Id="rId1" '
                   f'Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", f'<workbook {ns} xmlns:r="{rel_ns}"><sheets>'
                   + "".join(f'<sheet name={quoteattr(n)} sheetId="{k}" r:id="rId{k}"/>'
                             for k, (n, _) in enumerate(sheets, 1)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{pkg_ns}">'
                   + "".join(f'<Relationship Id="rId{k}" Type="{rel_ns}/worksheet" '
                             f'Target="worksheets/sheet{k}.xml"/>' for k in range(1, len(sheets) + 1))
                   + "</Relationships>")
        for k, (_, rows) in enumerate(sheets, 1):
            body = []
            for ri, row in enumerate(rows, 1):
                cells = [f'<c r="{ref(ci, ri)}"><v>{v}</v></c>' if isinstance(v, (int, float)) else
                         f'<c r="{ref(ci, ri)}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
                         for ci, v in enumerate(row)]
                body.append(f'<row r="{ri}">{"".join(cells)}</row>')
            z.writestr(f"xl/worksheets/sheet{k}.xml",
                       f"<worksheet {ns}><sheetData>{''.join(body)}</sheetData></worksheet>")


def check_table_cards_xlsx(home: Path) -> bool:
    """15b) A big workbook gets a card too, built from the staged markdown tables.

    The 2026-10-04 extension of the card decision: two OGDOC code-registry workbooks
    (71,223 and 24,474 rows) had memos of row-level claims that only duplicated their SQL
    tables. Checked: both markdown dialects parse (doc_ingest's stdlib reader, and
    doc-tools' xlstotext where it is on PATH -- a lone sheet there has no name, and the card
    must not invent one); every claim sits literally on the staged line it names; the
    numbers are exact; and the paused worker writes and verifies the card without memo_gen.
    """
    import re as _re
    import ingest
    import table_card
    print("\n15b) workbook table cards")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    xt = ["=== Codes (3 rows) ===", "code | label", "--- | ---", "A1 | first", "A2 | second", "",
          "=== Doses (2 rows) ===", "id | dose", "--- | ---", "1 | 5"]
    sh = table_card._md_sheets(xt)
    chk([s["name"] for s in sh] == ["Codes", "Doses"] and sh[0]["rows"] == [["A1", "first"], ["A2", "second"]]
        and sh[0]["lines"] == [4, 5] and sh[1]["head_line"] == 8,
        "xlstotext's dialect parses: sheet names, rows, 1-based line numbers")
    lone = table_card._md_sheets(["code | label", "--- | ---", "A1 | first"])
    chk(len(lone) == 1 and lone[0]["name"] == "" and lone[0]["rows"] == [["A1", "first"]],
        "a lone unnamed sheet parses, and gets no invented name")

    ms = Path(os.path.expanduser(mg.load_config().get("memo_index_path", ""))) / "scripts"
    if not (ms / "doc_ingest.py").exists():
        print("   skip workbook staging: memo-index's doc_ingest.py is not installed")
        return ok
    root = home / "card-root-x"
    (root / "data").mkdir(parents=True, exist_ok=True)
    rel = "data/codes.xlsx"
    beta = [["id", "dose", "unit"]] + [[i, 5 + (i * 7) % 95, "mg" if i % 4 else "ml"] for i in range(1, 16501)]
    _write_xlsx(root / rel, [("alpha", [["code", "label"], ["A1", "first"], ["A2", "second"], ["A3", "third"]]),
                             ("beta", beta)])
    _write_xlsx(root / "data" / "small.xlsx", [("only", [["a", "b"], [1, 2]])])
    ab = str((root / rel).resolve())
    chk(table_card.chunks(ab) >= 100, "the workbook fixture is big enough to get a card")
    mname, text, info = table_card.build(root, rel, {"alpha": "t3", "beta": "t4"})
    _, _, slines = table_card.staged(ab)
    claims = _re.findall(r"^- \[C\d+\] \[PENDING\] (.*) @L(\d+) `([^`]*)`$", text, _re.M)
    chk(claims and all(s and s in slines[int(n) - 1].replace("`", "") for _, n, s in claims),
        f"every one of {len(claims)} claims is anchored to a literal snippet on its line")
    chk(f"- L1-{len(slines)}:" in text, "the card covers the whole staged workbook")
    chk("codes.xlsx, sheet 'alpha', is a table of 3 data rows and 2 columns: code, label; "
        "the full sheet is SQL table t3" in text
        and "codes.xlsx, sheet 'beta', is a table of 16,500 data rows and 3 columns: id, dose, unit; "
        "the full sheet is SQL table t4" in text,
        "each sheet's size, columns and SQL table are named")
    chk("column 'dose' is numeric (16,500 values) and ranges from 5 to 99" in text
        and "column 'unit' has 2 distinct values; most frequent: mg (12,375), ml (4,125)" in text,
        "the largest sheet's column statistics are exact")

    cfg = {"corpus_roots": [str(root)], "memo_index_path": str(ms.parent), "table_card_min_chunks": 100,
           "corpus_tables": False}
    chk(ingest._is_card(root / rel, ".xlsx", cfg)
        and not ingest._is_card(root / "data" / "small.xlsx", ".xlsx", cfg),
        "only the big workbook is carded")
    calls = []
    real_run = ingest.subprocess.run

    def no_model(*a, **k):
        cmd = a[0] if a else k.get("args", [])
        if any("memo_gen" in str(x) for x in cmd):
            calls.append(cmd)
            raise RuntimeError("no model in this test")
        return real_run(*a, **k)               # staging and verify_anchors run for real

    ingest.subprocess.run = no_model
    flag = ingest.qdir() / "paused"
    flag.write_text("selftest", encoding="utf-8")
    try:
        ingest.enqueue(root / rel, "test", cfg)
        done = ingest.work(cfg, debounce=0, idle_exit=0)
        mp = root / ".memo" / mname
        card = mp.read_text(encoding="utf-8") if mp.exists() else ""
        chk(done.get("cards") == 1 and not done.get("deferred") and not calls,
            "the worker writes the workbook card while paused, without starting memo_gen")
        m = _re.search(r"^verified: (\d+) confirmed\s*$", card, _re.M)
        chk(m and int(m.group(1)) == len(claims) and "[PENDING]" not in card,
            f"verify_anchors confirms all {len(claims)} card claims against freshly staged text")
    finally:
        ingest.subprocess.run = real_run
        flag.unlink(missing_ok=True)
    return ok


def check_text_encoding() -> bool:
    """18) No text file is read or written in the platform's code page.

    Windows hands Python the ANSI code page (cp1250 here) unless UTF-8 mode is on, and the
    hooks ran without it: from 2026-08-25 every RESUME.md on the Windows machine was empty,
    because the compressor died writing '→' into conversation.md (198 tracebacks). The same
    default read and rewrote ~/.claude/settings.json and the memory export pushed to the
    other machine. Checked: every hook starts Python in UTF-8 mode; a child of any script
    inherits it; and no text-mode open/read_text/write_text in the scripts omits encoding=
    (the selftest's own fixtures included), so running one by hand is safe too.
    """
    import ast
    import json as _json
    import subprocess as _sp
    print("\n18) text encoding")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    here = Path(__file__).resolve().parent
    hooks = _json.loads((here.parent / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    cmds = [h["command"] for groups in hooks.values() for g in groups for h in g["hooks"]]
    chk(cmds and all(c.startswith("python3 -X utf8 ") for c in cmds),
        f"all {len(cmds)} hook commands start Python in UTF-8 mode")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
    probe = ("import sys, subprocess; sys.path.insert(0, sys.argv[1]); import mg_lib; "
             "print(subprocess.run([sys.executable, '-c', 'import sys; print(sys.flags.utf8_mode)'], "
             "capture_output=True, text=True).stdout.strip())")
    r = _sp.run([sys.executable, "-X", "utf8=0", "-c", probe, str(here)], capture_output=True,
                text=True, env=env, timeout=60)
    chk(r.stdout.strip() == "1", "a child of a script that imports mg_lib runs in UTF-8 mode")

    bad = []
    for p in sorted(here.glob("*.py")):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
            if name not in ("write_text", "read_text", "open") or owner in ("os", "zipfile", "z", "zf"):
                continue
            if any(k.arg == "encoding" for k in n.keywords):
                continue
            mode = next((k.value for k in n.keywords if k.arg == "mode"), None)
            if mode is None and name == "open":
                # open(file, mode) and gzip/io.open(file, mode), but Path(...).open(mode): the
                # mode is the first argument of a method call, whatever the object expression
                i = 1 if isinstance(f, ast.Name) or owner in ("gzip", "io", "codecs") else 0
                mode = n.args[i] if len(n.args) > i else None
            m = mode.value if isinstance(mode, ast.Constant) and isinstance(mode.value, str) else ""
            if "b" in m or (name == "open" and owner == "gzip" and "t" not in m):
                continue
            bad.append(f"{p.name}:{n.lineno}")
    chk(not bad, "every text-mode read/write names its encoding"
        + (f" (missing: {', '.join(bad[:6])}{' ...' if len(bad) > 6 else ''})" if bad else ""))
    return ok


def check_table_card_bibliographic(home: Path) -> bool:
    """15d) A list of publications gets a card at any size, and nothing else does on that ground.

    Decided 2026-10-04: a model memo of a screening list or reference list pairs titles,
    authors, years and PMIDs across rows, the shape of a fabricated reference, which the
    verifier cannot see. Checked: the header rule against the false positives the workspace
    scan turned up (a data dictionary's 'cim'/'ev_tol', TRIPOD's '_ev' evidence columns,
    'study_type', an analytic table that only cites a PMID); a 5-row screening list is carded
    by the worker while paused and without memo_gen, every row a claim with its exact
    values; and the config switch turns the rule off.
    """
    import ingest
    import table_card
    print("\n15d) publication lists get cards")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    bh = table_card.bibliographic_header
    yes = [["pmid", "cim", "decision"], ["pmid", "decision", "reason", "phase"],
           ["doi", "first_author", "journal", "year"], ["title", "author_or_body", "year"],
           ["pmid", "study", "d1"], ["PMID", "Reason for exclusion at full text"]]
    no = [["exposure", "current_rr", "achievable_rr", "pmid", "evidence"],
          ["valtozo", "cim", "ev_tol"], ["pmid", "3c_inequalities", "3c_inequalities_ev"],
          ["title", "study_type", "n"], ["a", "b"]]
    chk(all(bh(h) for h in yes), "screening, reference and evidence headers are publication lists")
    chk(not any(bh(h) for h in no),
        "a data dictionary, TRIPOD evidence, 'study_type' and a PMID-citing analytic table are not")

    root = home / "card-root-b"
    (root / "lit").mkdir(parents=True, exist_ok=True)
    rel = "lit/dontesek.csv"
    rows = [("38012345", "Semaglutide in pregnancy: a cohort", "exclude", "no comparator"),
            ("37123456", "GLP-1 receptor agonists and congenital malformations", "include", ""),
            ("36234567", "Liraglutide exposure in early gestation", "exclude", "case report"),
            ("35345678", "Incretin therapy and fertility outcomes", "include", ""),
            ("34456789", "Tirzepatide: a narrative review", "exclude", "review")]
    # Saved as Excel's "CSV UTF-8", with a byte-order mark: 272 of the workspace's cards had
    # carried it into the first column's name ('﻿pmid').
    (root / rel).write_text("﻿pmid,cim,decision,reason\n"
                            + "".join(f'{p},"{t}",{d},{r}\n' for p, t, d, r in rows), encoding="utf-8")
    other = root / "lit" / "prevention.csv"
    other.write_text("exposure,rr,pmid\nsmoking,1.3,31234567\nobesity,1.8,32345678\n", encoding="utf-8")
    cfg = {"corpus_roots": [str(root)], "memo_index_path": "", "table_card_min_chunks": 100,
           "corpus_tables": False}
    chk(ingest._is_card(root / rel, ".csv", cfg) and not ingest._is_card(other, ".csv", cfg),
        "a 5-row screening list is carded; an analytic table citing PMIDs is not")
    chk(not ingest._is_card(root / rel, ".csv", dict(cfg, table_card_bibliographic=False)),
        "table_card_bibliographic: false turns the rule off")
    mname = ingest.memo_name(ingest.staged_stem(str((root / rel).resolve())) + ".txt")
    calls = []
    real_run = ingest.subprocess.run

    def no_model(*a, **k):
        calls.append(a)
        raise RuntimeError("no model in this test")

    ingest.subprocess.run = no_model
    flag = ingest.qdir() / "paused"
    flag.write_text("selftest", encoding="utf-8")
    try:
        ingest.enqueue(root / rel, "test", cfg)
        done = ingest.work(cfg, debounce=0, idle_exit=0)
        mp = root / ".memo" / mname
        text = mp.read_text(encoding="utf-8") if mp.exists() else ""
        chk(done.get("cards") == 1 and not done.get("deferred") and not calls
            and "generator: table-card" in text,
            "the worker writes the card while paused, without starting memo_gen")
        chk(all(f"pmid={p}; cim={t}; decision={d}" + (f"; reason={r}" if r else "") in text
                for p, t, d, r in rows),
            "every row is a claim carrying its PMID, title and decision verbatim")
        claim_lines = [l for l in text.splitlines() if l.startswith("- [C")]
        chk(claim_lines and not any("﻿" in l for l in claim_lines),
            "a byte-order mark reaches no claim, neither its text nor its snippet")
    finally:
        ingest.subprocess.run = real_run
        flag.unlink(missing_ok=True)
    return ok


def check_table_card_fallback(home: Path) -> bool:
    """15c) A small table the model says nothing about still gets a card, every row a claim.

    Measured 2026-10-04: a meta-analysis's pooled-estimates table and a Monte Carlo summary
    came back NO CLAIMS on every one of 3-4 model passes, so the study's headline numbers
    were in no memo at all. Checked: each row of a small table becomes a claim carrying
    every column (a result row is one finding read across); a cut value ends on a whole
    token, never mid-identifier; and the worker writes the card when memo_gen leaves no memo.
    """
    import re as _re
    import subprocess as _sp
    import ingest
    import table_card
    print("\n15c) no-claims fallback cards")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    chk(table_card._clean("11111111 22222222 33333333", 20) == "11111111 22222222…"
        and table_card._clean("x" * 30, 10) == "x" * 9 + "…",
        "a cut value ends on a whole token (a hard cut only for one long word)")
    root = home / "card-root-f"
    (root / "out").mkdir(parents=True, exist_ok=True)
    rel = "out/pooled.csv"
    rows = [("MCM - all exposure windows", 5, "1.0019", "0.9169", "1.0947", "1.00 (0.92 to 1.09)"),
            ("Urinary malformations", 1, "1.2472", "1.0468", "1.4858", "1.25 (1.05 to 1.49)"),
            ("Stillbirth", 2, "1.8952", "0.0067", "533.95", "1.90 (0.01 to 533.95)"),
            ("Gestational diabetes - preconception exposure only", 5, "1.1513", "0.8044", "1.6478",
             "1.15 (0.80 to 1.65)")]
    (root / rel).write_text('"analysis","k","est","lo","hi","summary"\n'
                            + "".join(f'"{a}",{k},{e},{lo},{hi},"{s}"\n' for a, k, e, lo, hi, s in rows),
                            encoding="utf-8")
    _, text, info = table_card.build(root, rel, "t9")
    got = {int(m.group(1)): m.group(2) for m in
           _re.finditer(r"data row (\d+): (.*?) @L\d+ `", text)}
    chk(len(got) == len(rows) and all(
        all(f"{h}={v}" in got[i + 1] for h, v in zip(("analysis", "k", "est", "lo", "hi", "summary"), r))
        for i, r in enumerate(rows)),
        f"all {len(rows)} rows are claims, each with every column and its exact value")
    chk("column 'analysis' has 4 distinct values, each once" in text and "most frequent" not in text,
        "a label column is not reported as 'most frequent: x (1), y (1)'")

    ms = Path(os.path.expanduser(mg.load_config().get("memo_index_path", ""))) / "scripts"
    if not (ms / "verify_anchors.py").exists():
        print("   skip worker fallback: memo-index is not installed")
        return ok
    cfg = {"corpus_roots": [str(root)], "memo_index_path": str(ms.parent), "table_card_min_chunks": 100,
           "corpus_tables": False}
    calls = []
    real_run, real_gpu = ingest.subprocess.run, ingest.ensure_ollama

    def silent_model(*a, **k):
        cmd = a[0] if a else k.get("args", [])
        if any("memo_gen" in str(x) for x in cmd):
            calls.append(cmd)                  # NO CLAIMS: exits 0, writes no memo
            return _sp.CompletedProcess(cmd, 0, "", "1 file(s) produced NO claims")
        return real_run(*a, **k)

    ingest.subprocess.run, ingest.ensure_ollama = silent_model, (lambda cfg: True)
    try:
        ingest.enqueue(root / rel, "test", cfg)
        done = ingest.work(cfg, debounce=0, idle_exit=0)
        cards = list((root / ".memo").glob("*.memo.md"))
        card = cards[0].read_text(encoding="utf-8") if len(cards) == 1 else ""
        n = len(_re.findall(r"^- \[C\d+\]", card, _re.M))
        chk(calls and done.get("cards") == 1 and not done.get("errors") and not done.get("no_claims"),
            "after a model pass with no claims, the worker writes a computed card")
        chk("generator: table-card" in card and _re.search(rf"^verified: {n} confirmed\s*$", card, _re.M),
            f"verify_anchors confirms all {n} of its claims")
    finally:
        ingest.subprocess.run, ingest.ensure_ollama = real_run, real_gpu
    return ok


def check_concepts(home: Path) -> bool:
    """17) Concept vectors follow their claims.

    The store re-imports a changed memo by deleting its claims, and claim ids are INTEGER
    PRIMARY KEY without AUTOINCREMENT. A vector left behind is an orphan in every clustering,
    and once its id is reused it is read as the next claim's vector (2026-10-04: 167 of the
    first 256 vectors were orphans). Checked, with a deterministic stand-in for the embedding
    model: a re-imported memo leaves no orphan vector, membership or conflict edge; a claim
    whose text changed is re-embedded; a reused id never inherits the old vector; a claim
    verified away after the clustering is no concept-search answer.
    """
    import hashlib as _h
    import store
    import concepts
    print("\n17) concept vectors")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    try:
        np = concepts._np()
    except ImportError:
        print("   skip: numpy is not installed")
        return ok
    saved = os.environ["MEMO_GUARD_HOME"]
    os.environ["MEMO_GUARD_HOME"] = str(home / "cpt")
    real_embed, real_mi = concepts.embed_batch, store._memo_index

    def fake_embed(texts, prefix, timeout=120.0, retries=3):
        out = []
        for t in texts:
            v = np.frombuffer(_h.sha512(t.encode()).digest() * 4, dtype=np.uint8)[:concepts.DIM]
            v = v.astype(np.float32) - 127.5
            out.append(v / np.linalg.norm(v))
        return np.vstack(out)

    concepts.embed_batch = fake_embed
    store._memo_index = lambda cfg: (_ for _ in ()).throw(ImportError("hermetic"))
    try:
        root = home / "cpt-root"
        (root / ".memo").mkdir(parents=True, exist_ok=True)
        mp = root / ".memo" / "notes.md-00000001.memo.md"
        lines = [f"- [C{i}] [CONFIRMED] Cohort {i} reported finding number {i} for donor screening "
                 f"@L{i} `finding {i}`" for i in range(1, 61)]
        lines.append("- [C61] [UNSUPPORTED] Cohort 61 reported an invented finding for donors @L61 `x`")

        def write(ls):
            mp.write_text("---\nsource: notes.md\nsha256: x\nlines: 61\nprofile: prose\n---\n\n"
                          "## Claims\n\n" + "\n".join(ls) + "\n", encoding="utf-8")

        write(lines)
        store.sync_root(root, cfg={}, log=lambda *a: None)
        # A second memo after it, so the first one's re-import cannot simply get its old
        # (highest) ids back -- that coincidence would hide every orphan.
        (root / ".memo" / "later.md-00000002.memo.md").write_text(
            "---\nsource: later.md\nsha256: y\nlines: 5\nprofile: prose\n---\n\n## Claims\n\n"
            + "\n".join(f"- [C{i}] [CONFIRMED] A later memo states fact number {i} about stool banks "
                        f"@L{i} `fact {i}`" for i in range(1, 6)) + "\n", encoding="utf-8")
        store.sync_root(root, cfg={}, log=lambda *a: None)
        e1 = concepts.build_embeddings(log=lambda *a: None)
        chk(e1["embedded"] == 65, f"only CONFIRMED/DRIFTED claims are embedded ({e1['embedded']} of 66)")
        c1 = concepts.cluster(k=3, log=lambda *a: None)
        db = concepts.connect()
        a, b = [r[0] for r in db.execute("SELECT id FROM claim ORDER BY id LIMIT 2")]
        db.execute("INSERT INTO edge VALUES (?,?,'conflict',0.95,'test',0)", (a, b))
        db.commit()
        chk(c1.get("claims") == 65, "the clustering holds exactly the embedded claims")

        def ids_of():
            return dict(db.execute("SELECT c.cid, c.id FROM claim c JOIN doc d ON d.id = c.doc_id"
                                   " WHERE d.memo = 'notes.md-00000001.memo.md'"))

        before = ids_of()
        lines[0] = lines[0].replace("finding number 1 ", "finding number one ")
        write(lines)
        store.sync_root(root, cfg={}, log=lambda *a: None)
        orphans = {t: db.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} NOT IN (SELECT id FROM claim)")
                   .fetchone()[0] for t, c in (("emb", "claim_id"), ("concept_member", "claim_id"),
                                               ("edge", "src"))}
        chk(not any(orphans.values()), f"a re-imported memo leaves no orphans {orphans}")
        after = ids_of()
        chk(after["1"] != before["1"] and all(after[c] == before[c] for c in before if c != "1"),
            "re-imported in place: only the claim whose text changed gets a new row")
        e2 = concepts.build_embeddings(log=lambda *a: None)
        chk(e2["embedded"] == 1, "so only it is embedded again; the other 59 keep their vectors")

        # A verifier pass changes statuses, not texts: nothing may be lost to it.
        db.execute("UPDATE claim SET hits = 7 WHERE id=?", (after["3"],))
        db.commit()
        lines[1] = lines[1].replace("[CONFIRMED]", "[DRIFTED]")
        write(lines)
        store.sync_root(root, cfg={}, log=lambda *a: None)
        c2 = db.execute("SELECT id, status FROM claim WHERE id=?", (after["2"],)).fetchone()
        kept = db.execute("SELECT COUNT(*) FROM emb WHERE claim_id=?", (after["2"],)).fetchone()[0]
        hits = db.execute("SELECT hits FROM claim WHERE id=?", (after["3"],)).fetchone()
        chk(c2 == (after["2"], "DRIFTED") and kept == 1 and hits == (7,)
            and concepts.build_embeddings(log=lambda *a: None)["embedded"] == 0,
            "a status change keeps the claim's row, its vector and its recall hits")

        x = db.execute("SELECT id FROM claim WHERE status='CONFIRMED' ORDER BY id LIMIT 1").fetchone()[0]
        db.execute("UPDATE claim SET text = text || ' (revised)' WHERE id=?", (x,))
        db.commit()
        e3 = concepts.build_embeddings(log=lambda *a: None)
        chk(e3["embedded"] == 1, "a claim whose text changed in place is re-embedded")

        # a reused id: an old vector sits under an id the next claim takes
        new_id = db.execute("SELECT MAX(id) FROM claim").fetchone()[0] + 1
        doc = db.execute("SELECT doc_id FROM claim LIMIT 1").fetchone()[0]
        stale = fake_embed(["a different, older claim text"], "")[0].astype(np.float16).tobytes()
        db.execute("INSERT INTO emb (claim_id, model, dim, vec, sha) VALUES (?,?,?,?,?)",
                   (new_id, concepts.MODEL, concepts.DIM, stale, concepts._sha("a different, older claim text")))
        db.execute("INSERT INTO claim (id, doc_id, cid, text, status) VALUES (?,?,?,?,?)",
                   (new_id, doc, "C99", "Cohort 99 reported a new finding for donor screening", "CONFIRMED"))
        db.commit()
        ids, _ = concepts._load_vectors(db)
        chk(new_id not in set(ids.tolist()), "a reused id's old vector is in no clustering")
        e4 = concepts.build_embeddings(log=lambda *a: None)
        chk(e4["embedded"] == 1, "and the new claim gets its own vector")

        concepts.cluster(k=3, log=lambda *a: None)
        y, ytext = db.execute("SELECT id, text FROM claim WHERE status='CONFIRMED' ORDER BY id DESC"
                              " LIMIT 1 OFFSET 5").fetchone()
        db.execute("UPDATE claim SET status='UNSUPPORTED' WHERE id=?", (y,))
        db.commit()
        got = concepts.search(ytext, top=3, claims_per=60, db=db)
        served = {c["id"] for g in got for c in g["claims"]}
        chk(got and y not in served, "a claim verified away after the clustering is no answer")

        # A long embedding run must not hold the write lock between batches: committing every
        # 20 batches kept it for minutes and the store sync beside it hit "database is locked".
        import sqlite3 as _sq
        import threading
        db.execute("DELETE FROM emb")
        db.commit()

        def slow_embed(texts, prefix, timeout=120.0, retries=3):
            time.sleep(0.5)
            return fake_embed(texts, prefix)

        concepts.embed_batch = slow_embed
        th = threading.Thread(target=lambda: concepts.build_embeddings(batch=8, log=lambda *a: None))
        th.start()
        time.sleep(1.2)                               # mid-run, between two batches
        wrote = False
        try:
            w = _sq.connect(str(store.db_path()), timeout=0.3)
            w.execute("UPDATE doc SET memo_mtime = memo_mtime")
            w.commit()
            w.close()
            wrote = True
        except _sq.OperationalError:
            pass
        th.join()
        chk(wrote, "a writer gets in between embedding batches: no lock is held across them")
        db.close()
    finally:
        concepts.embed_batch, store._memo_index = real_embed, real_mi
        os.environ["MEMO_GUARD_HOME"] = saved
    return ok


def check_sync_tombstones(home: Path) -> bool:
    """14) A deleted claim verdict stays deleted on every synced machine.

    Until 0.15.1 `claims --forget` only deleted locally, and the union import put the
    verdict back from any machine that still held it. That is how a self-test fixture
    -- an invented sample size, "recount gave 389" -- survived in a real store. Three
    stores here stand in for three machines; each is its own sandbox directory.
    """
    import embed
    import sync
    print("\n14) sync: verdict tombstones")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    embed.set_timeout(0.5)                  # the server is not what is under test
    text = "The cohort enrolled 512 participants"
    saved = os.environ["MEMO_GUARD_HOME"]

    def machine(name: str):
        os.environ["MEMO_GUARD_HOME"] = str(home / "machines" / name)
        import claims
        import memory
        return memory.connect(), claims.connect(), claims

    try:
        # machine A records the verdict, B already has it (it synced before)
        db_b, cdb_b, cl = machine("b")
        cl.record(cdb_b, text, "REFUTED", note="test fixture")
        db_a, cdb_a, cl = machine("a")
        fp = cl.record(cdb_a, text, "REFUTED", note="test fixture")["fp"]
        r = cl.forget(cdb_a, text)
        chk(r["deleted"] == 1 and r["matched"] == "exact", "forget deletes the local verdict")
        chk(db_a.execute("SELECT 1 FROM tombstone WHERE fp=?", (fp,)).fetchone(),
            "and leaves a tombstone keyed by the verdict's fingerprint")
        out = home / "machines" / "repo"
        sync.export(db_a, out)
        exported = json.loads((out / "claims.json").read_text(encoding="utf-8"))
        tombs = json.loads((out / "tombstones.json").read_text(encoding="utf-8"))
        chk(fp not in {v["fp"] for v in exported} and fp in {t["fp"] for t in tombs},
            "the export drops the verdict and carries the tombstone")

        db_b, cdb_b, cl = machine("b")
        r = sync.import_(db_b, out)
        chk(not cdb_b.execute("SELECT 1 FROM verdict WHERE fp=?", (fp,)).fetchone()
            and r.get("deleted_claims") == 1,
            "a machine that still had it deletes it on import")

        # an exporter that has not seen the tombstone still lists the verdict
        stale = home / "machines" / "stale-repo"
        stale.mkdir(parents=True, exist_ok=True)
        (stale / "claims.json").write_text(json.dumps(
            [{"fp": fp, "text": text, "status": "REFUTED", "note": "", "replacement": ""}]),
            encoding="utf-8")
        (stale / "tombstones.json").write_text(json.dumps([{"fp": fp, "deleted_at": time.time()}]),
                                               encoding="utf-8")
        db_c, cdb_c, cl = machine("c")
        sync.import_(db_c, stale)
        chk(not cdb_c.execute("SELECT 1 FROM verdict WHERE fp=?", (fp,)).fetchone(),
            "a stale export listing it does not bring it back")

        r = cl.forget(cdb_c, "The PMOS registry number nobody ever recorded")
        chk(r["deleted"] == 0 and db_c.execute("SELECT 1 FROM tombstone WHERE fp=?",
                                               (r["fp"],)).fetchone(),
            "a verdict that is only in the sync repo is tombstoned by its text")

        db_a, cdb_a, cl = machine("a")
        cl.record(cdb_a, text, "REFUTED", note="judged again")
        sync.export(db_a, out)
        exported = json.loads((out / "claims.json").read_text(encoding="utf-8"))
        chk(not db_a.execute("SELECT 1 FROM tombstone WHERE fp=?", (fp,)).fetchone()
            and fp in {v["fp"] for v in exported},
            "a deliberate new verdict lifts the tombstone and is exported again")
    finally:
        os.environ["MEMO_GUARD_HOME"] = saved
    return ok


def check_corpus(home: Path) -> bool:
    """13) Corpus store, tables, ingest queue, corpus recall - all inside the sandbox.

    Every assertion is a failure that would otherwise be silent: a REFUTED claim served
    as fact, a staged PDF memo pointing at a .txt nobody has, an incremental sync that
    re-reads everything, a Hungarian decimal stored as text, a write through the
    read-only SQL door, a corpus claim leaking into a session outside the root.
    """
    import hashlib as _h
    import store
    import tables
    import ingest
    print("\n13) corpus store / tables / ingest / corpus recall")
    ok = True

    def chk(cond, what):
        nonlocal ok
        print(f"   {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    root = home / "corpus-root"
    (root / "kutatas" / "proj").mkdir(parents=True, exist_ok=True)
    (root / ".memo").mkdir(exist_ok=True)
    src = root / "kutatas" / "proj" / "notes.md"
    src.write_text("# notes\n\nDonor exclusion criteria in 34 studies.\n\nexclusion\n", encoding="utf-8")
    sha = _h.sha256(src.read_bytes()).hexdigest()
    (root / ".memo" / "kutatas__proj__notes.md-00000001.memo.md").write_text(
        f"---\nsource: kutatas/proj/notes.md\nsha256: {sha}\nlines: 5\nprofile: prose\n---\n\n"
        "# kutatas/proj/notes.md\n\n## Claims\n\n"
        "- [C1] [CONFIRMED] Donor exclusion criteria were reported in 34 studies @L3 `exclusion criteria in 34`\n"
        "- [C2] [REFUTED] Donor exclusion criteria were reported in 99 studies @L3 `exclusion criteria in 99`\n"
        "- [C3] [CONFIRMED] @L5 `exclusion` @semantic L1-5\n", encoding="utf-8")
    (root / ".memo" / "paper_pdf-abcdef12.txt-00000002.memo.md").write_text(
        "---\nsource: paper_pdf-abcdef12.txt\nsha256: x\nlines: 20\nprofile: prose\n---\n\n## Claims\n\n"
        "- [C1] [CONFIRMED] Donor exclusion criteria included recent antibiotic use @L10 `recent antibiotic use`\n",
        encoding="utf-8")
    (root / ".memo" / "_source_map.tsv").write_text(
        "staged\toriginal\tmode\npaper_pdf-abcdef12.txt\tkutatas/proj/paper.pdf\tingest\n", encoding="utf-8")

    real_mi = store._memo_index
    store._memo_index = lambda cfg: (_ for _ in ()).throw(ImportError("hermetic"))
    try:
        r1 = store.sync_root(root, cfg={}, log=lambda *a: None)
        hits = store.search("donor exclusion criteria")
        texts = " | ".join(h["text"] for h in hits)
        chk(any("34 studies" in h["text"] and h["path"] == "kutatas/proj/notes.md" and h["line"] == 3
                for h in hits), "a CONFIRMED claim comes back with its file and line")
        chk("99 studies" not in texts, "a REFUTED claim never comes back")
        chk(not any(h["text"].startswith("@L") for h in hits), "an anchor-only claim is not an answer")
        chk(any(h["path"] == "kutatas/proj/paper.pdf" and h["project"] == "kutatas/proj" for h in hits),
            "a staged .txt memo resolves to the original PDF and its project")
        r2 = store.sync_root(root, cfg={}, log=lambda *a: None)
        chk(r1["added"] == 2 and r2["added"] == 0 and r2["changed"] == 0,
            f"incremental: second sync touches nothing ({r2['added']} added, {r2['changed']} changed)")
        mp = root / ".memo" / "paper_pdf-abcdef12.txt-00000002.memo.md"
        mp.write_text(mp.read_text(encoding="utf-8").replace("recent antibiotic use @L10", "recent antibiotic use within 3 months @L10"), encoding="utf-8")
        r3 = store.sync_root(root, cfg={}, log=lambda *a: None)
        mp.unlink()
        r4 = store.sync_root(root, cfg={}, log=lambda *a: None)
        chk(r3["changed"] == 1 and r4["removed"] == 1, "an edited memo is re-imported, a deleted one removed")
        t0 = time.time(); store.search("donor exclusion criteria"); ms = (time.time() - t0) * 1000
        chk(ms < 200, f"search latency {ms:.0f} ms")
    finally:
        store._memo_index = real_mi

    (root / "kutatas" / "proj" / "tabla.csv").write_text(
        "id;varos;prevalencia\n0123;Szeged;33,2\n0456;Debrecen;22\n", encoding="utf-8")
    tr = tables.sync_root(root, log=lambda *a: None)
    chk(tr["tables"] == 1, "one CSV becomes one SQL table")
    rows = tables.find("Szeged")
    chk(rows and rows[0]["path"] == "kutatas/proj/tabla.csv", "a row is found by full-text search")
    name = rows[0]["table"] if rows else "t1"
    cols, data = tables.sql(f'SELECT "prevalencia", "id" FROM {name} ORDER BY 1 DESC')
    chk(data and data[0][0] == 33.2 and data[0][1] == "0123",
        "'33,2' is the number 33.2; '0123' stays an identifier")
    try:
        tables.sql(f"DELETE FROM {name}")
        chk(False, "the SQL door is read-only")
    except Exception:
        chk(True, "the SQL door is read-only")

    cfg = {"corpus_roots": [str(root)], "ingest": True}
    chk(ingest.enqueue(root / "kutatas" / "proj" / "new.md", "test", cfg), "a file inside the root is queued")
    chk(not ingest.enqueue(home / "elsewhere.md", "test", cfg), "a file outside every root is not")
    chk(not ingest.enqueue(root / ".memo" / "x.memo.md", "test", cfg), "the memo dir itself is never queued")
    items = ingest._take_queue()
    chk(len(items) == 1 and items[0]["rel"] == "kutatas/proj/new.md", "the queue hands over exactly what was queued")

    cfgp = mg.data_dir() / "config.json"
    saved = cfgp.read_text(encoding="utf-8") if cfgp.exists() else None
    c = json.loads(saved) if saved else {}
    c.update({"corpus_roots": [str(root)], "corpus_recall": True})
    cfgp.write_text(json.dumps(c), encoding="utf-8")
    try:
        q = "What were the donor exclusion criteria reported in the studies?"
        _, out_in = hook("recall.py", {"session_id": "corpus-test", "prompt": q, "cwd": str(root),
                                       "hook_event_name": "UserPromptSubmit"})
        _, out_out = hook("recall.py", {"session_id": "corpus-test-2", "prompt": q,
                                        "cwd": str(home / "fake-projects"),
                                        "hook_event_name": "UserPromptSubmit"})
        chk("[memo-guard corpus]" in out_in and "34 studies" in out_in and "99 studies" not in out_in,
            "inside the root the hook injects the verified claim, never the refuted one")
        chk("[memo-guard corpus]" not in out_out, "outside the root nothing from the corpus leaks in")
    finally:
        if saved is None:
            cfgp.unlink(missing_ok=True)
        else:
            cfgp.write_text(saved, encoding="utf-8")

    # 0.15.13: corpus_exclude keeps a workspace's copies, work folders and tool lists out of
    # every store. 2026-10-05: data.db held 42 tables (26,510 rows) that the memo index had
    # excluded on purpose, among them the indexer's own 18,847-row file list.
    bundle = root / "kutatas" / "proj" / "BUNDLE_2026-01-01"
    bundle.mkdir(exist_ok=True)
    # tables.py skips files under 50 bytes, so both fixtures are a few rows long
    (bundle / "tabla.csv").write_text("id;varos;prevalencia\n9;Pecs;12,5\n10;Gyor;8\n11;Eger;3,1\n",
                                      encoding="utf-8")
    (root / "kutatas" / "proj" / "listing.csv").write_text(
        "path;size\nkutatas/proj/notes.md;71\nkutatas/proj/tabla.csv;58\n", encoding="utf-8")
    ex = {"corpus_exclude": ["/BUNDLE_[^/]*/", r"/proj/listing\.csv$", "(unclosed"]}
    t_all = tables.sync_root(root, log=lambda *a: None, cfg={})
    chk(t_all["files_imported"] == 2 and tables.find("Pecs"),
        "without corpus_exclude a bundle's copy and a file list are imported")
    t_ex = tables.sync_root(root, log=lambda *a: None, cfg=ex)
    chk(t_ex["removed"] == 2 and not tables.find("Pecs") and tables.find("Szeged"),
        "with it both tables are dropped, the rest stays, and a broken pattern is ignored")
    chk(mg.corpus_excluded("kutatas\\proj\\BUNDLE_x\\a.md", ex)
        and not mg.corpus_excluded("kutatas/proj/notes.md", ex)
        and not mg.corpus_excluded("kutatas/proj/BUNDLE_x/a.md", {}),
        "corpus_excluded takes either slash, and matches only what it names")
    chk(not ingest.enqueue(bundle / "new.md", "test", {**cfg, **ex}),
        "an excluded path is never queued for ingest")
    ingest._take_queue()
    bsrc = bundle / "b.md"
    bsrc.write_text("# b\n\nA bundle copy of the donor notes.\n", encoding="utf-8")
    bsha = _h.sha256(bsrc.read_bytes()).hexdigest()
    (root / ".memo" / "kutatas__proj__BUNDLE_2026-01-01__b.md-00000003.memo.md").write_text(
        f"---\nsource: kutatas/proj/BUNDLE_2026-01-01/b.md\nsha256: {bsha}\nlines: 3\nprofile: prose\n"
        "---\n\n## Claims\n\n"
        "- [C1] [CONFIRMED] The bundle copies the donor notes @L3 `bundle copy of the donor notes`\n",
        encoding="utf-8")
    store._memo_index = lambda cfg: (_ for _ in ()).throw(ImportError("hermetic"))
    try:
        s1 = store.sync_root(root, cfg={}, log=lambda *a: None)
        s2 = store.sync_root(root, cfg=ex, log=lambda *a: None)
        s3 = store.sync_root(root, cfg=ex, log=lambda *a: None)
        chk(s1["added"] == 1 and s2["removed"] == 1 and s3["added"] == 0,
            "a memo of an excluded path leaves the memo store and is not imported again "
            f"({s1['added']}/{s2['removed']}/{s3['added']})")
    finally:
        store._memo_index = real_mi
    return ok


def check_doctor(home: Path) -> bool:
    """The two destructive operations, on a sandbox that looks like the real one.

    `--fix` edits the user's settings.json and `--clean-handoffs` deletes files.
    Both are narrow by design, and "narrow by design" is worth exactly as much
    as a test that the blast radius really is what the design says.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    cfgdir = home / "doctor-claude"
    cfgdir.mkdir(parents=True, exist_ok=True)
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
    import autopilot, doctor
    importlib.reload(autopilot)
    importlib.reload(doctor)

    (cfgdir / "settings.json").write_text(json.dumps({
        "env": {"KEEP": "1"},
        "theme": "dark",
        "hooks": {
            "UserPromptSubmit": [{"hooks": [
                {"type": "command",
                 "command": "bash $HOME/.claude/skills/memo-index/scripts/hook_gate.sh"}]}],
            "PostToolUse": [{"matcher": "*", "hooks": [
                {"type": "command",
                 "command": "python3 $HOME/.claude/skills/memo-index/scripts/ctx_watch.py --hook"},
                {"type": "command", "command": "echo someone-elses-hook"}]}],
        },
    }, indent=2), encoding="utf-8")

    doctor.apply_fix()
    got = json.loads((cfgdir / "settings.json").read_text(encoding="utf-8"))
    post = got.get("hooks", {}).get("PostToolUse", [])
    remaining = [h["command"] for g in post for h in g["hooks"]]

    # Running it again must be a no-op, not a second round of edits.
    before = (cfgdir / "settings.json").read_text(encoding="utf-8")
    doctor.apply_fix()
    idempotent = (cfgdir / "settings.json").read_text(encoding="utf-8") == before

    # Handoff litter: one unfilled template, one someone actually wrote in.
    root = home / "litter"
    (root / "a" / ".memo").mkdir(parents=True, exist_ok=True)
    (root / "b" / ".memo").mkdir(parents=True, exist_ok=True)
    (root / "a" / ".memo" / "HANDOFF.md").write_text(
        "# Handoff\n<!-- Fill this in before /clear: the question -->\n", encoding="utf-8")
    (root / "b" / ".memo" / "HANDOFF.md").write_text(
        "# Handoff\nWe decided to switch module_13 to exponential backoff.\n", encoding="utf-8")
    doctor.clean_handoffs(root)

    print("\n11) DOCTOR")
    checks = {
        "ctx_watch hook removed":
            not any("ctx_watch" in c for c in remaining),
        "an unrelated hook in the same group survives":
            any("someone-elses-hook" in c for c in remaining),
        "MEMO_CTX_THRESHOLD raised above 100":
            float(got["env"].get("MEMO_CTX_THRESHOLD", 0)) > 100,
        "unrelated settings untouched":
            got.get("theme") == "dark" and got["env"].get("KEEP") == "1",
        "running --fix twice changes nothing": idempotent,
        "unfilled handoff deleted":
            not (root / "a" / ".memo" / "HANDOFF.md").exists(),
        "a handoff someone wrote in is kept":
            (root / "b" / ".memo" / "HANDOFF.md").exists(),
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


STUB_MEMO_GEN = """#!/usr/bin/env python3
import argparse, os, pathlib, sys, time
a = argparse.ArgumentParser(); a.add_argument("--root"); a.add_argument("--include",
    action="append"); a.add_argument("--memo-dir"); a.add_argument("--profile")
n = a.parse_args()
name = n.include[0].split("/")[-1]
if name in os.environ.get("STUB_FAIL", "").split(","):
    sys.stderr.write("stub: refusing " + name); sys.exit(1)
if name in os.environ.get("STUB_SLOW", "").split(","):
    time.sleep(30)
d = pathlib.Path(n.memo_dir); d.mkdir(parents=True, exist_ok=True)
(d / (name + ".memo.md")).write_text("stub memo for " + name)
pathlib.Path(os.environ["STUB_ORDER"]).open("a").write(name + "\\n")
"""


def check_map_reduce(home: Path) -> bool:
    """Does the model path survive one bad source?

    The old shape ran `memo_gen` once over every source with a single timeout,
    read the kill as total failure, and fell back to deterministic — discarding
    memos it had already written. This checks the replacement without needing a
    model: a stub generator that fails on demand, sleeps on demand, and records
    the order it was called in. What is being tested is the control flow, which
    is the part that was wrong.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import compressor
    importlib.reload(compressor)

    wd = home / "mapreduce"
    (wd / "sources").mkdir(parents=True, exist_ok=True)
    # Deliberately out of size order, so "smallest first" is visible and
    # conversation.md jumping the queue is not an accident of the filesystem.
    for name, size in [("conversation.md", 5000), ("aaa_big.md", 9000),
                       ("bbb_small.md", 100), ("ccc_mid.md", 2000),
                       ("ddd_tiny.md", 50)]:
        (wd / "sources" / name).write_text("x" * size, encoding="utf-8")
    skill = home / "stubskill"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "memo_gen.py").write_text(STUB_MEMO_GEN, encoding="utf-8")

    order_file = home / "stub_order.txt"

    def run(fail="", slow="", total=900.0, step=240.0):
        order_file.write_text("", encoding="utf-8")
        for f in (wd / ".memo").glob("*"):
            f.unlink()
        os.environ.update({"STUB_FAIL": fail, "STUB_SLOW": slow,
                           "STUB_ORDER": str(order_file)})
        done, failed = compressor.map_sources(wd, skill, step, total,
                                              lambda m: None)
        seen = order_file.read_text(encoding="utf-8").split()
        return done, failed, seen

    done, failed, seen = run()
    ordering = seen[:1] == ["conversation.md"] and seen[1:] == [
        "ddd_tiny.md", "bbb_small.md", "ccc_mid.md", "aaa_big.md"]

    d2, f2, s2 = run(fail="ccc_mid.md")
    isolated = "ccc_mid.md" in f2 and len(d2) == 4 and "aaa_big.md" in d2

    d3, f3, _ = run(slow="bbb_small.md", step=2.0)
    slow_ok = "bbb_small.md" in f3 and len(d3) == 4

    d4, f4, _ = run(total=0.0)
    deadline_ok = d4 == [] and len(f4) == 5

    print("\n10) MODEL PATH ON A BIG TRANSCRIPT (stub generator)")
    checks = {
        "conversation first, then smallest-first": ordering,
        "a failing source skips one file, not the run": isolated,
        "a source that times out is skipped, run continues": slow_ok,
        "the total deadline stops it and names what was dropped": deadline_ok,
        "every source is accounted for (done + failed)":
            all(len(d) + len(f) == 5 for d, f in
                [(done, failed), (d2, f2), (d3, f3), (d4, f4)]),
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_recall_quality() -> bool:
    """Guard the retrieval numbers, not just the plumbing.

    Section 8 proves the hook fires and stays quiet in the right places. It says
    nothing about whether what comes back is any good — and every knob in the
    retriever (the relevance floor, the coverage damping, the score blend) is
    one edit away from quietly trading precision for recall. The floors below
    are the measured values with a margin, so a real regression trips them and
    normal drift does not.

    Run as a subprocess on purpose: the harness rebuilds MEMO_GUARD_HOME and
    drops modules from sys.modules, which would pull the store out from under
    the rest of this file.
    """
    r = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "recall_eval.py"),
         "--no-embed", "--json"], capture_output=True, text=True, timeout=120)
    print("\n9) RECALL QUALITY (bundled corpus, lexical only)")
    try:
        m = json.loads(r.stdout)["modes"]["lexical only"]
    except Exception:
        print(f"   FAIL harness did not produce JSON: "
              f"{(r.stderr or r.stdout)[:200]}")
        return False
    checks = {
        f"recall >= 65%  (got {m['recall']:.0%})": m["recall"] >= 0.65,
        f"lexical recall = 100%  (got {m['recall_lexical']:.0%})":
            m["recall_lexical"] >= 0.99,
        f"precision >= 85%  (got {m['precision']:.0%})": m["precision"] >= 0.85,
        f"false injection <= 5%  (got {m['false_injection_rate']:.0%})":
            m["false_injection_rate"] <= 0.05,
        f"zero cross-project leaks  (got {m['gate_breaches']})":
            m["gate_breaches"] == 0,
        f"<= 30 tok/prompt  (got {m['mean_tokens_per_prompt']:.0f})":
            m["mean_tokens_per_prompt"] <= 30,
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    # Not a pass/fail line: paraphrase recall is the honest weak spot of the
    # lexical path and the number the semantic path has to justify itself
    # against. Printing it keeps that visible instead of comfortable.
    print(f"   ..  paraphrase recall {m['recall_paraphrase']:.0%} "
          f"(lexical path only — this is what embeddings are for)")
    return all(checks.values())


def check_calibration_converges() -> bool:
    """Does the correction loop actually land on the target?

    This runs the loop against a transcription of Claude Code's own arithmetic
    (2.1.237: `min(floor(effWin * pct/100), effWin - 13000)`, with
    `effWin = window - min(reserve, 20000)`). It therefore proves the loop
    converges *given that formula* — it cannot prove the formula is still the
    product's. That is the honest scope: it catches a regression in the
    correction maths, not a change upstream.
    """
    import importlib, math
    sys.path.insert(0, str(Path(__file__).parent))
    import autopilot
    importlib.reload(autopilot)

    def fires_at(window, override, reserve=20000):
        eff = window - min(reserve, 20000)
        return min(math.floor(eff * override / 100.0), eff - 13000)

    cases = [("1M / autoCompactWindow 800k", 1_000_000, 800_000),
             ("1M / no override window", 1_000_000, 1_000_000),
             ("200k window", 200_000, 200_000)]
    target, results = 70.0, {}
    for label, real, cc in cases:
        autopilot.save_state({})
        autopilot.cmd_enable(target)
        measured, rounds = None, 0
        for rounds in range(6):
            ov = float(autopilot.load_state()["override"])
            measured = 100.0 * fires_at(cc, ov) / real
            if abs(measured - target) <= autopilot.TOLERANCE_PCT:
                break
            autopilot.record_firing(measured, mg.load_config())
        results[f"{label}: {measured:.1f}% after {rounds} correction(s)"] = (
            abs(measured - target) <= autopilot.TOLERANCE_PCT and rounds <= 2)
    print("\n6) CALIBRATION")
    for name, val in results.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(results.values())


def check_calibration_outlier(home: Path) -> bool:
    """One odd compaction must not undo a calibration that is on target.

    Replays the sequence that did exactly that under 0.14.1 (target 70, a 1M
    window with autoCompactWindow 800k): the first firing, at the default
    override, landed at 54.6% and moved it to 89.7; 89.7 then fired at 69.6,
    69.5 and 68.7 — on target — and then once at 65.1%. Taken at its word, that
    one firing gave 89.7 * 70 / 65.1 = 96.5, clamped to 95, and the next
    compaction overshot to 73.2%.

    Robustness bought by ignoring evidence would be no fix, so the other side is
    checked too: a genuine change is still followed, and a state file written by
    0.14.1 still reports and learns.
    """
    import importlib, io, math
    from contextlib import redirect_stdout
    sys.path.insert(0, str(Path(__file__).parent))
    cfgdir = home / "outlier-claude"
    cfgdir.mkdir(parents=True, exist_ok=True)
    (cfgdir / "settings.json").write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
    import autopilot
    importlib.reload(autopilot)
    cfg = mg.load_config()

    def override() -> float:
        return float(autopilot.load_state()["override"])

    def written() -> float:
        return float(json.loads((cfgdir / "settings.json").read_text(encoding="utf-8"))
                     ["env"][autopilot.ENV_KEY])

    def calibrated() -> bool:
        return autopilot.load_state().get("calibrated") is True

    def fires_at(ov, cc_window, real=1_000_000):
        """Claude Code's trigger, as in check_calibration_converges."""
        eff = cc_window - 20_000
        return 100.0 * min(math.floor(eff * ov / 100.0), eff - 13000) / real

    checks = {}
    autopilot.save_state({})
    with redirect_stdout(io.StringIO()):
        autopilot.cmd_enable(70.0)
    autopilot.record_firing(54.6, cfg)
    checks["a cold start still corrects on its first firing (70 -> 89.7)"] = (
        override() == 89.7)
    for pct in (69.6, 69.5, 68.7):
        autopilot.record_firing(pct, cfg)
    checks["89.7 is calibrated after firing at 69.6, 69.5, 68.7"] = calibrated()
    autopilot.record_firing(65.1, cfg)
    checks[f"the lone 65.1% firing leaves it at 89.7, not 95 "
           f"(override {override():g}, settings.json {written():g})"] = (
        override() == 89.7 and written() == 89.7)
    checks["...and it is still calibrated"] = calibrated()

    # A genuine change: autoCompactWindow removed, so 89.7 now fires at 87.9%.
    # The first such firing is a lone high one and is outvoted like the low
    # one; by the third, three of the last five agree and the median follows.
    autopilot.record_firing(fires_at(override(), 1_000_000), cfg)
    checks["a lone high firing is outvoted too"] = override() == 89.7
    for _ in range(2):
        autopilot.record_firing(fires_at(override(), 1_000_000), cfg)
    landed = fires_at(override(), 1_000_000)
    checks[f"a genuine change is corrected by its third firing "
           f"(override now {override():g}, which fires at {landed:.1f}%)"] = (
        abs(landed - 70.0) <= autopilot.TOLERANCE_PCT)

    # The state 0.14.1 left behind on the machine this was found on: thrown to
    # 95, overshot, corrected to 90.9 — and a last_correction without the keys
    # this version adds.
    autopilot.save_state({
        "enabled": True, "target": 70.0, "override": 90.9, "calibrated": False,
        "samples": [{"measured": m, "override": o, "ts": ts} for m, o, ts in [
            (69.6, 89.7, "2026-09-14T11:28:29"),
            (69.5, 89.7, "2026-09-17T19:32:50"),
            (68.7, 89.7, "2026-09-21T09:36:26"),
            (65.1, 89.7, "2026-09-21T11:12:40"),
            (73.2, 95.0, "2026-09-22T21:12:40")]],
        "last_correction": {"from": 95.0, "to": 90.9, "fired_at_pct": 73.2,
                            "target": 70.0, "ts": "2026-09-22T21:12:40"}})
    autopilot.apply_override(90.9)
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            autopilot.cmd_status()
        out = out.getvalue()
    except Exception as e:
        out = f"cmd_status raised {e!r}"
    checks["a 0.14.1 state file still reports its last correction"] = (
        "after firing at 73.2%" in out)
    checks["...and the median puts its 90.9 on target (70.0%)"] = (
        "70.0% at override 90.9" in out)
    autopilot.record_firing(fires_at(90.9, 800_000), cfg)
    checks["...and the next firing confirms it rather than moving it"] = (
        calibrated() and override() == 90.9)

    print("\n6b) CALIBRATION AGAINST ONE ODD FIRING")
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_stub_visible(home: Path) -> bool:
    """A session that ended at "stub" must still be findable — and must never
    outrank a real memo."""
    sd = home / "sessions"

    def mk(name, phase, cwd, age_h, body):
        d = sd / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "RESUME.md").write_text(body, encoding="utf-8")
        (d / "STATE.json").write_text(json.dumps(
            {"phase": phase, "cwd": cwd, "resume_tokens_est": 400,
             "raw_tokens_est": 80000}), encoding="utf-8")
        t = time.time() - age_h * 3600
        os.utime(d / "RESUME.md", (t, t))

    mk("zz-stub", "stub", "/stubproj", 1, "STUBBODY pointing at the archive\n" * 8)
    _, out1 = hook("inject_resume.py", {"session_id": "n1", "cwd": "/stubproj",
                                        "source": "startup",
                                        "hook_event_name": "SessionStart"})
    mk("zz-done", "done", "/stubproj", 5, "DONEBODY the real memo\n" * 8)
    _, out2 = hook("inject_resume.py", {"session_id": "n2", "cwd": "/stubproj",
                                        "source": "startup",
                                        "hook_event_name": "SessionStart"})
    _, out3 = hook("inject_resume.py", {"session_id": "n3", "cwd": "/elsewhere",
                                        "source": "startup",
                                        "hook_event_name": "SessionStart"})
    checks = {
        "a stub-only project is still pointed at": "zz-stub" in out1,
        "a real memo outranks a newer stub": "zz-done" in out2,
        "no pointer leaks to another project": "zz-" not in out3,
    }
    print("\n7) STUB FALLBACK")
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_recall_stays_offline() -> bool:
    """`allow_semantic=False` has to mean no model call, all the way down.

    A stopwatch cannot assert this. The model server on a developer's machine
    answers, so a stray embed costs milliseconds here and seconds on a machine
    where the embed model is missing or wedged — the timing check passes and the
    user waits 2.3 s per keystroke. Count the calls instead: none is none on
    every machine.

    Both short-circuits that hid the original regression are removed first — a
    verdict vector is planted, so claims.py cannot decline before embedding.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import claims, embed, memory
    importlib.reload(memory)

    db = memory.connect()
    memory.promote(db, "The PMOS review protocol was registered before "
                       "screening began", "/offline-probe", kind="reference")
    cdb = claims.connect()
    claims.record(cdb, "The PMOS cohort enrolled 412 participants", "REFUTED",
                  note="recount gave 389")
    fp = cdb.execute("SELECT fp FROM verdict LIMIT 1").fetchone()
    if not fp:
        return False
    cdb.execute("INSERT OR REPLACE INTO verdict_vec (fp,model,dim,data)"
                " VALUES (?,?,?,?)",
                (fp[0], "stub-embed", 3, embed.pack([1.0, 0.0, 0.0])))
    cdb.commit()

    calls: list[str] = []
    real = embed.embed

    def counted(*a, **k):
        calls.append(str(a[:1]))
        return None

    embed.embed = counted
    try:
        memory.recall(db, "When was the PMOS review protocol registered?",
                      "/offline-probe", goal=None, allow_semantic=False)
    finally:
        embed.embed = real
    if calls:
        print(f"   (recall made {len(calls)} embed call(s) with the semantic "
              "path switched off)")
    return not calls


def check_recall(home: Path) -> bool:
    """The recall hook is judged on what it stays silent about.

    Injecting a relevant fact is the easy half. The half that decides whether
    this is worth having on every prompt is the three cases where it must
    produce nothing at all — and the latency, because this runs in front of a
    keystroke.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import embed
    # The model server may be slow or wedged on the machine running this; the
    # test is about the hook's behaviour, not the server's.
    embed.set_timeout(0.5)
    import memory, claims
    importlib.reload(memory)

    db = memory.connect()
    memory.promote(db, "The PROSPERO registration number for the PMOS review "
                       "is CRD42024518822", "/repo", kind="reference",
                   utility=0.8)
    memory.promote(db, "The rosacea review was rejected for AI-fabricated "
                       "references", "/repo", kind="decision", utility=0.8)
    claims.record(claims.connect(),
                  "The sample size in the PMOS cohort was 412 participants",
                  "REFUTED", note="recount gave 389")

    def run(prompt: str, sid: str) -> tuple[str, float]:
        t = time.time()
        rc, out = hook("recall.py", {"prompt": prompt, "cwd": "/repo",
                                     "session_id": sid,
                                     "hook_event_name": "UserPromptSubmit"})
        return out.strip(), (time.time() - t) * 1000

    # First call pays for the model-server health probe (0.6 s against a wedged
    # server) and caches the verdict for a minute. Timing that one would measure
    # the probe, not the hook; timing only the warm one would hide it. Both.
    _, cold_ms = run("A first prompt that warms the health probe cache only",
                     "rc0")
    hit_out, hit_ms = run("What was the PROSPERO registration number we used "
                          "for the PMOS review?", "rc1")
    again, _ = run("Remind me of the PROSPERO registration number for PMOS",
                   "rc1")
    short, _ = run("ok go", "rc2")
    slash, _ = run("/memo-guard:status plus several more words to pass length",
                   "rc2")
    off, _ = run("Can you refactor the pagination logic in the checkout "
                 "service please?", "rc3")
    warn, _ = run("I think the sample size in the PMOS cohort was 412 "
                  "participants, right?", "rc4")

    # The budget below is a behaviour assertion, not a stopwatch on this box.
    # Measured on this machine, 12 warm calls each, subprocess round trip
    # included (bare `python3 -c pass` is ~27 ms of that):
    #   sandbox fixture, 2 facts        min 42  median 46   max 61 ms
    #   copy of a real store, 46 facts  min 88  median 127  max 135 ms
    # So 400 ms is not a tight budget for the lexical path — it is roughly 3x
    # the real-corpus median, and anything that breaches it has stopped being
    # the lexical path. That is exactly what happened: memory._refuted() called
    # claims.match() without passing `allow_semantic` down, so each candidate
    # fact took an embed round trip after the caller had already decided the
    # model server was unaffordable — 2.3 s per prompt on a store with verdict
    # vectors. The fixture here cannot reproduce that (no embedder, so no
    # verdict vectors, so claims.py short-circuits before embedding), which is
    # why the timing check is backed by the no-network assertion below.
    #
    # Not covered by either: recall_deadline_s is advisory. Nothing interrupts
    # a call that has already started; the deadline only gates whether the
    # semantic path is attempted at all.
    no_net = check_recall_stays_offline()

    print("\n8) RECALL")
    checks = {
        "relevant prompt recalls the fact": "CRD42024518822" in hit_out,
        "same fact not injected twice in a session": again == "",
        "short prompt stays silent": short == "",
        "slash command stays silent": slash == "",
        "unrelated prompt stays silent": off == "",
        "refuted claim is flagged": "REFUTED" in warn,
        "marked as data, not instructions": "not instructions" in hit_out,
        f"warm latency under 400 ms (was {hit_ms:.0f} ms, "
        f"cold {cold_ms:.0f} ms incl. interpreter start)": hit_ms < 400,
        "lexical-only recall makes no model call": no_net,
    }
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_busy_vs_wedged() -> bool:
    """A server serving somebody else must never be diagnosed as broken.

    The two states are identical at the socket: a request goes out, nothing
    comes back. The prescriptions are opposite — wedged wants a restart, busy
    wants patience — so getting this wrong is not a cosmetic error. It happened
    here: a memo-index run held the only slot (`-np 1`) for twenty minutes
    while /api/tags answered in 3 ms, the doctor called it wedged, and the fix
    it printed would have killed the job.
    """
    print("\n[busy is not wedged]")
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import broker
    importlib.reload(broker)
    import doctor
    importlib.reload(doctor)

    checks = {}

    checks["ps TIME mm:ss.ff parses"] = abs(broker._cpu_seconds("12:34.56") - 754.56) < 0.01
    checks["ps TIME hh:mm:ss parses"] = broker._cpu_seconds("1:02:03") == 3723
    checks["ps TIME dd-hh:mm:ss parses"] = broker._cpu_seconds("2-03:04:05") == 183845
    checks["an unparseable TIME field is 0, not a crash"] = broker._cpu_seconds("??") == 0.0

    real_cpu = broker.runner_cpu_ms
    real_clients = broker.other_clients
    real_sleep = broker.time.sleep
    try:
        broker.time.sleep = lambda _s: None

        def cpu(*vals):
            it = iter(vals)
            broker.runner_cpu_ms = lambda: next(it)

        cpu(1000.0, 1400.0)
        broker.other_clients = lambda: 1
        ev = broker.busy_evidence(sample_s=1.0)
        checks["CPU burning + another client attached reads as busy"] = (
            ev["busy"] and ev["cpu_ms"] == 400 and ev["clients"] == 1)

        # The mirror of the original bug. Loading a 5 GB model burns CPU with
        # nobody attached, and on a paging machine that load outlasts the probe
        # timeout — so CPU alone would call a merely-slow server "busy" and
        # advise waiting for a queue that does not exist.
        cpu(1000.0, 1400.0)
        broker.other_clients = lambda: 0
        ev = broker.busy_evidence(1.0)
        checks["CPU burning with nobody attached is NOT busy"] = not ev["busy"]
        checks["...and it says why: loading, not serving"] = "loading" in ev["why"]

        cpu(1000.0, 1000.0)
        broker.other_clients = lambda: 1
        checks["an idle runner does not read as busy"] = not broker.busy_evidence(1.0)["busy"]

        cpu(1000.0, 1400.0)
        broker.other_clients = lambda: None
        ev = broker.busy_evidence(1.0)
        checks["no lsof means unknown, not a guess"] = (
            (not ev["known"]) and not ev["busy"] and ev["clients"] is None)

        broker.runner_cpu_ms = lambda: None
        broker.other_clients = lambda: 1
        ev = broker.busy_evidence(1.0)
        checks["unmeasurable is not silently 'idle'"] = (not ev["known"]) and not ev["busy"]
    finally:
        broker.runner_cpu_ms = real_cpu
        broker.other_clients = real_clients
        broker.time.sleep = real_sleep

    # The verdicts, with the server stubbed out entirely.
    real = (broker.healthy, broker.port_up, broker.busy_evidence,
            broker.loaded_models, broker.probe_hardware)
    try:
        broker.healthy = lambda *a, **k: False
        broker.loaded_models = lambda: [{"name": "m", "size_mb": 1, "on_gpu": 1.0}]
        broker.probe_hardware = lambda: {}

        broker.port_up = lambda *a, **k: False
        checks["nothing listening reads as DOWN, not wedged"] = (
            broker.diagnose()["verdict"] == "DOWN")

        broker.port_up = lambda *a, **k: True
        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": True,
                                                "cpu_ms": 400, "why": "w"}
        busy = broker.diagnose()
        checks["port up + runner computing reads as BUSY"] = busy["verdict"] == "BUSY"
        checks["the BUSY fix never says restart"] = not any(
            w in busy["fix"].lower() for w in ("restart", "level 3", "kill"))
        checks["the BUSY fix does not prescribe more slots"] = (
            "num_parallel" not in busy["fix"].lower())

        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": False,
                                                "cpu_ms": 0, "why": "w"}
        wedged = broker.diagnose()
        checks["port up + nothing computing still reads as WEDGED"] = (
            wedged["verdict"] == "WEDGED")
        checks["the WEDGED fix does say level 3"] = "level 3" in wedged["fix"]
    finally:
        (broker.healthy, broker.port_up, broker.busy_evidence,
         broker.loaded_models, broker.probe_hardware) = real

    # The doctor has to carry the distinction through, not re-derive it.
    real_d = (broker.healthy, broker.diagnose)
    try:
        broker.healthy = lambda *a, **k: False
        broker.diagnose = lambda *a, **k: {
            "verdict": "BUSY", "why": "another client holds the slot",
            "fix": "wait", "loaded": []}
        f = doctor.check_model_server()
        checks["the doctor reports BUSY as info, not a warning"] = (
            len(f) == 1 and f[0].level == "info")
        checks["the doctor's BUSY text never advises a restart"] = not any(
            w in (f[0].detail + f[0].fix).lower()
            for w in ("--recover --level 3", "restarts the model server"))

        broker.diagnose = lambda *a, **k: {
            "verdict": "WEDGED", "why": "no runner is computing",
            "fix": "recover --level 2, then --level 3", "loaded": []}
        f = doctor.check_model_server()
        checks["the doctor still warns, and offers level 3, when truly wedged"] = (
            f[0].level == "warn" and "level 3" in f[0].fix)
    finally:
        broker.healthy, broker.diagnose = real_d

    # Level 3 says "restart". Killing and not starting is not a restart.
    real_r = (broker._run, broker._spawn_server, broker.busy_evidence,
              broker.loaded_models, broker.healthy, broker.diagnose,
              broker.probe_hardware, broker.time.sleep)
    try:
        killed, spawned = [], []
        broker._run = lambda cmd, **k: killed.append(cmd)
        broker._spawn_server = lambda: spawned.append(True)
        broker.loaded_models = lambda: []
        broker.healthy = lambda *a, **k: True
        broker.diagnose = lambda *a, **k: {"verdict": "OK"}
        broker.probe_hardware = lambda: {}
        broker.time.sleep = lambda _s: None

        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": False,
                                                "cpu_ms": 0, "why": "idle"}
        r = broker.recover(3)
        checks["level 3 kills the server"] = bool(killed)
        checks["level 3 also starts one again"] = spawned == [True]
        checks["an idle level 3 does not cry wolf"] = not any(
            "WARNING" in a for a in r["actions"])

        killed, spawned = [], []
        broker.busy_evidence = lambda *a, **k: {"known": True, "busy": True,
                                                "cpu_ms": 400, "why": "w"}
        r = broker.recover(3)
        checks["level 3 says out loud that it aborted a live request"] = any(
            "WARNING" in a for a in r["actions"])
    finally:
        (broker._run, broker._spawn_server, broker.busy_evidence,
         broker.loaded_models, broker.healthy, broker.diagnose,
         broker.probe_hardware, broker.time.sleep) = real_r

    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_degradation(home: Path) -> bool:
    """What memo-guard does when the model server is up but does not answer.

    This is the failure mode that hides: /api/tags replies in a millisecond
    while /api/embed never returns, so every health check that asks "is the
    server there" says yes and every prompt pays the full embed timeout. Both
    findings below were live on the machine this was written on.
    """
    import importlib
    sys.path.insert(0, str(Path(__file__).parent))
    import embed, broker, recall as R
    importlib.reload(embed)

    checks = {}

    # 1) A lock whose owner died must not disable the semantic path forever.
    #    lock_status reports `stale`; the caller used to throw the whole dict at
    #    a truthiness test, so a compressor that crashed holding the model lock
    #    switched semantic recall off permanently and said nothing.
    real = broker.lock_status
    try:
        broker.lock_status = lambda name: {"owner": "compressor/dead",
                                           "age_s": 900.0, "stale": True}
        # The assertion has to be that the LOCK stops being the veto, not that
        # the whole gate opens — the health probe may still, correctly, close
        # it. So: with a stale lock present, the probe must be reached at all.
        # (An earlier version of this check was `x is not False or True`, which
        # cannot fail and therefore tested nothing.)
        seen = {}
        R._cached_health(lambda: seen.setdefault("probed", True) or True, ttl=0)
        checks["a stale lock lets the health probe run at all"] = bool(seen)

        broker.lock_status = lambda name: {"owner": "compressor/alive",
                                           "age_s": 3.0, "stale": False}
        checks["a live lock still stands the hook down"] = (
            R.semantic_affordable(99) is False)
    finally:
        broker.lock_status = real

    # 2) A server that times out must be paid for once, not once per call.
    #    Measured before the breaker: one recall cost 2x the embed budget,
    #    because the query embedding and the claim check each waited it out.
    embed._BREAKER.update(until=0.0, reason="")
    try:
        (embed._state_path()).unlink()
    except OSError:
        pass
    calls = {"n": 0}

    def _hang(path, payload, timeout):
        calls["n"] += 1
        raise TimeoutError("wedged")

    real_post = embed._post
    try:
        embed._post = _hang
        embed.set_timeout(0.2)
        embed.embed("first call trips the breaker")
        first = calls["n"]
        embed.embed("second call must not reach the server")
        embed.embed("nor the third")
        checks["a wedged server is contacted once, not once per call"] = (
            first == 1 and calls["n"] == 1)
        st = embed.breaker_state()
        checks["the breaker says why it is open"] = (
            st["open"] and "Timeout" in st["reason"])
    finally:
        embed._post = real_post
        embed._BREAKER.update(until=0.0, reason="")
        try:
            (embed._state_path()).unlink()
        except OSError:
            pass

    # 3) metrics.jsonl is multi-event; readers must select by type, not position.
    mg.append_metrics({"session": "sX", "raw_tokens_est": 10}, event=mg.COMPRESS)
    mg.append_metrics({"session": "sX", "ms": 1.0}, event="recall")
    comp = mg.read_metrics(event=mg.COMPRESS, session="sX")
    checks["a recall row is never read as a compression row"] = (
        len(comp) == 1 and "raw_tokens_est" in comp[-1])

    print("\n12) DEGRADED-MODEL BEHAVIOUR")
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


def check_autopilot(home: Path) -> bool:
    """Autopilot edits the user's own settings.json, so the test that matters is
    not "did it write the key" but "did it leave everything else alone"."""
    import importlib
    cfgdir = home / "fake-claude"
    cfgdir.mkdir(parents=True, exist_ok=True)
    keep = {"env": {"KEEP_ME": "1"}, "hooks": {"X": []}, "theme": "dark"}
    (cfgdir / "settings.json").write_text(json.dumps(keep, indent=2), encoding="utf-8")
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)

    sys.path.insert(0, str(Path(__file__).parent))
    import autopilot
    importlib.reload(autopilot)

    print("\n5) AUTOPILOT")
    autopilot.cmd_enable(70.0)
    got = json.loads((cfgdir / "settings.json").read_text(encoding="utf-8"))
    wrote = got.get("env", {}).get(autopilot.ENV_KEY) == "70"
    kept = (got.get("theme") == "dark" and got.get("hooks") == {"X": []}
            and got.get("env", {}).get("KEEP_ME") == "1")

    # A compaction that fired at 88.6% of a 70% target must pull the override
    # DOWN, not up. Getting this sign wrong would drive the threshold to the
    # ceiling and compaction would stop happening at all.
    autopilot.record_firing(88.6, mg.load_config())
    after = float(json.loads((cfgdir / "settings.json").read_text(encoding="utf-8"))
                  ["env"][autopilot.ENV_KEY])
    direction = after < 70

    # Inside tolerance nothing should move.
    autopilot.record_firing(70.0 + autopilot.TOLERANCE_PCT / 2, mg.load_config())
    stable = float(json.loads((cfgdir / "settings.json").read_text(encoding="utf-8"))
                   ["env"][autopilot.ENV_KEY]) == after

    autopilot.cmd_disable()
    final = json.loads((cfgdir / "settings.json").read_text(encoding="utf-8"))
    removed = autopilot.ENV_KEY not in final.get("env", {})
    restored = (final.get("theme") == "dark"
                and final.get("env", {}).get("KEEP_ME") == "1")

    checks = {"override written": wrote, "other settings kept": kept,
              "over-target correction goes down": direction,
              "in-tolerance firing changes nothing": stable,
              "disable removes only its own key": removed and restored}
    for name, val in checks.items():
        print(f"   {'ok ' if val else 'FAIL'} {name}")
    return all(checks.values())


if __name__ == "__main__":
    sys.exit(main())
