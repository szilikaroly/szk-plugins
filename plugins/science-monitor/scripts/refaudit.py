#!/usr/bin/env python3
"""Check a manuscript's reference list against Crossref and Europe PMC.

Reference lists written from recall are the reliable way to get a manuscript
embarrassed in review. This resolves every DOI and compares the first author
and the year against what the registries hold.

Two things learned the hard way and encoded here:

* **Crossref is not authoritative for author lists.** Some publishers deposit
  only one author — Front Biosci deposits the *last* one — so a Crossref-only
  check reports a false mismatch. Anything Crossref flags is re-checked against
  Europe PMC before it is called an error.
* **Surname prefixes break naive matching.** `van der Zanden`, `De Graaff` and
  `van Kolfschooten` are one surname, not a first token. So the manuscript
  entry is matched against the whole family name — but the match must end at a
  word boundary. Plain `startswith` silently accepts `Sachedina` for a
  registered `Sachedin`, which is exactly the kind of one-letter error this is
  supposed to catch.
"""

import json
import os
import re
import sys
import urllib.parse
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm_lib as L  # noqa: E402

# Crossref rate-limits anonymous traffic hard. A contact address puts the
# requests in the polite pool, and 429 still has to be honoured with a wait.
def _ua():
    mail = L.load_config().get("mail_address", "")
    contact = f"mailto:{mail}" if mail else "https://github.com/szilikaroly/szk-plugins"
    return f"science-monitor/1.0 ({contact})"


UA = _ua()
MAX_WORKERS = 3
REF_HEADS = ("## References", "# References", "## Irodalom", "## Hivatkozások")


def fetch(url, attempts=4):
    delay = 2.0
    last = None
    for _ in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            wait = exc.headers.get("Retry-After")
            time.sleep(float(wait) if wait and wait.isdigit() else delay)
            delay *= 2
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(delay); delay *= 2
    raise last


def crossref(doi):
    try:
        return fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
    except Exception as exc:
        return {"__error__": f"{type(exc).__name__}: {getattr(exc, 'code', exc)}"}


def europepmc(doi):
    q = urllib.parse.quote(f'DOI:"{doi}"')
    try:
        res = fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
                    f"?query={q}&resultType=core&format=json&pageSize=1")
        hits = res.get("resultList", {}).get("result", [])
        return hits[0] if hits else {}
    except Exception:
        return {}


def parse_refs(text):
    """Numbered Vancouver entries ending in a DOI."""
    tail = text
    for head in REF_HEADS:
        if head in text:
            tail = text.split(head)[-1]
            break
    out = []
    for m in re.finditer(r"^\s*(\d+)\.\s+(.+?)\s+doi:\s*(10\.\S+?)\s*$", tail, re.M):
        body, doi = m.group(2), m.group(3).rstrip(".")
        year = re.search(r"\((\d{4})\)", body)
        out.append({"n": int(m.group(1)), "raw": body, "doi": doi,
                    "year": int(year.group(1)) if year else None})
    return out


def edit_distance(a, b, cap=3):
    """Levenshtein, cheap and capped — we only care about 'nearly the same'."""
    a, b = a.lower(), b.lower()
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def near_identical(a, b, cap=2):
    """A one- or two-character difference — a typo, or a legitimate variant.

    These are the cases nobody may decide alone. `Sachedina` vs `Sachedin` reads
    like an obvious typo and is not one: MEDLINE and the publisher's deposit
    genuinely disagree. Correcting it on a hunch turned a right name wrong.
    """
    a, b = a.strip(), b.strip()
    if not a or not b or a.lower() == b.lower():
        return False
    return edit_distance(a, b, cap) <= cap


def surname_matches(written, family):
    """Does `written` ("Sachedin A") carry exactly the surname `family`?

    The family name may contain spaces, so the comparison is on the prefix —
    but it has to end on a word boundary, or a longer surname passes for a
    shorter registered one.
    """
    w, f = written.strip().lower(), family.strip().lower()
    if not f or not w.startswith(f):
        return False
    rest = w[len(f):]
    return rest == "" or not rest[0].isalpha()


def reg_year(meta):
    for key in ("published-print", "published-online", "issued"):
        parts = meta.get(key, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0]:
            return parts[0][0]
    return None


def crossref_dates(meta):
    """The dates a year disagreement actually turns on, spelled out."""
    out = {}
    for key in ("published-print", "published-online", "issued"):
        parts = meta.get(key, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0]:
            out[key] = "-".join(f"{x:02d}" if i else str(x)
                                for i, x in enumerate(parts[0]))
    return out


def check(ref):
    cr = crossref(ref["doi"])
    if "__error__" in cr:
        return ref, "DOI nem oldható fel", cr["__error__"], "error"

    problems = []
    severity = "error"
    epmc = None  # fetched at most once, lazily

    year = reg_year(cr)
    if ref["year"] and year and ref["year"] != year:
        epmc = europepmc(ref["doi"])
        med = epmc.get("pubYear")
        med = int(med) if str(med).isdigit() else None
        dates = crossref_dates(cr)
        shown = ", ".join(f"{k.replace('published-', '')}: {v}"
                          for k, v in dates.items() if k != "issued")
        if med and med == ref["year"]:
            # Frontiers and friends assign an article to a volume year and put
            # it online in January of the next one. MEDLINE indexes the volume
            # year, and a Vancouver list follows the journal's own year.
            problems.append(
                f"évszám: kéziratban {ref['year']} (= Europe PMC/MEDLINE pubYear), "
                f"Crossref {year} — {shown}. A kötet éve és a tényleges megjelenés "
                f"tér el, nem hiba; a MEDLINE-évet tartsd meg")
            severity = "note"
        elif abs(ref["year"] - year) > 1:
            problems.append(f"év {ref['year']} vs {year} ({shown})")
        else:
            problems.append(
                f"EGY ÉV ELTÉRÉS: kéziratban {ref['year']}, Crossref {year}"
                + (f", MEDLINE {med}" if med else ", MEDLINE nem ismeri")
                + f" — {shown}. Leadás/kötet vs tényleges megjelenés; kérdezz rá")
            severity = "ask"

    authors = cr.get("author") or []
    family = (authors[0].get("family", "") if authors else "").strip()
    # The manuscript's first author is whatever precedes the first comma.
    written = ref["raw"].split(",")[0].strip()
    if family and not surname_matches(written, family):
        # Crossref may hold a partial or differently-spelled author list;
        # Europe PMC (MEDLINE) is the authority a Vancouver list is checked on.
        if epmc is None:
            epmc = europepmc(ref["doi"])
        astr = (epmc.get("authorString") or "").strip()
        if astr:
            first = astr.split(",")[0].strip()
            # Europe PMC gives "Surname AB"; compare on everything but initials.
            fam = " ".join(first.split()[:-1]) or first
            written_fam = " ".join(written.split()[:-1]) or written
            if not surname_matches(written, fam):
                if near_identical(written_fam, fam):
                    problems.append(
                        f"EGY-KÉT KARAKTER ELTÉRÉS: kéziratban '{written_fam}', "
                        f"Europe PMC/MEDLINE '{fam}' — el kell dönteni, "
                        f"magadtól ne írd át")
                    severity = "ask"
                else:
                    problems.append(f"első szerző '{written}' vs '{first}' (Europe PMC)")
            else:
                # The manuscript agrees with MEDLINE and Crossref differs — that
                # is a registry disagreement, not a manuscript error. Worth
                # seeing, never worth "fixing" against MEDLINE.
                if near_identical(family, fam):
                    problems.append(
                        f"EGY-KÉT KARAKTER ELTÉRÉS a regiszterek közt: Crossref "
                        f"'{family}' vs Europe PMC/MEDLINE '{fam}'. A kézirat a "
                        f"MEDLINE-nal egyezik. Elgépelésnek látszik, de nem az — "
                        f"kérdezz rá, magadtól ne írd át")
                    severity = "ask"
                else:
                    problems.append(
                        f"regiszter-eltérés: Crossref '{family}' vs Europe PMC/MEDLINE "
                        f"'{fam}' — a kézirat a MEDLINE-nal egyezik, NE írd át")
                    severity = "note"
        else:
            problems.append(f"első szerző '{written}' vs '{family}' (csak Crossref, "
                            "Europe PMC nem ismeri — ellenőrizd kézzel)")
            severity = "note"

    if not problems:
        return None
    return ref, " · ".join(problems), (cr.get("title") or [""])[0][:70], severity


def run(conn, ref_arg, path=None, limit=None):
    if path:
        paths = [os.path.abspath(os.path.expanduser(path))]
        title = os.path.basename(paths[0])
    else:
        p = L.get_project(conn, ref_arg)
        title = p["title"][:60]
        paths = [f["path"] for f in L.files_of(conn, p["id"], "manuscript")
                 if f["path"].lower().endswith((".md", ".txt", ".tex"))]
        if not paths:
            L.die("nincs szöveges kézirat-fájl (md/txt/tex) — adj meg egyet a --file "
                  "kapcsolóval, vagy konvertáld doc-tools-szal")

    for src in paths:
        if not os.path.exists(src):
            continue
        refs = parse_refs(open(src, encoding="utf-8", errors="ignore").read())
        if not refs:
            print(f"{os.path.basename(src)}: nem találtam DOI-val záruló hivatkozásjegyzéket")
            continue
        if limit:
            refs = refs[:limit]
        print(f"\n{title}\n{os.path.basename(src)} — {len(refs)} hivatkozás DOI-val")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            results = [r for r in ex.map(check, refs) if r]
        errs = [r for r in results if r[3] == "error"]
        asks = [r for r in results if r[3] == "ask"]
        notes = [r for r in results if r[3] == "note"]
        print(f"  ✓ rendben: {len(refs) - len(results)}   ✗ hiba: {len(errs)}"
              f"   ? döntést kér: {len(asks)}   · megjegyzés: {len(notes)}")
        icon = {"error": "✗", "ask": "?", "note": "·"}
        for ref, why, extra, sev in errs + asks + notes:
            print(f"\n  {icon[sev]} [{ref['n']:>3}] {why}")
            print(f"        kéziratban: {ref['raw'][:100]}")
            if extra:
                print(f"        regiszter : {extra}")
        if not errs and not asks:
            print("\n  Hiba nincs: minden DOI feloldódik, első szerző és évszám egyezik.")
        if asks:
            print(f"\n  ⚠ {len(asks)} tétel EGY-KÉT KARAKTERBEN tér el. Ezeket nem "
                  "szabad magadtól átírni — egy elgépelésnek látszó eltérés lehet a\n"
                  "    regiszterek közti valódi különbség. Kérdezd meg a szerzőt, "
                  "tételenként, a két változatot egymás mellé téve.")
