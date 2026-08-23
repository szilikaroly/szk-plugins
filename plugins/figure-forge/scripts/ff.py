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
    sp.add_argument("--no-typography", action="store_true",
                    help="leave every string exactly as given: no minus sign for "
                         "negative numbers, no en dash for ranges, no ± × ≤ ≥. "
                         "Use it when a label is a literal identifier you must "
                         "not have touched.")
    sp.add_argument("--max-iter", type=int, default=40)


def _finish(fig, verifier, args):
    """Shared tail: QC loop -> export -> report. Returns the report dict."""
    import ff_export as E
    import ff_typography as T
    formats = L.parse_formats(args.formats)
    residual, log = ([], ["skipped (--no-check)"])
    if not args.no_check:
        residual, log = verifier.autofix(max_iter=args.max_iter)

    paths = L.out_paths(args.out, formats, args.outdir)
    label_boxes = None
    if "pptx" in formats:
        label_boxes = E.label_boxes_for_pptx(fig, verifier, dpi=args.dpi)
    written = E.save_figure(fig, paths, dpi=args.dpi, label_boxes=label_boxes)
    export_audit = E.audit_outputs(written)
    glyphs = T.check_figure_glyphs(fig)

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
        "typography": {
            "enabled": T.ENABLED,
            "summary": T.summarise(),
            "substitutions": T.LOG,
        },
        "glyphs": glyphs,
        "editability": export_audit,
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
    ty = r.get("typography") or {}
    if not ty.get("enabled", True):
        print("  typography: disabled (--no-typography) — strings rendered as given")
    else:
        print(f"  {ty.get('summary', '')}")

    g = r.get("glyphs") or {}
    if g and not g.get("ok", True):
        print(f"  GLYPH WARNING: the resolved font cannot draw "
              f"{', '.join(repr(c) for c in g['missing'])} — these render as "
              f"empty boxes in the vector master, not in the raster proof.")
        print(f"    font: {g.get('font')}")
        print( "    fix: install Arial/Helvetica, choose a font that has them, "
               "or re-run with --no-typography for an ASCII-only figure.")
    ed = (r.get("editability") or {}).get("svg")
    if ed:
        from ff_editable import audit_line
        print(audit_line(ed))
    pdf = (r.get("editability") or {}).get("pdf")
    if pdf and not pdf.get("editable", True):
        print(f"  PDF WARNING: {pdf['type3_fonts']} Type 3 font(s) — the text is "
              "outlines, not text. Check pdf.fonttype.")
    if r.get("overlay"):
        print(f"  proof overlay: {r['overlay']}")
    print(f"  audit: {r['qc_report']}")


# ------------------------------------------------------------- subcommands ----
def cmd_advise(args):
    import ff_advise as A
    print(A.format_advice(args.description))


def _typography(args):
    import ff_typography as T
    T.ENABLED = not getattr(args, "no_typography", False)
    T.LOG.clear()


def cmd_boxplot(args):
    _typography(args)
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    df = L.load_data(args.data)
    fig, v = R.box_plot(df, args.value, args.group, width=args.width,
                        ylabel=args.ylabel, title=args.title)
    _finish(fig, v, args)


def cmd_plot(args):
    _typography(args)
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    df = L.load_data(args.data)
    fig, v = R.xy_plot(df, args.x, args.y, series=args.series, kind=args.kind,
                       width=args.width, xlabel=args.xlabel, ylabel=args.ylabel,
                       title=args.title, direct_label=not args.no_direct_label)
    _finish(fig, v, args)


def cmd_forest(args):
    _typography(args)
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    df = L.load_data(args.data)
    fig, v = R.forest_plot(df, label=args.label, effect=args.effect,
                           low=args.low, high=args.high, width=args.width,
                           xlabel=args.xlabel, ref=args.ref, logx=args.logx,
                           weight=args.weight, title=args.title)
    _finish(fig, v, args)


def cmd_flowchart(args):
    _typography(args)
    S.apply_style(args.palette, args.dpi)
    import ff_render as R
    spec = L.load_spec(args.spec)
    fig, v = R.flowchart(spec, width=args.width, title=args.title)
    _finish(fig, v, args)



def cmd_panelflow(args):
    _typography(args)
    S.apply_style(args.palette, args.dpi)
    import ff_panelflow as PF
    spec = L.load_spec(args.spec)
    fig, viol = PF.panelflow(spec, title=args.title)
    import ff_export as E
    formats = L.parse_formats(args.formats)
    paths = L.out_paths(args.out, formats, args.outdir)
    pptx_path = paths.pop("pptx", None)
    written = E.save_figure(fig, paths, dpi=args.dpi, tight=False) if paths else {}
    if pptx_path:
        n = PF.save_pptx_exact(fig, pptx_path, dpi=args.dpi)
        written["pptx"] = str(pptx_path)
        print(f"  pptx: {n} editable text boxes over the image, slide at the figure's exact size")
    for fmt, o in written.items():
        print(f"  wrote  {fmt:5s} -> {Path(o).name}")
    n = sum(len(c["boxes"]) for c in spec["columns"])
    print(f"  boxes checked: {n}   columns: {len(spec['columns'])}")
    if viol:
        print(f"  QC result: {len(viol)} line(s) overflow their box:")
        for v in viol[:8]:
            print(f"    - [{v['rule']} {v['where']}] {v['text'][:60]!r} "
                  f"{v.get('width_mm','')} mm > {v.get('avail_mm','')} mm")
        print("  fix: shorten the text, widen the figure (--width), or use fewer columns.")
    else:
        print("  QC result: CLEAN - every wrapped line fits inside its box.")

    import ff_typography as T
    print(f"  {T.summarise()}" if T.ENABLED else
          "  typography: disabled (--no-typography) — strings rendered as given")
    glyphs = T.check_figure_glyphs(fig)
    if not glyphs["ok"]:
        print(f"  GLYPH WARNING: the resolved font cannot draw "
              f"{', '.join(repr(c) for c in glyphs['missing'])} — these render "
              "as empty boxes in the vector master, not in the raster proof.")
    ed = E.audit_outputs(written)
    if ed.get("svg"):
        from ff_editable import audit_line
        print(audit_line(ed["svg"]))

    rep = {"violations": viol, "boxes": n, "columns": len(spec["columns"]),
           "typography": {"enabled": T.ENABLED, "summary": T.summarise(),
                          "substitutions": T.LOG},
           "glyphs": glyphs, "editability": ed}
    outp = Path(args.outdir) / (args.out + ".qc.json")
    L.dump_report(rep, outp)
    print(f"  audit: {outp}")


def cmd_assemble(args):
    _typography(args)
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


def cmd_audit(args):
    """Editability and typography of a file we may not have made ourselves."""
    import ff_editable as ED
    import ff_typography as T
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"no such file: {path}")

    print(f"[figure-forge] editability audit — {path.name}")
    rep: dict = {"file": str(path)}
    if path.suffix.lower() == ".svg":
        a = ED.audit_svg(path)
        rep["svg"] = a
        print(f"  {a['text_elements']} <text> element(s), "
              f"{a['outlined_text_groups']} outlined to paths")
        print(f"  fonts: {', '.join(a['font_families']) or 'none declared'}")
        print(f"  font fallback stack: {'yes' if a['font_fallback_stack'] else 'NO'}")
        print(f"  named layers: {a['named_layers']}")
        if not a["editable"]:
            print("  VERDICT: NOT EDITABLE — the text was converted to outlines. "
                  "Nothing can recover it; the figure has to be re-rendered from "
                  "its source with svg.fonttype='none'.")
        else:
            print("  VERDICT: editable — every label is real text.")

        # Typography, reported and never silently corrected: this file may not
        # be ours, and rewriting someone's figure text without asking is not a
        # fix, it is an edit.
        problems = []
        for lab in a["labels"]:
            want = T.tx(lab)
            if want != lab:
                problems.append((lab, want))
        if problems:
            print(f"  typography: {len(problems)} label(s) use a hyphen where a "
                  "sign or a range dash belongs:")
            for before, after in problems[:12]:
                print(f"    - {before!r} -> {after!r}")
            print("  (not changed — re-render from source, or edit the SVG yourself)")
        else:
            print("  typography: sign and punctuation already differentiated")
        rep["typography_suggestions"] = [{"from": b, "to": a_} for b, a_ in problems]

        missing = T.missing_glyphs("".join(a["labels"]))
        if missing:
            print(f"  GLYPH WARNING: the current font cannot draw "
                  f"{', '.join(repr(c) for c in sorted(missing))}")
        rep["missing_glyphs"] = sorted(missing)

        if args.fix:
            r = ED.harden_svg(path)
            print(f"  hardened in place: {r['font_stack_applied']} font stacks, "
                  f"{r['layers_named']} layers named, "
                  f"{r['xml_space_added']} xml:space added")
            rep["hardened"] = r
    elif path.suffix.lower() == ".pdf":
        a = ED.audit_pdf(path)
        rep["pdf"] = a
        print(f"  Type 3 fonts: {a['type3_fonts']}   "
              f"embedded TrueType: {a['truetype_embedded']}")
        print("  VERDICT: " + ("editable — text is text."
                               if a["editable"] else
                               "NOT EDITABLE — Type 3 fonts are outlines."))
    else:
        sys.exit("audit works on .svg and .pdf (a raster has no text to audit)")

    outp = path.with_suffix(".editability.json")
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

    pf = sub.add_parser("panelflow", help="staged pipeline/architecture figure from a column/box spec")
    pf.add_argument("--spec", required=True, help="spec .json/.yaml or inline JSON")
    _common(pf)
    pf.set_defaults(func=cmd_panelflow)

    asm = sub.add_parser("assemble", help="compose panel PNGs into a composite")
    asm.add_argument("panels", nargs="+")
    _common(asm)
    asm.set_defaults(func=cmd_assemble)

    fx = sub.add_parser("fixsvg", help="QC labels in an existing SVG")
    fx.add_argument("svg")
    fx.add_argument("--preview", action="store_true")
    fx.set_defaults(func=cmd_fixsvg)

    au = sub.add_parser("audit", help="is this SVG/PDF really editable, and is "
                                      "its sign/punctuation right?")
    au.add_argument("file")
    au.add_argument("--fix", action="store_true",
                    help="harden the SVG in place: font fallback stack, named "
                         "layers, xml:space. Does NOT rewrite label text.")
    au.set_defaults(func=cmd_audit)

    st = sub.add_parser("selftest", help="run the built-in self test")
    st.set_defaults(func=cmd_selftest)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
