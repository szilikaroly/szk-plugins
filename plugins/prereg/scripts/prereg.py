#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prereg — registration spec → routing, Pass-1 checks, fill plan, Pass-3 read-back.

    prereg.py route    SPEC                              PROSPERO, OSF, ask, or blocked — with reasons
    prereg.py check    SPEC --registry prospero|osf [--out F]   Pass 1: deterministic findings
    prereg.py plan     SPEC --registry prospero|osf --out PLAN  label → value list for the browser
    prereg.py readback PLAN ACTUAL [--out F]             Pass 3: what the live form shows vs. the plan
    prereg.py similar  QUERY [--out F]                   OSF public API, topic words only
    prereg.py fields   prospero|osf

Nothing here drives a browser or writes to a registry. `similar` is the only network
call, and it sends only the query string: keep names, e-mails and ORCIDs out of it.
Exit code 1 means at least one HIBA (blocking) finding.

Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "skills" / "prereg" / "references"
OSF_SR_SCHEMA_ID = "69cbc587cd7e8b69fa11ab52"

#: Review kinds PROSPERO does not register (CRD guidance: no narrative, scoping, literature, mapping).
PROSPERO_INELIGIBLE_KINDS = {"scoping", "narrative", "literature", "mapping"}
REVIEW_KINDS = {"systematic", "rapid", "umbrella", "other"} | PROSPERO_INELIGIBLE_KINDS
POPULATIONS = {"human", "animal", "in-vitro", "mixed"}
STAGE_STATES = ("not_started", "started", "completed")
STAGE_ROWS = ["pilot_work", "formal_searching", "screening", "data_extraction", "risk_of_bias", "data_synthesis"]
SPEC_TOP_KEYS = {"slug", "registry", "review_kind", "population_scope", "outcome_health",
                 "cochrane_protocol", "prospero", "osf", "similar", "notes"}

#: PROSPERO text is English. Affiliations, funding and names are exempt.
ENGLISH_ONLY_PROSPERO = {
    "title", "rationale", "objectives", "condition", "population_included", "population_excluded",
    "exposure_included", "exposure_excluded", "comparator", "study_design", "context",
    "protocol_available", "unpublished_studies", "sources", "language_restrictions", "date_restrictions",
    "other_methods", "selection", "searching_other", "extraction", "risk_of_bias", "reporting_bias",
    "certainty", "outcomes_main", "outcomes_additional", "synthesis", "review_status", "publication",
    "conflicts", "other_databases", "subgroups",
}

PLACEHOLDER = re.compile(
    r"\b(TBD|TODO|FIXME|XXX+|lorem|ipsum)\b|\?\?\?|\[[^\]]*(VERIFY|INSERT|AUTHOR|TODO)[^\]]*\]"
    r"|\{\{.*?\}\}|<<.*?>>",
    re.IGNORECASE,
)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
ORCID_ANYWHERE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
HU_ACCENT = re.compile(r"[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]")
RESERVED_DOMAIN = re.compile(r"example\.(?:org|com|net)\b|\.test\b|\.invalid\b", re.IGNORECASE)
DESIGN_WORD = re.compile(r"systematic|meta-analy|umbrella|rapid review", re.IGNORECASE)


# ---------------------------------------------------------------- helpers

def load_json(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"nincs ilyen fájl: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"hibás JSON ({path}): {e.msg}, sor {e.lineno}, oszlop {e.colno}")


def _dict(x) -> dict:
    """A section that is not an object is reported by check(); here it is treated as empty."""
    return x if isinstance(x, dict) else {}


def form_for(registry: str) -> dict:
    name = "prospero-form.json" if registry == "prospero" else "osf-sr-form.json"
    return json.loads((REF / name).read_text(encoding="utf-8"))


def orcid_valid(value: str) -> bool:
    """ISO 7064 MOD 11-2 check digit, as used by ORCID."""
    if not ORCID.match(value):
        return False
    digits = value.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    return ("X" if result == 10 else str(result)) == digits[-1]


def is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, tuple)):
        return all(is_empty(x) for x in v)
    if isinstance(v, dict):
        return all(is_empty(x) for x in v.values())
    return False


def iter_strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{path}[{i}]")


def canon(value, kind: str) -> str:
    """The one string form both the plan and the read-back use. Keep it identical."""
    if kind == "checkbox":
        if isinstance(value, bool):
            return "checked" if value else "unchecked"
        s = str(value).strip().lower()
        return "checked" if s in ("checked", "true", "✓", "yes", "1") else "unchecked"
    if isinstance(value, str):
        return " ".join(value.split())
    if kind == "list" and isinstance(value, list):
        if value and isinstance(value[0], dict):
            parts = []
            for m in value:
                bits = [m.get("name", ""), m.get("affiliation", ""),
                        f"ORCID {m['orcid']}" if m.get("orcid") else "",
                        f"COI: {m['coi']}" if m.get("coi") else ""]
                parts.append(" | ".join(b for b in bits if b))
            return "; ".join(parts)
        return "; ".join(str(x) for x in value)
    if kind == "contact" and isinstance(value, dict):
        bits = [value.get("name", ""), value.get("email", ""),
                f"ORCID {value['orcid']}" if value.get("orcid") else "", value.get("affiliation", "")]
        return " | ".join(b for b in bits if b)
    if isinstance(value, list):
        return "; ".join(str(x) for x in value)
    return " ".join(str(value or "").split())


# ---------------------------------------------------------------- route

def route(spec: dict) -> dict:
    kind = spec.get("review_kind", "")
    pop = spec.get("population_scope", "human")
    pro = _dict(spec.get("prospero"))
    stage = _dict(pro.get("stage"))
    requested = spec.get("registry", "auto")
    blockers, notes = [], []

    if kind in PROSPERO_INELIGIBLE_KINDS:
        blockers.append(f"'{kind}' review: a PROSPERO nem veszi fel (csak szisztematikus, rapid és "
                        "umbrella review egészségügyi kimenettel)")
    if kind == "other":
        notes.append("review_kind = other: a befogadást nem lehet automatikusan eldönteni — "
                     "egyeztess a CRD-vel vagy válassz konkrét típust")
    if pop == "animal":
        blockers.append("csak állatkísérletes review: a PROSPERO állat-szekciójába tartozik, nem ebbe az űrlapba")
    if pop == "in-vitro":
        blockers.append("csak in vitro review: a CRD az OSF-et javasolja")
    if pop == "mixed":
        notes.append("vegyes populáció: a PROSPERO-hoz humán részre kell szűkíteni, vagy ellenőrizni kell a befogadást")
    if not spec.get("outcome_health", False):
        blockers.append("nincs egészségügyi kimenet: a PROSPERO csak egészséggel kapcsolatos kimenetű review-t vesz fel")
    if spec.get("cochrane_protocol"):
        blockers.append("Cochrane-protokoll: a PROSPERO automatikusan importálja, külön nem regisztrálható")
    if stage.get("data_extraction") in ("started", "completed"):
        blockers.append("az adatkinyerés már elkezdődött: a PROSPERO 2019 óta nem fogad el ilyen regisztrációt, "
                        "és nincs visszamenőleges regisztrációs kategória")
    if stage.get("formal_searching") in ("started", "completed") or stage.get("screening") in ("started", "completed"):
        notes.append("a formális keresés vagy szűrés már elindult: a regisztráció nem előzi meg a keresést; "
                     "ezt a kéziratban nyíltan közölni kell")

    eligible = not blockers
    if kind == "other":
        decision = "ask"
    elif requested == "prospero":
        decision = "prospero" if eligible else "blocked"
    elif requested == "osf":
        decision = "osf"
    else:
        decision = "prospero" if eligible else "osf"

    osf_note = ""
    if decision == "osf" and kind in PROSPERO_INELIGIBLE_KINDS:
        notes.append("OSF-en a 'Generalized Systematic Review Registration' séma nem illik nem-szisztematikus "
                     "review-hoz; az 'Open-Ended Registration' (5df83f7dd28338001ac0ab0d) a megfelelőbb, de ehhez "
                     "a plugin még nem tartalmaz térképet")
    if stage.get("data_extraction") in ("started", "completed"):
        osf_note = ("OSF-en a 'Current review stage' mezőben egyértelműen le kell írni, hogy az adatkinyerés "
                    "már elkezdődött: ez nem prospektív regisztráció.")
    return {"decision": decision, "prospero_eligible": eligible, "requested": requested,
            "blockers": blockers, "notes": notes, "osf_note": osf_note}


# ---------------------------------------------------------------- check (Pass 1)

def check(spec: dict, registry: str) -> list[dict]:
    f: list[dict] = []

    def add(sev, field, msg):
        f.append({"sev": sev, "field": field, "msg": msg})

    for k in spec:
        if k not in SPEC_TOP_KEYS:
            add("HIBA", k, "ismeretlen kulcs a spec gyökerében")
    if spec.get("review_kind") not in REVIEW_KINDS:
        add("HIBA", "review_kind", f"review_kind kötelező: {', '.join(sorted(REVIEW_KINDS))}")
    if spec.get("population_scope", "human") not in POPULATIONS:
        add("HIBA", "population_scope", f"population_scope: {', '.join(sorted(POPULATIONS))}")

    form = form_for(registry)
    for key in ("prospero", "osf", "similar"):
        if key in spec and not isinstance(spec[key], dict):
            add("HIBA", key, "ennek objektumnak kell lennie")
    similar = _dict(spec.get("similar"))
    if not similar.get("checked"):
        add("FIGYELEM", "similar", "a hasonló regisztrációk még nincsenek ellenőrizve (prereg.py similar + böngésző)")
    for i, hit in enumerate(similar.get("hits") or []):
        if not isinstance(hit, dict):
            add("HIBA", f"similar.hits[{i}]", "a találat objektum kell legyen")
            continue
        if is_empty(hit.get("why_different")):
            add("HIBA", f"similar.hits[{i}]",
                f"hasonló rekord ({hit.get('id', '?')}) van, de nincs indoklás, miért folytatod")

    if registry == "prospero":
        for reason in route(spec)["blockers"]:
            add("HIBA", "routing", reason)
        pro = _dict(spec.get("prospero"))
        if "stage" in pro and not isinstance(pro["stage"], dict):
            add("HIBA", "stage", "a szakasztábla objektum kell legyen")
        by_key = {x["key"]: x for x in form["fields"]}
        for k in pro:
            if k == "stage":
                continue
            if k not in by_key:
                add("HIBA", k, "nincs ilyen PROSPERO-mező (references/prospero-form.json)")
            elif by_key[k]["kind"] == "system":
                add("FIGYELEM", k, "rendszermező: a PROSPERO maga tölti ki, ne add meg")
        for fld in form["fields"]:
            if fld["kind"] == "system":
                continue
            if fld["required"] and is_empty(pro.get(fld["key"])):
                add("HIBA", fld["key"], f"kötelező mező üres: {fld['label']}")
        stage = _dict(pro.get("stage"))
        for row in STAGE_ROWS:
            if row not in stage:
                add("HIBA", f"stage.{row}", "a szakasztábla sora hiányzik")
            elif stage[row] not in STAGE_STATES:
                add("HIBA", f"stage.{row}", f"érvénytelen állapot: {stage[row]} ({', '.join(STAGE_STATES)})")
        if stage.get("data_extraction") in ("started", "completed"):
            add("HIBA", "stage.data_extraction", "az adatkinyerés elkezdődött: PROSPERO nem fogadja")
        if stage.get("formal_searching") in ("started", "completed") or stage.get("screening") in ("started", "completed"):
            add("FIGYELEM", "stage", "formális keresés/szűrés már fut vagy lezárult: a kéziratban nyíltan közöld, "
                                    "hogy a regisztráció nem előzte meg")
        start = pro.get("review_start")
        end = pro.get("review_end")
        for name, v in (("review_start", start), ("review_end", end)):
            if v is not None and not is_empty(v):
                try:
                    dt.date.fromisoformat(str(v))
                except ValueError:
                    add("HIBA", name, f"nem ISO dátum (ÉÉÉÉ-HH-NN): {v}")
        if start and end:
            try:
                if dt.date.fromisoformat(end) < dt.date.fromisoformat(start):
                    add("HIBA", "review_end", "a befejezés korábbi, mint a kezdés")
            except ValueError:
                pass
        if start and all(stage.get(r, "not_started") == "not_started" for r in STAGE_ROWS):
            try:
                if dt.date.fromisoformat(start) < dt.date.today():
                    add("FIGYELEM", "review_start", "a kezdő dátum a múltban van, miközben minden szakasz "
                                                   "'not_started' — a kettő nem egyezik")
            except ValueError:
                pass
        title = pro.get("title", "")
        if kind_is_systematic(spec) and not DESIGN_WORD.search(title or ""):
            add("FIGYELEM", "title", "a címből nem derül ki a review-típus (pl. 'systematic review')")
        for key in ENGLISH_ONLY_PROSPERO:
            if key in pro and HU_ACCENT.search(str(pro[key])):
                add("FIGYELEM", key, "magyar ékezetes karakter angol mezőben — a PROSPERO angolt vár")
        team = pro.get("team") or []
        if not isinstance(team, list):
            add("HIBA", "team", "a csapattagok listája kell legyen")
            team = []
        for m_i, member in enumerate(team):
            if not isinstance(member, dict):
                add("HIBA", f"team[{m_i}]", "a csapattag objektum kell legyen")
                continue
            if member.get("orcid") and not orcid_valid(member["orcid"]):
                add("HIBA", f"team[{m_i}].orcid", f"érvénytelen ORCID-ellenőrző jegy: {member['orcid']}")
        contact = _dict(pro.get("named_contact"))
        if contact.get("orcid") and not orcid_valid(contact["orcid"]):
            add("HIBA", "named_contact.orcid", f"érvénytelen ORCID-ellenőrző jegy: {contact['orcid']}")
        if contact and not EMAIL.match(contact.get("email", "")):
            add("HIBA", "named_contact.email", "a kapcsolattartó e-mail-címe hibás vagy hiányzik")
        scope = pro
    else:
        osf = _dict(spec.get("osf"))
        known = {q["key"]: q for q in form["questions"]}
        for k in osf:
            if k not in known:
                add("HIBA", k, "nincs ilyen OSF-kérdés (references/osf-sr-form.json)")
        for q in form["questions"]:
            if q["required"] and is_empty(osf.get(q["key"])):
                add("HIBA", q["key"], f"kötelező OSF-kérdés üres: {q['label']}")
        for k, v in osf.items():
            if k in known and HU_ACCENT.search(str(v)):
                add("FIGYELEM", k, "magyar ékezetes karakter az OSF-válaszban — az OSF-űrlap angolt vár")
        scope = osf

    for path, s in iter_strings(scope):
        if RESERVED_DOMAIN.search(s):
            add("HIBA", path, "példa- vagy fenntartott domain (example.*/.test): valódi adat kell ide")
        if PLACEHOLDER.search(s):
            add("HIBA", path, f"kitöltetlen helyőrző a szövegben: {PLACEHOLDER.search(s).group(0)!r}")
    return f


def kind_is_systematic(spec: dict) -> bool:
    return spec.get("review_kind") in ("systematic", "rapid", "umbrella")


def print_findings(findings: list[dict], title: str) -> None:
    h = sum(1 for x in findings if x["sev"] == "HIBA")
    w = sum(1 for x in findings if x["sev"] == "FIGYELEM")
    print(f"{title}: HIBA {h} · FIGYELEM {w}")
    for x in findings:
        print(f"  {x['sev']:<9} {x['field']:<28} {x['msg']}")
    if not findings:
        print("  Nincs eltérés.")


def write_out(path: str | None, payload: dict) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  → {path}")


# ---------------------------------------------------------------- plan

def plan(spec: dict, registry: str) -> dict:
    form = form_for(registry)
    entries = []
    if registry == "prospero":
        pro = spec.get("prospero") or {}
        for fld in form["fields"]:
            if fld["kind"] == "system":
                continue
            if fld["kind"] == "stage":
                stage = pro.get("stage") or {}
                for row, label in form["stage_rows"]:
                    state = stage.get(row, "not_started")
                    for col, value in (("Started", state in ("started", "completed")),
                                       ("Completed", state == "completed")):
                        entries.append({"section": fld["section"], "label": f"{label} [{col}]",
                                        "key": f"stage.{row}.{col.lower()}", "kind": "checkbox",
                                        "expect": canon(value, "checkbox")})
                continue
            val = pro.get(fld["key"])
            if is_empty(val):
                continue
            entries.append({"section": fld["section"], "label": fld["label"], "key": fld["key"],
                            "kind": fld["kind"] if fld["kind"] in ("list", "contact") else "text",
                            "value": val, "expect": canon(val, fld["kind"] if fld["kind"] in ("list", "contact") else "text")})
    else:
        osf = spec.get("osf") or {}
        for q in form["questions"]:
            val = osf.get(q["key"], "")
            entries.append({"section": q["page"], "label": q["label"], "key": q["key"], "kind": "text",
                            "value": val, "expect": canon(val, "text")})
    return {"registry": registry, "slug": spec.get("slug", ""), "count": len(entries), "entries": entries}


def readback(plan_doc: dict, actual: dict) -> list[dict]:
    f: list[dict] = []
    expected = {e["key"]: e for e in plan_doc["entries"]}
    for key, e in expected.items():
        if key not in actual:
            f.append({"sev": "HIBA", "field": key, "msg": f"nincs visszaolvasva: {e['label']}"})
            continue
        got = canon(actual[key], e["kind"])
        if got != e["expect"]:
            f.append({"sev": "HIBA", "field": key,
                      "msg": f"eltérés — {e['label']}: várt {e['expect'][:80]!r}, a formon {got[:80]!r}"})
    for key in actual:
        if key not in expected:
            f.append({"sev": "FIGYELEM", "field": key, "msg": "a formon van, a tervben nincs"})
    return f


# ---------------------------------------------------------------- similar (OSF API)

def split_terms(query: str) -> list[str]:
    """Terms are separated by ';' or '|'. The OSF title filter is a phrase match, so each term is searched alone."""
    terms = [" ".join(t.split()) for t in re.split(r"[;|]", query)]
    return [t for t in terms if t]


RETRY_SLEEP = 2  # seconds between attempts; tests set it to 0
MAX_PAGES = 5    # 5 × 50 = 250 results per term; anything beyond is reported as truncated


def _get_json(url: str) -> dict:
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.load(r)
        except (OSError, ValueError) as e:
            last = e
            if attempt < 2:
                time.sleep(RETRY_SLEEP * (attempt + 1))
    sys.exit(f"az OSF API nem válaszolt három kísérlet után: {last}")


def similar(query: str) -> dict:
    terms = split_terms(query)
    if not terms:
        sys.exit("adj legalább egy kifejezést")
    if any(not (3 <= len(t) <= 60) for t in terms):
        sys.exit("minden kifejezés 3–60 karakter legyen")
    if "@" in query or ORCID_ANYWHERE.search(query):
        sys.exit("a keresésbe nem kerülhet e-mail-cím vagy ORCID — csak témakifejezés")
    merged: dict[str, dict] = {}
    per_term: dict[str, int | None] = {}
    truncated: list[str] = []
    for term in terms:
        url = "https://api.osf.io/v2/registrations/?" + urllib.parse.urlencode(
            {"filter[title][icontains]": term, "page[size]": 50})
        total = None
        pages = 0
        while url and pages < MAX_PAGES:
            d = _get_json(url)
            pages += 1
            if total is None:
                total = (d.get("links", {}).get("meta", {}) or {}).get("total")
            for it in d.get("data", []):
                rid = it.get("id")
                if rid in merged:
                    if term not in merged[rid]["matched_terms"]:
                        merged[rid]["matched_terms"].append(term)
                    continue
                a = it.get("attributes", {})
                href = (it.get("relationships", {}).get("registration_schema", {})
                        .get("links", {}).get("related", {}).get("href", ""))
                m = re.search(r"/schemas/registrations/([0-9a-f]{24})/", href)
                sid = m.group(1) if m else ""
                merged[rid] = {"id": rid, "title": a.get("title", ""),
                               "date_registered": a.get("date_registered", ""),
                               "withdrawn": bool(a.get("withdrawn")), "schema_id": sid,
                               "is_sr_schema": sid == OSF_SR_SCHEMA_ID,
                               "url": f"https://osf.io/{rid}/", "matched_terms": [term]}
            url = (d.get("links") or {}).get("next")
        per_term[term] = total
        if url:
            truncated.append(term)
    hits = sorted(merged.values(), key=lambda h: h["date_registered"], reverse=True)
    return {"terms": terms, "source": "osf-api", "per_term_total": per_term,
            "truncated_terms": truncated, "retrieved": len(hits), "hits": hits,
            "note": "A PROSPERO nincs API-n: a böngészős keresést a prereg skill mezőkódjaival kell futtatni."}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("route")
    r.add_argument("spec", type=Path)

    c = sub.add_parser("check")
    c.add_argument("spec", type=Path)
    c.add_argument("--registry", choices=["prospero", "osf"], required=True)
    c.add_argument("--out")

    p = sub.add_parser("plan")
    p.add_argument("spec", type=Path)
    p.add_argument("--registry", choices=["prospero", "osf"], required=True)
    p.add_argument("--out", required=True)

    rb = sub.add_parser("readback")
    rb.add_argument("plan", type=Path)
    rb.add_argument("actual", type=Path)
    rb.add_argument("--out")

    s = sub.add_parser("similar")
    s.add_argument("query", help="kifejezések ';'-vel elválasztva, pl. 'gestational diabetes; dose-response'")
    s.add_argument("--out")

    fl = sub.add_parser("fields")
    fl.add_argument("registry", choices=["prospero", "osf"])

    a = ap.parse_args(argv)

    if a.cmd == "route":
        out = route(load_json(a.spec))
        print(f"routing: {out['decision']}  (PROSPERO-képes: {'igen' if out['prospero_eligible'] else 'nem'})")
        for b in out["blockers"]:
            print(f"  HIBA      {b}")
        for n in out["notes"]:
            print(f"  FIGYELEM  {n}")
        if out["osf_note"]:
            print(f"  OSF       {out['osf_note']}")
        return 0 if out["decision"] in ("prospero", "osf") else 1

    if a.cmd == "check":
        findings = check(load_json(a.spec), a.registry)
        print_findings(findings, f"Pass 1 — {a.registry}")
        write_out(a.out, {"pass": 1, "registry": a.registry, "findings": findings})
        return 1 if any(x["sev"] == "HIBA" for x in findings) else 0

    if a.cmd == "plan":
        spec = load_json(a.spec)
        findings = check(spec, a.registry)
        blocking = [x for x in findings if x["sev"] == "HIBA"]
        if blocking:
            print_findings(blocking, "A terv nem készülhet: van HIBA")
            return 1
        doc = plan(spec, a.registry)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"terv: {doc['count']} bejegyzés → {a.out}")
        return 0

    if a.cmd == "readback":
        findings = readback(load_json(a.plan), load_json(a.actual))
        print_findings(findings, "Pass 3 — visszaolvasás")
        write_out(a.out, {"pass": 3, "findings": findings})
        return 1 if any(x["sev"] == "HIBA" for x in findings) else 0

    if a.cmd == "similar":
        doc = similar(a.query)
        per = ", ".join(f"'{t}': {n}" for t, n in doc["per_term_total"].items())
        print(f"OSF: {doc['retrieved']} egyedi találat · összesen szerint: {per} · "
              f"SR-sémás: {sum(h['is_sr_schema'] for h in doc['hits'])}")
        if doc["truncated_terms"]:
            print(f"  FIGYELEM  csonkolva ({MAX_PAGES * 50}-nél több találat): {', '.join(doc['truncated_terms'])}")
        for h in doc["hits"][:15]:
            flag = "SR" if h["is_sr_schema"] else "  "
            print(f"  {flag} {h['date_registered'][:10]} {h['id']:<8} {h['title'][:90]}")
        write_out(a.out, doc)
        return 0

    if a.cmd == "fields":
        form = form_for(a.registry)
        items = form["fields"] if a.registry == "prospero" else form["questions"]
        for it in items:
            req = "*" if it.get("required") else " "
            print(f"  {req} {it['key']:<34} {it['label']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
