"""The checkers. Each takes the Document + profile and returns a list of
Finding. All deterministic — no network, no language model, no spell dictionary
(so no false positives on medical terms). Import and run via pc.py.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from pc_lib import F, ERROR, WARN, INFO, word_count

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
YEAR_RE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


# ============================================================ STRUCTURE =======
def check_structure(doc, profile):
    out = []
    present = set(doc.sections.get("_order", []))
    # choose expected set: case report vs original, by presence of a case section
    if "case presentation" in present and profile.get("case_report_sections"):
        expected = profile["case_report_sections"]
    else:
        expected = profile.get("required_sections", [])
    for sec in expected:
        if sec not in present:
            out.append(F("structure", WARN, "missing-section",
                         f"Expected section not found: '{sec}'.",
                         fix=f"Add a clearly-titled '{sec.title()}' section, or "
                             "rename the existing heading to match."))
    if not present:
        out.append(F("structure", INFO, "no-headings",
                     "No section headings were detected — the checker could not "
                     "map the manuscript to IMRaD.",
                     fix="Use explicit headings (Introduction, Methods, ...)."))
    return out


# ============================================================ AUTHORS =========
def check_authors(doc, profile):
    out = []
    head = doc.sections.get("_preamble", "")[:2000]
    if not EMAIL_RE.search(head) and not EMAIL_RE.search(doc.text[:3000]):
        out.append(F("authors", WARN, "no-corresponding-email",
                     "No corresponding-author email found near the title block.",
                     where="title/authors",
                     fix="Add the corresponding author's email address."))
    aff_markers = ("department", "university", "hospital", "institute",
                   "faculty", "clinic", "college", "school of", "centre",
                   "center")
    if not any(m in head.lower() for m in aff_markers):
        out.append(F("authors", WARN, "no-affiliation",
                     "No institutional affiliation detected in the author block.",
                     where="title/authors",
                     fix="List each author's department and institution."))
    if "orcid" not in doc.text.lower():
        out.append(F("authors", INFO, "no-orcid",
                     "No ORCID iD found. Many journals now require ORCID for "
                     "the corresponding (or all) authors.",
                     fix="Add ORCID iDs where required."))
    return out


# ===================================================== ABSTRACT + KEYWORDS ====
def check_abstract(doc, profile):
    out = []
    abs_txt = doc.sections.get("abstract", "")
    if not abs_txt:
        out.append(F("abstract", ERROR, "no-abstract",
                     "No Abstract section detected.",
                     fix="Add a titled 'Abstract' section."))
    else:
        wc = word_count(abs_txt)
        amax = profile.get("abstract_max_words")
        amin = profile.get("abstract_min_words")
        if amax and wc > amax:
            out.append(F("abstract", WARN, "abstract-too-long",
                         f"Abstract is {wc} words; {profile['name']} limit is "
                         f"~{amax}.", where="abstract",
                         fix=f"Trim to <= {amax} words."))
        if amin and wc < amin:
            out.append(F("abstract", INFO, "abstract-short",
                         f"Abstract is only {wc} words.", where="abstract",
                         fix="Make sure background, methods, results and "
                             "conclusion are all represented."))
    # keywords
    kw = doc.sections.get("keywords", "")
    if not kw:
        out.append(F("keywords", WARN, "no-keywords",
                     "No Keywords line detected.",
                     fix=f"Add {profile.get('keywords_min',3)}–"
                         f"{profile.get('keywords_max',5)} keywords."))
    else:
        parts = [k.strip() for k in re.split(r"[;,\n]", kw) if k.strip()]
        n = len(parts)
        lo, hi = profile.get("keywords_min", 3), profile.get("keywords_max", 6)
        if n < lo:
            out.append(F("keywords", WARN, "too-few-keywords",
                         f"Only {n} keyword(s); {profile['name']} wants "
                         f"{lo}–{hi}.", where="keywords"))
        elif n > hi:
            out.append(F("keywords", INFO, "too-many-keywords",
                         f"{n} keywords; {profile['name']} suggests {lo}–{hi}.",
                         where="keywords"))
    return out


# ============================================================ REFERENCES ======
def _reference_entries(doc):
    """Return the list of raw reference entries from the References section."""
    ref = doc.sections.get("references", "")
    if not ref:
        return []
    lines = [l.strip() for l in ref.splitlines() if l.strip()]
    entries, cur = [], ""
    numbered = re.compile(r"^\[?(\d{1,3})[\].]\s+")
    started = False
    for l in lines:
        if numbered.match(l):
            started = True
            if cur:
                entries.append(cur.strip())
            cur = numbered.sub("", l)
        elif started:
            cur += " " + l
        else:
            # no numbering — treat each non-empty line as an entry
            entries.append(l)
    if cur:
        entries.append(cur.strip())
    return [e for e in entries if len(e) > 3]


def _cited_numbers(doc):
    """Numeric in-text citations, excluding the references section."""
    body = doc.text
    ref = doc.sections.get("references", "")
    if ref:
        body = body.split(ref)[0] if ref in body else body
    nums = set()
    for m in re.finditer(r"\[(\d{1,3}(?:\s*[-,]\s*\d{1,3})*)\]", body):
        for part in re.split(r",", m.group(1)):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-")[:2]
                try:
                    nums.update(range(int(a), int(b) + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                nums.add(int(part))
    return nums


def check_references(doc, profile):
    out = []
    entries = _reference_entries(doc)
    if not entries:
        out.append(F("references", ERROR, "no-references",
                     "No reference list detected.",
                     fix="Add a 'References' section."))
        return out

    n = len(entries)
    out.append(F("references", INFO, "ref-count",
                 f"{n} references detected.", where="references"))

    # per-entry completeness
    for i, e in enumerate(entries, 1):
        if not YEAR_RE.search(e):
            out.append(F("references", WARN, "ref-no-year",
                         f"Reference {i} has no publication year.",
                         where=f"ref {i}", fix="Add the year: " + _snip(e)))
        if len(e) < 30:
            out.append(F("references", WARN, "ref-incomplete",
                         f"Reference {i} looks incomplete (very short).",
                         where=f"ref {i}", fix="Check for a missing journal "
                         "title, authors or pages: " + _snip(e)))
        if "doi" in e.lower() and not DOI_RE.search(e):
            out.append(F("references", WARN, "ref-bad-doi",
                         f"Reference {i} mentions a DOI but none is valid.",
                         where=f"ref {i}", fix="Fix the DOI (10.xxxx/...)."))

    # duplicates: by DOI, then by fuzzy title/text
    seen_doi = {}
    for i, e in enumerate(entries, 1):
        m = DOI_RE.search(e)
        if m:
            key = m.group(0).lower().rstrip(".")
            if key in seen_doi:
                out.append(F("references", ERROR, "ref-dup-doi",
                             f"References {seen_doi[key]} and {i} share the same "
                             f"DOI ({key}).", where=f"ref {i}",
                             fix="Remove the duplicate entry."))
            else:
                seen_doi[key] = i
    norm = [_norm_ref(e) for e in entries]
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            if norm[i] and SequenceMatcher(None, norm[i], norm[j]).ratio() > 0.92:
                out.append(F("references", ERROR, "ref-duplicate",
                             f"References {i+1} and {j+1} appear to be duplicates.",
                             where=f"ref {i+1}/{j+1}",
                             fix="Keep one; delete the other and renumber."))

    # in-text cross-check
    cited = _cited_numbers(doc)
    if cited:
        over = sorted(c for c in cited if c > n)
        for c in over:
            out.append(F("references", ERROR, "cite-out-of-range",
                         f"In-text citation [{c}] has no matching reference "
                         f"(only {n} in the list).", where="body",
                         fix="Add the reference or fix the citation number."))
        uncited = sorted(set(range(1, n + 1)) - cited)
        if uncited and len(uncited) <= n:
            preview = ", ".join(map(str, uncited[:12]))
            out.append(F("references", WARN, "ref-uncited",
                         f"{len(uncited)} reference(s) never cited in the text: "
                         f"[{preview}{'…' if len(uncited) > 12 else ''}].",
                         where="references",
                         fix="Cite each reference in the text, or remove it."))
    else:
        out.append(F("references", INFO, "no-numeric-citations",
                     "No numeric [n] in-text citations found — cross-check with "
                     "the reference list was skipped (author–year style?).",
                     where="body"))
    return out


def _norm_ref(e):
    return re.sub(r"[^a-z0-9 ]", "", e.lower())


def _snip(e, n=60):
    return (e[:n] + "…") if len(e) > n else e


# ============================================================ ETHICS ==========
DISCLOSURE_PATTERNS = {
    "conflict of interest": r"conflict[s]? of interest|competing interest|"
                            r"declaration of interest|no .{0,20}conflict",
    "funding": r"funding|financial support|grant|no .{0,10}funding|"
               r"received no .{0,20}support",
    "human subjects": r"human subjects|irb|institutional review board|"
                      r"ethics committee|ethical approval|ethics approval",
    "animal subjects": r"animal subjects|iacuc|animal care|animal ethics",
    "informed consent": r"informed consent|consent (?:was|to|for|obtained)|"
                        r"consent for publication",
    "data availability": r"data availability|data are available|"
                         r"available (?:on|upon) request|supplementary data",
    "acknowledgements": r"acknowledg",
    "author contributions": r"author contribution|contributorship|"
                            r"conceptualization|CRediT",
}


def check_ethics(doc, profile):
    out = []
    low = doc.text.lower()
    req = [d.lower() for d in profile.get("required_disclosures", [])]
    rec = [d.lower() for d in profile.get("recommended_disclosures", [])]
    for name, pat in DISCLOSURE_PATTERNS.items():
        found = re.search(pat, low) is not None
        if name in req and not found:
            out.append(F("ethics", ERROR, f"missing-{name.replace(' ','-')}",
                         f"Required disclosure missing: {name}.",
                         fix=f"Add an explicit '{name}' statement — "
                             f"{profile['name']} requires it at submission."))
        elif name in rec and not found:
            out.append(F("ethics", WARN, f"missing-{name.replace(' ','-')}",
                         f"Recommended statement missing: {name}.",
                         fix=f"Add an explicit '{name}' statement."))
    return out


# ============================================================ FORMAT ==========
def check_format(doc, profile):
    out = []
    text = doc.text
    # repeated word (the the)
    reps = set()
    for m in re.finditer(r"\b([A-Za-z]{2,})\s+\1\b", text, re.IGNORECASE):
        w = m.group(1).lower()
        if w not in ("had", "that"):   # legitimate doublings
            reps.add(w)
    if reps:
        out.append(F("format", WARN, "repeated-word",
                     f"Repeated word(s): {', '.join(sorted(reps)[:8])}.",
                     fix="Delete the accidental duplication."))
    # double spaces
    if re.search(r"[^\n] {2,}\S", text):
        out.append(F("format", INFO, "double-space",
                     "Multiple consecutive spaces found.",
                     fix="Replace runs of spaces with a single space."))
    # space before punctuation
    if re.search(r"\s+[,;:.](?:\s|$)", text):
        out.append(F("format", INFO, "space-before-punct",
                     "Space before a comma/period/semicolon found.",
                     fix="Remove the space before punctuation."))
    # missing space after sentence-ending punctuation (avoid decimals, URLs)
    mm = re.findall(r"[a-z]{2}[.!?][A-Z][a-z]", text)
    if mm:
        out.append(F("format", INFO, "missing-space-after-period",
                     f"Possible missing space after a sentence: e.g. '{mm[0]}'.",
                     fix="Add a space after the full stop."))
    # mixed straight/curly quotes
    if ('"' in text) and ("“" in text or "”" in text):
        out.append(F("format", INFO, "mixed-quotes",
                     "Both straight (\") and curly (“ ”) quotes are used.",
                     fix="Use one quote style consistently."))
    # mixed hyphen/en-dash for ranges
    if re.search(r"\d\s?[-]\s?\d", text) and re.search(r"\d\s?[–]\s?\d", text):
        out.append(F("format", INFO, "mixed-dashes",
                     "Number ranges use both '-' and '–'.",
                     fix="Use an en-dash (–) for numeric ranges consistently."))
    return out


ALL_CHECKS = {
    "structure": check_structure,
    "authors": check_authors,
    "abstract": check_abstract,
    "references": check_references,
    "ethics": check_ethics,
    "format": check_format,
}
