"""Raw .docx inspection — the things python-docx hides.

python-docx gives you the *accepted* text. A manuscript about to be submitted
can still carry unresolved tracked changes and reviewer comments inside the
package, and a journal opening the file will see them. This module reads
word/document.xml and word/comments.xml directly and reports what is still in
there, without accepting or rejecting anything.

Everything here degrades to "unknown" rather than raising: a .pdf, a .txt or a
corrupt archive simply yields a DocxFacts with nothing flagged.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class DocxFacts:
    is_docx: bool = False
    insertions: int = 0
    deletions: int = 0
    comments: int = 0
    revision_authors: list = field(default_factory=list)
    comment_authors: list = field(default_factory=list)
    sample_comment: str = ""
    sample_insertion: str = ""


def inspect(path) -> DocxFacts:
    p = Path(str(path)).expanduser()
    facts = DocxFacts()
    if p.suffix.lower() != ".docx" or not p.exists():
        return facts
    try:
        z = zipfile.ZipFile(p)
        names = set(z.namelist())
        if "word/document.xml" not in names:
            return facts
        facts.is_docx = True
        doc = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception:
        return facts

    facts.insertions = len(re.findall(r"<w:ins[ >]", doc))
    facts.deletions = len(re.findall(r"<w:del[ >]", doc))
    authors = set(re.findall(r'<w:(?:ins|del)\b[^>]*w:author="([^"]*)"', doc))
    facts.revision_authors = sorted(a for a in authors if a)

    m = re.search(r"<w:ins\b[^>]*>.*?<w:t[^>]*>(.*?)</w:t>", doc, re.S)
    if m:
        facts.sample_insertion = _clean(m.group(1))

    if "word/comments.xml" in names:
        try:
            c = z.read("word/comments.xml").decode("utf-8", "replace")
            facts.comments = len(re.findall(r"<w:comment[ >]", c))
            cauth = set(re.findall(r'<w:comment\b[^>]*w:author="([^"]*)"', c))
            facts.comment_authors = sorted(a for a in cauth if a)
            first = re.search(r"<w:comment\b[^>]*>(.*?)</w:comment>", c, re.S)
            if first:
                txt = " ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", first.group(1), re.S))
                facts.sample_comment = _clean(txt)
        except Exception:
            pass
    return facts


def _clean(s, n=70):
    s = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&apos;", "'"))
    return s[:n] + ("…" if len(s) > n else "")
