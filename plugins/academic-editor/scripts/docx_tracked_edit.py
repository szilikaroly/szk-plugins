#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply {find, replace, comment} edits to a .docx as REAL Word tracked changes.

    docx_tracked_edit.py manuscript.docx edits.json -o manuscript_edited.docx
    docx_tracked_edit.py manuscript.docx edits.json -o out.docx --author "K. Szili, MD"
    docx_tracked_edit.py manuscript.docx edits.json --dry-run

edits.json
----------
    [
      {"find":    "increase risk of developing RBD",
       "replace": "increase the risk of developing RBD"},

      {"find":    "the reducing score rates",
       "replace": "the changes",
       "comment": "Changed throughout this paragraph because you appear to be
                   describing changes in general (some of which are increases)
                   rather than reductions. Please check carefully.",
       "count":   0}
    ]

`count` is how many occurrences to change: 1 (default) or 0 for every occurrence.
`comment` is optional and anchors to the edited span.

Why the file is written this way
--------------------------------
The deliverable of a professional edit is a document the author can *reject*.
That means genuine `w:ins`/`w:del` revision marks — not a rewritten paragraph, not
coloured text, not a diff in a side file. An author who cannot click "Reject" on a
single change has not been given an editable manuscript; they have been given a
replacement of their own.

So this operates on `word/document.xml` directly rather than through a document
model: every other part of the package is copied through byte-for-byte, which is
what keeps styles, numbering, embedded images, equations and the reference field
codes intact. A round-trip through a document library is where those get quietly
dropped.

Run splitting is the whole difficulty. A phrase almost never lives in one `w:r`:
Word breaks runs at every formatting change and at every spell-check boundary, so
"the risk of" can be four runs. The matched span is therefore located in the
paragraph's *concatenated* text, and the runs are rebuilt around it — prefix,
deleted middle, inserted replacement, suffix — with the original `w:rPr` carried
onto each piece so the edit does not silently restyle the sentence.

Needs lxml. No other dependency.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from lxml import etree
except ImportError:  # pragma: no cover
    sys.exit("Hiányzó függőség: lxml. Telepítés: pip install lxml")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
def w(tag: str) -> str:
    return f"{{{W}}}{tag}"

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

COMMENTS_CT = ("application/vnd.openxmlformats-officedocument."
               "wordprocessingml.comments+xml")
COMMENTS_REL = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships/comments")


# --------------------------------------------------------------------------- runs


def run_texts(paragraph) -> list[tuple[object, str]]:
    """(run element, its text) for runs that carry visible text, in order.

    Only direct-child runs. Text already inside a `w:del` is not in the document
    the author sees, so matching it would anchor an edit to deleted text; text
    inside an existing `w:ins` is skipped for the same reason in reverse — editing
    someone else's pending insertion silently rewrites their proposal. Run this on
    a clean manuscript, and read any existing revisions first.
    """
    out = []
    for r in paragraph.findall(f"{w('r')}"):
        t = r.find(w("t"))
        if t is not None:
            out.append((r, t.text or ""))
    return out


def clone_rpr(run):
    rpr = run.find(w("rPr"))
    return None if rpr is None else etree.fromstring(etree.tostring(rpr))


def make_run(text: str, rpr, deleted: bool = False):
    r = etree.Element(w("r"))
    if rpr is not None:
        r.append(etree.fromstring(etree.tostring(rpr)))
    t = etree.SubElement(r, w("delText") if deleted else w("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return r


class IdGen:
    def __init__(self, start: int = 1000):
        self.n = start

    def __call__(self) -> str:
        self.n += 1
        return str(self.n)


def apply_to_paragraph(paragraph, find: str, replace: str, comment_id: str | None,
                       author: str, stamp: str, ids: IdGen) -> bool:
    """Replace the FIRST occurrence of `find` in this paragraph. True if it hit."""
    runs = run_texts(paragraph)
    if not runs:
        return False
    joined = "".join(t for _, t in runs)
    at = joined.find(find)
    if at < 0:
        return False
    end = at + len(find)

    # Map the character span back onto runs.
    spans: list[tuple[object, int, int]] = []   # run, start, end (absolute)
    pos = 0
    for r, t in runs:
        spans.append((r, pos, pos + len(t)))
        pos += len(t)

    touched = [(r, s, e) for r, s, e in spans if e > at and s < end]
    first_run = touched[0][0]
    rpr = clone_rpr(first_run)
    anchor = list(paragraph).index(first_run)

    lookup = {id(r): t for r, t in runs}
    prefix = lookup[id(touched[0][0])][: at - touched[0][1]]
    suffix = lookup[id(touched[-1][0])][end - touched[-1][1]:]

    for r, _, _ in touched:
        paragraph.remove(r)

    new_nodes = []
    if prefix:
        new_nodes.append(make_run(prefix, rpr))
    if comment_id is not None:
        crs = etree.Element(w("commentRangeStart"))
        crs.set(w("id"), comment_id)
        new_nodes.append(crs)

    # Deletion and insertion, in that order: Word shows the original struck
    # through and the replacement after it, which is how an author reads a
    # substitution.
    if find:
        d = etree.Element(w("del"))
        d.set(w("id"), ids()); d.set(w("author"), author); d.set(w("date"), stamp)
        d.append(make_run(find, rpr, deleted=True))
        new_nodes.append(d)
    if replace:
        i = etree.Element(w("ins"))
        i.set(w("id"), ids()); i.set(w("author"), author); i.set(w("date"), stamp)
        i.append(make_run(replace, rpr))
        new_nodes.append(i)

    if comment_id is not None:
        cre = etree.Element(w("commentRangeEnd"))
        cre.set(w("id"), comment_id)
        new_nodes.append(cre)
        ref = etree.Element(w("r"))
        rpr2 = etree.SubElement(ref, w("rPr"))
        style = etree.SubElement(rpr2, w("rStyle"))
        style.set(w("val"), "CommentReference")
        cr = etree.SubElement(ref, w("commentReference"))
        cr.set(w("id"), comment_id)
        new_nodes.append(ref)

    if suffix:
        new_nodes.append(make_run(suffix, rpr))

    for offset, node in enumerate(new_nodes):
        paragraph.insert(anchor + offset, node)
    return True


# --------------------------------------------------------------------------- comments part


COMMENTS_SKELETON = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<w:comments xmlns:w="{W}"></w:comments>'
)


def add_comment(comments_root, cid: str, text: str, author: str, stamp: str,
                initials: str) -> None:
    c = etree.SubElement(comments_root, w("comment"))
    c.set(w("id"), cid); c.set(w("author"), author)
    c.set(w("date"), stamp); c.set(w("initials"), initials)
    for line in text.split("\n\n"):
        p = etree.SubElement(c, w("p"))
        r = etree.SubElement(p, w("r"))
        t = etree.SubElement(r, w("t"))
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = re.sub(r"\s+", " ", line).strip()


def ensure_comment_wiring(names: list[str], ct_xml: bytes, rels_xml: bytes
                          ) -> tuple[bytes, bytes]:
    ct = etree.fromstring(ct_xml)
    if not any(o.get("PartName") == "/word/comments.xml"
               for o in ct.findall(f"{{{CT}}}Override")):
        o = etree.SubElement(ct, f"{{{CT}}}Override")
        o.set("PartName", "/word/comments.xml")
        o.set("ContentType", COMMENTS_CT)

    rels = etree.fromstring(rels_xml)
    if not any(r.get("Type") == COMMENTS_REL
               for r in rels.findall(f"{{{REL}}}Relationship")):
        existing = {r.get("Id") for r in rels.findall(f"{{{REL}}}Relationship")}
        n = 1
        while f"rIdComments{n}" in existing:
            n += 1
        r = etree.SubElement(rels, f"{{{REL}}}Relationship")
        r.set("Id", f"rIdComments{n}")
        r.set("Type", COMMENTS_REL)
        r.set("Target", "comments.xml")
    return (etree.tostring(ct, xml_declaration=True, encoding="UTF-8", standalone=True),
            etree.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone=True))


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("edits", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--author", default="Academic Editor")
    ap.add_argument("--initials", default="AE")
    ap.add_argument("--dry-run", action="store_true",
                    help="report which edits would match; write nothing")
    args = ap.parse_args(argv)

    if not args.docx.exists():
        sys.exit(f"nincs ilyen fájl: {args.docx}")
    edits = json.loads(args.edits.read_text(encoding="utf-8"))
    if isinstance(edits, dict):
        edits = edits.get("edits", [])
    if not isinstance(edits, list):
        sys.exit("az edits.json gyökere lista (vagy {\"edits\": [...]}) legyen")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = IdGen()

    with zipfile.ZipFile(args.docx) as z:
        names = z.namelist()
        parts = {n: z.read(n) for n in names}

    doc = etree.fromstring(parts["word/document.xml"])
    paragraphs = doc.findall(f".//{w('p')}")

    comments_root = etree.fromstring(
        parts.get("word/comments.xml", COMMENTS_SKELETON.encode()))
    used_cids = {c.get(w("id")) for c in comments_root.findall(w("comment"))}
    next_cid = 0

    applied = 0
    missed: list[str] = []
    for e in edits:
        find = e.get("find", "")
        replace = e.get("replace", "")
        if not find:
            missed.append("(üres 'find')")
            continue
        want = int(e.get("count", 1)) or 10_000
        hits = 0
        for p in paragraphs:
            while hits < want:
                cid = None
                if e.get("comment") and hits == 0:
                    while str(next_cid) in used_cids:
                        next_cid += 1
                    cid = str(next_cid)
                    used_cids.add(cid)
                if not apply_to_paragraph(p, find, replace, cid, args.author, stamp, ids):
                    if cid is not None:
                        used_cids.discard(cid)
                    break
                if cid is not None:
                    add_comment(comments_root, cid, e["comment"], args.author, stamp,
                                args.initials)
                hits += 1
                applied += 1
            if hits >= want:
                break
        if hits == 0:
            missed.append(find[:70])

    print(f"Alkalmazott szerkesztés: {applied}")
    if missed:
        print(f"NEM TALÁLT ({len(missed)}) — a 'find' szövegének BETŰRE pontosan kell "
              "egyeznie a kézirattal (idézőjelek, kötőjelek, szóközök is):")
        for m in missed:
            print(f"  · {m}")
    n_comments = len(comments_root.findall(w("comment")))
    print(f"Szerkesztői kérdés a dokumentumban: {n_comments}")

    if args.dry_run:
        print("(--dry-run: semmit nem írtam ki)")
        return 1 if missed else 0

    out = args.out or args.docx.with_name(args.docx.stem + "_edited.docx")
    parts["word/document.xml"] = etree.tostring(
        doc, xml_declaration=True, encoding="UTF-8", standalone=True)
    if n_comments:
        parts["word/comments.xml"] = etree.tostring(
            comments_root, xml_declaration=True, encoding="UTF-8", standalone=True)
        parts["[Content_Types].xml"], parts["word/_rels/document.xml.rels"] = \
            ensure_comment_wiring(list(parts), parts["[Content_Types].xml"],
                                  parts["word/_rels/document.xml.rels"])

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        # Original order preserved; Word tolerates any order but diffing tools do not.
        for n in list(dict.fromkeys(list(names) + list(parts))):
            if n in parts:
                z.writestr(n, parts[n])
    print(f"Írva: {out}")
    print("Nyisd meg Wordben: Review ▸ Track Changes ▸ All Markup — minden edit "
          "külön elfogadható/elutasítható.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
