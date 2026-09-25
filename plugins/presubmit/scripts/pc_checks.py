"""The checkers. Each takes the Document + profile and returns a list of
Finding. All deterministic — no network, no language model, no spell dictionary
(so no false positives on medical terms). Import and run via pc.py.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from pc_lib import F, ERROR, WARN, INFO, word_count

try:  # vendored from ~/.szk-blacklist; offline — reads a local JSON only
    import journal_blacklist as _jbl
    _BL = _jbl.load()
except Exception:
    _BL = None

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
        # Not every article type carries an abstract: opinion, commentary and
        # editorial formats usually do not. The profile decides.
        if profile.get("abstract_required", True):
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
        if profile.get("keywords_required", True):
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

    out.extend(_blacklist_findings(entries, profile))

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


def _blacklist_findings(entries, profile):
    """The user's standing ban: MTMT "Norvég lista" journals are neither cited
    nor submitted to. ISSN or NLM-abbreviation hit = ERROR; a bare title match
    (a namesake is possible) = WARN."""
    if _BL is None:
        return [F("references", INFO, "blacklist-unavailable",
                  "Journal blacklist (MTMT Norvég lista) not found — "
                  "run journal_blacklist.py update.", where="references")]
    out = []
    v, j, why = _BL.check_title(profile.get("name", ""))
    if v == "BLOCKED" or (v == "SUSPECT" and profile.get("name", "").lower() != "generic"):
        out.append(F("references", ERROR, "target-journal-blacklisted",
                     f"Target journal {profile['name']} is on the MTMT Norvég lista "
                     f"({_jbl.describe(j)}): publications there do not count and "
                     "must not be used.", where="journal",
                     fix="Choose a different journal."))
    for i, e in enumerate(entries, 1):
        v, j, why = _BL.check_reference(e)
        if v == "BLOCKED":
            out.append(F("references", ERROR, "ref-blacklisted-journal",
                         f"Reference {i} is from a blacklisted journal: "
                         f"{j['title']} ({why}).", where=f"ref {i}",
                         fix="Replace with a source from a non-listed journal: " + _snip(e)))
        elif v == "SUSPECT":
            out.append(F("references", WARN, "ref-blacklist-suspect",
                         f"Reference {i} may be from a blacklisted journal: "
                         f"{j['title']} ({why}).", where=f"ref {i}",
                         fix="Check the journal's ISSN against the list: " + _snip(e)))
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


# ============================================================ SUBMISSION =====
# Things that must not survive into a submitted file, and the arithmetic a
# journal will do the moment it opens the manuscript. Learned from a real
# Annals of Internal Medicine editorial round.

PLACEHOLDER_PATTERNS = [
    (r"\bTBD\b", "TBD"),
    (r"\bTODO\b", "TODO"),
    (r"\bFIXME\b", "FIXME"),
    (r"\bXXX+\b", "XXX"),
    (r"\bPLACEHOLDER\b", "PLACEHOLDER"),
    (r"\bLorem ipsum\b", "Lorem ipsum"),
    (r"\[(?:insert|add|cite|ref)[^\]]{0,40}\]", "[insert …]"),
    (r"<[^>]{0,30}(?:insert|todo|name|date)[^>]{0,30}>", "<insert …>"),
    (r"\?{3,}", "???"),
    # an ellipsis sitting inside a sentence, not at its end: "an RCT of…, we"
    (r"(?<=[a-z])\s?(?:\.\.\.|…)\s?,", "…, (unfinished phrase)"),
]

# Abbreviations that are not trial names. Anything the manuscript defines
# itself — "major adverse cardiovascular events (MACE)" — is excluded
# automatically, so this list only needs the ones authors leave undefined.
NOT_A_TRIAL = {
    "AND", "THE", "FOR", "WITH", "NOT", "ALL", "ANY", "USA", "USE", "III", "II",
    "CI", "SD", "SE", "IQR", "ITT", "RCT", "HR", "RR", "OR", "AE", "SAE", "NNT",
    "BMI", "HDL", "LDL", "DNA", "RNA", "MRI", "DXA", "BIA", "ECG", "FDA", "EMA",
    "NICE", "WHO", "NIH", "ACP", "ICMJE", "PRISMA", "CONSORT", "STROBE", "GRADE",
    "PROSPERO", "QALY", "ANOVA", "GLP", "GIP", "MACE", "ASCVD", "HOMA", "NMA",
    "PDF", "DOI", "ORCID", "COI", "AI", "LLM", "CT", "PET", "US", "UK", "EU",
    # academic degrees and fellowships — never trial names
    "MD", "MS", "MA", "BA", "MSC", "MBA", "MPH", "BSC", "PHD", "DPHIL", "DSC",
    "PHARMD", "RN", "FRCP", "FACP", "FRCPC", "MRCP",
}

# Words that mark a token as a gene, a variant or an administrative identifier
# rather than a study: "the GLP1R variant", "Decision SZE/ETT-82/2026".
_NOT_STUDY_CONTEXT = re.compile(
    r"\b(?:variant|variants|allele|alleles|gene|genes|receptor|polymorphism|"
    r"genotype|locus|decision|dossier|approval|registration|identifier|"
    r"grant|number)\b", re.I)

# Positive evidence that an all-caps token is being introduced as a study.
_STUDY_INTRO = re.compile(r"\b(?:in|of|from|the|and|with|versus|vs\.?)\s+$", re.I)

TRIAL_DESCRIPTORS = re.compile(
    r"\b(?:a|an|the)\s+(?:\w+[\s-]+){0,4}"
    r"(?:randomi[sz]ed|randomi[sz]ation|trial|study|cohort|analysis|review|"
    r"survey|registry|phase\s*\d|post\s*hoc|meta-analysis|RCT)\b"
    r"|\bin which\b|\bwhich (?:enrolled|randomly|compared|assigned|included)\b"
    r"|\b(?:enrolled|randomly assigned|recruited)\s+[\d,\s]+\s*(?:adults|patients|participants)\b",
    re.I)

EFFECT_MEASURES = re.compile(
    r"\b(?:hazard ratio|risk ratio|relative risk|odds ratio|rate ratio|"
    r"incidence rate ratio|mean difference|standardi[sz]ed mean difference)\b"
    r"|\b(?:aHR|aOR|aRR|HR|RR|OR|IRR|SMD|WMD|MD)\b(?=[\s,=:]*[\d.])",
    re.I)

PRECISION = re.compile(r"\bCI\b|\bconfidence interval|\bcredible interval|\bIQR\b"
                       r"|\binterquartile\b|\bSD\b|\bstandard deviation\b", re.I)

OWN_STUDY = re.compile(
    r"\bour own\s+(?:study|studies|program|programme|trial|cohort|series|data|work)\b"
    r"|\bour (?:ongoing|current|planned|forthcoming)\s+(?:study|trial|program|programme|cohort)\b"
    r"|\bwe are (?:currently\s+)?(?:enrolling|recruiting|conducting|running|testing this)\b"
    r"|\bis (?:currently\s+)?(?:enrolling|recruiting)\b"
    r"|\bplanned,? not (?:yet\s+)?begun\b",
    re.I)

REGISTRATION = re.compile(r"\bClinicalTrials\.gov\b|\bNCT\d{6,}\b|\bISRCTN\d+\b"
                          r"|\bCRD42\d+\b|\bEudraCT\b|\btrial registration\b", re.I)

META_LABEL = re.compile(
    r"^\s*(?:word count|references?|figures?|tables?|running (?:head|title)|"
    r"corresponding author|conflicts? of interest|competing interests?|"
    r"funding|financial support|ethics(?: and registration)?|registration|"
    r"language and ai(?: use)?|ai use|author contributions?|"
    r"acknowledge?ments?|data availability|key ?words?|orcid|disclosures?)\b"
    r"\s*[:.—-]", re.I)

FIGURE_LEGEND = re.compile(r"^\s*(?:figure|fig\.?)\s*(?:legends?|\d+[.:])", re.I)

DECLARED_WC = re.compile(r"\bword count\s*[:=—-]\s*([\d][\d , ]*)", re.I)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[\"'“(]?[A-Z])", text or "")
            if s.strip()]


def _defined_abbreviations(text):
    """Abbreviations the manuscript defines itself, e.g. '... events (MACE)'."""
    out = set()
    for m in re.finditer(r"[a-z][^()]{3,80}?\(([A-Z][A-Za-z0-9‑-]{1,14})\)", text or ""):
        out.add(m.group(1).upper())
    return out


def _body_paragraphs(doc):
    """The body only: no title page block, no references, no figure legend.
    Returns (paragraphs, confident). Best-effort — everything built on it is
    reported as an estimate, never as the authoritative number."""
    paras = [t for t, _ in doc.paragraphs]
    seen_meta = any(META_LABEL.match(t) for t in paras)
    start = 0
    if seen_meta:
        # everything up to and including the last metadata label is title page
        for i, t in enumerate(paras):
            if META_LABEL.match(t):
                start = i + 1
    keep, in_legend = [], False
    for t in paras[start:]:
        if t.strip().lower() in ("references", "reference list", "bibliography"):
            break
        if FIGURE_LEGEND.match(t):
            in_legend = True
            continue
        if META_LABEL.match(t):
            in_legend = False
            continue
        if in_legend:
            continue
        keep.append(t)
    return keep, seen_meta


def _body_text(doc):
    keep, _ = _body_paragraphs(doc)
    if not keep:
        text = doc.text
        ref = doc.sections.get("references", "")
        return text.split(ref)[0] if ref and ref in text else text
    return "\n".join(keep)


def _body_estimate(doc):
    keep, confident = _body_paragraphs(doc)
    return word_count("\n".join(keep)), confident


def check_submission(doc, profile):
    out = []
    text = doc.text

    # --- 1. placeholders left in the text -----------------------------------
    hits = []
    for pat, label in PLACEHOLDER_PATTERNS:
        m = re.search(pat, text)
        if m:
            hits.append((label, _ctx(text, m)))
    for label, ctx in hits:
        out.append(F("submission", ERROR, "placeholder-left",
                     f"Placeholder text still in the manuscript: {label}.",
                     where=ctx,
                     fix="Replace it with the real content, or delete it. An editor "
                         "reading a placeholder assumes the draft was not finished."))

    # --- 2. tracked changes / comments still in the .docx --------------------
    path = getattr(doc, "path", None)
    if path:
        try:
            import pc_docx
            facts = pc_docx.inspect(path)
        except Exception:
            facts = None
        if facts and facts.is_docx:
            if facts.insertions or facts.deletions:
                who = ", ".join(facts.revision_authors) or "unknown"
                out.append(F("submission", ERROR, "tracked-changes-left",
                             f"The .docx still contains unresolved tracked changes "
                             f"({facts.insertions} insertion(s), {facts.deletions} "
                             f"deletion(s); author(s): {who}).",
                             where=facts.sample_insertion,
                             fix="Accept or reject every revision, then save. The journal "
                                 "opens the file you upload, not the version you see."))
            if facts.comments:
                who = ", ".join(facts.comment_authors) or "unknown"
                out.append(F("submission", ERROR, "comments-left",
                             f"The .docx still contains {facts.comments} embedded "
                             f"comment(s) (author(s): {who}).",
                             where=facts.sample_comment,
                             fix="Delete every comment before submitting."))

    # --- 3. declared word count ---------------------------------------------
    limit = profile.get("body_max_words")
    m = DECLARED_WC.search(text)
    declared = None
    if m:
        try:
            declared = int(re.sub(r"[^\d]", "", m.group(1)))
        except ValueError:
            declared = None
    measured, confident = _body_estimate(doc)

    if declared is not None and limit:
        if declared > limit:
            out.append(F("submission", ERROR, "declared-over-limit",
                         f"The declared word count ({declared}) exceeds the "
                         f"{profile['name']} limit of {limit}.",
                         where="title page",
                         fix="Cut the text to the limit, or correct the declared number "
                             "if it is a typo — an order-of-magnitude slip here is common."))
        elif declared > limit * 0.98:
            out.append(F("submission", WARN, "declared-near-limit",
                         f"The declared word count ({declared}) is within 2% of the "
                         f"{limit}-word limit — no room for the next revision round.",
                         where="title page"))
    if declared is not None and confident and measured:
        drift = abs(measured - declared) / float(declared)
        if drift > 0.15:
            out.append(F("submission", INFO, "declared-vs-measured",
                         f"Declared word count is {declared}; the body measures about "
                         f"{measured} (estimate, title page and references excluded).",
                         where="title page",
                         fix="Re-count in the word processor. A large gap usually means a "
                             "typo in the declared number or a stale figure from an "
                             "earlier draft."))
    if limit and confident and measured > limit and declared is None:
        out.append(F("submission", WARN, "body-over-limit",
                     f"The body measures about {measured} words against a limit of "
                     f"{limit} (estimate).",
                     fix="Re-count in the word processor and cut to the limit."))

    # --- 4. reference and figure ceilings ------------------------------------
    rmax = profile.get("references_max")
    if rmax:
        n = len(_reference_entries(doc))
        if n > rmax:
            out.append(F("submission", ERROR, "too-many-references",
                         f"{n} references against a limit of {rmax} for "
                         f"{profile['name']}.",
                         fix=f"Cut to {rmax}. If an editor asks you to add one, it has to "
                             "replace an existing reference, not extend the list."))

    # --- 5. disclosures that do not belong in this article type --------------
    for name in profile.get("discouraged_disclosures", []):
        pat = DISCLOSURE_PATTERNS.get(name)
        if pat and re.search(pat, text.lower()):
            out.append(F("submission", WARN, "discouraged-disclosure",
                         f"This article type normally carries no '{name}' statement in "
                         f"the manuscript ({profile['name']}).",
                         fix="Move it to the disclosure form, which is published alongside "
                             "the article, and delete it from the title page."))
    if profile.get("registration_in_text_discouraged") and REGISTRATION.search(text):
        out.append(F("submission", WARN, "registration-in-text",
                     "A trial registration statement appears in the manuscript, which this "
                     "article type normally does not carry.",
                     fix="Move registration details to the disclosure form."))
    return out


# ============================================================ CLAIMS =========
# How evidence is presented. Editors ask for these in almost every round.

def check_claims(doc, profile):
    out = []
    text = doc.text
    body = _body_text(doc)

    # --- 1. effect estimates without a measure of precision ------------------
    # Parenthetical-level, not sentence-level: the failure an editor actually
    # notices is a headline estimate carrying its CI next to subgroup values
    # in the same sentence that do not.
    naked, seen_inner = [], set()
    for s in _sentences(body):
        if not EFFECT_MEASURES.search(s) and not re.search(r"\bratio\b|\brisk\b", s, re.I):
            continue
        for pm in re.finditer(r"\(([^()]{1,120})\)", s):
            inner = pm.group(1).strip()
            if not re.search(r"\d+\.\d+", inner):
                continue                   # a bare (8) is a citation, not an estimate
            if PRECISION.search(inner):
                continue                   # already carries its precision
            if re.fullmatch(r"[Pp]\s*[<>=≤≥]\s*[\d.]+", inner):
                continue                   # a P value needs no CI
            if inner in seen_inner:
                continue
            seen_inner.add(inner)
            naked.append((inner, s))
    for inner, sent in naked[:4]:
        out.append(F("claims", WARN, "estimate-without-ci",
                     f"The estimate ({inner}) is reported without a confidence interval.",
                     where=_short(sent),
                     fix="Add the 95% CI. Reviewers ask for precision around every "
                         "estimate you choose to quote, including subgroup values."))
    if len(naked) > 4:
        out.append(F("claims", INFO, "estimate-without-ci-more",
                     f"{len(naked) - 4} further estimate(s) without a confidence interval.",
                     fix="Check every quoted estimate."))

    # --- 2. trial acronyms used without a one-line description ---------------
    # Only flag a token we are confident names a study: it sits in a sentence
    # that carries a citation, it is introduced like a study ("In SELECT,"),
    # and it is not being used as a gene, a variant or an approval number.
    # Absence of a description is worth reporting only once we are sure the
    # token IS a study — otherwise every gene symbol becomes a false positive.
    defined = _defined_abbreviations(text) | NOT_A_TRIAL
    seen = {}
    for sent in _sentences(body):
        if not re.search(r"[(\[]\d{1,3}[)\]]", sent):
            continue
        for m in re.finditer(r"\b([A-Z][A-Z0-9]{2,}(?:[-‑][A-Z0-9]+)*)\b", sent):
            tok = m.group(1)
            if tok.upper() in defined or tok in seen:
                continue
            if re.search(r"(?:19|20)\d\d", tok) or tok.count("-") >= 2:
                continue
            before = sent[max(0, m.start() - 60):m.start()]
            after = sent[m.end():m.end() + 60]
            if _NOT_STUDY_CONTEXT.search(before) or _NOT_STUDY_CONTEXT.search(after[:30]):
                continue
            if not (_STUDY_INTRO.search(before)
                    or re.match(r"\s*(?:trial|study)\b", after, re.I)):
                continue
            if TRIAL_DESCRIPTORS.search(after) or TRIAL_DESCRIPTORS.search(before):
                continue
            seen[tok] = _short(sent)
    for tok, ctx in list(seen.items())[:6]:
        out.append(F("claims", WARN, "acronym-study-undescribed",
                     f"'{tok}' is referred to by acronym with no description nearby.",
                     where=ctx,
                     fix="Add a clause saying what it was — population, design, "
                         "comparator. A general readership cannot look it up mid-sentence."))

    # --- 3. the authors' own study promoted in the closing -------------------
    # The closing is the end of the *body*. Almost every manuscript ends with
    # its reference list, so counting back from the last paragraph of the file
    # would look at references instead of the conclusion.
    bparas, _conf = _body_paragraphs(doc)
    bparas = [t for t in bparas if t.strip()]
    tail = "\n".join(bparas[-3:]) if bparas else ""
    concl = doc.sections.get("conclusions", "")
    for chunk, where in ((concl, "conclusions"), (tail, "closing paragraphs")):
        if chunk and OWN_STUDY.search(chunk):
            m = OWN_STUDY.search(chunk)
            out.append(F("claims", WARN, "own-study-in-conclusion",
                         "The closing refers to the authors' own ongoing or planned study.",
                         where=_ctx(chunk, m),
                         fix="Editors read this as self-promotion that dilutes the "
                             "conclusion. State the gap; let someone else's trial fill it."))
            break

    # --- 4. the same reference described twice -------------------------------
    out.extend(_duplicate_citation_descriptions(doc, body))
    return out


def _citation_marker_sentences(body):
    """{citation number -> [sentence, ...]} for (1) and [1] style markers."""
    hits = {}
    for s in _sentences(body):
        nums = set()
        for m in re.finditer(r"[\(\[](\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)[\)\]]", s):
            for part in re.split(r"[,–-]", m.group(1)):
                part = part.strip()
                if part.isdigit() and 0 < int(part) < 200:
                    nums.add(int(part))
        for n in nums:
            hits.setdefault(n, []).append(s)
    return hits


_STOP = set("the a an and or of in to for with on by is was were are be been that this "
            "it its as at from than then which who whom whose but not no more most "
            "only also both each per about over under between".split())


def _content_words(s):
    return {w for w in re.findall(r"[a-z][a-z-]{3,}", (s or "").lower()) if w not in _STOP}


def _duplicate_citation_descriptions(doc, body):
    out = []
    for num, sents in _citation_marker_sentences(body).items():
        if len(sents) < 2:
            continue
        for i in range(len(sents)):
            for j in range(i + 1, len(sents)):
                a, b = sents[i], sents[j]
                if min(len(a), len(b)) < 60:
                    continue
                wa, wb = _content_words(a), _content_words(b)
                if not wa or not wb:
                    continue
                shared = wa & wb
                jac = len(shared) / float(len(wa | wb))
                ratio = SequenceMatcher(None, a, b).ratio()
                if len(shared) >= 5 and (jac >= 0.30 or ratio >= 0.55):
                    out.append(F("claims", INFO, "duplicate-citation-description",
                                 f"Reference ({num}) is described in two places with "
                                 f"overlapping wording.",
                                 where=_short(a),
                                 fix="Describe a study once, where it first appears, and "
                                     "refer back afterwards. Repeating it is the most "
                                     "common source of 'this paragraph is repetitive'."))
                    break
            else:
                continue
            break
    return out[:4]


def _ctx(text, m, n=60):
    start = max(0, m.start() - 25)
    frag = re.sub(r"\s+", " ", text[start:m.start() + n]).strip()
    return ("…" if start else "") + frag


def _short(s, n=80):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:n] + ("…" if len(s) > n else "")



ALL_CHECKS = {
    "structure": check_structure,
    "authors": check_authors,
    "abstract": check_abstract,
    "references": check_references,
    "ethics": check_ethics,
    "format": check_format,
    "submission": check_submission,
    "claims": check_claims,
}
