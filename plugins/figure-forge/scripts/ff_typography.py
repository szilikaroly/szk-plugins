"""Sign is not punctuation. One module that knows the difference.

A figure that writes `-0.42` with a hyphen-minus, `12-24` with the same
character, and `follow-up` with it again has used one glyph for three different
things. On screen it passes; at 600 dpi in print, and to a copy editor, it reads
as sloppy — and in a forest plot the hyphen sitting where a minus belongs is
narrower and lower than the digits beside it, so a column of negative estimates
visibly fails to line up.

The three characters, and what each one is for
----------------------------------------------
    -  U+002D  HYPHEN-MINUS   joins words: follow-up, Kruskal-Wallis, IL-6
    −  U+2212  MINUS SIGN     signs a number: −0.42, Δ = −1.5
    –  U+2013  EN DASH        spans a range: 12–24 months, 2019–2021

Matplotlib already gets tick labels right (`axes.unicode_minus`). Everything a
caller supplies — axis titles, study names, node text, legend entries, direct
labels — arrives as raw ASCII and was, until this module, rendered with whatever
the author typed.

What it will not do
-------------------
Corrupt an identifier. `IL-6`, `HLA-B27`, `COVID-19`, `2-fold`, `p-value` and
`NCT01032434` all keep their hyphens, because every rule that could touch them
requires digits on BOTH sides of the separator with no letter adjacent. Every
substitution is also reported, never silent: `tx_report()` returns what changed
and why, and the CLI prints the tally. A typographic rule that quietly edits data
is worse than no rule.

Mathtext is protected. Anything between `$...$` is passed through untouched, so
`$\\Delta$ = $-1.5$` renders as matplotlib intends.
"""
from __future__ import annotations

import re
import unicodedata

MINUS = "−"     # −
ENDASH = "–"    # –
EMDASH = "—"    # —
TIMES = "×"     # ×
PLUSMINUS = "±"  # ±
LE, GE, NE, APPROX = "≤", "≥", "≠", "≈"
DEGREE, MICRO, PERMILLE, MIDDOT = "°", "µ", "‰", "·"

#: Every non-ASCII character this module can introduce. The glyph check tests
#: exactly this set against the resolved font, because a substitution that
#: renders as a hollow box is worse than the ASCII it replaced.
INTRODUCED = {MINUS, ENDASH, EMDASH, TIMES, PLUSMINUS, LE, GE, NE, APPROX,
              DEGREE, MICRO, PERMILLE, MIDDOT, "²", "³"}

#: Superscripted unit forms. An explicit map, not a rule: `mm3` is a volume but
#: `H2O` is not a squared H, and no regex tells them apart reliably.
SUPERSCRIPT_UNITS = {
    "mm2": "mm²", "mm3": "mm³",
    "cm2": "cm²", "cm3": "cm³",
    "m2": "m²", "m3": "m³",
    "km2": "km²", "km3": "km³",
    "nm2": "nm²", "nm3": "nm³",
    "um2": "µm²", "um3": "µm³",
    "µm2": "µm²", "µm3": "µm³",
}

#: Rules run in this order and the order is load-bearing. Ranges must be settled
#: before signs, or `12-24` becomes `12−24` — a subtraction where a span was
#: meant. Each entry is (name, pattern, replacement).
_RULES: list[tuple[str, re.Pattern, str]] = [
    # --- unambiguous operator spellings -------------------------------------
    ("plus-minus", re.compile(r"\+\s*/?\s*-(?=\s*\d|\s|$)"), PLUSMINUS),
    ("less-equal", re.compile(r"<\s*="), LE),
    ("greater-equal", re.compile(r">\s*="), GE),
    ("not-equal", re.compile(r"!\s*=|<\s*>"), NE),
    ("approx", re.compile(r"~\s*="), APPROX),

    # --- range: digits on BOTH sides, no letter adjacent --------------------
    # `12-24` `2019-2021` `0.5-1.2` become spans. `IL-6`, `2-fold` and
    # `COVID-19` cannot match: each needs a digit on the far side too.
    # A thousands separator belongs INSIDE a number; a trailing comma does not.
    # `[\d.,]*` swallowed the comma in `(-0.71, -0.13)` and turned the second
    # confidence limit into a range: `(−0.71,–0.13)`. Each separator must now be
    # followed by digits to be part of the number at all.
    ("range-en-dash",
     re.compile(r"(?<![A-Za-z0-9.])(\d+(?:[.,]\d+)*)\s*-\s*"
                r"(\d+(?:[.,]\d+)*)(?![A-Za-z])"),
     r"\1" + ENDASH + r"\2"),

    # --- sign: a hyphen directly before a number, with no word before it ----
    ("minus-sign", re.compile(r"(?<![\w.])-(?=\d|\.\d)"), MINUS),

    # --- multiplication -----------------------------------------------------
    ("times-between", re.compile(r"(?<=\d)\s*[xX]\s*(?=\d)"), " " + TIMES + " "),
    ("times-magnification", re.compile(r"(?<=\d)[xX](?![\w])"), TIMES),

    # --- units --------------------------------------------------------------
    # SI sets a space before the degree sign: 37 °C, not 37°C.
    ("degree-celsius", re.compile(r"(?<=\d)\s*(?:deg|degrees)\s*C\b"),
     " " + DEGREE + "C"),
    ("micro-metre", re.compile(r"(?<=\d)\s*um\b"), " " + MICRO + "m"),
]

#: Spacing around relational operators — Nature sets `p < 0.05`, not `p<0.05`.
#: Separated from the rules above because it changes spacing rather than
#: characters, and a caller may reasonably want one without the other.
_SPACING = [
    ("operator-spacing",
     re.compile(r"(?<=[A-Za-z\d\)])\s*([<>=" + LE + GE + NE + APPROX + r"])\s*"
                r"(?=[\d.\-" + MINUS + r"])"),
     r" \1 "),
]

_MATH = re.compile(r"(\$[^$]*\$)")
_HAS_EQUATION = re.compile(r"[A-Za-z0-9)]\s*=\s*[^=]")

ENABLED = True

#: Every substitution made since the process started. The CLI prints a tally
#: from this and writes it into the QC audit, so a reader of the figure can see
#: which characters the tool changed and check them. A typographic rule applied
#: without a record is indistinguishable from a typo.
LOG: list[dict] = []


def _apply(segment: str, rules, log: list) -> str:
    for name, pat, rep in rules:
        def _sub(m):
            before = m.group(0)
            after = m.expand(rep) if "\\" in rep else rep
            if before != after:
                log.append({"rule": name, "from": before, "to": after})
            return after
        segment = pat.sub(_sub, segment)
    return segment


def tx_report(s, *, spacing: bool = True, superscripts: bool = True):
    """(converted string, [{rule, from, to}, ...]).

    Returns the input untouched when typography is disabled or the value is not
    a string, so callers can wrap anything without type-checking first.
    """
    if not ENABLED or not isinstance(s, str) or not s:
        return s, []
    log: list[dict] = []

    # An equation is not a range. `5-3=2` means subtraction; `12-24 months`
    # means a span. The presence of `=` is the only signal available in a bare
    # label string, and guessing wrong the other way turns data into a typo.
    rules = list(_RULES)
    if _HAS_EQUATION.search(s):
        rules = [r for r in rules if r[0] != "range-en-dash"]
        rules.insert(0, ("minus-in-equation",
                         re.compile(r"(?<=[\d\s])-(?=\s*\d)"),
                         " " + MINUS + " "))

    out_parts = []
    for part in _MATH.split(s):
        if part.startswith("$") and part.endswith("$"):
            out_parts.append(part)          # mathtext: matplotlib owns this
            continue
        seg = _apply(part, rules, log)
        if spacing:
            seg = _apply(seg, _SPACING, log)
        if superscripts:
            for plain, sup in SUPERSCRIPT_UNITS.items():
                pat = re.compile(r"(?<![A-Za-zµ])" + re.escape(plain) + r"\b")
                if pat.search(seg):
                    seg = pat.sub(sup, seg)
                    log.append({"rule": "superscript-unit", "from": plain,
                                "to": sup})
        out_parts.append(seg)
    out = "".join(out_parts)
    out = re.sub(r"[ \t]{2,}", " ", out)
    if log:
        LOG.extend(dict(e, context=s) for e in log)
    return out, log


def tx(s, **kw):
    """The convenience form: converted string only."""
    return tx_report(s, **kw)[0]


def summarise(logs=None) -> str:
    """One line naming what was changed, for the CLI. Never silent."""
    from collections import Counter
    entries = LOG if logs is None else [e for batch in logs for e in batch]
    c = Counter(e["rule"] for e in entries)
    if not c:
        return "typography: nothing to change"
    parts = [f"{n}× {rule.replace('-', ' ')}" for rule, n in c.most_common()]
    return "typography: " + ", ".join(parts)


# --------------------------------------------------------------- glyph check

def resolved_font_path(family: str | None = None) -> str | None:
    from matplotlib import font_manager, rcParams
    fam = family or rcParams.get("font.family", ["sans-serif"])
    if isinstance(fam, (list, tuple)):
        fam = fam[0] if fam else "sans-serif"
    try:
        return font_manager.findfont(fam, fallback_to_default=True)
    except Exception:
        return None


def missing_glyphs(text: str, font_path: str | None = None) -> set[str]:
    """Characters in `text` the font cannot draw.

    This is the half of the job people skip. With `svg.fonttype: none` the SVG
    names the font instead of embedding outlines, so a minus sign the font does
    not carry becomes a hollow box in the reader's editor — and it becomes one
    silently, in the vector master, after the raster proof looked fine.
    """
    path = font_path or resolved_font_path()
    if not path:
        return set()
    try:
        from matplotlib.ft2font import FT2Font
        font = FT2Font(path)
    except Exception:
        return set()
    missing = set()
    for ch in set(text):
        if ord(ch) < 0x20 or ch.isspace():
            continue
        try:
            if font.get_char_index(ord(ch)) == 0:
                missing.add(ch)
        except Exception:
            pass
    return missing


def check_figure_glyphs(fig) -> dict:
    """Every Text artist in the figure, tested against the resolved font."""
    path = resolved_font_path()
    used = "".join(t.get_text() or "" for t in fig.findobj(match=_is_text))
    missing = missing_glyphs(used, path)
    return {
        "font": path,
        "characters_used": len(set(used)),
        "missing": sorted(missing),
        "ok": not missing,
    }


def _is_text(o):
    from matplotlib.text import Text
    return isinstance(o, Text)


def ascii_fallback(s: str) -> str:
    """Undo the substitutions, for a font that cannot draw them.

    Deliberately lossy and deliberately loud: the caller is told this happened.
    Rendering a box where a minus belongs is not an option, and neither is
    pretending the figure is typographically correct when it is not.
    """
    table = {MINUS: "-", ENDASH: "-", EMDASH: "--", TIMES: "x",
             PLUSMINUS: "+/-", LE: "<=", GE: ">=", NE: "!=", APPROX: "~",
             DEGREE: " deg", MICRO: "u", PERMILLE: " per mille", MIDDOT: ".",
             "²": "2", "³": "3"}
    return "".join(table.get(ch, ch) for ch in s)
