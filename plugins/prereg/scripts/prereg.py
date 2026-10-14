#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prereg — registration spec → routing, Pass-1 checks, fill plan, Pass-3 read-back.

    prereg.py route    SPEC                              PROSPERO, OSF, ask, or blocked — with reasons
    prereg.py check    SPEC --registry prospero|osf [--out F]   Pass 1: deterministic findings
    prereg.py plan     SPEC --registry prospero|osf --out PLAN  label → value list for the browser
    prereg.py readback PLAN ACTUAL [--out F]             Pass 3: what the live form shows vs. the plan
    prereg.py similar  QUERY [--out F]                   OSF public API, topic words only
    prereg.py fields   prospero|osf
    prereg.py orcid    NAME                              base-registry lookup for a team member
    prereg.py protocol SPEC --registry prospero|osf --out DIR [--pdf]
                                                         protocol.md (+ .pdf) and protocol.json manifest

Nothing here drives a browser or writes to a registry. `similar` is the only network
call, and it sends only the query string: keep names, e-mails and ORCIDs out of it.
`protocol` writes local files only; the upload is a browser step with its own approval.
Exit code 1 means at least one HIBA (blocking) finding.

Stdlib only; `protocol --pdf` also needs pandoc and xelatex on PATH.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

REF = Path(__file__).resolve().parent.parent / "skills" / "prereg" / "references"
OSF_SR_SCHEMA_ID = "69cbc587cd7e8b69fa11ab52"
ORCID_REGISTRY_FILE = REF / "orcid-registry.json"

#: Review kinds PROSPERO does not register (CRD guidance: no narrative, scoping, literature, mapping).
PROSPERO_INELIGIBLE_KINDS = {"scoping", "narrative", "literature", "mapping"}
REVIEW_KINDS = {"systematic", "rapid", "umbrella", "other"} | PROSPERO_INELIGIBLE_KINDS
POPULATIONS = {"human", "animal", "in-vitro", "mixed"}
STAGE_STATES = ("not_started", "started", "completed")
STAGE_ROWS = ["pilot_work", "formal_searching", "screening", "data_extraction", "risk_of_bias", "data_synthesis"]
SPEC_TOP_KEYS = {"slug", "registry", "review_kind", "population_scope", "outcome_health",
                 "human_health_relevance", "cochrane_protocol", "prospero", "osf", "similar", "notes", "osf_metadata", "stage",
                 "aims", "protocol", "protocol_visibility"}

#: Protocol visibility is the user's choice, recorded in the spec. PROSPERO: the upload option. OSF: the final
#: registration dialog ("Make registration public immediately" or "Enter registration into embargo").
PROTOCOL_VISIBILITY = {
    "prospero": {"public_now": "make public now", "until_review_end": "do not publish until the review end date"},
    "osf": {"public_immediately": "Make registration public immediately",
            "embargo": "Enter registration into embargo"},
}

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
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
#: Word limits (min, max) of the live PROSPERO form, read on 2026-10-12. Fields not listed are not counted.
PROSPERO_WORDS = {
    "title": (5, 30),
    "review_affiliation": (1, 20),
    "rationale": (5, 250),
    "objectives": (10, 200),
    "population_included": (5, 200),
    "population_excluded": (0, 200),
    "context": (5, 250),
    "outcomes_main": (5, 250),
    "outcomes_additional": (0, 300),
    "synthesis": (30, 500),
    "certainty": (5, 250),
    "other_databases": (1, 50),
    "other_methods": (0, 50),
    "searching_other": (0, 250),
    "funding": (0, 50),
    "reporting_bias": (0, 50),
    "revision_note": (0, 250),
}
#: "Link to search strategy" is a choice on the live form, not a URL field.
PROSPERO_STRATEGY_VALUES = {"not_available", "upload_pdf", "in_protocol"}
OSF_METADATA_KEYS = ("title", "description", "license", "subjects")


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
    if pop == "animal" and not spec.get("human_health_relevance"):
        blockers.append("állatkísérletes review, amely nincs igazoltan közvetlenül releváns az emberi egészség "
                        "szempontjából: a PROSPERO csak ezt veszi fel (human_health_relevance = true kell hozzá)")
    if pop == "animal" and spec.get("human_health_relevance"):
        notes.append("állatkísérletes review: a PROSPERO űrlapja ezt külön, állat-opcióként kínálja "
                     "('directly relevant to human health'); az egészség-relevanciát a leírásban is igazold")
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

_ORCID_REG_CACHE: list[dict] | None = None
TITLE_WORDS = re.compile(r"\b(dr|prof|mr|mrs|ms)\.?\s*", re.IGNORECASE)


def _fold(s: str) -> str:
    """Lower-case, accents and separators removed: 'Gulyás-Oldal' and 'gulyasoldal' compare equal."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", s.lower())


def norm_name(name: str) -> str:
    return _fold(TITLE_WORDS.sub("", name or ""))


def load_orcid_registry() -> list[dict]:
    global _ORCID_REG_CACHE
    if _ORCID_REG_CACHE is None:
        _ORCID_REG_CACHE = json.loads(ORCID_REGISTRY_FILE.read_text(encoding="utf-8")).get("members", [])
    return _ORCID_REG_CACHE


def lookup_orcid(name: str) -> tuple[str, list[dict]]:
    """('none' | 'one' | 'many', matches). Matches full names and listed aliases only, never a bare surname."""
    key = norm_name(name)
    if not key:
        return "none", []
    hits = [m for m in load_orcid_registry()
            if any(norm_name(f) == key for f in [m["name"], *m.get("aliases", [])])]
    if not hits:
        return "none", []
    return ("one", hits) if len(hits) == 1 else ("many", hits)


def _orcid_registry_check(person: dict, path: str, add) -> None:
    status, hits = lookup_orcid(person.get("name", ""))
    if status == "none":
        return
    if status == "many":
        add("FIGYELEM", path, "a név több törzsadatnak is megfelel — az ORCID-et kézzel kell megerősíteni")
        return
    reg = hits[0]["orcid"]
    given = (person.get("orcid") or "").strip()
    if not given:
        add("FIGYELEM", f"{path}.orcid", f"a törzsadatok szerint ennek a névnek az ORCID-je: {reg} "
                                         "— megerősítés után töltsd ki")
    elif given != reg:
        add("HIBA", f"{path}.orcid", f"a megadott ORCID ({given}) eltér a törzsadatoktól ({reg}) "
                                     "ugyanehhez a névhez — ellenőrizd, melyik a helyes")


def check(spec: dict, registry: str) -> list[dict]:
    f: list[dict] = []

    def add(sev, field, msg):
        f.append({"sev": sev, "field": field, "msg": msg})

    for k in spec:
        if k not in SPEC_TOP_KEYS:
            add("HIBA", k, "ismeretlen kulcs a spec gyökerében")
    if "human_health_relevance" in spec and not isinstance(spec["human_health_relevance"], bool):
        add("HIBA", "human_health_relevance", "logikai érték kell legyen (true/false)")
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
        for key, (lo, hi) in PROSPERO_WORDS.items():
            if is_empty(pro.get(key)):
                continue
            n = len(str(pro[key]).split())
            if n < lo:
                add("HIBA", key, f"{n} szó, a PROSPERO-űrlap minimuma {lo} (élő űrlap, 2026-10-12)")
            elif n > hi:
                add("HIBA", key, f"{n} szó, a PROSPERO-űrlap maximuma {hi}")
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
        if end and not is_empty(end):
            try:
                if dt.date.fromisoformat(str(end)) < dt.date.today() + dt.timedelta(days=28):
                    add("HIBA", "review_end", "az űrlap szerint a befejezés legalább 28 nappal a jövőben legyen "
                                              "(az 'end date should be at least 28 days in the future')")
            except ValueError:
                pass
        strat = pro.get("strategy_url")
        if not is_empty(strat) and str(strat) not in PROSPERO_STRATEGY_VALUES:
            add("HIBA", "strategy_url", "a PROSPERO nem URL-t kér: 'not_available', 'upload_pdf' vagy "
                                        "'in_protocol' (a keresési stratégia PDF-feltöltése)")
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
        if team:
            if len(team) < 2:
                add("HIBA", "team", "legalább két csapattag kell (az űrlap szabálya)")
            if not any(isinstance(m, dict) and m.get("guarantor") is True for m in team):
                add("HIBA", "team", "egy csapattagnak guarantornak kell lennie (guarantor: true)")
            for m_i, member in enumerate(team):
                if isinstance(member, dict) and member.get("consent") is not True:
                    add("HIBA", f"team[{m_i}].consent", "csapattag csak a beleegyezésével szerepelhet "
                                                         "(consent: true); nem vehető fel név szerint hozzájárulás nélkül")
        for m_i, member in enumerate(team):
            if isinstance(member, dict):
                _orcid_registry_check(member, f"team[{m_i}]", add)
        contact = _dict(pro.get("named_contact"))
        _orcid_registry_check(contact, "named_contact", add)
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
            if "query" in k and " AND " in str(v) and " OR " in str(v) and "(" not in str(v):
                add("FIGYELEM", k, "AND és OR zárójelek nélkül: a PubMed a sorrendtől függően más találatot adhat — "
                                   "futtasd le a pubmed-count paranccsal, mielőtt rögzíted")
        meta = _dict(spec.get("osf_metadata"))
        for mk in OSF_METADATA_KEYS:
            if is_empty(meta.get(mk)):
                add("HIBA", f"osf_metadata.{mk}", "az OSF-regisztráció ezt kötelezőnek jelöli a Register előtt "
                                                   "(cím, leírás, licenc, tárgykör)")
        stage_spec = _dict(spec.get("stage")) or _dict(_dict(spec.get("prospero")).get("stage"))
        if stage_spec.get("data_extraction") in ("started", "completed"):
            cs = str(osf.get("review-methods/current-review-stage") or "").lower()
            if "retrospective" not in cs and "not prospective" not in cs:
                add("HIBA", "review-methods/current-review-stage",
                    "az adatkinyerés már elkezdődött: a 'Current review stage' mezőben ki kell mondani, hogy a "
                    "regisztráció utólagos (retrospective), nem prospektív")
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

def pubmed_count(term: str, mindate: str, maxdate: str, datetype: str = "pdat") -> int:
    """Hits for a PubMed query, passed through unchanged, so a registered string can be checked against its recorded count.
    Dates are YYYY/MM/DD. datetype: pdat (publication) or edat (entry). A string without parentheses is read by PubMed
    in its own operator order: compare the two forms before recording either one."""
    qs = urllib.parse.urlencode({"db": "pubmed", "term": term, "retmode": "json", "retmax": 0,
                                 "datetype": datetype, "mindate": mindate, "maxdate": maxdate})
    return int(_get_json(f"{PUBMED_ESEARCH}?{qs}")["esearchresult"]["count"])


#: Protocol sections in order: (heading, PROSPERO spec key). Values come from the spec, never from the agent.
PROTOCOL_SECTIONS = [
    ("Review type", "review_type"), ("Rationale", "rationale"), ("Objectives", "objectives"),
    ("Condition or domain", "condition"), ("Keywords", "keywords"), ("Country", "country"),
    ("Population: included", "population_included"), ("Population: excluded", "population_excluded"),
    ("Intervention or exposure: included", "exposure_included"),
    ("Intervention or exposure: excluded", "exposure_excluded"),
    ("Comparator", "comparator"), ("Study design", "study_design"), ("Context", "context"),
    ("Review start", "review_start"), ("Review end", "review_end"),
    ("Protocol availability", "protocol_available"), ("Unpublished studies", "unpublished_studies"),
    ("Sources", "sources"), ("Other databases", "other_databases"),
    ("Language restrictions", "language_restrictions"), ("Date restrictions", "date_restrictions"),
    ("Other methods", "other_methods"), ("Other means of identifying studies", "searching_other"),
    ("Selection process", "selection"), ("Data extraction", "extraction"), ("Risk of bias", "risk_of_bias"),
    ("Reporting bias", "reporting_bias"), ("Certainty of evidence", "certainty"),
    ("Outcomes: main", "outcomes_main"), ("Outcomes: additional", "outcomes_additional"),
    ("Data synthesis", "synthesis"), ("Review status", "review_status"), ("Publication", "publication"),
    ("Funding", "funding"), ("Conflicts of interest", "conflicts"),
    ("Review affiliation", "review_affiliation"), ("Peer review", "peer_review"),
    ("Revision note", "revision_note"),
]


def _aims_text(aims) -> str:
    if isinstance(aims, list):
        return "\n".join(f"{i}. {a.strip()}" for i, a in enumerate(aims, 1) if isinstance(a, str) and a.strip())
    return aims.strip() if isinstance(aims, str) else ""


def render_protocol(spec: dict) -> str:
    pro = _dict(spec.get("prospero"))
    lines = [f"# {pro.get('title', '').strip()}", "",
             f"Registry: {spec.get('registry', 'prospero').upper()}. Protocol version 1.0.", ""]
    lines += ["## Team", ""]
    for m in pro.get("team") or []:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        role = "guarantor" if m.get("guarantor") is True else "team member"
        orcid = f", ORCID {m['orcid']}" if m.get("orcid") else ""
        lines.append(f"- {m['name']} ({role}), {m.get('affiliation', '').strip()}{orcid}")
    contact = _dict(pro.get("named_contact"))
    if contact.get("name"):
        lines.append(f"- Named contact: {contact['name']}, {contact.get('email', '')}")
    lines += ["", "## Aims", "", _aims_text(spec.get("aims")), ""]
    lines += ["## Registered methods", ""]
    for heading, key in PROTOCOL_SECTIONS:
        value = pro.get(key)
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value if str(v).strip())
        if isinstance(value, str) and value.strip():
            lines += [f"### {heading}", "", value.strip(), ""]
    return "\n".join(lines).rstrip() + "\n"


def render_protocol_osf(spec: dict) -> str:
    """OSF protocol: the answers under the schema keys, grouped by the form's pages, in the form's order."""
    osf = _dict(spec.get("osf"))
    meta = _dict(spec.get("osf_metadata"))
    lines = [f"# {meta.get('title', '').strip()}", "",
             "Registry: OSF Registries, Generalized Systematic Review Registration. Protocol version 1.0.", ""]
    team = _dict(spec.get("prospero")).get("team") or []
    names = [m for m in team if isinstance(m, dict) and m.get("name")]
    if names:
        lines += ["## Team", ""]
        lines += [f"- {m['name']}, {m.get('affiliation', '').strip()}"
                  + (f", ORCID {m['orcid']}" if m.get("orcid") else "") for m in names]
        lines.append("")
    lines += ["## Aims", "", _aims_text(spec.get("aims")), ""]
    page = None
    for q in load_json(REF / "osf-sr-form.json")["questions"]:
        value = osf.get(q["key"])
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value if str(v).strip())
        if not (isinstance(value, str) and value.strip()):
            continue
        if q["page"] != page:
            page = q["page"]
            lines += [f"## {page}", ""]
        lines += [f"### {q['label']}", "", value.strip(), ""]
    return "\n".join(lines).rstrip() + "\n"


def cmd_protocol(a) -> int:
    spec = load_json(a.spec)
    findings = check(spec, a.registry)
    blocking = [x for x in findings if x["sev"] == "HIBA"]
    if not _aims_text(spec.get("aims")):
        blocking.append({"sev": "HIBA", "field": "aims", "msg": "a célok (aims) hiányoznak — kérd be a felhasználótól"})
    vis = spec.get("protocol_visibility")
    if vis not in PROTOCOL_VISIBILITY[a.registry]:
        choices = ", ".join(PROTOCOL_VISIBILITY[a.registry])
        blocking.append({"sev": "HIBA", "field": "protocol_visibility",
                         "msg": f"a protokoll láthatósága hiányzik vagy nem való ehhez a regiszterhez "
                                f"(válassz: {choices}) — a felhasználó döntése"})
    if blocking:
        print_findings(blocking, "A protokoll nem készülhet: van HIBA")
        return 1
    text = render_protocol(spec) if a.registry == "prospero" else render_protocol_osf(spec)
    leftover = PLACEHOLDER.search(text)
    if leftover:
        print(f"HIBA  protokoll: kitöltetlen helyőrző maradt: {leftover.group(0)!r}")
        return 1
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    md = out / "protocol.md"
    md.write_text(text, encoding="utf-8")
    files = {"protocol.md": hashlib.sha256(md.read_bytes()).hexdigest()}
    pdf_note = "PDF nem készült (nincs --pdf)"
    if a.pdf:
        pandoc, xelatex = shutil.which("pandoc"), shutil.which("xelatex")
        if pandoc and xelatex:
            pdf = out / "protocol.pdf"
            subprocess.run([pandoc, str(md), "-o", str(pdf), "--pdf-engine=xelatex",
                            "-V", "geometry:margin=2cm"], check=True)
            files["protocol.pdf"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
            pdf_note = "PDF kész: protocol.pdf"
        else:
            pdf_note = "FIGYELEM  PDF nem készült: a pandoc vagy a xelatex hiányzik a PATH-ról"
    manifest = {
        "title": _dict(spec.get("prospero")).get("title", ""),
        "registry": a.registry,
        "created": dt.date.today().isoformat(),
        "sha256": files,
        "team": [m.get("name") for m in _dict(spec.get("prospero")).get("team") or [] if isinstance(m, dict)],
        "visibility": {"choice": vis, "meaning": PROTOCOL_VISIBILITY[a.registry][vis]},
        "upload": {"prospero": "Protocol upload, PDF, in the 'Availability of full protocol' item",
                   "osf": "file upload to the registration draft; visibility is set at submission (Gate B)"},
        "approval": "uploading needs an explicit user yes; this file does not upload anything",
    }
    (out / "protocol.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"protokoll: {md}  ({pdf_note})  manifest: {out / 'protocol.json'}")
    return 0


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

    pc = sub.add_parser("pubmed-count", help="PubMed-találatszám egy stringre, változtatás nélkül")
    pc.add_argument("term")
    pc.add_argument("--mindate", default="1900/01/01")
    pc.add_argument("--maxdate", required=True, help="YYYY/MM/DD, pl. a keresés napja")
    pc.add_argument("--datetype", choices=["pdat", "edat"], default="pdat")

    fl = sub.add_parser("fields")
    fl.add_argument("registry", choices=["prospero", "osf"])

    og = sub.add_parser("orcid", help="törzsadat-keresés egy csapattag nevére")
    og.add_argument("name")

    pr = sub.add_parser("protocol", help="protokoll.md (+ .pdf) és manifest a spec-ből")
    pr.add_argument("spec", type=Path)
    pr.add_argument("--registry", choices=["prospero", "osf"], required=True)
    pr.add_argument("--out", required=True, help="célmappa")
    pr.add_argument("--pdf", action="store_true", help="PDF is készüljön (pandoc + xelatex kell)")

    a = ap.parse_args(argv)

    if a.cmd == "orcid":
        status, hits = lookup_orcid(a.name)
        if status == "none":
            print("nincs ilyen név a törzsadatokban — kérd be a felhasználótól, ne találd ki")
            return 1
        if status == "many":
            print("több törzsadat is illik ehhez a névhez — az ORCID-et kézzel kell megerősíteni")
            return 1
        m = hits[0]
        print(f"{m['name']}: {m['orcid']}  (byline: {m.get('byline', m['name'])})"
              + (f"  — {m['note']}" if m.get("note") else ""))
        return 0

    if a.cmd == "protocol":
        return cmd_protocol(a)

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

    if a.cmd == "pubmed-count":
        print(pubmed_count(a.term, a.mindate, a.maxdate, a.datetype))
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
