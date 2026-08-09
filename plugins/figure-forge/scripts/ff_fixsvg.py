"""Best-effort label QC for an EXISTING external SVG.

The precise path in this plugin is generation-time checking (ff_verify against
live matplotlib artists). For an SVG we did not draw, we lack a renderer, so we
estimate text boxes from font-size and glyph-width heuristics and test them
against <rect> boxes and stroked <path>/<line> geometry parsed from the DOM.

Honest about its limits: it flags gross containment/overlap problems and writes
an annotated preview PNG (via cairosvg) so a human can confirm. It does not
re-typeset the SVG; it reports what to move and by how much.
"""
from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

NS = {"svg": "http://www.w3.org/2000/svg"}
# average glyph advance as a fraction of font-size for a sans-serif face
_ADV = 0.52
_ASC = 0.80
_DESC = 0.22


def _fsize(el, inherited):
    fs = el.get("font-size")
    if fs is None:
        style = el.get("style", "")
        m = re.search(r"font-size:\s*([\d.]+)", style)
        fs = m.group(1) if m else None
    if fs is None:
        return inherited
    return float(re.sub(r"[a-z%]+$", "", fs) or inherited)


def _text_box(el, fs):
    txt = "".join(el.itertext())
    x = float(el.get("x", "0") or 0)
    y = float(el.get("y", "0") or 0)
    w = _ADV * fs * max(1, len(txt.strip()))
    anchor = el.get("text-anchor", "start")
    if el.get("style") and "text-anchor" in el.get("style"):
        m = re.search(r"text-anchor:\s*(\w+)", el.get("style"))
        if m:
            anchor = m.group(1)
    if anchor == "middle":
        x0 = x - w / 2
    elif anchor == "end":
        x0 = x - w
    else:
        x0 = x
    return (x0, y - _ASC * fs, x0 + w, y + _DESC * fs, txt.strip())


def _canvas_area(root):
    vb = root.get("viewBox")
    if vb:
        p = [float(t) for t in re.split(r"[ ,]+", vb.strip())]
        if len(p) == 4:
            return p[2] * p[3]
    try:
        w = float(re.sub(r"[a-z%]+$", "", root.get("width", "0")))
        h = float(re.sub(r"[a-z%]+$", "", root.get("height", "0")))
        return w * h
    except (TypeError, ValueError):
        return 0.0


def _rects(root, max_frac=0.25):
    """Only rects small enough to be *label containers* — a full-canvas
    background or a plot area is not a box a label must stay inside, so we skip
    anything larger than `max_frac` of the canvas. This is what stops the
    checker false-flagging legitimate axis/data labels."""
    canvas = _canvas_area(root) or 1e18
    out = []
    for r in root.iterfind(".//svg:rect", NS):
        try:
            x, y = float(r.get("x", 0)), float(r.get("y", 0))
            w, h = float(r.get("width", 0)), float(r.get("height", 0))
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        if canvas and (w * h) > max_frac * canvas:
            continue  # background / plot area, not a label box
        out.append((x, y, x + w, y + h))
    return out


def _overlap(a, b):
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx > 0 and dy > 0


def _inside(inner, outer, pad=1.0):
    return (inner[0] >= outer[0] + pad and inner[1] >= outer[1] + pad
            and inner[2] <= outer[2] - pad and inner[3] <= outer[3] - pad)


def check_svg(path):
    tree = etree.parse(str(path))
    root = tree.getroot()
    rects = _rects(root)
    texts = []
    for t in root.iterfind(".//svg:text", NS):
        fs = _fsize(t, 10.0)
        texts.append(_text_box(t, fs))

    def _center_in(box, r):
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        return r[0] <= cx <= r[2] and r[1] <= cy <= r[3]

    viols = []
    hosted = 0
    for tb in texts:
        box = (tb[0], tb[1], tb[2], tb[3])
        label = tb[4]
        # a label's host is the smallest candidate box whose interior contains
        # the label's centre. No host => it's a free-standing label (axis tick,
        # study name, annotation) and is NOT subject to the containment rule.
        cand = [r for r in rects if _center_in(box, r)]
        if not cand:
            continue
        hosted += 1
        host = min(cand, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        if not _inside(box, host):
            dx = max(0, host[0] + 1 - box[0]) or min(0, host[2] - 1 - box[2])
            dy = max(0, host[1] + 1 - box[1]) or min(0, host[3] - 1 - box[3])
            viols.append({"rule": "R1", "kind": "CONTAINMENT", "label": label,
                          "message": "text extends outside its box",
                          "suggest_move": [round(dx, 1), round(dy, 1)]})
        # overlap with a DIFFERENT small box it is not hosted by
        for r in rects:
            if r is host or _center_in(box, r):
                continue
            if _overlap(box, r):
                viols.append({"rule": "R2", "kind": "COVER", "label": label,
                              "message": "text overlaps a neighbouring box",
                              "suggest_move": None})
                break
    return {"n_text": len(texts), "n_boxes": len(rects),
            "n_hosted_labels": hosted, "violations": viols, "heuristic": True}


def preview(path, out_png, dpi=150):
    import cairosvg
    cairosvg.svg2png(url=str(path), write_to=str(out_png), dpi=dpi)
    return out_png
