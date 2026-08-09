---
description: Nature-style grouped box plot from a data file, with the label QC loop
allowed-tools: Bash
---
Build a box plot. Arguments the user gave: $ARGUMENTS

You need a data file and the value + group columns. If any are missing, ask once,
or inspect the file's header with `head -1 FILE` to find the column names. Then
run (fill in the real paths and column names):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" boxplot --data DATA.csv --value VALUECOL --group GROUPCOL --out STEM --formats svg,png,tiff --width single
```

Flags: `--ylabel "..."`, `--title "..."`, `--palette okabe-ito|nature`,
`--width single|1.5|double|<mm>`, `--dpi 600`, `--formats svg,png,tiff,pdf,pptx`.

After it runs, report the QC result verbatim — especially whether it is CLEAN or
has unresolved violations — and list the files written, including the
`.overlay.png` proof and the `.qc.json` audit. If violations remain, suggest a
wider column or a shorter label. Show the user the generated PNG.
