#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROSPERO protocol record — scaffold it, check it, export it for submission.

    prospero.py init --project endo-diet --title "..."     # scaffold protocol.json
    prospero.py check --protocol protocol.json             # eligibility + completeness
    prospero.py stage --protocol protocol.json --set formal_screening=started
    prospero.py export --protocol protocol.json --out protocol.md
    prospero.py fields                                     # the 36 registration fields

Why a protocol file at all
--------------------------
PROSPERO's value is prospectivity: a protocol registered *before* screening
starts is a promise that the eligibility criteria were not written after seeing
which papers would make the result come out well. That promise is only worth
something if the registration really preceded the screening — which means the
protocol has to exist as a file, with dates, before `collect` runs, not as an
intention. So `collect --protocol` stamps every search with the registration
number and the review's stage at search time, and refuses to pretend when there
isn't one.

The two rules this enforces that people get wrong
-------------------------------------------------
1. **PROSPERO does not register every kind of review.** Systematic reviews,
   rapid reviews and umbrella reviews of health outcomes are eligible. Scoping
   reviews, NARRATIVE reviews, literature reviews and mapping reviews are not.
   Registering the wrong type is a rejection, and — worse — writing "registered
   in PROSPERO" in a narrative review's methods is a claim a reviewer can check
   and disprove. `check` says so before that happens; OSF Registries takes what
   PROSPERO won't.
2. **Registration must precede data extraction.** PROSPERO will not accept a
   record for a review that has moved past the start of data extraction. `check`
   reads the stage table and says whether the window is still open.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

#: The PROSPERO registration record, in submission order. `True` = mandatory.
FIELDS: list[tuple[str, str, bool]] = [
    ("title",                 "Review title", True),
    ("original_language_title", "Original language title", False),
    ("start_date",            "Anticipated or actual start date", True),
    ("completion_date",       "Anticipated completion date", True),
    ("stage",                 "Stage of review at time of submission", True),
    ("named_contact",         "Named contact", True),
    ("named_contact_email",   "Named contact email", True),
    ("named_contact_affiliation", "Named contact organisational affiliation", True),
    ("review_team",           "Review team members and affiliations", True),
    ("funding",               "Funding sources / sponsors", True),
    ("conflicts",             "Conflicts of interest", True),
    ("collaborators",         "Collaborators", False),
    ("review_question",       "Review question", True),
    ("searches",              "Searches — databases, dates, restrictions", True),
    ("search_strategy_url",   "URL to search strategy", False),
    ("condition",             "Condition or domain being studied", True),
    ("participants",          "Participants / population", True),
    ("intervention",          "Intervention(s), exposure(s)", True),
    ("comparator",            "Comparator(s) / control", True),
    ("study_types",           "Types of study to be included", True),
    ("context",               "Context", False),
    ("main_outcomes",         "Main outcome(s) and measures", True),
    ("additional_outcomes",   "Additional outcome(s)", False),
    ("data_extraction",       "Data extraction — selection and coding", True),
    ("risk_of_bias",          "Risk of bias (quality) assessment", True),
    ("synthesis",             "Strategy for data synthesis", True),
    ("subgroups",             "Analysis of subgroups or subsets", False),
    ("review_type",           "Type and method of review", True),
    ("health_area",           "Health area of the review", True),
    ("language",              "Language", True),
    ("country",               "Country", True),
    ("other_registration",    "Other registration details", False),
    ("published_protocol",    "Reference / URL for published protocol", False),
    ("dissemination",         "Dissemination plans", False),
    ("keywords",              "Keywords", False),
    ("existing_reviews",      "Details of any existing review of the same topic", False),
    ("review_status",         "Current review status", True),
    ("additional_info",       "Any additional information", False),
    ("final_report",          "Details of final report / publication", False),
]

#: PROSPERO's own stage table. Order matters: it is also the timeline.
STAGES = [
    "preliminary_searches",
    "piloting_selection",
    "formal_screening",
    "data_extraction",
    "risk_of_bias",
    "data_analysis",
]
STAGE_VALUES = ("no", "started", "completed")

ELIGIBLE_TYPES = {
    "systematic review", "rapid review", "umbrella review",
    "systematic review of reviews", "meta-analysis",
}
INELIGIBLE_TYPES = {
    "narrative review", "scoping review", "literature review", "mapping review",
    "state-of-the-art review", "expert review", "perspective", "editorial",
}


def scaffold(title: str, project: str) -> dict:
    today = date.today().isoformat()
    rec = {key: "" for key, _, _ in FIELDS}
    rec.update({
        "_project": project,
        "prospero_id": "",
        "registered": "",
        "title": title,
        "start_date": today,
        "review_status": "The review has not yet started",
        "language": "English",
        "country": "Hungary",
        "review_type": "Systematic review",
        "stage": {s: "no" for s in STAGES},
        "status": "draft",
    })
    return rec


def check(rec: dict) -> int:
    problems: list[str] = []
    warnings: list[str] = []

    rtype = str(rec.get("review_type", "")).strip().lower()
    if rtype:
        if any(t in rtype for t in INELIGIBLE_TYPES):
            problems.append(
                f"'{rec['review_type']}' NEM regisztrálható a PROSPERO-ban. "
                "A PROSPERO szisztematikus, rapid és umbrella review-kat vesz fel "
                "egészségügyi kimenettel; a narratív, scoping és irodalmi review "
                "nem tartozik ide. Regisztráld inkább az OSF Registries-ben "
                "(osf.io/registries), és a kéziratban azt hivatkozd — a "
                "\"registered in PROSPERO\" mondat egy narratív review-ban "
                "ellenőrizhetően valótlan.")
        elif not any(t in rtype for t in ELIGIBLE_TYPES):
            warnings.append(f"ismeretlen review-típus: '{rec['review_type']}' — "
                            "ellenőrizd a PROSPERO befogadási körét")

    stage = rec.get("stage") or {}
    bad = [f"{k}={v}" for k, v in stage.items()
           if k in STAGES and v not in STAGE_VALUES]
    if bad:
        problems.append("érvénytelen szakasz-érték: " + ", ".join(bad)
                        + f" (megengedett: {', '.join(STAGE_VALUES)})")
    if stage.get("data_extraction") == "completed" or stage.get("data_analysis") in ("started", "completed"):
        problems.append(
            "A review már túl van az adatkinyerés kezdetén, ezért a PROSPERO "
            "nem regisztrálja. Ez nem formalitás: a prospektivitás az egyetlen "
            "dolog, amit a regisztráció bizonyít. Retrospektív regisztráció "
            "helyett írd le a kéziratban, hogy nem volt regisztrálva.")
    elif stage.get("formal_screening") in ("started", "completed") and not rec.get("prospero_id"):
        warnings.append(
            "A formális szűrés már elindult, de nincs regisztrációs szám. "
            "A regisztrációnak a szűrés MEGKEZDÉSE előtt kellett volna megtörténnie.")

    missing = [label for key, label, required in FIELDS
               if required and not rec.get(key)]
    if missing:
        problems.append(f"{len(missing)} kötelező mező üres:\n      - "
                        + "\n      - ".join(missing))

    if not rec.get("prospero_id"):
        warnings.append("nincs prospero_id — a rekord még nincs beküldve/regisztrálva")

    print(f"PROSPERO protokoll: {rec.get('title') or '(cím nélkül)'}")
    print(f"  típus: {rec.get('review_type') or '—'}   "
          f"regisztráció: {rec.get('prospero_id') or 'nincs'}")
    print(f"  szakaszok: " + ", ".join(f"{k}={stage.get(k, 'no')}" for k in STAGES))
    for w in warnings:
        print(f"  FIGYELEM  {w}")
    for p in problems:
        print(f"  HIBA      {p}")
    if not problems:
        print("  A rekord beküldhető." if not warnings else "  Beküldhető, a figyelmeztetésekkel.")
    return 1 if problems else 0


def export_md(rec: dict) -> str:
    stage = rec.get("stage") or {}
    lines = [f"# {rec.get('title') or 'Untitled review'}", ""]
    if rec.get("prospero_id"):
        lines += [f"**PROSPERO:** {rec['prospero_id']}"
                  + (f" (registered {rec['registered']})" if rec.get("registered") else ""), ""]
    else:
        lines += ["**PROSPERO:** not yet registered", ""]
    for key, label, required in FIELDS:
        if key == "stage":
            lines += [f"## {label}", "",
                      "| Stage | Status |", "|---|---|"]
            lines += [f"| {s.replace('_', ' ').capitalize()} | {stage.get(s, 'no')} |"
                      for s in STAGES]
            lines.append("")
            continue
        value = rec.get(key, "")
        if not value and not required:
            continue
        lines += [f"## {label}", "", str(value) if value else "_(kitöltendő)_", ""]
    return "\n".join(lines)


def load(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"nincs ilyen protokoll: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    i = sub.add_parser("init", help="scaffold a protocol JSON")
    i.add_argument("--project", required=True)
    i.add_argument("--title", default="")
    i.add_argument("--out", type=Path)

    c = sub.add_parser("check", help="eligibility and completeness")
    c.add_argument("--protocol", type=Path, required=True)

    s = sub.add_parser("stage", help="update the stage table")
    s.add_argument("--protocol", type=Path, required=True)
    s.add_argument("--set", dest="sets", action="append", required=True,
                   metavar="STAGE=VALUE")

    e = sub.add_parser("export", help="submission-ready markdown")
    e.add_argument("--protocol", type=Path, required=True)
    e.add_argument("--out", type=Path)

    sub.add_parser("fields", help="list the registration fields")

    args = ap.parse_args(argv)

    if args.cmd == "fields":
        for key, label, required in FIELDS:
            print(f"  {'*' if required else ' '} {key:<26} {label}")
        print("\n  * = kötelező. Szakaszok: " + ", ".join(STAGES))
        return 0

    if args.cmd == "init":
        out = args.out or Path(f"{args.project}-protocol.json")
        if out.exists():
            sys.exit(f"már létezik: {out} — nem írom felül")
        rec = scaffold(args.title or args.project, args.project)
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Protokoll váz: {out}\n"
              f"  Töltsd ki a kötelező mezőket, majd: prospero.py check --protocol {out}\n"
              f"  A keresés ezután: collect --protocol {out} ...")
        return 0

    if args.cmd == "check":
        return check(load(args.protocol))

    if args.cmd == "stage":
        rec = load(args.protocol)
        stage = rec.setdefault("stage", {s: "no" for s in STAGES})
        for pair in args.sets:
            if "=" not in pair:
                sys.exit(f"--set formátuma STAGE=VALUE, ez nem az: {pair}")
            k, v = pair.split("=", 1)
            if k not in STAGES:
                sys.exit(f"ismeretlen szakasz: {k}\n  megengedett: {', '.join(STAGES)}")
            if v not in STAGE_VALUES:
                sys.exit(f"ismeretlen érték: {v}\n  megengedett: {', '.join(STAGE_VALUES)}")
            stage[k] = v
        args.protocol.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print("Szakasztábla frissítve:")
        return check(rec)

    if args.cmd == "export":
        rec = load(args.protocol)
        text = export_md(rec)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"Protokoll: {args.out}")
        else:
            print(text)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
