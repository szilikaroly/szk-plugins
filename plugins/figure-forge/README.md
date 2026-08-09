# Figure Forge

Nature-style scientific figures with a **self-correcting label-quality loop**.

Build box plots, forest / meta-analysis plots, CONSORT flowcharts, box-and-arrow
diagrams and multi-panel composites — at **600 dpi**, with **editable-text**
labels — then let the engine guarantee that **no label sits outside its box and
no label covers a curve, marker or arrow**. Every figure ships with a QC audit
and a visual proof overlay.

## Why it exists

Getting figures through peer review is death by a thousand label collisions: a
study name lying across a confidence interval, a box caption spilling past its
rectangle, a panel letter clipped at the margin. Figure Forge measures every
label's true bounding box **from the same renderer that draws the figure**, then
runs `check → correct → recheck` until the layout is clean or reports exactly
what it could not fix.

## The QC guarantees

| rule | meaning |
|------|---------|
| **R1 containment** | a label bound to a box stays fully inside it |
| **R2 cover** | no label overlaps a data mark, curve, arrow or other box |
| **R3 collision** | no two labels overlap |
| **R4 canvas** | no label crosses the figure edge |

Correction order: recentre in the parent box → shrink font to the 5 pt floor →
spiral-search for free space → report if still impossible (box too small).

## Commands

| command | what it does |
|---------|--------------|
| `/ff:advise "<goal>"` | recommend a chart type + Nature checklist before you plot |
| `/ff:boxplot` | grouped box plot with jittered raw points |
| `/ff:plot` | line / scatter plot with direct end-of-line labels (no legend clutter) |
| `/ff:forest` | forest / meta-analysis plot; labels kept off every CI line |
| `/ff:flowchart` | node/edge flowchart (CONSORT-friendly); labels kept inside boxes |
| `/ff:assemble` | combine panel PNGs into a multi-panel figure with bold a, b, c |
| `/ff:fixsvg` | heuristic label check of an existing external SVG |

Natural-language requests ("make me a Nature-style forest plot of these ORs")
trigger the bundled **figure-forge skill**, which drives the same CLI.

## Defaults

600 dpi · Nature style · editable-text SVG master · Okabe-Ito colourblind-safe
palette · single-column (89 mm) sizing · Arial/Helvetica → DejaVu Sans fallback.

## Outputs

For stem `fig1` you get the requested formats plus proof and audit:

```
fig1.svg          editable-text vector master (labels editable in Illustrator)
fig1.png          600 dpi flat raster
fig1.tiff         LZW-compressed, 600 dpi tag embedded
fig1.pdf          vector, embedded fonts
fig1.pptx         one slide, real size, image + native editable text boxes
fig1.overlay.png  visual proof: a box round every checked label
fig1.qc.json      the audit (rules, residual violations, iteration log)
```

## Requirements

Python 3 with `matplotlib`, `numpy`, `pandas`, `lxml`, `python-pptx`, `Pillow`
(all standard in Anaconda). `cairosvg` is optional and only used to rasterise
external SVGs in `/ff:fixsvg`.

## Self-test

```bash
python3 scripts/ff.py selftest
```

Proves the QC loop corrects a deliberately-misplaced label and that every export
format writes correctly.

## Examples

The `examples/` folder contains a CONSORT flowchart spec, a meta-analysis CSV,
and the figures they produce — including the `.overlay.png` proofs.

---

Part of the **szk-plugins** marketplace · MIT · Dr. Szili Károly
