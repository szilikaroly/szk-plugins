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

    print(f"\n{'ALL PASSED' if passed else 'FAILURES PRESENT'}  (artifacts: {tmp})")
    return passed


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
