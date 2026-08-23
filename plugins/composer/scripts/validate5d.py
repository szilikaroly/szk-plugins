#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5D bibliographic validation — Crossref against PubMed, one verdict per record.

    validate5d.py --records records.csv --out validation.csv
    validate5d.py --doi 10.3390/nu16172885 --pmid 39275201
    validate5d.py --records records.csv --out validation.csv --offline   # cache only

The five dimensions
-------------------
D1 doi          the DOI exists, is syntactically valid, and Crossref returns
                THAT DOI (not a redirect to another work)
D2 elso_szerzo  first-author surname agrees between the two authorities
D3 szerzok      the author list agrees — same head surnames, same length or a
                clean "et al." truncation of the longer one
D4 folyoirat    journal title agrees (full title, ISO abbreviation or ISSN)
D5 kotet        volume agrees; for article-number journals the e-locator is
                compared instead, and that substitution is reported, not hidden

A record is ADMITTED only when all five are `ok` AND its full text is on disk.
Anything else is quarantined with the reason attached. That is the whole point:
a reference that cannot be checked is not the same as a reference that checks
out, and a corpus that mixes them cannot be cited.

Why the comparison is this fussy
--------------------------------
Each normalisation below exists because its absence produced a FALSE POSITIVE on
a real reference list, not because it seemed tidy:

  * "et al." truncation — a 40-author paper printed with 6 surnames is correct;
    compare only the printed head against the canonical head.
  * particle and accented surnames — van, De, Di, von, Núñez-Cortés, Thøgersen.
    ASCII-fold, strip leading nobiliary particles, compare the last token too.
  * ARTICLE-NUMBER JOURNALS (MDPI, BMC, Frontiers, Scientific Reports): PubMed
    esummary leaves `pages` empty and often carries no volume the way Crossref
    does, while Crossref carries the e-locator in `article-number`. Comparing
    `volume` blindly flags every MDPI paper in the corpus as a mismatch.
  * Crossref `container-title` is a list, sometimes with the abbreviation as a
    second entry; PubMed gives the full title and the ISO abbreviation in
    different fields. Any-to-any match, not field-to-field.

Stdlib only, so it runs anywhere and offline against its cache.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DIMENSIONS = ("doi", "elso_szerzo", "szerzok", "folyoirat", "kotet")

CROSSREF = "https://api.crossref.org/works/"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "composer-validate5d/1.0 (https://orcid.org/0000-0001-9803-9103; mailto:{mail})"

#: Leading name particles that some authorities keep and others drop.
PARTICLES = {
    "van", "von", "de", "del", "della", "der", "den", "di", "da", "dos", "das",
    "du", "la", "le", "el", "al", "bin", "ibn", "st", "ter", "ten", "op", "af",
}

_WS = re.compile(r"\s+")
_NONALNUM = re.compile(r"[^a-z0-9 ]+")
_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:a-z0-9<>\[\]+]+$", re.I)


# --------------------------------------------------------------------------- text


def fold(text: str) -> str:
    """ASCII-fold, lowercase, strip punctuation. Thøgersen -> thogersen."""
    if not text:
        return ""
    text = text.replace("ø", "o").replace("Ø", "O").replace("ß", "ss")
    text = text.replace("ð", "d").replace("þ", "th").replace("đ", "d").replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _NONALNUM.sub(" ", text)
    return _WS.sub(" ", text).strip()


def surname_key(name: str) -> str:
    """A surname reduced to what two authorities can be expected to agree on.

    'van der Meer' -> 'meer' plus the joined form, so either convention matches.
    """
    folded = fold(name)
    if not folded:
        return ""
    tokens = [t for t in folded.split() if t]
    while len(tokens) > 1 and tokens[0] in PARTICLES:
        tokens.pop(0)
    return "".join(tokens)


def surnames_match(a: str, b: str) -> bool:
    ka, kb = surname_key(a), surname_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    # Hyphenated vs. spaced compounds, and last-token fallback for the cases
    # where one authority kept the particle inside the family name.
    la, lb = fold(a).split(), fold(b).split()
    if la and lb and la[-1] == lb[-1]:
        return True
    return ka.startswith(kb) or kb.startswith(ka)


def journal_key(title: str) -> str:
    """Normalise a journal title so 'Br. J. Nutr.' can meet 'British Journal of Nutrition'.

    Only the reductions that are safe both ways: punctuation, articles and the
    handful of words that carry no discriminating power.
    """
    t = fold(title)
    drop = {"the", "of", "and", "for", "a", "an", "journal", "j", "review", "reviews"}
    tokens = [w for w in t.split() if w not in drop]
    return " ".join(tokens)


def journals_match(pubmed_titles: list[str], crossref_titles: list[str]) -> bool:
    """Any-to-any. Crossref container-title is a list; PubMed has title + ISO abbrev."""
    pk = {journal_key(t) for t in pubmed_titles if t}
    ck = {journal_key(t) for t in crossref_titles if t}
    pk.discard("")
    ck.discard("")
    if not pk or not ck:
        return False
    if pk & ck:
        return True
    # Abbreviation containment: 'br nutr' inside 'british nutrition'.
    for p in pk:
        for c in ck:
            short, long_ = sorted((p, c), key=len)
            if short and all(
                any(w.startswith(s) for w in long_.split()) for s in short.split()
            ):
                return True
    return False


def norm_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
    return doi.strip().rstrip(".").lower()


# --------------------------------------------------------------------------- fetch


class Fetcher:
    """Cached HTTP with a fixed inter-request gap. Crossref's polite pool wants
    a mailto; NCBI wants a tool and email. Both are set from --email."""

    def __init__(self, cache: Path | None, email: str, gap: float = 0.2,
                 offline: bool = False, timeout: int = 20):
        self.path = cache
        self.email = email or "anonymous@example.org"
        self.gap = gap
        self.offline = offline
        self.timeout = timeout
        self._last = 0.0
        self.store: dict = {}
        self.hits = 0
        self.misses = 0
        if cache and cache.exists():
            try:
                self.store = json.loads(cache.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.store = {}

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.store, ensure_ascii=False, indent=1),
                                 encoding="utf-8")

    def get_json(self, url: str) -> dict | None:
        if url in self.store:
            self.hits += 1
            return self.store[url]
        if self.offline:
            return None
        self.misses += 1
        wait = self.gap - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": UA.format(mail=self.email),
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            data = {"__error__": f"HTTP {exc.code}"}
        except Exception as exc:  # network, JSON, timeout
            # Not cached: a transient failure must not become a permanent verdict.
            self._last = time.monotonic()
            return {"__error__": str(exc)[:120], "__transient__": True}
        self._last = time.monotonic()
        self.store[url] = data
        return data


def crossref_record(doi: str, fetcher: Fetcher) -> dict | None:
    if not doi:
        return None
    url = CROSSREF + urllib.parse.quote(doi, safe="")
    data = fetcher.get_json(url)
    if not data or "__error__" in data:
        return data if data and "__error__" in data else None
    return data.get("message")


def pmid_from_doi(doi: str, fetcher: Fetcher) -> str:
    """DOI -> PMID via esearch's [AID] field.

    Without this, a bare DOI has only one authority behind it and every
    dimension comes back `missing` — technically honest, practically useless.
    The whole design is two authorities disagreeing or agreeing; this is how the
    second one is found when the caller supplied only a DOI.
    """
    if not doi:
        return ""
    q = urllib.parse.urlencode({
        "db": "pubmed", "term": f"{doi}[AID]", "retmode": "json", "retmax": "2",
        "tool": "composer-validate5d", "email": fetcher.email,
    })
    data = fetcher.get_json(f"{ESEARCH}?{q}")
    if not data or "__error__" in data:
        return ""
    ids = ((data.get("esearchresult") or {}).get("idlist") or [])
    # Two hits mean the DOI is ambiguous in PubMed (duplicate deposit); refuse
    # rather than pick one, or the "verification" verifies against a coin flip.
    return ids[0] if len(ids) == 1 else ""


def pubmed_summary(pmid: str, fetcher: Fetcher) -> dict | None:
    if not pmid:
        return None
    q = urllib.parse.urlencode({
        "db": "pubmed", "id": pmid, "retmode": "json",
        "tool": "composer-validate5d", "email": fetcher.email,
    })
    data = fetcher.get_json(f"{EUTILS}?{q}")
    if not data or "__error__" in data:
        return None
    return (data.get("result") or {}).get(str(pmid))


# --------------------------------------------------------------------------- extract


def europepmc_record(doi: str, pmid: str, fetcher: Fetcher) -> dict | None:
    """The third authority, consulted only to fill what the first two left blank.

    Crossref is authoritative for the DOI and excellent for journal metadata, but
    it carries no author list for many book-series chapters and no volume for a
    number of society journals. PubMed is authoritative for the biomedical record
    but leaves `pages` empty on article-number journals. Europe PMC indexes both
    and fills exactly those two holes. It is a tie-breaker, never an override: a
    dimension already judged `ok` or `mismatch` is not revisited.
    """
    if not (doi or pmid):
        return None
    term = f'DOI:"{doi}"' if doi else f"EXT_ID:{pmid} AND SRC:MED"
    q = urllib.parse.urlencode({
        "query": term, "resultType": "core", "format": "json", "pageSize": "2",
    })
    data = fetcher.get_json(f"{EPMC}?{q}")
    if not data or "__error__" in data:
        return None
    hits = ((data.get("resultList") or {}).get("result") or [])
    # Same rule as the PMID lookup: an ambiguous hit is no hit.
    return hits[0] if len(hits) == 1 else None


def from_europepmc(rec: dict) -> dict:
    authors = [
        (a.get("lastName") or a.get("collectiveName") or "").strip()
        for a in ((rec.get("authorList") or {}).get("author") or [])
        if (a.get("lastName") or a.get("collectiveName"))
    ]
    ji = rec.get("journalInfo") or {}
    j = ji.get("journal") or {}
    titles = [j.get("title", ""), j.get("isoabbreviation", ""), j.get("medlineAbbreviation", "")]
    return {
        "doi": norm_doi(rec.get("doi", "")),
        "elso_szerzo": authors[0] if authors else "",
        "szerzok": authors,
        "folyoirat": [t for t in titles if t],
        "kotet": str(ji.get("volume", "") or "").strip(),
        "elocator": str(rec.get("pageInfo", "") or "").strip(),
        "issn": [s for s in (j.get("issn", ""), j.get("essn", "")) if s],
        "ev": str(ji.get("yearOfPublication", "") or ""),
        "cim": rec.get("title", ""),
    }


def merge_canonical(primary: dict, extra: dict) -> dict:
    """Fill only the blanks in `primary`; list fields are unioned, never replaced."""
    out = dict(primary)
    for key in ("doi", "elso_szerzo", "kotet", "elocator", "ev", "cim"):
        if not out.get(key) and extra.get(key):
            out[key] = extra[key]
    for key in ("szerzok", "issn"):
        if not out.get(key) and extra.get(key):
            out[key] = extra[key]
    seen = list(out.get("folyoirat") or [])
    for t in extra.get("folyoirat") or []:
        if t and t not in seen:
            seen.append(t)
    out["folyoirat"] = seen
    return out


def from_crossref(msg: dict) -> dict:
    authors = [
        (a.get("family") or a.get("name") or "").strip()
        for a in (msg.get("author") or [])
        if (a.get("family") or a.get("name"))
    ]
    titles = list(msg.get("container-title") or []) + list(msg.get("short-container-title") or [])
    return {
        "doi": norm_doi(msg.get("DOI", "")),
        "elso_szerzo": authors[0] if authors else "",
        "szerzok": authors,
        "folyoirat": titles,
        "kotet": (msg.get("volume") or "").strip(),
        "elocator": (msg.get("article-number") or msg.get("page") or "").strip(),
        "issn": [s for s in (msg.get("ISSN") or []) if s],
        "ev": _cr_year(msg),
        "cim": (msg.get("title") or [""])[0],
    }


def _cr_year(msg: dict) -> str:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = ((msg.get(key) or {}).get("date-parts") or [[]])[0]
        if parts:
            return str(parts[0])
    return ""


def from_pubmed_summary(rec: dict) -> dict:
    authors = [a.get("name", "").split()[0] for a in (rec.get("authors") or [])
               if a.get("authtype") == "Author" and a.get("name")]
    ids = {i.get("idtype"): str(i.get("value", "")) for i in (rec.get("articleids") or [])}
    return {
        "doi": norm_doi(ids.get("doi", "")),
        "elso_szerzo": authors[0] if authors else "",
        "szerzok": authors,
        "folyoirat": [rec.get("fulljournalname", ""), rec.get("source", "")],
        "kotet": str(rec.get("volume", "")).strip(),
        # esummary leaves `pages` empty for article-number journals; this is the
        # documented trap, so the emptiness is data, not an error.
        "elocator": str(rec.get("pages", "")).strip(),
        "issn": [s for s in (rec.get("issn", ""), rec.get("essn", "")) if s],
        "ev": str(rec.get("pubdate", ""))[:4],
        "cim": rec.get("title", ""),
    }


def from_row(row: dict) -> dict:
    """A harvest CSV row -> the same shape. Column names are the collector's."""
    raw = (row.get("szerzok") or "").strip()
    authors = [a.strip() for a in re.split(r"[;|]", raw) if a.strip()] if raw else []
    return {
        "doi": norm_doi(row.get("doi", "")),
        "elso_szerzo": (row.get("elso_szerzo") or (authors[0] if authors else "")).strip(),
        "szerzok": authors,
        "folyoirat": [row.get("folyoirat", ""), row.get("folyoirat_rovid", "")],
        "kotet": (row.get("kotet") or "").strip(),
        "elocator": (row.get("oldalak") or "").strip(),
        "issn": [s for s in (row.get("issn", ""),) if s],
        "ev": (row.get("ev") or row.get("publikacio_datuma", ""))[:4],
        "cim": row.get("cim", ""),
    }


# --------------------------------------------------------------------------- compare


def compare(local: dict, canon: dict) -> dict[str, tuple[str, str]]:
    """{dimension: (verdict, note)} where verdict is ok | mismatch | missing."""
    out: dict[str, tuple[str, str]] = {}

    # D1 DOI --------------------------------------------------------------
    ldoi, cdoi = local.get("doi", ""), canon.get("doi", "")
    if not ldoi:
        out["doi"] = ("missing", "a rekordban nincs DOI")
    elif not _DOI_RE.match(ldoi):
        out["doi"] = ("mismatch", f"szintaktikailag érvénytelen DOI: {ldoi}")
    elif not cdoi:
        out["doi"] = ("missing", "a Crossref nem adott vissza DOI-t")
    elif ldoi != cdoi:
        out["doi"] = ("mismatch", f"{ldoi} -> a Crossref {cdoi}-t adta vissza")
    else:
        out["doi"] = ("ok", ldoi)

    # D2 first author -----------------------------------------------------
    lf, cf = local.get("elso_szerzo", ""), canon.get("elso_szerzo", "")
    if not lf or not cf:
        out["elso_szerzo"] = ("missing", f"helyi='{lf}' kanonikus='{cf}'")
    elif surnames_match(lf, cf):
        out["elso_szerzo"] = ("ok", cf)
    else:
        out["elso_szerzo"] = ("mismatch", f"'{lf}' vs '{cf}'")

    # D3 author list ------------------------------------------------------
    la, ca = local.get("szerzok") or [], canon.get("szerzok") or []
    if not la or not ca:
        out["szerzok"] = ("missing", f"{len(la)} vs {len(ca)} szerző")
    else:
        # "et al." truncation: compare only the shorter, printed head.
        n = min(len(la), len(ca))
        bad = [i for i in range(n) if not surnames_match(la[i], ca[i])]
        if bad:
            i = bad[0]
            out["szerzok"] = ("mismatch",
                              f"{i + 1}. szerző: '{la[i]}' vs '{ca[i]}'"
                              + (f" (+{len(bad) - 1} további)" if len(bad) > 1 else ""))
        elif len(la) == len(ca):
            out["szerzok"] = ("ok", f"{len(ca)} szerző, sorrend egyezik")
        else:
            out["szerzok"] = ("ok", f"{n} egyező fej, csonkolt lista ({len(la)}/{len(ca)})")

    # D4 journal ----------------------------------------------------------
    lj = [t for t in (local.get("folyoirat") or []) if t]
    cj = [t for t in (canon.get("folyoirat") or []) if t]
    lissn = {s.replace("-", "").upper() for s in (local.get("issn") or []) if s}
    cissn = {s.replace("-", "").upper() for s in (canon.get("issn") or []) if s}
    if not lj or not cj:
        out["folyoirat"] = ("missing", f"helyi={lj} kanonikus={cj}")
    elif journals_match(lj, cj):
        out["folyoirat"] = ("ok", cj[0])
    elif lissn & cissn:
        out["folyoirat"] = ("ok", f"cím eltér, de az ISSN egyezik ({sorted(lissn & cissn)[0]})")
    else:
        out["folyoirat"] = ("mismatch", f"'{lj[0]}' vs '{cj[0]}'")

    # D5 volume -----------------------------------------------------------
    lv, cv = local.get("kotet", ""), canon.get("kotet", "")
    lv_n, cv_n = fold(lv), fold(cv)
    if lv_n and cv_n:
        out["kotet"] = ("ok", cv) if lv_n == cv_n else ("mismatch", f"'{lv}' vs '{cv}'")
    else:
        # Article-number journals: no volume on one side is normal, not an error.
        # Fall back to the e-locator, and SAY that the substitution happened.
        le, ce = fold(local.get("elocator", "")), fold(canon.get("elocator", ""))
        if le and ce and le == ce:
            out["kotet"] = ("ok", f"kötet helyett cikkszám egyezik ({canon.get('elocator')})")
        elif le and ce:
            out["kotet"] = ("mismatch",
                            f"kötet hiányzik, a cikkszám is eltér: "
                            f"'{local.get('elocator')}' vs '{canon.get('elocator')}'")
        else:
            out["kotet"] = ("missing", f"kötet: '{lv}' vs '{cv}'; cikkszám sincs mindkét oldalon")
    return out


#: A mismatch on these means the record describes a DIFFERENT WORK — reject.
IDENTITY = ("doi", "elso_szerzo", "szerzok")
#: A mismatch on these means the same work is LABELLED differently — flag, don't reject.
LABEL = ("folyoirat", "kotet")


def verdict_of(dims: dict[str, tuple[str, str]],
               has_fulltext: bool | None) -> tuple[str, str, dict[str, tuple[str, str]]]:
    """The gate, plus the one distinction that keeps it usable.

    Rejecting on a journal-title mismatch sounds rigorous and is wrong. Two real
    cases from the first 25-record run: *Biopolymers* was renamed *Peptide
    Science* (new ISSN, same DOI, same authors, same volume), and *Bratislavske
    lekarske listy* is indexed by PubMed under its Slovak title and by Crossref
    under its English one. Neither reference is fabricated; both would have been
    thrown out. So when the DOI and both author dimensions agree, the work is
    already identified beyond doubt and a differing label is a VARIANT — held
    back with the discrepancy named, not discarded.

    Full text is a separate, equally hard condition: 5/5 with nothing on disk is
    still not admitted, because the corpus promises readable papers.
    """
    dims = dict(dims)
    id_fail = [d for d in IDENTITY if dims[d][0] == "mismatch"]
    if id_fail:
        return "elutasitva", "azonosság-eltérés: " + ", ".join(id_fail), dims

    id_ok = all(dims[d][0] == "ok" for d in IDENTITY)
    label_fail = [d for d in LABEL if dims[d][0] == "mismatch"]
    if label_fail and id_ok:
        for d in label_fail:
            dims[d] = ("variant", dims[d][1] + " — a DOI és a szerzők egyeznek, "
                                               "tehát ugyanaz a mű, más néven/adattal")
        return ("fuggoben",
                "azonosítva, de eltérő megnevezés: " + ", ".join(label_fail), dims)
    if label_fail:
        return "elutasitva", "eltérés: " + ", ".join(label_fail), dims

    gaps = [d for d in DIMENSIONS if dims[d][0] == "missing"]
    if gaps:
        return "fuggoben", "nem ellenőrizhető: " + ", ".join(gaps), dims
    if has_fulltext is False:
        return "fuggoben", "5D rendben, de nincs letöltött teljes szöveg", dims
    suffix = "" if has_fulltext is None else " + teljes szöveg"
    return "befogadva", "5/5 dimenzió egyezik" + suffix, dims


# --------------------------------------------------------------------------- run


def validate_row(row: dict, fetcher: Fetcher, require_fulltext: bool,
                 use_epmc: bool = True) -> dict:
    local = from_row(row)
    canon: dict = {}
    source = ""
    err = ""

    doi = local["doi"]
    if doi:
        msg = crossref_record(doi, fetcher)
        if isinstance(msg, dict) and "__error__" in msg:
            err = f"Crossref: {msg['__error__']}"
        elif msg:
            canon = from_crossref(msg)
            source = "Crossref"

    # PubMed fills the gaps in the LOCAL record (a harvest CSV may lack volume),
    # and stands in as the authority when the work has no DOI at all.
    pmid = str(row.get("pmid", "")).strip()
    if not pmid and doi:
        pmid = pmid_from_doi(doi, fetcher)
    if pmid:
        summ = pubmed_summary(pmid, fetcher)
        if summ:
            pm = from_pubmed_summary(summ)
            for key in ("elso_szerzo", "kotet", "elocator", "doi", "cim"):
                if not local.get(key):
                    local[key] = pm[key]
            for key in ("szerzok", "issn"):
                if not local.get(key):
                    local[key] = pm[key]
            local["folyoirat"] = [t for t in (local.get("folyoirat") or []) + pm["folyoirat"] if t]
            if not canon:
                canon, source = pm, "PubMed"

    if not canon:
        dims = {d: ("missing", err or "nincs elérhető hitelesítő forrás") for d in DIMENSIONS}
    else:
        dims = compare(local, canon)

    # Escalate to the third authority whenever anything is unsettled — a gap OR
    # a disagreement. Two authorities can only tell you THAT they differ; three
    # can tell you which one is wrong.
    #
    # This is not hypothetical. Crossref's deposit for
    # 10.1186/s12916-024-03503-y carries 18 authors because four consortium
    # members' GIVEN names ("Mait", "Andres", "Lili", "Tõnu") were deposited as
    # family names. PubMed and Europe PMC both have the correct 14. Rejecting on
    # a two-way disagreement threw out a real, correctly-recorded paper on the
    # strength of a publisher's malformed metadata.
    notes: list[str] = []
    unsettled = [d for d in DIMENSIONS if dims[d][0] in ("missing", "mismatch")]
    if unsettled and use_epmc:
        rec = europepmc_record(local["doi"], pmid, fetcher)
        if rec:
            third = from_europepmc(rec)
            # (a) independent comparison — settles disagreements by majority
            solo = compare(local, third)
            # (b) merged canonical — settles gaps by filling them
            merged = merge_canonical(canon, third) if canon else third
            filled = compare(local, merged)
            for d in unsettled:
                if dims[d][0] == "mismatch" and solo[d][0] == "ok":
                    dims[d] = ("ok", f"{solo[d][1]} — Europa PMC és a rekord egyezik, "
                                     f"a Crossref eltér ({dims[d][1]}); "
                                     f"Crossref-oldali adathiba")
                    notes.append(f"{d}: Crossref-adathiba gyanú")
                elif dims[d][0] == "missing" and filled[d][0] != "missing":
                    dims[d] = (filled[d][0], filled[d][1] + " [Europa PMC]")
                elif dims[d][0] == "mismatch" and solo[d][0] == "mismatch":
                    notes.append(f"{d}: mindkét hitelesítő eltér")
            canon = merged
            source = (source + "+EuropePMC") if source else "EuropePMC"

    ft = None
    if require_fulltext:
        f = (row.get("fajl") or "").strip()
        ft = bool(f) and Path(f).expanduser().exists()

    state, why, dims = verdict_of(dims, ft)
    out = {
        "pmid": pmid,
        "doi": local["doi"],
        "cim": (row.get("cim") or local.get("cim", ""))[:180],
        "hitelesito": source or "-",
        "allapot": state,
        "indok": why + (f" [{err}]" if err else ""),
        "teljes_szoveg": "" if ft is None else ("van" if ft else "nincs"),
        "megjegyzes": "; ".join(notes),
    }
    for d in DIMENSIONS:
        out[f"d_{d}"] = dims[d][0]
        out[f"n_{d}"] = dims[d][1]
    return out


def read_records(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", type=Path, help="harvest CSV to validate")
    ap.add_argument("--out", type=Path, help="validation CSV to write")
    ap.add_argument("--doi", help="validate a single DOI instead")
    ap.add_argument("--pmid", default="", help="PMID for the single-record mode")
    ap.add_argument("--cache", type=Path, help="JSON cache (re-runs go offline)")
    ap.add_argument("--email", default="", help="contact address for the polite pools")
    ap.add_argument("--offline", action="store_true", help="cache only, no network")
    ap.add_argument("--no-fulltext-gate", action="store_true",
                    help="judge the 5 dimensions only; do not require a downloaded file")
    ap.add_argument("--no-europepmc", action="store_true",
                    help="skip the Europe PMC tie-breaker (two authorities only)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    email = args.email or _email_from_env()
    fetcher = Fetcher(args.cache, email, offline=args.offline)

    if args.doi:
        rows = [{"doi": args.doi, "pmid": args.pmid}]
    elif args.records:
        if not args.records.exists():
            sys.exit(f"nincs ilyen fájl: {args.records}")
        rows = read_records(args.records)
    else:
        ap.print_help()
        return 0

    results = []
    for i, row in enumerate(rows, 1):
        res = validate_row(row, fetcher, require_fulltext=not args.no_fulltext_gate,
                           use_epmc=not args.no_europepmc)
        results.append(res)
        if not args.quiet:
            mark = {"befogadva": "+", "elutasitva": "!", "fuggoben": "?"}[res["allapot"]]
            print(f"  {mark} [{i}/{len(rows)}] {res['allapot']:<11} "
                  f"{res['doi'] or res['pmid'] or '-':<34} {res['indok']}")
    fetcher.save()

    if args.out and results:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"\nValidációs riport: {args.out}")

    counts = {s: sum(1 for r in results if r["allapot"] == s)
              for s in ("befogadva", "fuggoben", "elutasitva")}
    print(f"\n5D eredmény: befogadva {counts['befogadva']} · "
          f"függőben {counts['fuggoben']} · elutasítva {counts['elutasitva']}"
          f"   (cache {fetcher.hits} találat / {fetcher.misses} lekérés)")
    # Non-zero only when something actually failed its check, so a harvest with
    # unverifiable-but-not-wrong records does not break a pipeline.
    return 1 if counts["elutasitva"] else 0


def _email_from_env() -> str:
    import os
    env = os.environ.get("NCBI_EMAIL", "")
    if env:
        return env
    cfg = Path.home() / ".config" / "ncbi" / "env"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*(?:export\s+)?NCBI_EMAIL\s*=\s*"?([^"\n]+)"?', line)
            if m:
                return m.group(1).strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
