"""Extract text and coarse structure from a manuscript file.

Returns a Document with:
  .paragraphs : list of (text, is_heading_style)   -> feeds section splitting
  .text       : the whole plain text
  .sections   : dict from pc_lib.split_sections
  .source     : file type used

Prefers python-docx for .docx (keeps heading styles), PyMuPDF/pdftotext for PDF,
latextotext for .tex, and reads .txt/.md directly.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pc_lib


class Document:
    def __init__(self, paragraphs, source, path=None, sup_citations=None):
        self.paragraphs = paragraphs
        self.source = source
        self.path = path
        self.text = "\n".join(t for t, _ in paragraphs)
        self.sections = pc_lib.split_sections(paragraphs)
        # numeric citations carried by superscript runs instead of [n] brackets
        # (the default EndNote numbered style); empty for every other source
        self.sup_citations = set(sup_citations or ())


def _docx_paragraphs(d):
    """Paragraphs in document order, including those inside content controls.

    EndNote — like Word's own bibliography feature — wraps the generated
    reference list in a <w:sdt> content control, and python-docx's
    Document.paragraphs skips sdt content. On a field-managed manuscript that
    makes the entire reference list invisible, so `no-references` fires and
    every other reference check (duplicates, uncited entries, citations with no
    entry) silently never runs. Tables stay excluded, exactly as before.
    """
    try:
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
    except Exception:                                  # pragma: no cover
        return list(d.paragraphs)

    P, SDT, CONTENT = qn("w:p"), qn("w:sdt"), qn("w:sdtContent")

    def walk(el):
        for child in el:
            if child.tag == P:
                yield Paragraph(child, d)
            elif child.tag == SDT:
                content = child.find(CONTENT)
                if content is not None:
                    yield from walk(content)

    try:
        out = list(walk(d.element.body))
    except Exception:                                  # pragma: no cover
        return list(d.paragraphs)
    return out or list(d.paragraphs)


def _superscript_numbers(p):
    """Citation numbers carried by superscript runs: '1,2' or '47-49' -> {…}.

    A numbered EndNote or Word citation renders as a superscript run, never as
    '[n]', so a bracket-only scan finds nothing and the uncited / out-of-range
    cross-check is skipped on exactly those manuscripts that manage their
    references with a field code.
    """
    import re as _re
    out = set()
    for r in getattr(p, "runs", []):
        sup = None
        try:
            sup = r.font.superscript
        except Exception:                              # pragma: no cover
            sup = None
        if not sup:                                    # character-style case
            try:
                if 'w:val="superscript"' not in r._element.xml:
                    continue
            except Exception:                          # pragma: no cover
                continue
        txt = (r.text or "").strip()
        if not txt or not _re.fullmatch(r"[\d,\s‐-―-]+", txt):
            continue
        for part in txt.split(","):
            part = part.strip()
            m = _re.fullmatch(r"(\d{1,3})\s*[‐-―-]\s*(\d{1,3})", part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if a <= b and b - a < 100:
                    out.update(range(a, b + 1))
            elif part.isdigit():
                out.add(int(part))
    return out


def _docx_table_paragraphs(d):
    """Paragraphs inside table cells, in document order, nested tables included."""
    try:
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
    except Exception:                                  # pragma: no cover
        return []

    P, TBL = qn("w:p"), qn("w:tbl")
    SDT, CONTENT = qn("w:sdt"), qn("w:sdtContent")
    TR, TC = qn("w:tr"), qn("w:tc")

    def walk(el, in_table):
        for child in el:
            if child.tag == P:
                if in_table:
                    yield Paragraph(child, d)
            elif child.tag == TBL:
                yield from walk(child, True)
            elif child.tag in (TR, TC):
                yield from walk(child, in_table)
            elif child.tag == SDT:
                content = child.find(CONTENT)
                if content is not None:
                    yield from walk(content, in_table)

    try:
        return list(walk(d.element.body, False))
    except Exception:                                  # pragma: no cover
        return []


def _from_docx(path):
    """Return (paragraphs, superscript citation numbers).

    Table cells deliberately stay out of `paragraphs` — pulling them in would
    change section splitting and every word count — but their superscript
    citations are still harvested, because a review typically cites a large
    share of its references only from inside its evidence tables. Missing them
    turns the uncited-reference check into a false-positive generator.
    """
    import docx
    d = docx.Document(str(path))
    paras, sups = [], set()
    for p in _docx_paragraphs(d):
        t = p.text.strip()
        if not t:
            continue
        style = (p.style.name or "").lower() if p.style else ""
        is_head = style.startswith("heading") or style == "title"
        if "bibliography" not in style:
            sups |= _superscript_numbers(p)
        paras.append((t, is_head))
    for p in _docx_table_paragraphs(d):
        style = (p.style.name or "").lower() if p.style else ""
        if "bibliography" not in style:
            sups |= _superscript_numbers(p)
    return paras, sups


def _from_pdf(path):
    text = ""
    try:
        import fitz
        doc = fitz.open(str(path))
        text = "\n".join(pg.get_text() for pg in doc)
    except Exception:
        try:
            text = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                  capture_output=True, text=True).stdout
        except Exception:
            text = ""
    return _plain_to_paras(text)


def _from_tex(path):
    try:
        out = subprocess.run(["latextotext", str(path)],
                             capture_output=True, text=True).stdout
        if out.strip():
            return _plain_to_paras(out)
    except Exception:
        pass
    return _plain_to_paras(Path(path).read_text(errors="ignore"))


def _plain_to_paras(text):
    paras = []
    for line in (text or "").splitlines():
        t = line.strip()
        if t:
            paras.append((t, False))
    return paras


def load(path) -> Document:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"manuscript not found: {p}")
    suf = p.suffix.lower()
    if suf == ".docx":
        paras, sups = _from_docx(p)
        return Document(paras, "docx", p, sups)
    if suf == ".pdf":
        return Document(_from_pdf(p), "pdf", p)
    if suf in (".tex", ".latex"):
        return Document(_from_tex(p), "tex", p)
    if suf in (".txt", ".md", ".text"):
        return Document(_plain_to_paras(p.read_text(errors="ignore")), suf[1:], p)
    # try doctotext as a last resort (handles .doc, .odt, .rtf ...)
    try:
        out = subprocess.run(["doctotext", str(p)],
                             capture_output=True, text=True).stdout
        if out.strip():
            return Document(_plain_to_paras(out), "doctotext", p)
    except Exception:
        pass
    raise ValueError(f"unsupported file type: {suf}")
