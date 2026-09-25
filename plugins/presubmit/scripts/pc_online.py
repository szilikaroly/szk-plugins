"""Opt-in online reference checks: has a cited paper been corrected or retracted?

Presubmit is offline and deterministic by default, and stays that way — nothing
in here runs unless the caller passes --online. When it does run it asks PubMed
one question per batch of references: does this PMID carry an erratum, a
retraction, or an expression of concern?

Every failure is soft. No network, a timeout, a rate limit or a malformed
response yields a single INFO finding saying the check could not run, never a
false "clean" and never a traceback.

Why this matters: a correction notice is invisible in the PDF you downloaded.
It can be a bare affiliation fix, or it can be the number you quoted.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "presubmit"
TIMEOUT = 12

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>,;)\]]+", re.I)
PMID_RE = re.compile(r"\bPMID:?\s*(\d{6,9})\b", re.I)

# What we look for in the efetch XML.
FLAGS = {
    "ErratumIn": ("erratum", "An erratum/correction has been published for this reference."),
    "RetractionIn": ("retraction", "This reference has been RETRACTED."),
    "ExpressionOfConcernIn": ("concern", "An expression of concern has been published."),
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "presubmit/0.3 (+manuscript checker)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _q(params):
    params = dict(params)
    params["tool"] = TOOL
    return urllib.parse.urlencode(params)


def dois_and_pmids(entries):
    """Pull DOIs and explicit PMIDs out of reference entry strings."""
    dois, pmids = [], []
    for e in entries:
        for d in DOI_RE.findall(e or ""):
            dois.append(d.rstrip(".,;"))
        for p in PMID_RE.findall(e or ""):
            pmids.append(p)
    return dois, pmids


# AMA style — the style Annals and JAMA use — prints no DOI:
#   "Roe A, Lee K, et al. A title. Journal of Examples. 2024;12(3):101-110."
# Without citation matching, the whole check would be a no-op on exactly the
# manuscripts most likely to need it.
CITATION_RE = re.compile(
    r"(?P<journal>[A-Z][A-Za-z.&'\- ]{2,60}?)\.\s*"
    r"(?P<year>(?:19|20)\d{2});\s*"
    r"(?P<vol>\d{1,4})"
    r"(?:\s*\([^)]{1,20}\))?"
    r"\s*:\s*(?P<page>[A-Za-z]?\d{1,6})")
AUTHOR_RE = re.compile(r"^\s*(?P<sur>[A-Z][A-Za-z'’\-]{1,30})\s+[A-Z]{1,3}\b")


def parse_citation(entry):
    """(journal, year, volume, first_page, first_author) or None."""
    m = CITATION_RE.search(entry or "")
    if not m:
        return None
    a = AUTHOR_RE.match(entry or "")
    journal = re.sub(r"\s+", " ", m.group("journal")).strip(" .,")
    if len(journal) < 3:
        return None
    return (journal, m.group("year"), m.group("vol"), m.group("page"),
            a.group("sur") if a else "")


def resolve_citations(entries):
    """Reference entries -> {entry_index: pmid} via PubMed's citation matcher."""
    rows, keys = [], {}
    for i, e in enumerate(entries, 1):
        parsed = parse_citation(e)
        if not parsed:
            continue
        journal, year, vol, page, author = parsed
        key = f"ref{i}"
        keys[key] = i
        rows.append(f"{journal}|{year}|{vol}|{page}|{author}|{key}|")
    if not rows:
        return {}
    out = {}
    try:
        body = "\r".join(rows)
        url = f"{EUTILS}/ecitmatch.cgi?" + _q({"db": "pubmed", "retmode": "xml",
                                               "bdata": body})
        text = _get(url)
    except Exception:
        return {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        pmid = parts[-1].strip()
        key = parts[-2].strip() if len(parts) >= 2 else ""
        if pmid.isdigit() and key in keys:
            out[keys[key]] = pmid
    return out


def resolve_dois(dois):
    """DOI -> PMID, one esearch per DOI. Returns {doi: pmid} for those found."""
    out = {}
    for doi in dois:
        try:
            url = f"{EUTILS}/esearch.fcgi?" + _q({
                "db": "pubmed", "term": f"{doi}[AID]", "retmode": "json"})
            data = json.loads(_get(url))
            ids = data.get("esearchresult", {}).get("idlist", [])
            if ids:
                out[doi] = ids[0]
        except Exception:
            continue
    return out


def corrections(pmids):
    """Returns {pmid: [(kind, message), ...]} for the pmids that carry notices."""
    if not pmids:
        return {}
    found = {}
    try:
        url = f"{EUTILS}/efetch.fcgi?" + _q({
            "db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
        xml = _get(url)
    except Exception:
        raise
    # split per article so a notice is attributed to the right PMID
    for chunk in re.split(r"(?=<PubmedArticle[ >])", xml):
        m = re.search(r"<PMID[^>]*>(\d+)</PMID>", chunk)
        if not m:
            continue
        pmid = m.group(1)
        hits = []
        for ref_type, (kind, msg) in FLAGS.items():
            if re.search(r'RefType="%s"' % ref_type, chunk):
                hits.append((kind, msg))
        if re.search(r"<PublicationType[^>]*>Retracted Publication</PublicationType>", chunk):
            if not any(k == "retraction" for k, _ in hits):
                hits.append(("retraction", "This reference has been RETRACTED."))
        if hits:
            found[pmid] = hits
    return found


def check(entries):
    """Returns (results, error). results: list of (entry_index, kind, message, ident)."""
    if not entries:
        return [], "no reference list found"
    dois, explicit = dois_and_pmids(entries)
    try:
        by_doi = resolve_dois(dois)
        by_cite = resolve_citations(entries)     # AMA style carries no DOI
        pmid_to_idx = dict(by_cite)
        for doi, pmid in by_doi.items():
            idx = _entry_of(entries, doi, pmid)
            pmid_to_idx.setdefault(idx, pmid)
        idx_of = {p: i for i, p in pmid_to_idx.items()}
        pmids = list(dict.fromkeys(list(pmid_to_idx.values()) + explicit))
        if not pmids:
            return [], "no reference could be resolved to a PubMed record"
        notices = corrections(pmids)
    except Exception as exc:
        return [], f"PubMed lookup failed ({type(exc).__name__})"

    back = {v: k for k, v in by_doi.items()}
    results = []
    for pmid, hits in notices.items():
        ident = back.get(pmid, f"PMID {pmid}")
        idx = idx_of.get(pmid) or _entry_of(entries, ident, pmid)
        for kind, msg in hits:
            results.append((idx, kind, msg, ident))
    return sorted(results), None


def _entry_of(entries, ident, pmid):
    for i, e in enumerate(entries, 1):
        if ident and ident.lower() in (e or "").lower():
            return i
        if pmid and pmid in (e or ""):
            return i
    return 0
