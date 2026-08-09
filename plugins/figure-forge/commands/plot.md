---
description: Nature-style line or scatter plot with direct end-of-line labels, QC-checked
allowed-tools: Bash
---
Build a line or scatter plot. Arguments the user gave: $ARGUMENTS

Needs a data file with an x column, a y column, and optionally a `series` column
that splits the data into one line/colour per group. Inspect the header with
`head -1 FILE` if unsure, then run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" plot --data DATA.csv --x day --y volume --series arm --kind line --xlabel "Day" --ylabel "Value" --out STEM --formats svg,png,tiff --width single
```

Flags: `--kind line|scatter`, `--series COL` (omit for a single series),
`--no-direct-label` (use a legend instead of end-of-line labels), plus the usual
`--palette`, `--width`, `--dpi`, `--formats`, `--title`.

By default each series is labelled at the end of its curve (Nature prefers this
to a legend), and the QC loop keeps those labels off every curve and off each
other. Report the QC result verbatim and show the PNG.
