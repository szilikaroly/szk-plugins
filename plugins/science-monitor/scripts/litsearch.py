#!/usr/bin/env python3
"""Run a literature search across sources, and log it while it is still true.

Why this sits next to search_log rather than replacing it
---------------------------------------------------------
`sm.py searchlog` already records what was searched, where, and how much was
kept — the audit trail a reviewer asks for when they want to know how studies
were identified. But it is a record of work done elsewhere, typed in by hand,
so the counts are only as accurate as the person copying them. This runs the
query and writes the count itself. The log stops being a memory exercise.

Sources, and what each is actually good for
-------------------------------------------
  europepmc   MEDLINE + PMC + preprints + patents, no key, honest boolean
              support. The closest free stand-in for a subscription database.
  openalex    broadest coverage including non-PubMed venues; good for
              citation-chasing and for catching what MEDLINE indexing missed.
  crossref    DOI registry. Use it to verify and complete records, not to
              discover — its relevance ranking is loose and totals are huge.
  embase      Elsevier, subscription. Needs a working key; see below.

Keys are never stored here
--------------------------
Read from the environment, or from `~/.science-monitor/keys.json`, which the
installer gitignores. Nothing in this repository should ever contain one:
this plugin lives in a public marketplace, and a key committed once stays in
the git history after it is deleted.

    export ELSEVIER_API_KEY=...          # embase / scopus
    export SCIENCE_MONITOR_MAILTO=...    # polite pool for openalex + crossref

  litsearch.py --query '...' --sources europepmc,openalex
  litsearch.py --query '...' --slug pmos --purpose topic --log
  litsearch.py --keys                  # which sources are usable right now

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

UA = "science-monitor/1.0 (literature search; mailto:%s)"
TIMEOUT = 30.0


def keys_file() -> Path:
    root = os.environ.get("SCIENCE_MONITOR_HOME") or (Path.home() / ".science-monitor")
    return Path(root) / "keys.json"


def get_key(name: str) -> str:
    """Environment first, then the gitignored local file. Never a literal."""
    v = os.environ.get(name)
    if v:
        return v.strip()
    try:
        return (json.loads(keys_file().read_text()).get(name) or "").strip()
    except Exception:
        return ""


def mailto() -> str:
    return get_key("SCIENCE_MONITOR_MAILTO") or "anonymous@example.org"


def _get(url: str, headers: dict | None = None) -> dict | None:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": UA % mailto(),
                                               **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read()[:300].decode("utf-8", "replace")}
    except Exception as e:
        return {"_error": type(e).__name__}


# --------------------------------------------------------------------------- sources

def search_europepmc(query: str, limit: int = 25) -> dict:
    d = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
             + urllib.parse.urlencode({"query": query, "format": "json",
                                       "pageSize": min(limit, 100),
                                       "resultType": "core"}))
    if not d or "_error" in d or "_http_error" in d:
        return {"source": "europepmc", "error": d, "hits": 0, "records": []}
    recs = []
    for r in (d.get("resultList") or {}).get("result", []):
        recs.append({"title": r.get("title", "").rstrip("."),
                     "year": r.get("pubYear", ""), "journal": r.get("journalTitle", ""),
                     "doi": (r.get("doi") or "").lower(),
                     "pmid": r.get("pmid", ""), "pmcid": r.get("pmcid", ""),
                     "open_access": r.get("isOpenAccess") == "Y",
                     "source": "europepmc"})
    return {"source": "europepmc", "hits": d.get("hitCount", 0), "records": recs}


def search_openalex(query: str, limit: int = 25) -> dict:
    d = _get("https://api.openalex.org/works?"
             + urllib.parse.urlencode({"search": query, "per-page": min(limit, 200),
                                       "mailto": mailto()}))
    if not d or "meta" not in d:
        return {"source": "openalex", "error": d, "hits": 0, "records": []}
    recs = []
    for r in d.get("results", []):
        loc = (r.get("primary_location") or {}).get("source") or {}
        recs.append({"title": (r.get("title") or "").rstrip("."),
                     "year": r.get("publication_year", ""),
                     "journal": loc.get("display_name", ""),
                     "doi": (r.get("doi") or "").replace("https://doi.org/", "").lower(),
                     "pmid": ((r.get("ids") or {}).get("pmid") or "").rsplit("/", 1)[-1],
                     "pmcid": "", "open_access": (r.get("open_access") or {}).get("is_oa", False),
                     "cited_by": r.get("cited_by_count", 0), "source": "openalex"})
    return {"source": "openalex", "hits": d["meta"].get("count", 0), "records": recs}


def search_crossref(query: str, limit: int = 25) -> dict:
    d = _get("https://api.crossref.org/works?"
             + urllib.parse.urlencode({"query": query, "rows": min(limit, 100),
                                       "mailto": mailto()}))
    if not d or "message" not in d:
        return {"source": "crossref", "error": d, "hits": 0, "records": []}
    m = d["message"]
    recs = []
    for r in m.get("items", []):
        recs.append({"title": (r.get("title") or [""])[0].rstrip("."),
                     "year": ((r.get("issued") or {}).get("date-parts") or [[""]])[0][0],
                     "journal": (r.get("container-title") or [""])[0],
                     "doi": (r.get("DOI") or "").lower(), "pmid": "", "pmcid": "",
                     "open_access": False, "source": "crossref"})
    # Crossref's relevance ranking is loose and its totals are corpus-wide; the
    # number is reported but should not be quoted as a search yield.
    return {"source": "crossref", "hits": m.get("total-results", 0),
            "records": recs, "note": "total is corpus-wide, not a search yield"}


def search_embase(query: str, limit: int = 25) -> dict:
    key = get_key("ELSEVIER_API_KEY")
    if not key:
        return {"source": "embase", "hits": 0, "records": [],
                "error": "no ELSEVIER_API_KEY (env or ~/.science-monitor/keys.json)"}
    d = _get("https://api.elsevier.com/content/search/scopus?"
             + urllib.parse.urlencode({"query": query, "count": min(limit, 25)}),
             headers={"X-ELS-APIKey": key})
    if not d or "search-results" not in d:
        return {"source": "embase", "hits": 0, "records": [], "error": d}
    sr = d["search-results"]
    recs = []
    for r in sr.get("entry", []):
        recs.append({"title": (r.get("dc:title") or "").rstrip("."),
                     "year": (r.get("prism:coverDate") or "")[:4],
                     "journal": r.get("prism:publicationName", ""),
                     "doi": (r.get("prism:doi") or "").lower(),
                     "pmid": r.get("pubmed-id", ""), "pmcid": "",
                     "open_access": r.get("openaccess") == "1", "source": "embase"})
    return {"source": "embase", "hits": int(sr.get("opensearch:totalResults", 0)),
            "records": recs}


SOURCES = {"europepmc": search_europepmc, "openalex": search_openalex,
           "crossref": search_crossref, "embase": search_embase}
FREE = ("europepmc", "openalex", "crossref")


# --------------------------------------------------------------------------- dedup

def dedupe(results: list[dict]) -> tuple[list[dict], dict]:
    """Merge by DOI, then PMID, then normalised title.

    Overlap between sources is the point of searching several, but it has to be
    counted once. What each source contributed UNIQUELY is the number worth
    reporting — it is the answer to "was adding that database worth it".
    """
    seen: dict[str, dict] = {}
    order: list[str] = []
    for res in results:
        for r in res.get("records", []):
            # Written first as `a or b if c else ""`, which Python reads as
            # `(a or b) if c else ""` — so a record without a PMID skipped
            # straight to the title key even when it had a DOI. Europe PMC
            # supplies PMIDs and OpenAlex often does not, so the same paper got
            # a DOI key from one source and a title key from the other and never
            # matched: two sources reported zero overlap on a topic where they
            # plainly overlap.
            key = (r.get("doi")
                   or (f"pmid:{r['pmid']}" if r.get("pmid") else "")
                   or "t:" + "".join(c for c in r["title"].lower() if c.isalnum())[:60])
            if not key or key == "t:":
                continue
            if key in seen:
                seen[key].setdefault("also_in", []).append(r["source"])
                # Keep the richest record: an id we did not have is worth having.
                for f in ("doi", "pmid", "pmcid", "journal", "year"):
                    if not seen[key].get(f) and r.get(f):
                        seen[key][f] = r[f]
                if r.get("open_access"):
                    seen[key]["open_access"] = True
            else:
                seen[key] = dict(r)
                order.append(key)
    merged = [seen[k] for k in order]

    # Collapse a preprint onto its published version. They carry different DOIs
    # — 10.20944/preprints… and 10.3390/… for the same paper — so DOI matching
    # correctly keeps them apart, and a systematic review would then count the
    # study twice. The published record wins; the preprint DOI is kept as
    # provenance rather than discarded.
    by_title: dict[str, dict] = {}
    collapsed: list[dict] = []
    for r in merged:
        t = "".join(c for c in r["title"].lower() if c.isalnum())[:60]
        if not t:
            collapsed.append(r)
            continue
        prev = by_title.get(t)
        if prev is None:
            by_title[t] = r
            collapsed.append(r)
            continue
        pre_new = _is_preprint(r.get("doi", ""))
        pre_old = _is_preprint(prev.get("doi", ""))
        if pre_new and not pre_old:
            prev.setdefault("preprint_of", r.get("doi"))
        elif pre_old and not pre_new:
            r["preprint_of"] = prev.get("doi")
            collapsed[collapsed.index(prev)] = r
            by_title[t] = r
        else:
            collapsed.append(r)          # genuinely two records; leave both

    # NOT a coverage figure. Each source was asked for a capped number of its
    # own top-ranked hits, and the rankings diverge sharply — europepmc and
    # openalex returned 46 and 50 DOIs with ZERO in common on one real query.
    # So this counts what the other sources' top-N did not also surface, which
    # is a statement about ranking overlap, not about what a database contains.
    # Quoting it in a Methods section as "database X contributed N unique
    # studies" would be wrong.
    top_n_only: dict[str, int] = {}
    for r in collapsed:
        if not r.get("also_in"):
            top_n_only[r["source"]] = top_n_only.get(r["source"], 0) + 1
    return collapsed, top_n_only


_PREPRINT_PREFIXES = ("10.20944/preprints", "10.1101/", "10.21203/rs.",
                      "10.31219/", "10.31234/", "10.2139/ssrn")


def _is_preprint(doi: str) -> bool:
    return any(doi.startswith(p) for p in _PREPRINT_PREFIXES)


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query")
    ap.add_argument("--sources", default="europepmc,openalex")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--slug", help="log the run against this manuscript")
    ap.add_argument("--purpose", default="topic",
                    choices=("topic", "verification", "journal-selection",
                             "citation-chase"))
    ap.add_argument("--filters", default="")
    ap.add_argument("--log", action="store_true", help="write into search_log")
    ap.add_argument("--keys", action="store_true", help="which sources are usable")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.keys:
        print(f"keys file : {keys_file()}"
              f"{'  (exists)' if keys_file().exists() else '  (absent)'}")
        print(f"mailto    : {mailto()}")
        for s in SOURCES:
            if s in FREE:
                print(f"  {s:<11} ready (no key needed)")
            else:
                k = get_key("ELSEVIER_API_KEY")
                print(f"  {s:<11} {'key present' if k else 'NO KEY — set ELSEVIER_API_KEY'}")
        return 0

    if not args.query:
        ap.print_help()
        return 2

    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]
    bad = [s for s in wanted if s not in SOURCES]
    if bad:
        print(f"unknown source(s): {', '.join(bad)}", file=sys.stderr)
        return 2

    results = [SOURCES[s](args.query, args.limit) for s in wanted]
    merged, unique = dedupe(results)

    if args.log:
        if not args.slug:
            print("--log needs --slug", file=sys.stderr)
            return 2
        import sm_lib as L
        conn = L.connect()
        row = conn.execute("SELECT id FROM projects WHERE slug = ?",
                           (args.slug,)).fetchone()
        if not row:
            print(f"no manuscript with slug '{args.slug}'", file=sys.stderr)
            return 1
        import sm
        for res in results:
            if res.get("error"):
                continue
            # `kept` means kept AFTER SCREENING, and screening has not happened
            # yet — this only ran the query. Writing the unique-contribution
            # count here made the generated Methods paragraph claim studies had
            # been selected when none had been looked at. It stays 0 until a
            # human screens; the retrieval statistic goes in notes, where it
            # cannot be mistaken for a selection decision.
            note = res.get("note", "")
            u = unique.get(res["source"], 0)
            if u:
                note = (note + "; " if note else "") + \
                    f"{u} of {len(res['records'])} fetched were not in the other " \
                    f"sources' top-N (ranking overlap, not coverage)"
            sm._searchlog_insert(conn, row[0], {
                "ran_at": L.now()[:10], "source": res["source"], "query": args.query,
                "filters": args.filters, "hits": res["hits"],
                "kept": 0, "purpose": args.purpose, "notes": note})
        conn.commit()

    if args.json:
        print(json.dumps({"query": args.query,
                          "per_source": [{k: v for k, v in r.items() if k != "records"}
                                         for r in results],
                          "unique_contribution": unique,
                          "merged": merged}, indent=2, ensure_ascii=False))
        return 0

    print(f"query: {args.query}\n")
    for r in results:
        if r.get("error"):
            print(f"  {r['source']:<11} UNAVAILABLE — {str(r['error'])[:80]}")
        else:
            note = f"   ({r['note']})" if r.get("note") else ""
            print(f"  {r['source']:<11} {r['hits']:>9,} hits, "
                  f"{len(r['records'])} fetched{note}")
    print(f"\n  merged: {len(merged)} unique record(s)")
    pre = sum(1 for r in merged if r.get("preprint_of"))
    if pre:
        print(f"  {pre} preprint/published pair(s) collapsed")
    if unique:
        print("  in only one source's top-N: " +
              ", ".join(f"{k} {v}" for k, v in sorted(unique.items())))
        print("  (ranking overlap, NOT database coverage — do not quote as "
              "\"contributed N unique studies\")")
    print()
    for r in merged[:20]:
        ids = r.get("doi") or (f"PMID {r['pmid']}" if r.get("pmid") else "no id")
        oa = " [OA]" if r.get("open_access") else ""
        also = f"  +{','.join(sorted(set(r['also_in'])))}" if r.get("also_in") else ""
        print(f"  {r['year']}  {r['title'][:66]}{oa}")
        print(f"        {r['journal'][:50]}  {ids}{also}")
    if len(merged) > 20:
        print(f"  … and {len(merged) - 20} more (use --json)")
    if args.log:
        print(f"\n  logged into search_log for '{args.slug}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
