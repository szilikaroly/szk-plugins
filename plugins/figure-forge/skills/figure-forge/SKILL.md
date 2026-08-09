---
name: figure-forge
description: Build publication-quality, Nature-style scientific figures at 600 dpi with editable-text labels and a self-correcting label-quality loop that guarantees no label sits outside its box or covers a curve, marker or arrow. Use whenever the user wants to CREATE, GENERATE, POLISH or FIX a figure, chart, plot or diagram for a paper — box plots, forest / meta-analysis plots, CONSORT / flowcharts, pathway or box-and-arrow diagrams, or multi-panel composites — or wants a figure exported as SVG, TIFF, PNG or PPTX, or asks how best to visualise some data. Also use to check/repair labels in an existing SVG. Hungarian triggers — ábra készítése, forest plot, folyamatábra, box plot, dobozdiagram, feliratok ellenőrzése, nature-stílusú ábra, 600 dpi, szerkeszthető feliratok.
---

# Figure Forge

Turn data or a description into a journal-ready figure whose labels are
provably clean. Everything is driven by one CLI; each subcommand builds the
figure, runs the QC loop, and exports every requested format.

## The one rule that defines this skill

**Never hand back a figure without running the QC loop.** Every generate
command already does this by default (`autofix`), and prints a QC result. Relay
that result to the user verbatim — whether it is CLEAN or has unresolved
violations. The guarantees the loop enforces:

- **R1 containment** — a label bound to a box stays fully inside it.
- **R2 cover** — no label overlaps a data mark, curve, arrow or other box.
- **R3 collision** — no two labels overlap.
- **R4 canvas** — no label crosses the figure edge.

Every figure also writes `<stem>.overlay.png` (a visual proof: a box drawn
round each checked label, green = clean, red = unresolved) and `<stem>.qc.json`
(the audit). Show the user the overlay when they want proof it was checked.

## Defaults

600 dpi · Nature style · editable-text SVG master · Okabe-Ito colourblind-safe
palette · single-column (89 mm) unless the figure wants more. Fonts fall back
from Arial/Helvetica to DejaVu Sans automatically.

## Workflow

1. **Advise first when the user is unsure.** `ff.py advise "<what they want to
   show>"` returns a chart-type recommendation and a Nature checklist. Relay it,
   add your judgement, then propose the exact build command.
2. **Build.** Pick the subcommand:
   - `boxplot  --data F --value V --group G` — grouped box plot + jittered points
   - `plot     --data F --x X --y Y [--series S] [--kind line|scatter]` — direct-labelled
   - `forest   --data F --label L --effect E --low LO --high HI [--weight W]`
   - `flowchart --spec SPEC.json` — nodes/edges; write the spec with the Write tool first
   - `assemble  a.png b.png c.png` — multi-panel composite with bold a/b/c
   - `fixsvg    old.svg --preview` — heuristic label check of an external SVG
3. **Report** the QC result and every file written; show the PNG.
4. **If violations remain**, the message says why (usually a box too small or a
   label too long). Widen the column (`--width double`), shorten the label, or
   enlarge the node box in the spec, then re-run — "recheck until polished".

## Running the CLI

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" <subcommand> [flags]
```

Common flags on every generate command: `--out STEM`, `--outdir DIR`,
`--formats svg,png,tiff,pdf,pptx` (default `svg,png`), `--dpi 600`,
`--palette okabe-ito|nature`, `--width single|1.5|double|<mm>`, `--title`,
`--no-check` (skip QC — discourage this), `--max-iter N`.

Inspect a data file's columns with `head -1 FILE` before choosing `--value`,
`--group`, `--label`, `--effect` etc. Never invent column names or data.

## Formats — what each is for

- **svg** — the editable master; text stays as `<text>`, so labels stay
  editable in Illustrator/Inkscape. This is what satisfies "editable labels".
- **tiff** — LZW-compressed, 600 dpi tag embedded; the classic raster ask.
- **png** — 600 dpi flat raster for submission portals and previews.
- **pdf** — vector with embedded fonts.
- **pptx** — one slide at the figure's real size, high-res image plus native,
  editable PowerPoint text boxes over each label.

## Self-test

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ff.py" selftest` proves the QC loop
corrects a deliberately-misplaced label and that every export format writes.
Run it if anything looks off.
