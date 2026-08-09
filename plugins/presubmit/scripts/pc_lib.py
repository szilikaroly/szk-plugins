"""Shared types and helpers for Presubmit.

A Finding is one issue with a severity, a machine code, a human message, an
optional location and an optional fix hint. Everything the checkers return is a
list of Finding; the CLI groups, scores and prints them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

# severities, ordered
ERROR = "error"     # will likely trigger rejection / desk-return
WARN = "warn"       # should fix before submitting
INFO = "info"       # worth a look, not blocking
SEV_RANK = {ERROR: 0, WARN: 1, INFO: 2}


@dataclass
class Finding:
    category: str
    severity: str
    code: str
    message: str
    where: str = ""          # section name or short context
    fix: str = ""            # what to do about it

    def as_dict(self):
        return asdict(self)


def F(category, severity, code, message, where="", fix=""):
    return Finding(category, severity, code, message, where, fix)


# ---- section splitting -------------------------------------------------------
# Canonical section names we recognise, mapped to a normalised key. Order-free.
SECTION_ALIASES = {
    "abstract": "abstract",
    "keywords": "keywords", "key words": "keywords",
    "introduction": "introduction", "background": "introduction",
    "methods": "methods", "materials and methods": "methods",
    "material and methods": "methods", "methodology": "methods",
    "patients and methods": "methods", "subjects and methods": "methods",
    "case": "case presentation", "case report": "case presentation",
    "case presentation": "case presentation", "case description": "case presentation",
    "results": "results", "findings": "results",
    "results and discussion": "results",
    "discussion": "discussion",
    "conclusion": "conclusions", "conclusions": "conclusions",
    "references": "references", "bibliography": "references",
    "acknowledgements": "acknowledgements", "acknowledgments": "acknowledgements",
    "funding": "funding", "financial support": "funding",
    "conflict of interest": "conflict of interest",
    "conflicts of interest": "conflict of interest",
    "competing interests": "conflict of interest",
    "declaration of interest": "conflict of interest",
    "disclosures": "conflict of interest",
    "ethics": "ethics approval", "ethics approval": "ethics approval",
    "ethical approval": "ethics approval",
    "data availability": "data availability",
    "author contributions": "author contributions",
    "informed consent": "informed consent",
}

_HEADING_MAX_WORDS = 8


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]", "", s.strip().lower()).strip()


def looks_like_heading(line: str, styled=False) -> str | None:
    """Return the normalised section key if `line` is a section heading, else
    None. `styled` is True when the source (docx) already tagged it a heading.
    """
    raw = line.strip().rstrip(":.").strip()
    if not raw:
        return None
    key = _norm(raw)
    key = re.sub(r"^\d+[.\)]?\s*", "", key)  # strip leading numbering
    if key in SECTION_ALIASES:
        return SECTION_ALIASES[key]
    if styled and len(raw.split()) <= _HEADING_MAX_WORDS:
        return key or None
    # ALLCAPS short standalone line is a strong heading signal. We deliberately
    # do NOT treat Title-Case short lines as headings — that would misread the
    # manuscript title and author names as section headings.
    if (len(raw.split()) <= _HEADING_MAX_WORDS and not raw.endswith(".")
            and raw.isupper() and len(raw) > 2):
        return SECTION_ALIASES.get(key, key)
    return None


def split_sections(paragraphs):
    """paragraphs: list of (text, is_heading_style). Returns dict
    section_key -> body text, plus '_preamble' for anything before the first
    heading (usually title/authors/affiliations)."""
    sections = {}
    order = []
    current = "_preamble"
    buf = []
    for text, styled in paragraphs:
        key = looks_like_heading(text, styled)
        if key:
            sections.setdefault(current, [])
            sections[current].append("\n".join(buf))
            buf = []
            current = key
            if key not in order:
                order.append(key)
        else:
            buf.append(text)
    sections.setdefault(current, [])
    sections[current].append("\n".join(buf))
    out = {k: "\n".join(v).strip() for k, v in sections.items()}
    out["_order"] = order
    return out


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def load_profile(name: str):
    here = Path(__file__).resolve().parent.parent / "profiles"
    p = here / f"{name.lower()}.json"
    if not p.exists():
        p = here / "generic.json"
    return json.loads(p.read_text())


def list_profiles():
    here = Path(__file__).resolve().parent.parent / "profiles"
    return sorted(p.stem for p in here.glob("*.json"))
