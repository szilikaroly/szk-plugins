#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure a target journal's current house style from its own recent papers.

    housestyle.py --journal "Frontiers in Endocrinology" --n 12 --out profile.json
    housestyle.py --issn 1664-2392 --years 3 --md profile.md
    housestyle.py --profile profile.json --compare manuscript.docx

Why measure instead of assume
-----------------------------
"Match the journal's style" is worthless as an instruction and checkable as a
number. Whether *this* journal's Results sections run 18 or 32 words to the
sentence, whether it hedges twice per thousand words or fifteen times, whether it
writes `P` or `p`, whether its headings are Title Case or sentence case, whether
first person is normal there or absent — every one of those is measurable from
what the journal has actually published in the last few years, and none of them
is guessable from its name.

So the profile is built from full texts, not from the guide for authors. A guide
for authors states policy; the papers state practice, and a reviewer's sense of
"this doesn't read like our journal" comes from practice.

Every number here is counted. Nothing is inferred by a language model — the
profile is meant to be quotable back to the author ("this journal's Discussion
sections average 24 words per sentence; yours average 38"), and a paraphrased
statistic cannot be quoted.

Source: Europe PMC — the Open Access subset only, because the measurement needs
the body text and the OA subset is the part that can be fetched legitimately.
Papers behind a paywall are counted in the denominator and reported as
unavailable, so the sample size is never quietly overstated.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = "academic-editor-housestyle/1.0 (mailto:{mail})"

HEDGES = re.compile(
    r"\b(may|might|could|would|appear(?:s|ed)?|seem(?:s|ed)?|suggest(?:s|ed|ing)?|"
    r"indicat(?:e|es|ed|ing)|likely|unlikely|possibl[ey]|probabl[ey]|potential(?:ly)?|"
    r"presumabl[ey]|apparent(?:ly)?|relatively|somewhat|tend(?:s|ed)? to|"
    r"it is conceivable|cannot be excluded|to some extent)\b", re.I)
FIRST_PERSON = re.compile(r"\b(we|our|us|I|my)\b")
PASSIVE = re.compile(
    r"\b(?:is|are|was|were|been|being|be)\s+(?:\w+ly\s+)?(\w+(?:ed|en|wn|ne))\b", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*")

#: Word-anchored. Without the boundary, "edema" matches inside "oedema",
#: "color" inside "colorectal" and "analys" inside "analysis" — so a British
#: paper scores as American, every gastroenterology paper scores as both, and
#: the word "analysis" makes every paper in existence look British.
UK_MARKERS = (r"\bcentres?\b", r"\bcolour", r"\bbehaviour", r"\banalyse[sd]?\b",
              r"\banalysing\b", r"\brandomis", r"\borganisation", r"\btumour",
              r"\boedema", r"\bpaediatric", r"\butilis", r"\blabelled",
              r"\bprogramme")
US_MARKERS = (r"\bcenters?\b", r"\bcolor(?!ect)", r"\bbehavior", r"\banalyze[sd]?\b",
              r"\banalyzing\b", r"\brandomiz", r"\borganization", r"\btumor",
              r"\b(?<!o)edema", r"\bpediatric", r"\butiliz", r"\blabeled",
              r"\bprogram(?!me)")


def fetch(url: str, email: str, timeout: int = 30) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA.format(mail=email)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return None


def search_journal(journal: str, issn: str, years: int, n: int, email: str,
                   article_type: str) -> list[dict]:
    bits = []
    if issn:
        bits.append(f'ISSN:"{issn}"')
    if journal:
        bits.append(f'JOURNAL:"{journal}"')
    if not bits:
        sys.exit("--journal vagy --issn kell")
    bits.append("OPEN_ACCESS:y")
    bits.append("HAS_FT:y")
    if article_type == "review":
        bits.append('PUB_TYPE:"review"')
    elif article_type == "research":
        bits.append('NOT PUB_TYPE:"review"')
    this_year = time.gmtime().tm_year
    bits.append(f"FIRST_PDATE:[{this_year - years} TO {this_year}]")
    q = urllib.parse.urlencode({
        "query": " AND ".join(bits), "format": "json", "resultType": "core",
        "pageSize": str(min(100, max(n * 3, 25))), "sort": "CITED desc",
    })
    data = fetch(f"{EPMC}/search?{q}", email)
    if not data:
        sys.exit("Europe PMC nem válaszolt")
    return ((json.loads(data).get("resultList") or {}).get("result") or [])


def fulltext(rec: dict, email: str) -> str | None:
    pmcid = rec.get("pmcid")
    if not pmcid:
        return None
    raw = fetch(f"{EPMC}/{pmcid}/fullTextXML", email)
    if not raw:
        return None
    try:
        return raw.decode("utf-8", "replace")
    except Exception:
        return None


# --------------------------------------------------------------------------- measure


#: Content that is not prose and would wreck every prose statistic if measured
#: as prose. A table dropped into a Results section produced a "71.8 words per
#: sentence" reading for a journal whose actual Results prose runs at ~25.
SKIP_TAGS = {"table-wrap", "table", "fig", "graphic", "disp-formula",
             "inline-formula", "ref-list", "back", "supplementary-material"}


def prose_text(el) -> str:
    """All text under `el` except the non-prose subtrees."""
    parts: list[str] = []

    def walk(node):
        for child in node:
            if child.tag in SKIP_TAGS:
                if child.tail:
                    parts.append(child.tail)
                continue
            if child.text:
                parts.append(child.text)
            walk(child)
            if child.tail:
                parts.append(child.tail)

    if el.text:
        parts.append(el.text)
    walk(el)
    return "".join(parts)


def jats_sections(xml_text: str) -> dict[str, str]:
    """{section-name: text}. JATS `sec-type` first, heading text as the fallback."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError:
        return {}
    out: dict[str, list[str]] = {}

    def norm(name: str) -> str:
        n = (name or "").lower()
        for key in ("introduction", "method", "result", "discussion", "conclusion"):
            if key in n:
                return {"method": "methods", "result": "results",
                        "conclusion": "conclusions"}.get(key, key)
        return ""

    abstract = root.find(".//abstract")
    if abstract is not None:
        out["abstract"] = [prose_text(abstract)]
        labels = [t.text for t in abstract.findall(".//title") if t.text]
        if labels:
            out["_abstract_labels"] = labels

    body = root.find(".//body")
    if body is not None:
        # Always keep a whole-body bucket. Narrative reviews — most of what many
        # journals publish — carry topical sections, not IMRaD ones, so an
        # IMRaD-only profile would silently describe two sections out of eight
        # and present that as the journal's style.
        out["body"] = [prose_text(body)]
        parent_of = {c: par for par in body.iter() for c in par}
        for sec in body.iter("sec"):
            title = sec.find("./title")
            name = norm(sec.get("sec-type") or (title.text if title is not None else ""))
            if not name:
                continue
            # Take the OUTERMOST classifiable section only. A nested "Methods"
            # inside a "Methods" would otherwise be measured twice and weight the
            # average toward whichever paper nests most deeply.
            node, nested = parent_of.get(sec), False
            while node is not None:
                if node.tag == "sec":
                    t = node.find("./title")
                    if norm(node.get("sec-type") or (t.text if t is not None else "")):
                        nested = True
                        break
                node = parent_of.get(node)
            if nested:
                continue
            out.setdefault(name, []).append(prose_text(sec))

    captions = []
    for fig in root.iter("fig"):
        cap = fig.find(".//caption")
        if cap is not None:
            captions.append(" ".join("".join(cap.itertext()).split()))
    if captions:
        out["_captions"] = captions

    heads = [t.text for t in root.iter("title") if t.text and len(t.text) < 70]
    if heads:
        out["_headings"] = heads
    return {k: (v if k.startswith("_") else "\n".join(v)) for k, v in out.items()}


def measure(text: str) -> dict:
    words = WORD.findall(text)
    n = len(words) or 1
    sents = [s for s in SENT_SPLIT.split(re.sub(r"\s+", " ", text)) if len(s) > 20]
    lens = [len(WORD.findall(s)) for s in sents]
    return {
        "words": len(words),
        "sentences": len(sents),
        "mean_sentence_words": round(sum(lens) / len(lens), 1) if lens else 0,
        "long_sentence_pct": round(100 * sum(1 for x in lens if x > 40) / len(lens), 1)
                             if lens else 0,
        "hedges_per_1k": round(1000 * len(HEDGES.findall(text)) / n, 1),
        "first_person_per_1k": round(1000 * len(FIRST_PERSON.findall(text)) / n, 1),
        "passive_per_1k": round(1000 * len(PASSIVE.findall(text)) / n, 1),
    }


def mechanics(text: str, xml_text: str = "") -> dict:
    # In-text citation style has to be read from the JATS markup, not from the
    # stripped text: the brackets or parentheses live in the <xref> element, and
    # stripping tags takes them with it. Counting on the stripped text reported
    # "no data" for every Open Access paper ever published.
    numeric = author_year = 0
    for m in re.finditer(r"<xref[^>]*ref-type=\"bibr\"[^>]*>(.*?)</xref>", xml_text, re.S):
        inner = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if re.fullmatch(r"[\[\(]?\d+[\]\)]?", inner):
            numeric += 1
        elif re.search(r"[A-Za-z]", inner):
            author_year += 1
    return {
        "numeric_xref": numeric,
        "author_year_xref": author_year,
        "p_lower": len(re.findall(r"(?<![A-Za-z])p\s*[=<>≤≥]", text)),
        "p_upper": len(re.findall(r"(?<![A-Za-z])P\s*[=<>≤≥]", text)),
        "pm_spaced": len(re.findall(r"\d\s+±\s+\d", text)),
        "pm_closed": len(re.findall(r"\d±\d", text)),
        "uk": sum(len(re.findall(m, text, re.I)) for m in UK_MARKERS),
        "us": sum(len(re.findall(m, text, re.I)) for m in US_MARKERS),
        "numeric_citations": len(re.findall(r"\[\d+(?:[,–-]\s*\d+)*\]", text)),
        "author_year_citations": len(re.findall(r"\([A-Z][a-z]+(?: et al\.)?,?\s+\d{4}\)", text)),
        "serial_comma": len(re.findall(r",\s+and\s+\w", text)),
        "no_serial_comma": len(re.findall(r"\w\s+and\s+\w+[.,]", text)),
    }


def build_profile(records: list[dict], email: str, n_target: int) -> dict:
    per_section: dict[str, list[dict]] = {}
    mech = Counter()
    caption_lens: list[int] = []
    heading_case = Counter()
    abstract_structured = 0
    abstract_labels = Counter()
    used: list[dict] = []
    no_fulltext = 0

    for rec in records:
        if len(used) >= n_target:
            break
        xml_text = fulltext(rec, email)
        if not xml_text:
            no_fulltext += 1
            continue
        secs = jats_sections(xml_text)
        if not secs.get("abstract") and not secs.get("discussion"):
            no_fulltext += 1
            continue
        used.append({
            "pmcid": rec.get("pmcid"), "doi": rec.get("doi"),
            "year": rec.get("pubYear"), "title": (rec.get("title") or "")[:120],
            "cited": rec.get("citedByCount"),
        })
        for name, body in secs.items():
            if name.startswith("_"):
                continue
            per_section.setdefault(name, []).append(measure(body))
        plain = re.sub(r"<[^>]+>", " ", xml_text)
        for k, v in mechanics(plain, xml_text).items():
            mech[k] += v
        for cap in secs.get("_captions", []):
            caption_lens.append(len(WORD.findall(cap)))
        for h in secs.get("_headings", []):
            words_ = [x for x in h.split() if x.isalpha()]
            if len(words_) >= 2:
                caps = sum(1 for x in words_[1:] if x[:1].isupper())
                heading_case["title"] += 1 if caps >= len(words_[1:]) * 0.6 else 0
                heading_case["sentence"] += 1 if caps < len(words_[1:]) * 0.6 else 0
        labels = secs.get("_abstract_labels") or []
        if len(labels) >= 3:
            abstract_structured += 1
            for lab in labels:
                abstract_labels[lab.strip().rstrip(":")] += 1
        time.sleep(0.2)

    sections_out = {}
    for name, rows in per_section.items():
        if not rows:
            continue
        sections_out[name] = {
            "n_papers": len(rows),
            "mean_sentence_words": round(
                sum(r["mean_sentence_words"] for r in rows) / len(rows), 1),
            "long_sentence_pct": round(
                sum(r["long_sentence_pct"] for r in rows) / len(rows), 1),
            "hedges_per_1k": round(sum(r["hedges_per_1k"] for r in rows) / len(rows), 1),
            "first_person_per_1k": round(
                sum(r["first_person_per_1k"] for r in rows) / len(rows), 1),
            "passive_per_1k": round(sum(r["passive_per_1k"] for r in rows) / len(rows), 1),
            "median_words": sorted(r["words"] for r in rows)[len(rows) // 2],
        }

    return {
        "n_papers_sampled": len(used),
        "n_no_fulltext": no_fulltext,
        "papers": used,
        "sections": sections_out,
        "mechanics": dict(mech),
        "figure_caption_words_median": (sorted(caption_lens)[len(caption_lens) // 2]
                                        if caption_lens else None),
        "heading_case": dict(heading_case),
        "abstract_structured_share": (round(abstract_structured / len(used), 2)
                                      if used else None),
        "abstract_labels": abstract_labels.most_common(12),
    }


# --------------------------------------------------------------------------- report


def _pick(a: int, b: int, name_a: str, name_b: str) -> str:
    if a == b == 0:
        return "nincs adat"
    total = a + b
    share = max(a, b) / total
    winner = name_a if a >= b else name_b
    if share >= 0.9:
        return f"**{winner}** ({max(a, b)}/{total})"
    return f"{winner} többségben, de vegyes ({a} {name_a} / {b} {name_b}) — kérdezd meg"


def to_markdown(profile: dict, label: str) -> str:
    L = [f"# Házistílus-profil — {label}", "",
         f"{profile['n_papers_sampled']} teljes szövegű, Open Access cikk mérve"
         + (f" ({profile['n_no_fulltext']} nem volt letölthető, ezek nincsenek benne)"
            if profile["n_no_fulltext"] else "") + ".", "",
         "Minden szám **számolt**, nem becsült. Ha a kézirat eltér valamelyiktől, az "
         "nem automatikusan hiba — de tudni kell róla, és a szerzőnek meg kell mondani.",
         "", "## Mondat- és regiszterszint szakaszonként", "",
         "| Szakasz | mondathossz | >40 szó | hedge/1k | E/1. sz./1k | passzív/1k | medián szó |",
         "|---|---|---|---|---|---|---|"]
    for name in ("abstract", "introduction", "methods", "results", "discussion",
                 "conclusions", "body"):
        s = profile["sections"].get(name)
        if not s:
            continue
        L.append(f"| {name} | {s['mean_sentence_words']} | {s['long_sentence_pct']}% | "
                 f"{s['hedges_per_1k']} | {s['first_person_per_1k']} | "
                 f"{s['passive_per_1k']} | {s['median_words']} |")

    m = profile["mechanics"]
    L += ["", "## Mechanika", "",
          f"- **`p` vs `P`:** {_pick(m.get('p_lower', 0), m.get('p_upper', 0), '`p`', '`P`')}",
          f"- **`±` szóköz:** {_pick(m.get('pm_spaced', 0), m.get('pm_closed', 0), 'szóközzel', 'szóköz nélkül')}",
          f"- **Helyesírás:** {_pick(m.get('uk', 0), m.get('us', 0), 'UK', 'US')}",
          f"- **Idézési forma a szövegben:** "
          f"{_pick(m.get('numeric_xref', 0) + m.get('numeric_citations', 0), m.get('author_year_xref', 0) + m.get('author_year_citations', 0), 'numerikus [1]', 'szerző–év (Kiss, 2024)')}",
          ]
    hc = profile.get("heading_case") or {}
    if hc:
        L.append(f"- **Alcímek:** {_pick(hc.get('title', 0), hc.get('sentence', 0), 'Title Case', 'sentence case')}")
    if profile.get("figure_caption_words_median") is not None:
        L.append(f"- **Ábrafelirat hossza:** medián {profile['figure_caption_words_median']} szó")
    share = profile.get("abstract_structured_share")
    if share is not None:
        L.append(f"- **Strukturált absztrakt:** a minta {int(share * 100)}%-a")
        if profile.get("abstract_labels"):
            L.append("  - gyakori címkék: "
                     + ", ".join(f"{k} ({v})" for k, v in profile["abstract_labels"][:8]))

    L += ["", "## Hogyan használd", "",
          "1. A **mondathossz** és a **hedge-sűrűség** a két szám, amit a lektorálás "
          "ténylegesen mozgat. Ha a kézirat Discussionje 38 szó/mondat, a folyóiraté "
          "pedig 24, akkor a mondatvágás nem ízlés, hanem illesztés — és ezt így is "
          "mondd meg a szerzőnek, a két számmal együtt.",
          "2. Az **E/1. személy** a legárulkodóbb: egy olyan folyóiratban, ahol a mért "
          "érték ~0, a „we found\" minden előfordulása kilóg; ahol 8/1000, ott a "
          "kiirtása teszi idegenné a szöveget.",
          "3. A **mechanikai** sorok közül csak azt vidd végig, ahol a minta egyértelmű "
          "(≥90%). A „vegyes\" jelzésűeket kérdezd meg a szerzőtől — a folyóirat maga "
          "sem következetes, tehát nincs mihez igazítani.",
          "4. Ez a profil **nem** nyelvhelyesség. Előbb a `language-mechanics.md` "
          "szerinti lektorálás, utána az illesztés ehhez a profilhoz.", "",
          "## A mért cikkek", ""]
    for p in profile["papers"]:
        L.append(f"- {p['year']} · {p['pmcid']} · {p['title']}")
    return "\n".join(L)


def compare(profile: dict, manuscript: Path) -> str:
    import manuscript_check as mc
    text = mc.read_text(manuscript)
    secs = mc.split_sections(text)
    L = [f"# Illesztés — {manuscript.name}", "",
         "| Szakasz | mondathossz (kézirat / folyóirat) | hedge/1k | E/1. sz./1k | passzív/1k |",
         "|---|---|---|---|---|"]
    for name in ("abstract", "introduction", "methods", "results", "discussion",
                 "conclusions"):
        body = secs.get(name)
        ref = profile["sections"].get(name)
        if not body or not ref:
            continue
        got = measure(body)
        def cell(a, b):
            flag = " ⚠" if b and abs(a - b) / max(b, 1) > 0.35 else ""
            return f"{a} / {b}{flag}"
        L.append(f"| {name} | {cell(got['mean_sentence_words'], ref['mean_sentence_words'])} "
                 f"| {cell(got['hedges_per_1k'], ref['hedges_per_1k'])} "
                 f"| {cell(got['first_person_per_1k'], ref['first_person_per_1k'])} "
                 f"| {cell(got['passive_per_1k'], ref['passive_per_1k'])} |")
    L += ["", "⚠ = 35%-nál nagyobb eltérés a folyóirat mért átlagától. Ez jelzés, nem "
          "ítélet: nézd meg, mi okozza, és csak akkor nyúlj hozzá, ha a szöveg tényleg "
          "emiatt olvasódik idegenül."]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--journal", default="")
    ap.add_argument("--issn", default="")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--n", type=int, default=10, help="how many full texts to measure")
    ap.add_argument("--type", dest="article_type", default="any",
                    choices=("any", "review", "research"))
    ap.add_argument("--out", type=Path, help="profile JSON")
    ap.add_argument("--md", type=Path, help="readable profile")
    ap.add_argument("--profile", type=Path, help="an existing profile, for --compare")
    ap.add_argument("--compare", type=Path, help="manuscript to measure against it")
    ap.add_argument("--email", default="")
    args = ap.parse_args(argv)

    email = args.email or "anonymous@example.org"

    if args.compare:
        if not args.profile:
            sys.exit("--compare mellé --profile kell")
        prof = json.loads(args.profile.read_text(encoding="utf-8"))
        print(compare(prof, args.compare))
        return 0

    label = args.journal or args.issn
    print(f"Europe PMC keresés: {label} (utolsó {args.years} év, OA teljes szöveg) ...")
    records = search_journal(args.journal, args.issn, args.years, args.n, email,
                             args.article_type)
    if not records:
        sys.exit("Nincs OA teljes szövegű találat. Ellenőrizd a folyóirat nevét/ISSN-jét, "
                 "vagy növeld a --years értéket. Egy zárt hozzáférésű folyóiratnál ez a "
                 "módszer nem működik — mondd meg ezt ahelyett, hogy találgatnál.")
    print(f"  {len(records)} jelölt; {args.n} teljes szöveg mérése ...")

    profile = build_profile(records, email, args.n)
    profile["journal"] = label
    profile["years"] = args.years
    profile["article_type"] = args.article_type

    if profile["n_papers_sampled"] < 3:
        print("FIGYELEM: 3-nál kevesebb teljes szöveg jött össze. Ez nem házistílus, "
              "hanem néhány cikk — ne hivatkozz rá átlagként.", file=sys.stderr)

    if args.out:
        args.out.write_text(json.dumps(profile, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"Profil: {args.out}")
    md = to_markdown(profile, label)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
        print(f"Olvasható profil: {args.md}")
    if not args.out and not args.md:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
