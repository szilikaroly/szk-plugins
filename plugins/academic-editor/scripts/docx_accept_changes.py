#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accept every tracked change in a .docx — the clean copy that ships alongside.

    docx_accept_changes.py manuscript_edited.docx -o manuscript_clean.docx
    docx_accept_changes.py manuscript_edited.docx -o clean.docx --keep-comments
    docx_accept_changes.py manuscript_edited.docx --reject -o original.docx

An editing service hands back two files: the tracked one the author works
through, and a clean one they can read as prose or drop into a submission
system. Producing the second by hand — or by asking the author to accept
everything in Word — loses the guarantee that the two files differ only by the
revisions. Here they do, by construction: `--reject` on the tracked file
reproduces the input to the editor byte-for-byte in content.

What it does, precisely
-----------------------
accept:  `w:ins` is unwrapped (its runs stay), `w:del` is removed with its text,
         an inserted paragraph mark stays, a deleted paragraph mark merges the
         paragraph into the next one.
reject:  the mirror image — `w:del` becomes ordinary text again (`w:delText` →
         `w:t`), `w:ins` is removed.
A deletion nested inside an insertion is a real thing Word produces (the editor
inserted text and then deleted part of it). Rejecting the insertion removes the
nested deletion with it, so `--reject` legitimately reports fewer `w:del` than
`--accept` on the same file. That is the semantics, not a miscount.

Comments are stripped by default, because a clean copy carries no queries; the
anchors (`commentRangeStart/End`, `commentReference`) go with them, or Word
reports the file as corrupt.

Needs lxml.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

try:
    from lxml import etree
except ImportError:  # pragma: no cover
    sys.exit("Hiányzó függőség: lxml. Telepítés: pip install lxml")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
def w(tag: str) -> str:
    return f"{{{W}}}{tag}"

REVISION_PARTS = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml",
                  "word/header1.xml", "word/header2.xml", "word/header3.xml",
                  "word/footer1.xml", "word/footer2.xml", "word/footer3.xml")

COMMENT_MARKS = ("commentRangeStart", "commentRangeEnd", "commentReference")


def unwrap(node) -> None:
    """Replace `node` with its children, in place."""
    parent = node.getparent()
    index = list(parent).index(node)
    tail = node.tail or ""
    for offset, child in enumerate(list(node)):
        node.remove(child)
        parent.insert(index + offset, child)
    parent.remove(node)
    if tail and index < len(parent):
        prev = parent[max(0, index - 1)]
        prev.tail = (prev.tail or "") + tail


def drop(node) -> None:
    node.getparent().remove(node)


def deltext_to_text(node) -> None:
    for dt in node.iter(w("delText")):
        dt.tag = w("t")


def process(root, reject: bool, keep_comments: bool) -> dict[str, int]:
    counts = {"ins": 0, "del": 0, "para_marks": 0, "comment_anchors": 0,
              "other_revisions": 0}

    # Paragraph-mark revisions live in w:pPr/w:rPr and must be handled before the
    # run-level pass, because accepting a deleted paragraph mark MERGES two
    # paragraphs — an operation that changes the tree the later pass walks.
    for ppr in list(root.iter(w("pPr"))):
        rpr = ppr.find(w("rPr"))
        if rpr is None:
            continue
        mark_ins = rpr.find(w("ins"))
        mark_del = rpr.find(w("del"))
        if mark_ins is not None:
            drop(mark_ins)
            counts["para_marks"] += 1
            if reject:
                _merge_with_next(ppr.getparent())
        if mark_del is not None:
            drop(mark_del)
            counts["para_marks"] += 1
            if not reject:
                _merge_with_next(ppr.getparent())

    for node in list(root.iter(w("ins"))):
        if node.getparent() is None:
            continue
        if reject:
            drop(node)
        else:
            unwrap(node)
        counts["ins"] += 1

    for node in list(root.iter(w("del"))):
        if node.getparent() is None:
            continue
        if reject:
            deltext_to_text(node)
            unwrap(node)
        else:
            drop(node)
        counts["del"] += 1

    # Formatting-only revisions (rPrChange, pPrChange, tblPrChange …) carry the
    # PREVIOUS formatting. Accepting means keeping the current formatting and
    # discarding the record; rejecting them properly would mean restoring it, and
    # this tool does not pretend to: it says how many it dropped.
    for tag in ("rPrChange", "pPrChange", "tblPrChange", "trPrChange", "tcPrChange",
                "sectPrChange", "cellIns", "cellDel", "cellMerge", "moveFrom",
                "moveTo", "moveFromRangeStart", "moveFromRangeEnd",
                "moveToRangeStart", "moveToRangeEnd"):
        for node in list(root.iter(w(tag))):
            if node.getparent() is None:
                continue
            if tag == "moveFrom":
                drop(node) if not reject else unwrap(node)
            elif tag == "moveTo":
                unwrap(node) if not reject else drop(node)
            else:
                drop(node)
            counts["other_revisions"] += 1

    if not keep_comments:
        for tag in COMMENT_MARKS:
            for node in list(root.iter(w(tag))):
                if node.getparent() is None:
                    continue
                parent = node.getparent()
                drop(node)
                counts["comment_anchors"] += 1
                # A run left holding only a comment reference is empty; remove it
                # so the clean file has no zero-width artefacts.
                if (parent.tag == w("r") and parent.find(w("t")) is None
                        and parent.getparent() is not None):
                    drop(parent)
    return counts


def _merge_with_next(paragraph) -> None:
    """Deleting a paragraph mark joins this paragraph to the following one."""
    if paragraph is None:
        return
    parent = paragraph.getparent()
    if parent is None:
        return
    idx = list(parent).index(paragraph)
    if idx + 1 >= len(parent):
        return
    nxt = parent[idx + 1]
    if nxt.tag != w("p"):
        return
    for child in list(nxt):
        if child.tag == w("pPr"):
            continue
        nxt.remove(child)
        paragraph.append(child)
    parent.remove(nxt)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--reject", action="store_true",
                    help="reject every change instead of accepting it")
    ap.add_argument("--keep-comments", action="store_true")
    args = ap.parse_args(argv)

    if not args.docx.exists():
        sys.exit(f"nincs ilyen fájl: {args.docx}")

    with zipfile.ZipFile(args.docx) as z:
        names = z.namelist()
        parts = {n: z.read(n) for n in names}

    total = {"ins": 0, "del": 0, "para_marks": 0, "comment_anchors": 0,
             "other_revisions": 0}
    for name in list(parts):
        if name not in REVISION_PARTS and not (
                name.startswith("word/header") or name.startswith("word/footer")):
            continue
        root = etree.fromstring(parts[name])
        counts = process(root, args.reject, args.keep_comments)
        for k, v in counts.items():
            total[k] += v
        parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                     standalone=True)

    if not args.keep_comments:
        parts.pop("word/comments.xml", None)
        parts.pop("word/commentsExtended.xml", None)
        parts.pop("word/commentsIds.xml", None)
        parts.pop("word/commentsExtensible.xml", None)
        ct = etree.fromstring(parts["[Content_Types].xml"])
        for o in list(ct):
            if (o.get("PartName") or "").startswith("/word/comments"):
                ct.remove(o)
        parts["[Content_Types].xml"] = etree.tostring(
            ct, xml_declaration=True, encoding="UTF-8", standalone=True)
        rels = etree.fromstring(parts["word/_rels/document.xml.rels"])
        for r in list(rels):
            if "comments" in (r.get("Target") or ""):
                rels.remove(r)
        parts["word/_rels/document.xml.rels"] = etree.tostring(
            rels, xml_declaration=True, encoding="UTF-8", standalone=True)

    verb = "elutasítva" if args.reject else "elfogadva"
    print(f"{total['ins']} beszúrás + {total['del']} törlés {verb}"
          f"; bekezdésjel-revízió: {total['para_marks']}"
          f"; egyéb revízió: {total['other_revisions']}"
          f"; eltávolított megjegyzés-horgony: {total['comment_anchors']}")

    out = args.out or args.docx.with_name(args.docx.stem + "_clean.docx")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in list(dict.fromkeys(list(names) + list(parts))):
            if n in parts:
                z.writestr(n, parts[n])
    print(f"Írva: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
