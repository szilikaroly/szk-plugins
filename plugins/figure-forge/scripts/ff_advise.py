"""Visualisation advisor — 'check, revise and give ideas to the creator on how
to visualise'. Rule-based chart-type guidance plus a Nature-style checklist.

Deliberately NOT an LLM call: it emits a structured recommendation the model
then relays and expands. Deterministic, offline, fast.
"""
from __future__ import annotations

import re

# intent keyword -> (recommended chart, why, forge command)
RULES = [
    (r"\b(compare|difference|between groups?|vs\.?|versus)\b.*\b(distribution|spread|values?)\b",
     "box plot (or violin if n is large)",
     "shows median, IQR and outliers per group without hiding the raw spread",
     "boxplot"),
    (r"\b(meta[- ]?analysis|odds ratio|hazard ratio|risk ratio|effect size|95% ?ci|pooled)\b",
     "forest plot",
     "one row per study, point = estimate, whiskers = CI, diamond = pooled",
     "forest"),
    (r"\b(pipeline|workflow|process|steps?|consort|inclusion|exclusion|screening|selection)\b",
     "flowchart",
     "boxes for stages, arrows for flow; CONSORT-style for study selection",
     "flowchart"),
    (r"\b(over time|trend|trajectory|time ?series|longitudinal|kinetic)\b",
     "line plot with markers (direct-labelled)",
     "time on x, response on y; one line per condition, labelled at line end",
     "plot --kind line"),
    (r"\b(correlat|scatter|relationship between two|association)\b",
     "scatter plot",
     "raw points; add a fit line and report r and n in the panel",
     "plot --kind scatter"),
    (r"\b(proportion|percentage|composition|share|fraction)\b",
     "stacked/grouped bar (avoid pie charts)",
     "bars compare lengths accurately; pies force angle judgement",
     "custom (describe it — I'll build a Nature-styled, QC'd bar chart)"),
    (r"\b(distribution|histogram|density|frequency)\b",
     "histogram or KDE",
     "show the shape; overlay groups with transparency, not stacking",
     "custom (describe it — I'll build it, same style and QC loop)"),
    (r"\b(matrix|heat ?map|expression|clustering|pairwise)\b",
     "heatmap with a colourblind-safe sequential map",
     "rows/cols ordered by clustering; annotate only if the grid is small",
     "custom (describe it — I'll build it, same style and QC loop)"),
]

CHECKLIST = [
    "Size to the column: 89 mm single, 120 mm 1.5, 183 mm double; height <= 247 mm.",
    "Type 5-7 pt at FINAL size; panel letters bold lower-case (a, b, c).",
    "Colourblind-safe palette (Okabe-Ito default); never red/green as the only cue.",
    "Lines >= 0.25 pt; drop top/right spines; no chart-junk gridlines.",
    "No label outside its box; no label over a curve, marker or arrow.",
    "Export: editable-text SVG master + 600 dpi TIFF/PNG; embed fonts in PDF.",
    "One message per panel; put detail in the caption, not on the plot.",
]


def advise(description: str) -> dict:
    d = description.lower()
    hits = []
    for pat, chart, why, cmd in RULES:
        if re.search(pat, d):
            hits.append({"chart": chart, "why": why, "command": cmd})
    if not hits:
        hits.append({"chart": "start from the question, not the data",
                     "why": "decide the single comparison the reader must make, "
                            "then pick the encoding that makes it a length or "
                            "position judgement",
                     "command": "advise (refine the question, then pick a builder)"})
    return {"recommendations": hits, "nature_checklist": CHECKLIST}


def format_advice(description: str) -> str:
    a = advise(description)
    out = ["VISUALISATION ADVICE", "=" * 60,
           f"request: {description.strip()}", ""]
    out.append("Recommended:")
    for i, r in enumerate(a["recommendations"], 1):
        out.append(f"  {i}. {r['chart']}")
        out.append(f"     why: {r['why']}")
        cmd = r["command"]
        out.append(f"     -> {cmd}" if cmd.startswith(("custom", "advise"))
                   else f"     -> /figure-forge:{cmd}")
    out.append("")
    out.append("Nature-style checklist:")
    for c in a["nature_checklist"]:
        out.append(f"  [ ] {c}")
    return "\n".join(out)
