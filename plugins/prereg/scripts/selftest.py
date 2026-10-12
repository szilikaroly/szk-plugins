#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline selftest for prereg.py. Every case pins a failure that matters for a registration.

    python3 scripts/selftest.py        # no network: the OSF call is never made
"""
import datetime as dt
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec_ = importlib.util.spec_from_file_location("prereg", HERE / "prereg.py")
P = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(P)

RESULTS = []


def case(name):
    def deco(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
        except AssertionError as e:
            RESULTS.append((name, False, str(e) or "assertion failed"))
        return fn
    return deco


def sev(findings, s):
    return [x for x in findings if x["sev"] == s]


def _text_for(key):
    """Neutral test text that meets the live word minimum of the field."""
    lo, _hi = P.PROSPERO_WORDS.get(key, (1, 999))
    words = f"Test value for {key}.".split()
    while len(words) < max(lo, 1):
        words.append("more")
    return " ".join(words)


def valid_prospero():
    """A spec with every required PROSPERO field filled with neutral English text that meets the live word limits."""
    form = P.form_for("prospero")
    pro = {}
    for f in form["fields"]:
        if f["kind"] == "system":
            continue
        pro[f["key"]] = _text_for(f["key"])
    pro["title"] = "Dietary fibre and gestational diabetes: a systematic review with dose-response meta-analysis"
    pro["review_start"] = "2026-08-01"
    pro["review_end"] = (dt.date.today() + dt.timedelta(days=200)).isoformat()
    pro["strategy_url"] = "not_available"
    pro["team"] = [
        {"name": "Test Author", "affiliation": "Test University", "orcid": "0000-0001-9803-9103", "coi": "None",
         "guarantor": True, "consent": True},
        {"name": "Test Second", "affiliation": "Test University", "orcid": "0000-0002-1825-0097", "coi": "None",
         "consent": True},
    ]
    pro["named_contact"] = {"name": "Test Author", "email": "author@university.hu",
                            "orcid": "0000-0001-9803-9103", "affiliation": "Test University"}
    pro["mesh"] = ["Pregnancy", "Diabetes, Gestational"]
    pro["stage"] = {r: "not_started" for r in P.STAGE_ROWS}
    pro["stage"]["pilot_work"] = "completed"
    return {"slug": "test", "registry": "prospero", "review_kind": "systematic",
            "population_scope": "human", "outcome_health": True, "prospero": pro,
            "similar": {"checked": True, "hits": []}}


def valid_osf():
    form = P.form_for("osf")
    return {"slug": "test", "registry": "osf", "review_kind": "narrative",
            "population_scope": "human", "outcome_health": True,
            "osf": {q["key"]: f"Test answer for {q['key']}." for q in form["questions"]},
            "osf_metadata": {"title": "Test registration title", "description": "Test description.",
                             "license": "CC0 1.0 Universal", "subjects": ["Medicine and Health Sciences"]},
            "similar": {"checked": True, "hits": []}}


# ---------------------------------------------------------------- routing

@case("narrative review is not routed to PROSPERO")
def _():
    r = P.route({"review_kind": "narrative", "outcome_health": True, "prospero": {"stage": {}}})
    assert r["decision"] == "osf" and not r["prospero_eligible"], r


@case("systematic human review with health outcome goes to PROSPERO")
def _():
    r = P.route(valid_prospero())
    assert r["decision"] == "prospero" and r["prospero_eligible"], r


@case("data extraction already started blocks PROSPERO and says why")
def _():
    s = valid_prospero()
    s["registry"] = "auto"
    s["prospero"]["stage"]["data_extraction"] = "started"
    r = P.route(s)
    assert r["decision"] == "osf", r
    assert any("adatkinyerés" in b for b in r["blockers"]), r["blockers"]
    assert r["osf_note"], "OSF must carry the non-prospective disclosure note"


@case("explicit PROSPERO request for an ineligible review is 'blocked', not silently changed")
def _():
    s = {"registry": "prospero", "review_kind": "scoping", "outcome_health": True, "prospero": {}}
    assert P.route(s)["decision"] == "blocked"


@case("animal-only review is routed away from the human PROSPERO form")
def _():
    r = P.route({"review_kind": "systematic", "population_scope": "animal", "outcome_health": True,
                 "prospero": {"stage": {}}})
    assert r["decision"] == "osf" and any("állat" in b for b in r["blockers"])


@case("review_kind=other asks the user instead of guessing")
def _():
    assert P.route({"review_kind": "other", "outcome_health": True, "prospero": {}})["decision"] == "ask"


# ---------------------------------------------------------------- Pass 1 checks

@case("a complete PROSPERO spec passes Pass 1 with no HIBA")
def _():
    f = P.check(valid_prospero(), "prospero")
    assert not sev(f, "HIBA"), sev(f, "HIBA")


@case("a complete OSF spec passes Pass 1 with no HIBA")
def _():
    f = P.check(valid_osf(), "osf")
    assert not sev(f, "HIBA"), sev(f, "HIBA")


@case("a placeholder left in any field blocks the check")
def _():
    s = valid_prospero()
    s["prospero"]["rationale"] = "The rationale is TBD, see the protocol."
    assert any(x["field"] == "rationale" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("an [AUTHOR-VERIFY] marker anywhere blocks the check")
def _():
    s = valid_prospero()
    s["prospero"]["comparator"] = "No comparator [AUTHOR-VERIFY: confirm]"
    assert sev(P.check(s, "prospero"), "HIBA")


@case("ORCID checksum is validated (the known-good ORCID passes, a bad digit fails)")
def _():
    assert P.orcid_valid("0000-0001-9803-9103")
    assert not P.orcid_valid("0000-0001-9803-9104")


@case("a bad ORCID in the team blocks the check")
def _():
    s = valid_prospero()
    s["prospero"]["team"][0]["orcid"] = "0000-0001-9803-9104"
    assert any("orcid" in x["field"] for x in sev(P.check(s, "prospero"), "HIBA"))


@case("end date before start date blocks the check")
def _():
    s = valid_prospero()
    s["prospero"]["review_end"] = "2026-07-01"
    assert any(x["field"] == "review_end" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("an unknown PROSPERO field is a blocking error, not silently ignored")
def _():
    s = valid_prospero()
    s["prospero"]["reviewtype"] = "Systematic review"
    assert any(x["field"] == "reviewtype" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("a PROSPERO-generated field supplied by the user is flagged")
def _():
    s = valid_prospero()
    s["prospero"]["registration_date"] = "2026-09-12"
    assert any(x["field"] == "registration_date" for x in sev(P.check(s, "prospero"), "FIGYELEM"))


@case("data extraction started is a HIBA for PROSPERO")
def _():
    s = valid_prospero()
    s["prospero"]["stage"]["data_extraction"] = "completed"
    assert any(x["field"] == "stage.data_extraction" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("formal searching already started is a FIGYELEM (disclose it), not silent")
def _():
    s = valid_prospero()
    s["prospero"]["stage"]["formal_searching"] = "completed"
    assert any(x["field"] == "stage" for x in sev(P.check(s, "prospero"), "FIGYELEM"))


@case("an invalid stage state is blocking")
def _():
    s = valid_prospero()
    s["prospero"]["stage"]["screening"] = "done"
    assert any(x["field"] == "stage.screening" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("Hungarian accents in an English-only PROSPERO field are flagged")
def _():
    s = valid_prospero()
    s["prospero"]["title"] = "Étrend és terhességi cukorbetegség: systematic review"
    assert any(x["field"] == "title" for x in sev(P.check(s, "prospero"), "FIGYELEM"))


@case("a similar record without a stated reason is blocking")
def _():
    s = valid_prospero()
    s["similar"] = {"checked": True, "hits": [{"id": "CRD42025000000", "title": "x"}]}
    assert sev(P.check(s, "prospero"), "HIBA")


@case("an unchecked similar-registration search is a FIGYELEM")
def _():
    s = valid_prospero()
    s["similar"] = {"checked": False}
    assert any(x["field"] == "similar" for x in sev(P.check(s, "prospero"), "FIGYELEM"))


@case("an empty required OSF answer is blocking")
def _():
    s = valid_osf()
    first = next(iter(s["osf"]))
    s["osf"][first] = "   "
    assert any(x["field"] == first for x in sev(P.check(s, "osf"), "HIBA"))


# ---------------------------------------------------------------- plan and read-back (Pass 3)

@case("plan has no system fields and expands the stage table into 12 checkboxes")
def _():
    doc = P.plan(valid_prospero(), "prospero")
    keys = [e["key"] for e in doc["entries"]]
    assert not any(k in ("first_submission", "registration_date", "similar_reviews") for k in keys)
    assert sum(1 for e in doc["entries"] if e["kind"] == "checkbox") == 12


@case("Completed implies Started in the stage plan")
def _():
    s = valid_prospero()
    s["prospero"]["stage"]["pilot_work"] = "completed"
    doc = P.plan(s, "prospero")
    box = {e["key"]: e["expect"] for e in doc["entries"] if e["kind"] == "checkbox"}
    assert box["stage.pilot_work.started"] == "checked" and box["stage.pilot_work.completed"] == "checked"


@case("read-back passes when the live form matches the plan exactly")
def _():
    doc = P.plan(valid_prospero(), "prospero")
    actual = {e["key"]: e["expect"] for e in doc["entries"]}
    assert not sev(P.readback(doc, actual), "HIBA")


@case("read-back catches a single changed value")
def _():
    doc = P.plan(valid_prospero(), "prospero")
    actual = {e["key"]: e["expect"] for e in doc["entries"]}
    actual["title"] = actual["title"] + " (edited)"
    fs = sev(P.readback(doc, actual), "HIBA")
    assert len(fs) == 1 and fs[0]["field"] == "title", fs


@case("read-back catches a missing field and a wrong checkbox")
def _():
    doc = P.plan(valid_prospero(), "prospero")
    actual = {e["key"]: e["expect"] for e in doc["entries"]}
    del actual["condition"]
    actual["stage.pilot_work.completed"] = "unchecked"
    msgs = sev(P.readback(doc, actual), "HIBA")
    assert len(msgs) == 2, msgs


@case("whitespace differences do not count as a mismatch")
def _():
    doc = P.plan(valid_prospero(), "prospero")
    actual = {e["key"]: e["expect"].replace(" ", "  ") for e in doc["entries"] if e["kind"] != "checkbox"}
    actual.update({e["key"]: e["expect"] for e in doc["entries"] if e["kind"] == "checkbox"})
    assert not sev(P.readback(doc, actual), "HIBA")


@case("team members canonicalise the same way in plan and read-back")
def _():
    members = [{"name": "A", "affiliation": "B", "orcid": "0000-0001-9803-9103", "coi": "None"}]
    assert P.canon(members, "list") == "A | B | ORCID 0000-0001-9803-9103 | COI: None"


@case("similar search splits terms on ';' and '|' and drops empties")
def _():
    assert P.split_terms("gestational diabetes; dose-response | protein intake ;") == \
        ["gestational diabetes", "dose-response", "protein intake"]


# ---------------------------------------------------------------- privacy guard and CLI

@case("the similar search refuses an e-mail address or ORCID in the query")
def _():
    for bad in ("szili@example.org gestational", "0000-0001-9803-9103 diabetes"):
        try:
            P.similar(bad)
        except SystemExit:
            continue
        raise AssertionError(f"accepted: {bad}")


@case("CLI check exits 1 on a blocking finding and 0 on a clean spec")
def _():
    with tempfile.TemporaryDirectory() as d:
        good = Path(d) / "good.json"
        bad = Path(d) / "bad.json"
        good.write_text(json.dumps(valid_prospero(), ensure_ascii=False), encoding="utf-8")
        b = valid_prospero()
        b["prospero"]["rationale"] = "TBD"
        bad.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            assert P.main(["check", str(good), "--registry", "prospero"]) == 0
            assert P.main(["check", str(bad), "--registry", "prospero"]) == 1


@case("the OSF map covers all 61 required questions and the PROSPERO map has no duplicate keys")
def _():
    osf = P.form_for("osf")["questions"]
    assert len(osf) == 61 and all(q["required"] for q in osf)
    keys = [f["key"] for f in P.form_for("prospero")["fields"]]
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------- regressions found by the 2026-10-12 probe

class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self._b


@case("PROSPERO end date closer than 28 days is blocked (form rule, found on the live form 2026-10-12)")
def _():
    s = valid_prospero()
    s["prospero"]["review_end"] = (dt.date.today() + dt.timedelta(days=10)).isoformat()
    f = P.check(s, "prospero")
    assert any(x["field"] == "review_end" for x in sev(f, "HIBA")), f


@case("a field below the live word minimum is blocked (was: 4-word placeholder passed)")
def _():
    s = valid_prospero()
    s["prospero"]["rationale"] = "Test value for rationale."
    f = P.check(s, "prospero")
    assert any(x["field"] == "rationale" and "minimuma" in x["msg"] for x in sev(f, "HIBA")), f


@case("a field above the live word maximum is blocked")
def _():
    s = valid_prospero()
    s["prospero"]["title"] = " ".join(["word"] * 31)
    f = P.check(s, "prospero")
    assert any(x["field"] == "title" and "maximuma" in x["msg"] for x in sev(f, "HIBA")), f


@case("a team of one is blocked, and a member without consent is blocked")
def _():
    s = valid_prospero()
    s["prospero"]["team"] = s["prospero"]["team"][:1]
    f = P.check(s, "prospero")
    assert any(x["field"] == "team" for x in sev(f, "HIBA")), f
    s = valid_prospero()
    s["prospero"]["team"][1].pop("consent")
    f = P.check(s, "prospero")
    assert any(x["field"] == "team[1].consent" for x in sev(f, "HIBA")), f


@case("a team without a guarantor is blocked")
def _():
    s = valid_prospero()
    for m in s["prospero"]["team"]:
        m.pop("guarantor", None)
    f = P.check(s, "prospero")
    assert any("guarantor" in x["msg"] for x in sev(f, "HIBA")), f


@case("'Link to search strategy' is a choice, not a URL (was: a URL was accepted)")
def _():
    s = valid_prospero()
    s["prospero"]["strategy_url"] = "https://osf.io/abcde/"
    f = P.check(s, "prospero")
    assert any(x["field"] == "strategy_url" for x in sev(f, "HIBA")), f


@case("OSF metadata (title, description, licence, subject) is required before Register")
def _():
    s = valid_osf()
    s.pop("osf_metadata")
    f = P.check(s, "osf")
    fields = {x["field"] for x in sev(f, "HIBA")}
    assert {"osf_metadata.title", "osf_metadata.description", "osf_metadata.license", "osf_metadata.subjects"} <= fields, fields


@case("when data extraction has started, the OSF current stage must say the registration is retrospective")
def _():
    s = valid_osf()
    s["stage"] = {r: "not_started" for r in P.STAGE_ROWS}
    s["stage"]["data_extraction"] = "completed"
    s["osf"]["review-methods/current-review-stage"] = "Test answer."
    f = P.check(s, "osf")
    assert any(x["field"] == "review-methods/current-review-stage" for x in sev(f, "HIBA")), f
    s["osf"]["review-methods/current-review-stage"] = "Data extraction completed; this registration is retrospective."
    f = P.check(s, "osf")
    assert not any(x["field"] == "review-methods/current-review-stage" for x in sev(f, "HIBA")), f


@case("an AND/OR query without parentheses gets a warning (PubMed reads it in its own order)")
def _():
    s = valid_osf()
    s["osf"]["search-strategy/query-strings"] = "gestational diabetes AND pregnancy OR fertility"
    f = P.check(s, "osf")
    assert any(x["field"] == "search-strategy/query-strings" for x in sev(f, "FIGYELEM")), f


def _osf_page(items, next_url=None, total=None):
    data = []
    for rid, title, date in items:
        data.append({"id": rid, "attributes": {"title": title, "date_registered": date, "withdrawn": False},
                     "relationships": {"registration_schema": {"links": {"related": {
                         "href": f"https://api.osf.io/v2/schemas/registrations/{P.OSF_SR_SCHEMA_ID}/"}}}}})
    return {"data": data, "links": {"meta": {"total": total if total is not None else len(items)},
                                    "next": next_url}}


def _with_fake_urlopen(fn, responses):
    """responses: callable(url) -> payload. Restores urlopen afterwards."""
    import urllib.request
    real = urllib.request.urlopen
    urllib.request.urlopen = lambda url, timeout=None: _FakeResp(responses(url))
    old_sleep = P.RETRY_SLEEP
    P.RETRY_SLEEP = 0
    try:
        return fn()
    finally:
        urllib.request.urlopen = real
        P.RETRY_SLEEP = old_sleep


@case("pubmed-count sends the term unchanged and reads the count")
def _():
    seen = {}

    def fake(url):
        seen["url"] = url
        return {"esearchresult": {"count": "658"}}

    n = _with_fake_urlopen(lambda: P.pubmed_count("(a[tiab] OR b[tiab]) AND c[tiab]", "2010/01/01", "2026/08/05", "pdat"), fake)
    assert n == 658, n
    assert "term=%28a%5Btiab%5D+OR+b%5Btiab%5D%29+AND+c%5Btiab%5D" in seen["url"], seen["url"]


@case("'other' review kind asks even when PROSPERO is requested explicitly (was: silently passed)")
def _():
    r = P.route({"registry": "prospero", "review_kind": "other", "outcome_health": True, "prospero": {}})
    assert r["decision"] == "ask", r


@case("a non-object section is a HIBA, not a traceback (prospero as a list)")
def _():
    f = P.check({"review_kind": "systematic", "outcome_health": True, "prospero": ["x"]}, "prospero")
    assert any(x["field"] == "prospero" and x["sev"] == "HIBA" for x in f), f


@case("a team that is not a list, or a member that is not an object, is a HIBA")
def _():
    s = valid_prospero()
    s["prospero"]["team"] = "Test Author"
    assert any(x["field"] == "team" for x in sev(P.check(s, "prospero"), "HIBA"))
    s = valid_prospero()
    s["prospero"]["team"] = ["Test Author"]
    assert any(x["field"] == "team[0]" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("malformed JSON gives a Hungarian message with line and column, not a traceback")
def _():
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        try:
            P.load_json(bad)
        except SystemExit as e:
            assert "hibás JSON" in str(e) and "sor" in str(e), str(e)
            return
        raise AssertionError("no SystemExit")


@case("similar follows OSF pagination and merges pages")
def _():
    def responder(url):
        if "page=2" in url:
            return _osf_page([("bbbbb", "T two", "2026-01-02T00:00:00"),
                              ("ccccc", "T three", "2026-01-03T00:00:00")], None, total=3)
        return _osf_page([("aaaaa", "T one", "2026-01-01T00:00:00")],
                         "https://api.osf.io/v2/registrations/?page=2&filter=x", total=3)
    doc = _with_fake_urlopen(lambda: P.similar("gestational diabetes"), responder)
    assert doc["retrieved"] == 3, doc
    assert doc["truncated_terms"] == [], doc


@case("the same registration found by two terms is counted once, with both terms recorded")
def _():
    page = _osf_page([("aaaaa", "Shared title", "2026-01-01T00:00:00")], None)
    doc = _with_fake_urlopen(lambda: P.similar("gestational diabetes; dose-response"), lambda url: page)
    assert doc["retrieved"] == 1, doc
    assert doc["hits"][0]["matched_terms"] == ["gestational diabetes", "dose-response"], doc["hits"][0]


@case("a term whose results never end is reported as truncated, not silently cut")
def _():
    def responder(url):
        return _osf_page([("endless", "T", "2026-01-01T00:00:00")],
                         "https://api.osf.io/v2/registrations/?next=1", total=999)
    doc = _with_fake_urlopen(lambda: P.similar("gestational diabetes"), responder)
    assert doc["truncated_terms"] == ["gestational diabetes"], doc["truncated_terms"]


@case("a network that never answers ends with a Hungarian message after three attempts")
def _():
    def boom(url, timeout=None):
        raise OSError("connection refused")
    import urllib.request
    real = urllib.request.urlopen
    urllib.request.urlopen = boom
    old = P.RETRY_SLEEP
    P.RETRY_SLEEP = 0
    try:
        P.similar("gestational diabetes")
    except SystemExit as e:
        assert "három kísérlet" in str(e), str(e)
        return
    finally:
        urllib.request.urlopen = real
        P.RETRY_SLEEP = old
    raise AssertionError("no SystemExit")


def _write(d, obj):
    p = d / "spec.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


@case("plan writes into a directory that does not exist yet")
def _():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "new" / "sub" / "plan.json"
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            rc = P.main(["plan", str(_write(Path(d), valid_prospero())), "--registry", "prospero", "--out", str(out)])
        assert rc == 0 and out.exists()


@case("the PROSPERO map carries the two fields the second public record shows")
def _():
    keys = {f["key"] for f in P.form_for("prospero")["fields"]}
    assert {"other_databases", "subgroups"} <= keys


@case("a reserved example domain in a contact or link is a HIBA (the reviewer caught this; Pass 1 did not)")
def _():
    s = valid_prospero()
    s["prospero"]["named_contact"]["email"] = "author@example.org"
    assert any(x["field"] == "named_contact.email" for x in sev(P.check(s, "prospero"), "HIBA"))
    s = valid_prospero()
    s["prospero"]["strategy_url"] = "https://example.com/strategy.pdf"
    assert any(x["field"] == "strategy_url" for x in sev(P.check(s, "prospero"), "HIBA"))


@case("a start date in the past while every stage is not_started is a FIGYELEM")
def _():
    s = valid_prospero()
    s["prospero"]["stage"] = {r: "not_started" for r in P.STAGE_ROWS}
    s["prospero"]["review_start"] = "2020-01-01"
    assert any(x["field"] == "review_start" for x in sev(P.check(s, "prospero"), "FIGYELEM"))


@case("animal review that is directly relevant to human health goes to PROSPERO (live form offers it, 2026-10-12)")
def _():
    r = P.route({"review_kind": "systematic", "population_scope": "animal", "outcome_health": True,
                 "human_health_relevance": True, "prospero": {"stage": {}}})
    assert r["decision"] == "prospero", r


@case("animal review without a stated human-health relevance still goes to OSF")
def _():
    r = P.route({"review_kind": "systematic", "population_scope": "animal", "outcome_health": True,
                 "prospero": {"stage": {}}})
    assert r["decision"] == "osf", r


@case("in-vitro review stays on OSF even if relevance is claimed")
def _():
    r = P.route({"review_kind": "systematic", "population_scope": "in-vitro", "outcome_health": True,
                 "human_health_relevance": True, "prospero": {"stage": {}}})
    assert r["decision"] == "osf", r


@case("human_health_relevance must be a boolean")
def _():
    s = valid_prospero()
    s["human_health_relevance"] = "yes"
    assert any(x["field"] == "human_health_relevance" for x in sev(P.check(s, "prospero"), "HIBA"))


if __name__ == "__main__":
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, msg in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        {msg}" if not ok else ""))
    print(f"\n{passed}/{len(RESULTS)} passed")
    sys.exit(0 if passed == len(RESULTS) else 1)
