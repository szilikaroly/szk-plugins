#!/usr/bin/env python3
"""End-to-end self test. Proves the QC loop actually moves a bad label back
inside its box and off the data, and that every export format is written.

Run:  python3 selftest.py     (exit 0 = pass)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

import ff_style as S


def _ok(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return cond


def run():
    print("figure-forge selftest")
    S.apply_style()
    passed = True
    tmp = Path(tempfile.mkdtemp(prefix="ff_selftest_"))

    import ff_render as R
    import ff_export as E
    import matplotlib.pyplot as plt

    # 1) QC actually corrects a deliberately-misplaced label ------------------
    spec = {"nodes": [
        {"id": "a", "text": "Recruited\n(n=120)", "x": 50, "y": 80, "w": 30, "h": 14},
        {"id": "b", "text": "Excluded (n=20)", "x": 50, "y": 45, "w": 30, "h": 14},
        {"id": "c", "text": "Analysed (n=100)", "x": 50, "y": 12, "w": 30, "h": 14},
    ], "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]}
    fig, v = R.flowchart(spec, width="single")
    # sabotage: shove the first label far outside its box and onto the arrow
    bad = v.labels[0]
    bad.artist.set_position((90, 80))
    before = len(v.check())
    residual, log = v.autofix()
    after = len(residual)
    passed &= _ok(f"QC fixed sabotaged label (before={before} viols, "
                  f"after={after}); log={log[-1]}", before > 0 and after == 0)
    plt.close(fig)

    # 2) box plot builds, verifies, exports every format ----------------------
    import pandas as pd
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "genotype": np.repeat(["WT", "Het", "KO"], 30),
        "activity": np.concatenate([rng.normal(m, 1, 30) for m in (5, 6.5, 3)]),
    })
    fig, v = R.box_plot(df, "activity", "genotype", ylabel="Activity (a.u.)")
    v.autofix()
    paths = {f: tmp / f"box.{f}" for f in ("svg", "png", "tiff", "pdf", "pptx")}
    lb = E.label_boxes_for_pptx(fig, v)
    written = E.save_figure(fig, paths, dpi=600, label_boxes=lb)
    for f, p in written.items():
        passed &= _ok(f"exported {f} ({Path(p).stat().st_size} bytes)",
                      Path(p).exists() and Path(p).stat().st_size > 0)
    plt.close(fig)

    # 3) editable-text SVG really keeps text as <text> ------------------------
    svg_txt = (tmp / "box.svg").read_text()
    passed &= _ok("SVG keeps editable <text> (fonttype=none)",
                  "<text" in svg_txt and "Activity" in svg_txt)

    # 4) TIFF is 600 dpi ------------------------------------------------------
    from PIL import Image
    im = Image.open(tmp / "box.tiff")
    dpi = im.info.get("dpi", (0, 0))[0]
    passed &= _ok(f"TIFF dpi tag = {dpi}", round(dpi) == 600)

    # 5) forest plot: study labels end up off every CI line -------------------
    fdf = pd.DataFrame({
        "study": [f"Study {chr(65+i)} et al." for i in range(5)],
        "or": [0.8, 1.2, 0.65, 1.5, 0.95],
        "lo": [0.5, 0.9, 0.4, 1.1, 0.7],
        "hi": [1.1, 1.6, 0.95, 2.0, 1.3],
    })
    fig, v = R.forest_plot(fdf, label="study", effect="or", low="lo", high="hi")
    residual, _ = v.autofix()
    passed &= _ok(f"forest labels clear of data (residual={len(residual)})",
                  len(residual) == 0)
    plt.close(fig)

    # 6) advisor returns a recommendation -------------------------------------
    import ff_advise as A
    rec = A.advise("forest plot of pooled odds ratios across studies")
    passed &= _ok("advisor recommends forest plot",
                  any("forest" in r["chart"] for r in rec["recommendations"]))

    # 7) sign vs punctuation --------------------------------------------------
    # One glyph doing three jobs is the failure this replaces. Each case below
    # is a string that was rendered wrongly before ff_typography existed, or an
    # identifier a careless rule would have corrupted.
    import ff_typography as T
    T.ENABLED = True
    convert = [
        ("Follow-up 12-24 months", "Follow-up 12\u201324 months", "range -> en dash"),
        ("Effect -0.42 (-0.71, -0.13)", "Effect \u22120.42 (\u22120.71, \u22120.13)",
         "sign -> minus, and a list comma is not a range"),
        ("Years 2019-2021", "Years 2019\u20132021", "year span -> en dash"),
        ("Mean +/- SD", "Mean \u00b1 SD", "+/- -> plus-minus"),
        ("p >= 0.05", "p \u2265 0.05", ">= -> greater-equal"),
        ("Size 10 x 10 mm", "Size 10 \u00d7 10 mm", "x -> times"),
        ("Volume (mm3)", "Volume (mm\u00b3)", "unit exponent"),
        ("p<0.05", "p < 0.05", "operator spacing"),
    ]
    for src, want, why in convert:
        got = T.tx(src)
        passed &= _ok(f"{why}: {src!r} -> {got!r}", got == want)

    # The rules must not touch an identifier. Every one of these has a hyphen
    # that means "hyphen", and a rule that reached for it would corrupt data.
    for keep in ("IL-6", "HLA-B27", "COVID-19", "2-fold increase", "p-value",
                 "Kruskal-Wallis test", "NCT01032434", "CD4-CD8 ratio",
                 "Pooled (random-effects)"):
        passed &= _ok(f"identifier preserved: {keep!r}", T.tx(keep) == keep)

    passed &= _ok("mathtext passed through untouched",
                  T.tx(r"$\Delta$ = $-1.5$") == r"$\Delta$ = $-1.5$")
    passed &= _ok("--no-typography leaves the string alone",
                  (lambda: (setattr(T, "ENABLED", False),
                            T.tx("Follow-up 12-24 months") == "Follow-up 12-24 months",
                            setattr(T, "ENABLED", True))[1])())

    # 8) glyph coverage -------------------------------------------------------
    # With svg.fonttype:none the SVG names a font instead of embedding outlines,
    # so a substitution the font cannot draw becomes a hollow box in the vector
    # master while the raster proof still looks right.
    probe = "".join(sorted(T.INTRODUCED))
    S.apply_style()
    missing = T.missing_glyphs(probe)
    passed &= _ok(f"resolved font draws every character the rules introduce "
                  f"(missing: {''.join(sorted(missing)) or 'none'})", not missing)
    passed &= _ok("a font without them is detected, not assumed",
                  T.missing_glyphs("\u2212\u00d7\u2264",
                                   _limited_font()) != set() or _limited_font() is None)
    passed &= _ok("ascii_fallback undoes every introduced glyph",
                  all(ord(c) < 128 for c in T.ascii_fallback(probe)))

    # 9) the exported SVG is editable, and says so from the file ---------------
    import ff_editable as ED
    fig, v = R.forest_plot(_meta_df(), label="study", effect="est",
                           low="lo", high="hi",
                           xlabel="Mean difference (95% CI), 12-24 months",
                           ref=0)
    v.autofix()
    out = tmp / "typo"
    written = E.save_figure(fig, {"svg": out.with_suffix(".svg"),
                                  "pdf": out.with_suffix(".pdf")}, dpi=150)
    audit = ED.audit_svg(written["svg"])
    passed &= _ok(f"SVG labels are real <text>, none outlined "
                  f"({audit['text_elements']} text, "
                  f"{audit['outlined_text_groups']} outlined)", audit["editable"])
    passed &= _ok("SVG carries a font fallback stack, not one family",
                  audit["font_fallback_stack"])
    passed &= _ok(f"SVG groups are named for a human ({audit['named_layers']})",
                  audit["named_layers"] > 0)
    passed &= _ok("the minus sign reached the file",
                  any("\u2212" in lab for lab in audit["labels"]))
    passed &= _ok("the en dash reached the file",
                  any("\u2013" in lab for lab in audit["labels"]))
    pdf_audit = ED.audit_pdf(written["pdf"])
    passed &= _ok(f"PDF text is text, not Type 3 outlines "
                  f"({pdf_audit['truetype_embedded']} embedded TrueType)",
                  pdf_audit["editable"])
    # Hardening must survive being run again: exports are re-run constantly.
    before = ED.audit_svg(written["svg"])
    ED.harden_svg(written["svg"])
    after = ED.audit_svg(written["svg"])
    passed &= _ok("harden_svg is idempotent",
                  before["named_layers"] == after["named_layers"]
                  and before["font_families"] == after["font_families"])
    plt.close(fig)

    print(f"\n{'ALL PASSED' if passed else 'FAILURES PRESENT'}  (artifacts: {tmp})")
    return passed


def _meta_df():
    import pandas as pd
    return pd.DataFrame({
        "study": ["Anderson 2019", "Becker 2020", "Chen 2021"],
        "est": [-0.42, -0.15, 0.31],
        "lo": [-0.71, -0.44, -0.02],
        "hi": [-0.13, 0.14, 0.64],
    })


def _limited_font():
    """A font known to lack the introduced glyphs, or None if none is installed."""
    from matplotlib import font_manager
    for f in font_manager.fontManager.ttflist:
        if f.name in ("cmr10", "cmss10", "cmtt10", "STIXNonUnicode"):
            return f.fname
    return None


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
