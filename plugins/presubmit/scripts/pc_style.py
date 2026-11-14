"""Style category — the tells of an AI-assisted draft, and the guard that a
rewrite kept every number and citation.

Adapted from academic-humanizer v0.3.3 by AIScientists-Dev (MIT; itself built
on blader/humanizer, MIT). That project is a language-model editing prompt; the
rules below are the part of it a regular expression can decide. Each finding
code maps to the layer it came from in
skills/presubmit/references/academic-humanizer.md, which also carries the
rewrite rules that `/presubmit:humanize` applies. Licence text:
licenses/academic-humanizer-LICENSE.

Report-only and English-only. A Hungarian manuscript gets one INFO saying so,
never a pile of false positives. Nothing here is ever an ERROR: an AI tell
makes a referee less patient, it does not get a paper desk-rejected. The
category is not part of `pc.py check`, so the readiness verdict is unchanged.

Self-contained on purpose, like pc_reviewer_open: it imports only pc_lib.
"""
from __future__ import annotations

import re
from collections import Counter

from pc_lib import F, WARN, INFO, word_count

CAT = "style"

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d\[\(\"“])")


# ---------------------------------------------------------------- helpers ----
def _sentences(text):
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            out.extend([s.strip() for s in _SENT_SPLIT.split(line) if s.strip()] or [line])
    return out


def _body(doc):
    """Everything before the reference list."""
    ref = doc.sections.get("references", "")
    if ref and ref in doc.text:
        return doc.text.split(ref)[0]
    return doc.text


# Title-page, declaration and back-matter labels. A paragraph that opens on one
# of these is form text, not prose: it is neither audited nor rewritten.
LABEL = re.compile(
    r"^\s*\*?\s*(?:word count|references?|figures?|tables?|running (?:head|title)|"
    r"corresponding author|correspondence|conflicts? of interest|competing interests?|"
    r"funding(?:/support)?|financial support|ethics(?: and registration)?|registration|"
    r"language and ai(?: use)?|ai use|author contributions?|acknowledge?ments?|"
    r"data availability(?: statement)?|key ?words?|orcid|disclosures?|abbreviations|"
    r"supplementary materials?|institutional review board statement|"
    r"informed consent statement|trial registration|declaration of [\w ]{3,40}|"
    r"author information|received|accepted|published)\b[^:.\n]{0,40}[:.—]", re.I)
LEGEND = re.compile(r"^\s*(?:(?:figure|fig\.?|table)\s*S?\d+[A-Za-z]?\s*[.:|]"
                    r"|(?:figure|table) legends?\s*$)", re.I)
REF_HEAD = re.compile(r"^\s*(?:\d+\.?\s*)?(?:references?|reference list|bibliography|"
                      r"irodalomjegyz[eé]k|irodalom)\s*$", re.I)
# A back-matter heading on a line of its own ends the prose: what follows it is
# declarations, abbreviations and supplementary lists, up to the references.
BACK_HEAD = re.compile(r"^\s*(?:\d+\.?\s*)?(?:declarations?|abbreviations|"
                       r"acknowledge?ments?|author contributions?|funding|"
                       r"conflicts? of interest|competing interests?|"
                       r"data availability(?: statement)?|supplementary (?:materials?|information)|"
                       r"ethics (?:approval|statement)[\w ,]*|appendix [A-Z\d]*|"
                       r"(?:figures?|tables?)(?: (?:legends?|captions?))?)\s*$", re.I)
_TITLE_PAGE = re.compile(r"ORCID|@|\b(?:Department|Faculty|University|Institute|Hospital|"
                         r"School|Clinic)\b")


def _is_prose(t):
    t = t.strip()
    return (len(t.split()) >= 25 and t[-1:] in ".!?)\u201d\"" and not LABEL.match(t)
            and not _TITLE_PAGE.search(t[:200]))


def prose_paragraphs(doc):
    """The paragraphs a style audit or a rewrite should touch: from the first
    real prose paragraph (the abstract or the opening of the text) to the
    reference list, without title-page lines, declarations, back matter or
    figure and table legends. Headings are kept so a rewrite keeps its shape."""
    paras = [t for t, _ in getattr(doc, "paragraphs", []) or []]
    if not paras:
        return [l for l in _body(doc).splitlines() if l.strip()]
    start = next((i for i, x in enumerate(paras) if _is_prose(x)), 0)
    out = []
    for x in paras[start:]:
        if REF_HEAD.match(x) or BACK_HEAD.match(x):
            break
        if not x.strip() or LABEL.match(x) or LEGEND.match(x):
            continue
        out.append(x)
    return out


def prose_text(doc):
    return "\n".join(prose_paragraphs(doc))


def strip_queries(text):
    """Author queries left by a rewrite (\u27e6AUTHOR: \u2026\u27e7) are not prose."""
    return re.sub(r"\s*\u27e6[^\u27e7]*\u27e7", "", text or "")


def prose_words(text):
    return len(strip_queries(text).split())


def is_synthesis(doc):
    head = doc.text[:2500]
    return bool(re.search(r"systematic review|meta-?analys|umbrella review|scoping review|"
                          r"network meta|pooled analysis", head, re.I))


def is_hungarian(doc):
    return len(re.findall(r"\b(és|hogy|nem|vagy|mint|amely|ezért)\b", doc.text)) >= 40


def _ctx(text, m, n=70):
    start = max(0, m.start() - 30)
    frag = re.sub(r"\s+", " ", text[start:m.end() + n]).strip()
    return ("…" if start else "") + frag[:n + 40] + ("…" if len(frag) > n + 40 else "")


def _short(s, n=90):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:n] + ("…" if len(s) > n else "")


def _tally(text, pattern, norm=lambda s: s.lower()):
    """(Counter of normalised hits, first match) for one pattern."""
    c, first = Counter(), None
    for m in re.finditer(pattern, text, re.I):
        c[norm(m.group(0))] += 1
        first = first or m
    return c, first


def _fmt(c, k=6):
    return ", ".join(f"'{w}' ×{n}" if n > 1 else f"'{w}'" for w, n in c.most_common(k))


# ------------------------------------------------------------ phrase rules ---
# (code, layer, pattern, message head, fix, warn_at)
# warn_at: the number of hits from which the finding is a WARN rather than INFO.
# Patterns are deliberately narrow: each one names a phrase, not a word that a
# medical manuscript uses legitimately ("relatively small", "various doses").
PHRASE_RULES = [
    ("ai-vocabulary", "L1",
     r"\bdelv(?:e|es|ed|ing)\b|\bunderscor(?:e|es|ed|ing)\b(?!\s+character)"
     r"|\bintricate(?:ly)?\b|\btapestry\b|\b(?:a|an)\s+(?:\w+\s+)?testament\b"
     r"|\bpivotal\b|\bshowcas(?:e|es|ed|ing)\b|\bfoster(?:s|ed|ing)?\b(?!\s+(?:care|home|parent|famil|child))"
     r"|\brealm\b|\bseamless(?:ly)?\b|\bmultifaceted\b|\bmeticulous(?:ly)?\b"
     r"|\b(?:evolving|ever-changing|changing|complex|dynamic)\s+landscape\b"
     r"|\bnavigat(?:e|es|ing)\s+the\s+complexit(?:y|ies)\b|\bin the realm of\b",
     "Vocabulary that marks a language-model draft",
     "Replace each with the plain word for what is meant ('examine', 'shows', "
     "'complex', 'key'), or cut it. Referees who have learned these words read "
     "the whole paper less charitably.", 5),
    ("significance-hype", "L2.2",
     r"\bpav(?:e|es|ed|ing) the way\b|\b(?:crucial|pivotal|critical|important) step (?:toward|towards|forward)\b"
     r"|\bpotential to revolutioni[sz]e\b|\brevolutioni[sz]e\b|\bopen(?:s|ed|ing)? (?:up )?new avenues\b"
     r"|\bshed(?:s|ding)? (?:new )?light on\b|\bof paramount importance\b|\bbridg(?:e|es|ing) the gap\b"
     r"|\bgroundbreaking\b|\bgame[- ]chang(?:er|ing)\b|\bcutting[- ]edge\b|\bparadigm shift\b",
     "Significance announced rather than shown",
     "Name the specific failure or gap the work addresses and point at the "
     "result that addresses it (Table/Figure/section).", 2),
    ("empty-intensifier", "L2.3",
     r"\b(?:extensive|comprehensive|thorough|exhaustive)\s+(?:experiments?|evaluations?|analys[ie]s|"
     r"investigations?|validation|testing)\b|\ba wide (?:range|variety|array|spectrum) of\b"
     r"|\ba plethora of\b|\ba myriad of\b",
     "Size asserted instead of counted",
     "Say how many and which: 'three cohorts (A, B, C)' rather than 'extensive "
     "experiments on a wide range of datasets'.", 3),
    ("novelty-padding", "L2.4",
     r"\bto the best of (?:our|the authors'?) knowledge\b|\bfor the first time\b"
     r"|\bthe first (?:study|report|trial|analysis) to\b",
     "Priority claimed by formula",
     "State what prior work did not do and cite it. A referee who finds one "
     "earlier paper discounts every other claim of priority.", 2),
    ("formulaic-opener", "L2.5",
     r"(?:^|(?<=[.!?]\s))(?:In recent (?:years|decades)|Over the (?:past|last) (?:few )?(?:years|decades)"
     r"|With the rapid (?:development|advancement|growth|progress) of|Despite (?:recent|significant|remarkable) advances"
     r"|In today'?s (?:world|era|society))\b"
     r"|\bha(?:s|ve) (?:attracted|gained|garnered|received) (?:increasing|growing|considerable|significant|much) "
     r"(?:attention|interest)\b",
     "Formulaic opener",
     "Open on the specific problem or finding instead of the field's popularity.", 2),
    ("boilerplate-emphasis", "L2.10",
     r"\bit (?:is|should be) (?:worth noting|important to note|noteworthy|worth mentioning|"
     r"(?:noted|emphasi[sz]ed|stressed|highlighted|mentioned|pointed out)) that\b"
     r"|(?:^|(?<=[.!?]\s))(?:Notably|Importantly|Interestingly|Crucially|Remarkably),",
     "Emphasis announced instead of earned",
     "Delete the frame; if the point matters, the sentence shows it.", 4),
    ("vague-hedge", "L2.9",
     r"\bsomewhat\b|\bto (?:some|a certain|a large) extent\b|\bfairly\b|\bquite\b",
     "Hedging by vagueness",
     "Quantify ('3 points higher, <1 point across seeds') or cut. Keep "
     "evidence-tied hedges such as 'suggests' or 'is consistent with'.", 4),
    ("copula-avoidance", "L1",
     r"\bserv(?:es|ed|ing) as (?:a|an|the)\b(?!\s+(?:control|reference|comparator|baseline|proxy|surrogate|marker))"
     r"|\bstands? as (?:a|an|the)\b|\bboasts?\b",
     "Copula avoided ('serves as', 'stands as', 'boasts')",
     "Use 'is' / 'has'. ('serves as a control/comparator/proxy' is left alone.)", 4),
    ("ing-tail", "L1",
     r",\s+(?:highlighting|underscoring|emphasi[sz]ing|showcasing|reflecting|illustrating|"
     r"demonstrating|reinforcing|signal(?:l)?ing)\s+(?:the|its|their|a|an|how|that)\b",
     "Participle tail that adds commentary instead of content",
     "End the sentence at the fact; if the implication matters, give it its own "
     "sentence with its evidence.", 3),
    ("filler-phrase", "L1",
     r"\bin order to\b|\bdue to the fact that\b|\bowing to the fact that\b|\bin spite of the fact that\b"
     r"|\bit is (?:clear|evident|obvious) that\b|\bplays? (?:a|an) (?:crucial|key|vital|pivotal|important|"
     r"significant|essential) role\b",
     "Filler phrase",
     "'to', 'because', 'although'; 'X is required for Y' rather than 'plays a "
     "crucial role in'.", 6),
    ("overclaim-verb", "L2.1",
     r"\b(?:prov(?:e|es|ed|en)|proof) that\b|\bwe (?:have )?prov(?:e|ed)\b"
     r"|\b(?:clearly|conclusively|unequivocally|undoubtedly|definitively) (?:demonstrat|show|establish|prov)\w*"
     r"|\bguarantee(?:s|d)? that\b",
     "Verb stronger than empirical evidence can carry",
     "Empirical work shows or provides evidence; it does not prove. Downgrade "
     "the verb, or attach the test and number that carries it.", 1),
]


def _phrase_findings(body):
    out = []
    for code, layer, pat, head, fix, warn_at in PHRASE_RULES:
        c, first = _tally(body, pat)
        n = sum(c.values())
        if not n:
            continue
        sev = WARN if n >= warn_at else INFO
        out.append(F(CAT, sev, code,
                     f"{head} [{layer}]: {_fmt(c)} — {n} in all.",
                     where=_ctx(body, first), fix=fix))
    return out


# ------------------------------------------------------- structural rules ----
CONNECTIVES = re.compile(r"^(?:Moreover|Furthermore|Additionally|In addition|Also|Besides|"
                         r"In particular|Notably|Importantly|Likewise|Similarly)\b,?", re.I)


def _connective_runs(sents):
    """L2.6 — consecutive sentences that each open on a stacking connective."""
    runs, cur = [], []
    for s in sents:
        if CONNECTIVES.match(s):
            cur.append(s)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    total = sum(1 for s in sents if CONNECTIVES.match(s))
    out = []
    if runs:
        longest = max(runs, key=len)
        out.append(F(CAT, WARN if len(longest) >= 3 or len(runs) >= 3 else INFO,
                     "connective-run",
                     f"{len(runs)} place(s) where consecutive sentences each open on "
                     f"Moreover/Furthermore/Additionally… (longest run: {len(longest)}) [L2.6].",
                     where=_short(longest[0]),
                     fix="Let the logic carry the link: merge the sentences or drop the "
                         "connective."))
    elif total >= 8:
        out.append(F(CAT, INFO, "connective-density",
                     f"{total} sentences open on a stacking connective [L2.6].",
                     fix="Cut most of them; keep the ones that mark a real turn."))
    return out


_CITE_GROUP = re.compile(r"[\[(](\d{1,3}(?:\s*[,;–—-]\s*\d{1,3})+)[\])]")


def _citation_dumps(body, synthesis=False):
    """L2.8 — six or more references behind one claim. In a systematic review
    or meta-analysis the caller passes only the narrative sections, because a
    list of included studies in Methods/Results is not citation dumping."""
    dumps = []
    for m in _CITE_GROUP.finditer(body):
        inner = m.group(1).strip().rstrip(",;")
        if not inner or not re.search(r"[,;–—-]", inner):
            continue
        n = 0
        ok = True
        for part in re.split(r"\s*[,;]\s*", inner):
            rng = re.split(r"\s*[–—-]\s*", part)
            if not all(p.isdigit() for p in rng) or not rng[0]:
                ok = False
                break
            nums = [int(p) for p in rng]
            if any(x == 0 or x > 400 for x in nums):
                ok = False
                break
            n += (nums[-1] - nums[0] + 1) if len(nums) == 2 and nums[1] > nums[0] else 1
        # years and page ranges look like groups; a citation group has small
        # integers and no four-digit token
        if ok and n >= 6:
            dumps.append((n, m))
    if not dumps:
        return []
    n_max, m_max = max(dumps, key=lambda t: t[0])
    scope = " in the narrative sections" if synthesis else ""
    return [F(CAT, WARN if len(dumps) >= 3 else INFO, "citation-dump",
              f"{len(dumps)} citation group(s) of six or more references{scope} "
              f"(largest: {n_max}) [L2.8].",
              where=_ctx(body, m_max),
              fix="Cite the one or two works that carry the claim and say what "
                  "each showed; a bracketed list tells the referee nothing.")]


def _long_sentences(sents, limit=40):
    """L2.11 — clause-stacked sentences. The source uses ~30 words; medical
    prose runs longer, so 40 is the floor here and only the five longest are
    shown."""
    long_ = []
    for s in sents:
        if "|" in s or s.count("\t") > 1:
            continue                      # table rows extracted as text
        if len(re.findall(r"\b(?:OR|AND|NOT)\b", s)) >= 3 or s.count(" = ") >= 2:
            continue                      # a search string or an abbreviation key
        bare = re.sub(r"[\[(][\d,;\s–—-]+[\])]", "", s)
        n = word_count(bare)
        if n > limit:
            long_.append((n, s))
    if not long_:
        return []
    long_.sort(key=lambda t: -t[0])
    share = len(long_) / max(1, len(sents))
    sev = WARN if len(long_) >= 8 or share >= 0.10 else INFO
    ex = "; ".join(f"{n} words: “{_short(s, 60)}”" for n, s in long_[:3])
    return [F(CAT, sev, "overlong-sentence",
              f"{len(long_)} sentence(s) over {limit} words ({share:.0%} of the text) "
              f"[L2.11]. Longest — {ex}",
              fix="One idea per sentence: split at the second 'which', 'while' or "
                  "'with', and cut subordinate clauses that carry no weight.")]


def _em_dashes(body):
    """L1 — em-dashes, English only. En-dash ranges (2–6%) are never counted."""
    credit = re.compile(r"writing\s*—\s*(?:original draft|review)", re.I)
    hits = [m for m in re.finditer(r"—|(?<=\w)\s?--\s?(?=\w)", body)
            if not credit.match(body, max(0, m.start() - 9))
            and not credit.search(body[max(0, m.start() - 9):m.end() + 16])]
    if not hits:
        return []
    return [F(CAT, INFO, "em-dash",
              f"{len(hits)} em-dash(es) in the body [L1].",
              where=_ctx(body, hits[0], 50),
              fix="Recast with a comma, colon, parentheses or a new sentence. "
                  "Numeric ranges keep their en dash (–).")]


def _significant_without_test(sents):
    """L2.1 — 'significantly' with no statistic in the sentence."""
    stat = re.compile(r"\b[Pp]\s*[<>=≤≥]|\bp-?value|\bCI\b|confidence interval|\bt\s*\(|"
                      r"\bχ2|\bchi-?square|\bF\s*\(|\bANOVA\b|\btest\b|Table|Fig|"
                      r"[\[(]\d{1,3}(?:\s*[,;–-]\s*\d{1,3})*[\])]", re.I)
    bare = [s for s in sents
            if re.search(r"\bsignificant(?:ly)?\b", s, re.I) and not stat.search(s)]
    if not bare:
        return []
    return [F(CAT, WARN if len(bare) >= 3 else INFO, "significant-without-test",
              f"{len(bare)} sentence(s) use 'significant(ly)' with no test, p value, "
              f"interval or citation in the sentence [L2.1/L4].",
              where=_short(bare[0]),
              fix="Either give the statistic (or point to the table that has it), or "
                  "use a word that does not imply a test: 'substantially', 'markedly'.")]


def _novel_repeats(doc):
    """L2.4 — 'novel' more than once in a section."""
    hits = []
    for name in doc.sections.get("_order", []):
        if name == "references":
            continue
        n = len(re.findall(r"\bnovel(?:ty)?\b", doc.sections.get(name, ""), re.I))
        if n >= 2:
            hits.append(f"{name} ×{n}")
    if not hits:
        return []
    return [F(CAT, INFO, "novel-repeated",
              f"'novel' used more than once in a section: {', '.join(hits)} [L2.4].",
              fix="Say once what is new, concretely; drop the adjective elsewhere.")]


# ------------------------------------------------------------------ entry ----
def check_style(doc, profile):
    if is_hungarian(doc):
        return [F(CAT, INFO, "style-english-only",
                  "Style rules (AI-draft tells) are English-only; this manuscript reads "
                  "as Hungarian, so none were applied.",
                  fix="For Hungarian register, use the hu-academic-style or "
                      "academic-editor skill.")]
    body = strip_queries(prose_text(doc))
    sents = _sentences(body)
    out = []
    out += _phrase_findings(body)
    out += _connective_runs(sents)
    if is_synthesis(doc):
        narrative = "\n".join(doc.sections.get(k, "") for k in
                               ("introduction", "background", "discussion", "conclusions",
                                "conclusion"))
        out += _citation_dumps(narrative, synthesis=True) if narrative.strip() else []
    else:
        out += _citation_dumps(body)
    out += _long_sentences(sents)
    out += _em_dashes(body)
    out += _significant_without_test(sents)
    out += _novel_repeats(doc)
    return out


# ====================================================== rewrite invariants ===
# The humanizer's one hard promise is that a rewrite changes no number,
# equation or citation. A prompt can promise that; this checks it.

_NUM = re.compile(r"(?<![\w.])[-−–]?\d+(?:[.,]\d+)*(?:\s?%)?")
_CITE_NUM = re.compile(r"[\[(]\s*\d{1,3}(?:\s*[,;–—-]\s*\d{1,3})*\s*[\])]")
_CITE_KEY = re.compile(r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^\]]*\])*\{([^}]+)\}")
_AUTHOR_YEAR = re.compile(r"\b[A-Z][A-Za-z'’-]+(?: et al\.?| and [A-Z][A-Za-z'’-]+)?,? \(?(?:19|20)\d\d[a-z]?\)?")
_DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_MATH = re.compile(r"\$[^$]+\$|\\\([^)]*\\\)|\\\[[^\]]*\\\]")
_REFS = re.compile(r"\b(?:Table|Figure|Fig\.|Supplementary (?:Table|Figure)|Eq\.|Equation|Section)\s*S?\d+[A-Za-z]?", re.I)


def _norm_num(s):
    return s.replace("−", "-").replace("–", "-").replace(" ", "")


def _expand_cite(s):
    out = set()
    for part in re.split(r"[,;]", s.strip("[]() ")):
        rng = [p.strip() for p in re.split(r"[–—-]", part) if p.strip()]
        if len(rng) == 2 and all(p.isdigit() for p in rng) and int(rng[1]) > int(rng[0]):
            out.update(range(int(rng[0]), int(rng[1]) + 1))
        elif rng and rng[0].isdigit():
            out.add(int(rng[0]))
    return out


def invariants(original: str, rewrite: str):
    """Multisets of the things a rewrite must not change. Returns a list of
    (kind, missing, added) where something differs; empty means preserved."""
    def bag(text):
        nums = Counter(_norm_num(m.group(0)) for m in _NUM.finditer(
            _CITE_NUM.sub(" ", _DOI.sub(" ", text))))
        cites = set()
        for m in _CITE_NUM.finditer(text):
            cites |= _expand_cite(m.group(0))
        keys = Counter(k.strip() for m in _CITE_KEY.finditer(text) for k in m.group(1).split(","))
        return {
            "number": nums,
            "citation number": Counter(cites),
            "cite key": keys,
            "author-year citation": Counter(re.sub(r"[()\s,]", "", m.group(0))
                                            for m in _AUTHOR_YEAR.finditer(text)),
            "DOI": Counter(_DOI.findall(text)),
            "math": Counter(re.sub(r"\s+", "", m.group(0)) for m in _MATH.finditer(text)),
            "cross-reference": Counter(re.sub(r"\s+", " ", m.group(0)).lower()
                                       for m in _REFS.finditer(text)),
        }
    a, b = bag(original), bag(rewrite)
    diffs = []
    for kind in a:
        missing = a[kind] - b[kind]
        added = b[kind] - a[kind]
        if missing or added:
            diffs.append((kind, sorted(missing.elements()), sorted(added.elements())))
    return diffs
