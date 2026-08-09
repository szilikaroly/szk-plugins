---
description: Nature-style forest / meta-analysis plot from a data file, QC-checked
allowed-tools: Bash
---
Build a forest plot. Arguments the user gave: $ARGUMENTS

Needs a data file with one row per study and columns for: study label, point
estimate, CI lower, CI upper (optionally a weight column). Inspect the header
with `head -1 FILE` if the column names are unknown, then run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" forest --data DATA.csv --label study --effect or --low lo --high hi --weight w --xlabel "Odds ratio (95% CI)" --out STEM --formats svg,png,tiff --width double
```

Flags: `--ref 1.0` (null line; use 0 for mean differences), `--logx` for ratio
measures, `--width double` (forests are usually full-width), plus the usual
`--palette`, `--dpi`, `--formats`, `--title`.

Report the QC result verbatim — the key guarantee here is that no study label
sits on a confidence-interval line. List every file written (SVG master, raster
exports, `.overlay.png` proof, `.qc.json` audit) and show the user the PNG.
