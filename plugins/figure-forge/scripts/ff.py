#!/usr/bin/env python3
"""Figure Forge — Nature-style scientific figures with a self-correcting label
quality loop.

Every slash command is a thin wrapper around one subcommand here, so the same
thing works from a plain terminal:

    ff.py advise "compare enzyme activity between three genotypes"
    ff.py boxplot  --data d.csv --value activity --group genotype --out fig1
    ff.py forest   --data m.csv --label study --effect or --low lo --high hi --out fig2
    ff.py flowchart --spec consort.json --out fig3
    ff.py assemble  a.png b.png c.png --out fig4
    ff.py fixsvg    old_figure.svg
    ff.py polish    --data d.csv --value v --group g --out fig1   # generate+recheck loop
    ff.py selftest

Defaults: 600 dpi, Nature style, editable-text SVG master. Outputs also include
<stem>.qc.json (the audit) and <stem>.overlay.png (visual proof each label was
checked). Add --no-check to skip the QC loop (not recommended).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ff_style as S
import ff_lib as L


def _common(sp):
    sp.add_argument("--out", default="figure", help="output filename stem")
    sp.add_argument("--outdir", default=".", help="output directory")
    sp.add_argument("--formats", default="svg,png",
                    help="comma list: svg,png,tiff,pdf,pptx (default svg,png)")
    sp.add_argument("--dpi", type=int, default=S.DEFAULT_DPI)
    sp.add_argument("--palette", default=S.DEFAULT_PALETTE,
                    choices=list(S.PALETTES))
    sp.add_argument("--width", default="single",
                    help="single | 1.5 | double | <mm>")
    sp.add_argument("--title", default=None)
    sp.add_argument("--no-check", action="store_true",
                    help="skip the label QC loop")
    sp.add_argument("--max-iter", type=int, default=40)


def _finish(fig, verifier, args):
    """Shared tail: QC loop -> export -> report. Returns the report dict."""
    import ff_export as E
    formats = L.parse_formats(args.formats)
    residual, log = ([], ["skipped (--no-check)"])
    if not args.no_check:
        residual, log = verifier.autofix(max_iter=args.max_iter)

    paths = L.out_paths(args.out, formats, args.outdir)
    label_boxes = None
    if "pptx" in formats:
        label_boxes = E.label_boxes_for_pptx(fig, verifier, dpi=args.dpi)
    written = E.save_figure(fig, paths, dpi=args.dpi, label_boxes=label_boxes)

    # audit + visual proof
    overlay = Path(args.outdir) / f"{args.out}.overlay.png"
    try:
        from ff_verify import annotate_overlay
        annotate_overlay(fig, verifier, overlay)
    except Exception as e:  # overlay is a nicety, never fatal
        overlay = None
    report = {
        "stem": args.out, "style": "nature", "dpi": args.dpi,
        "palette": args.palette, "formats": written,
        "labels_checked": len(verifier.labels),
        "obstacles": len(verifier.obstacles),
        "qc_log": log, "residual_violations": residual,
        "clean": (len(residual) == 0),
        "overlay": str(overlay) if overlay else None,
    }
    qc_path = Path(args.outdir) / f"{args.out}.qc.json"
    L.dump_report(report, qc_path)
    report["qc_report"] = str(qc_path)
    _print_report(report)
    return report


def _print_report(r):
    print(f"[figure-forge] {r['stem']}  ({r['dpi']} dpi, {r['style']} style)")
    for fmt, p in r["formats"].items():
        print(f"  wrote  {fmt:5} -> {p}")
    print(f"  labels checked: {r['labels_checked']}   "
          f"obstacles: {r['obstacles']}")
    print(f"  QC: {'; '.join(r['qc_log'])}")
    if r["clean"]:
        print("  QC result: CLEAN — no label outside a box, "
              "no label covering data/curves.")
    else:
        print(f"  QC result: {len(r['residual_violations'])} UNRESOLVED "
              "(shown below); consider a larger box or --width double:")
        for v in r["residual_violations"]:
            print(f"    - [{v['rule']} {v['kind']}] {v['label']}: {v['message']}")
    if r.get("overlay"):
        print(f"  proof overlay: {r['overlay']}")
    print(f"  audit: {r['qc_report']}")


# ------------------------------------------------------------- subcommands ----
def cmd_advise(args):
    import ff_advise as A
    print(A.format_advice(args.description))


def cmd_boxplot(args):
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    df = L.load_data(args.data)
    fig, v = R.box_plot(df, args.value, args.group, width=args.width,
                        ylabel=args.ylabel, title=args.title)
    _finish(fig, v, args)


def cmd_plot(args):
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    df = L.load_data(args.data)
    fig, v = R.xy_plot(df, args.x, args.y, series=args.series, kind=args.kind,
                       width=args.width, xlabel=args.xlabel, ylabel=args.ylabel,
                       title=args.title, direct_label=not args.no_direct_label)
    _finish(fig, v, args)


def cmd_forest(args):
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    df = L.load_data(args.data)
    fig, v = R.forest_plot(df, label=args.label, effect=args.effect,
                           low=args.low, high=args.high, width=args.width,
                           xlabel=args.xlabel, ref=args.ref, logx=args.logx,
                           weight=args.weight, title=args.title)
    _finish(fig, v, args)


def cmd_flowchart(args):
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    spec = L.load_spec(args.spec)
    fig, v = R.flowchart(spec, width=args.width, title=args.title)
    _finish(fig, v, args)


def cmd_assemble(args):
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    fig, v = R.assemble(args.panels, width=args.width)
    _finish(fig, v, args)


def cmd_fixsvg(args):
    import ff_fixsvg as F
    rep = F.check_svg(args.svg)
    print(f"[figure-forge] label QC on {args.svg} (heuristic)")
    print(f"  {rep['n_text']} text labels, {rep['n_boxes']} candidate boxes; "
          f"{rep['n_hosted_labels']} labels sit inside a box")
    if not rep["violations"]:
        print("  QC result: CLEAN — no gross containment/overlap problems found.")
    else:
        print(f"  QC result: {len(rep['violations'])} issue(s):")
        for v in rep["violations"]:
            mv = f"  (move ~{v['suggest_move']} px)" if v.get("suggest_move") else ""
            print(f"    - [{v['rule']} {v['kind']}] {v['label']}: {v['message']}{mv}")
    if args.preview:
        out = Path(args.svg).with_suffix(".preview.png")
        F.preview(args.svg, out)
        print(f"  preview: {out}")
    outp = Path(args.svg).with_suffix(".qc.json")
    L.dump_report(rep, outp)
    print(f"  audit: {outp}")


def cmd_selftest(args):
    from selftest import run
    sys.exit(0 if run() else 1)


def build_parser():
    p = argparse.ArgumentParser(prog="ff.py", description="Figure Forge")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("advise", help="recommend how to visualise")
    a.add_argument("description")
    a.set_defaults(func=cmd_advise)

    b = sub.add_parser("boxplot", help="grouped box plot from data")
    b.add_argument("--data", required=True)
    b.add_argument("--value", required=True)
    b.add_argument("--group", required=True)
    b.add_argument("--ylabel", default=None)
    _common(b)
    b.set_defaults(func=cmd_boxplot)

    pl = sub.add_parser("plot", help="line / scatter plot with direct labels")
    pl.add_argument("--data", required=True)
    pl.add_argument("--x", required=True)
    pl.add_argument("--y", required=True)
    pl.add_argument("--series", default=None, help="column that defines series")
    pl.add_argument("--kind", default="line", choices=["line", "scatter"])
    pl.add_argument("--xlabel", default=None)
    pl.add_argument("--ylabel", default=None)
    pl.add_argument("--no-direct-label", action="store_true",
                    help="use a legend instead of end-of-line labels")
    _common(pl)
    pl.set_defaults(func=cmd_plot)

    f = sub.add_parser("forest", help="forest / meta-analysis plot")
    f.add_argument("--data", required=True)
    f.add_argument("--label", required=True)
    f.add_argument("--effect", required=True)
    f.add_argument("--low", required=True)
    f.add_argument("--high", required=True)
    f.add_argument("--xlabel", default="Effect size (95% CI)")
    f.add_argument("--ref", type=float, default=1.0)
    f.add_argument("--logx", action="store_true")
    f.add_argument("--weight", default=None)
    _common(f)
    f.set_defaults(func=cmd_forest)

    fc = sub.add_parser("flowchart", help="flowchart from a node/edge spec")
    fc.add_argument("--spec", required=True, help="spec .json/.yaml or inline JSON")
    _common(fc)
    fc.set_defaults(func=cmd_flowchart)

    asm = sub.add_parser("assemble", help="compose panel PNGs into a composite")
    asm.add_argument("panels", nargs="+")
    _common(asm)
    asm.set_defaults(func=cmd_assemble)

    fx = sub.add_parser("fixsvg", help="QC labels in an existing SVG")
    fx.add_argument("svg")
    fx.add_argument("--preview", action="store_true")
    fx.set_defaults(func=cmd_fixsvg)

    st = sub.add_parser("selftest", help="run the built-in self test")
    st.set_defaults(func=cmd_selftest)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
