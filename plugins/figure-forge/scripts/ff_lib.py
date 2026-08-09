"""Shared helpers for Figure Forge: paths, data loading, JSON/YAML specs."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def load_data(path: str):
    """Load tabular data from CSV/TSV/JSON into a pandas DataFrame."""
    import pandas as pd
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"data file not found: {p}")
    suf = p.suffix.lower()
    if suf in (".csv",):
        return pd.read_csv(p)
    if suf in (".tsv", ".tab", ".txt"):
        return pd.read_csv(p, sep="\t")
    if suf in (".json",):
        return pd.read_json(p)
    if suf in (".xlsx", ".xls"):
        return pd.read_excel(p)
    # last resort: sniff
    return pd.read_csv(p, sep=None, engine="python")


def load_spec(path_or_str: str) -> dict:
    """Load a flowchart/diagram spec. Accepts a file path or inline JSON."""
    s = path_or_str
    p = Path(s).expanduser()
    if p.exists():
        text = p.read_text()
        if p.suffix.lower() in (".yml", ".yaml"):
            try:
                import yaml  # optional
                return yaml.safe_load(text)
            except Exception:
                pass
        return json.loads(text)
    # inline JSON
    return json.loads(s)


def out_paths(stem: str, formats, outdir: str = "."):
    """Return {fmt: Path} for the requested output formats."""
    d = Path(outdir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return {f: d / f"{stem}.{f}" for f in formats}


def parse_formats(s: str | None):
    """'svg,png,tiff,pptx' -> list; default svg+png."""
    if not s:
        return ["svg", "png"]
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def dump_report(report: dict, path: str):
    Path(path).expanduser().write_text(json.dumps(report, indent=2))
