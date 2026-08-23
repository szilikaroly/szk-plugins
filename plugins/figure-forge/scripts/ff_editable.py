"""Make the vector output actually editable, then prove that it is.

`svg.fonttype: none` and `pdf.fonttype: 42` are necessary and not sufficient. A
figure can satisfy both and still open badly:

* the SVG names exactly one font (`font-family: 'Arial'`). Open it on a machine
  without Arial — a Linux box, a co-author's laptop, a journal's conversion
  pipeline — and the renderer substitutes something with different metrics. The
  label-QC guarantee this plugin makes (no label outside its box, none over a
  curve) was computed against Arial's metrics and quietly stops holding;
* matplotlib names its groups `text_7`, `patch_2`, `PathCollection_1`. In
  Illustrator's Layers panel or Inkscape's Objects panel that is an
  undifferentiated list, so "editable" in practice means hunting by clicking;
* nothing checks afterwards. An SVG whose text was outlined looks identical in a
  browser and is not editable at all, and you find out when the copy editor asks
  for a two-character change and the answer is "re-render it".

So: harden the SVG after matplotlib writes it, and audit what was actually
written rather than trusting the rcParam that was supposed to produce it.
"""
from __future__ import annotations

import re
import html
from pathlib import Path

#: The stack every text element gets. Arial first (Nature house), then the
#: metric-compatible substitutes that exist on macOS, Windows, Linux and inside
#: most PDF pipelines, then the generic family so nothing falls back to a serif.
FONT_STACK = ("Arial, Helvetica, 'Helvetica Neue', 'Liberation Sans', "
              "'Nimbus Sans', 'DejaVu Sans', sans-serif")

INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

# Inside a style attribute the value runs to the next `;` or to the attribute's
# closing quote. An alternation that stopped at the first apostrophe truncated
# the fallback stack at `Arial, Helvetica,` — the audit then reported a single
# family and the substitution was not idempotent.
_FONT_IN_STYLE = re.compile(r'font-family:\s*([^;"]+)')
_FONT_ATTR = re.compile(r'font-family="([^"]*)"')
_TEXT_OPEN = re.compile(r"<text\b(?![^>]*xml:space)")
# Skip a group that already carries a label, or a second pass appends a second
# `inkscape:label` to every group and the editor shows duplicates.
_G_OPEN = re.compile(r'<g id="([^"]+)"(?![^>]*inkscape:label)')
_SVG_OPEN = re.compile(r"<svg\b([^>]*)>")


def _pretty(gid: str, text_lookup: dict) -> str | None:
    """A human name for a matplotlib group id, or None to leave it alone."""
    if gid in text_lookup:
        label = " ".join(text_lookup[gid].split())
        return f"text: {label[:48]}" if label else None
    m = re.match(r"^(figure|axes)_(\d+)$", gid)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m = re.match(r"^(xtick|ytick)_(\d+)$", gid)
    if m:
        return f"{m.group(1)[0]}-axis tick {m.group(2)}"
    m = re.match(r"^line2d_(\d+)$", gid)
    if m:
        return f"line {m.group(1)}"
    m = re.match(r"^patch_(\d+)$", gid)
    if m:
        return f"shape {m.group(1)}"
    m = re.match(r"^PathCollection_(\d+)$", gid)
    if m:
        return f"markers {m.group(1)}"
    m = re.match(r"^(matplotlib\.axis)_(\d+)$", gid)
    if m:
        return f"axis {m.group(2)}"
    return None


def _text_by_group(svg: str) -> dict:
    """{group id: text content} for every `<g id="text_N">` that holds a <text>."""
    out = {}
    for m in re.finditer(r'<g id="(text_\d+)">(.*?)</g>', svg, re.S):
        t = re.search(r"<text[^>]*>(.*?)</text>", m.group(2), re.S)
        if t:
            body = re.sub(r"<[^>]+>", "", t.group(1))
            out[m.group(1)] = body.strip()
    return out


def harden_svg(path, font_stack: str = FONT_STACK, layers: bool = True) -> dict:
    """Rewrite the SVG in place so it survives being opened somewhere else."""
    p = Path(path)
    svg = p.read_text(encoding="utf-8")
    report = {"font_stack_applied": 0, "layers_named": 0, "xml_space_added": 0}

    # 1. font fallback — inline styles and any attribute form
    def _stack(m):
        report["font_stack_applied"] += 1
        return f"font-family: {font_stack}"
    svg = _FONT_IN_STYLE.sub(_stack, svg)

    def _stack_attr(m):
        report["font_stack_applied"] += 1
        return f'font-family="{font_stack}"'
    svg = _FONT_ATTR.sub(_stack_attr, svg)

    # 2. leading and trailing spaces in a label are content, not formatting
    svg, n = _TEXT_OPEN.subn('<text xml:space="preserve"', svg)
    report["xml_space_added"] = n

    # 3. human-readable names in the editor's object tree
    if layers:
        text_lookup = _text_by_group(svg)

        def _name(m):
            gid = m.group(1)
            nice = _pretty(gid, text_lookup)
            if not nice:
                return m.group(0)
            report["layers_named"] += 1
            esc = nice.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
            return f'<g id="{gid}" inkscape:label="{esc}"'
        svg = _G_OPEN.sub(_name, svg)

        if report["layers_named"] and "xmlns:inkscape" not in svg:
            svg = _SVG_OPEN.sub(
                lambda m: f'<svg xmlns:inkscape="{INKSCAPE_NS}"{m.group(1)}>',
                svg, count=1)

    p.write_text(svg, encoding="utf-8")
    return report


# --------------------------------------------------------------------- audit

def audit_svg(path) -> dict:
    """What the file actually contains — not what the rcParams asked for."""
    svg = Path(path).read_text(encoding="utf-8")
    texts = re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)

    # A group named text_N that holds no <text> means the glyphs were outlined:
    # visually identical, completely uneditable, and invisible in a raster proof.
    groups = re.findall(r'<g id="(text_\d+)"[^>]*>(.*?)</g>', svg, re.S)
    outlined = [gid for gid, body in groups if "<text" not in body]

    families = set()
    for m in _FONT_IN_STYLE.finditer(svg):
        families.add(m.group(1).strip())
    for m in _FONT_ATTR.finditer(svg):
        families.add(m.group(1).strip())

    has_stack = any("," in f for f in families)
    # Unescape: a label reads `p&lt;0.05` in the file and `p<0.05` on screen.
    # Comparing the escaped form against a typography rule finds nothing and
    # reports a figure with wrong punctuation as clean.
    contents = [html.unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in texts]
    return {
        "file": str(path),
        "text_elements": len(texts),
        "outlined_text_groups": len(outlined),
        "font_families": sorted(families),
        "font_fallback_stack": has_stack,
        "named_layers": len(re.findall(r"inkscape:label=", svg)),
        "editable": len(texts) > 0 and not outlined,
        "labels": contents,
    }


def audit_pdf(path) -> dict:
    """Type 3 fonts are outlines pretending to be text. Type 42 / TrueType is text."""
    raw = Path(path).read_bytes()
    return {
        "file": str(path),
        "type3_fonts": raw.count(b"/Type3"),
        "truetype_embedded": raw.count(b"/FontFile2") + raw.count(b"/FontFile3"),
        "editable": b"/Type3" not in raw,
    }


def audit_line(report: dict) -> str:
    """One line for the CLI, naming the failure rather than a status word."""
    if report.get("outlined_text_groups"):
        return (f"  editability: NOT EDITABLE — "
                f"{report['outlined_text_groups']} label group(s) were outlined "
                f"to paths; check svg.fonttype")
    bits = [f"{report['text_elements']} labels as real text"]
    if report.get("font_fallback_stack"):
        bits.append("font fallback stack")
    else:
        bits.append("NO font fallback — the SVG names one font only")
    if report.get("named_layers"):
        bits.append(f"{report['named_layers']} named layers")
    return "  editability: " + ", ".join(bits)
