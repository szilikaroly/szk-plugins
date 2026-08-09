"""Nature-style figure defaults for Figure Forge.

Everything a journal figure needs, in one place: physical column widths,
colourblind-safe palettes, typography floors, line weights and the 600 dpi
default. Import `apply_style()` before building any figure.

References for the numbers (Nature / NPG artwork guidelines, widely published):
  * single column   = 89 mm   (~3.50 in)
  * 1.5 column      = 120 mm  (~4.72 in)
  * double column   = 183 mm  (~7.20 in)
  * max page height = 247 mm
  * body/label text 5-7 pt, never below 5 pt at final size
  * lines >= 0.25 pt so they survive print
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless; no display needed
import matplotlib.pyplot as plt
from matplotlib import font_manager

MM = 1.0 / 25.4  # mm -> inch

# ---- physical widths (inches) -------------------------------------------------
WIDTHS_MM = {"single": 89.0, "1.5": 120.0, "onehalf": 120.0, "double": 183.0}
MAX_HEIGHT_MM = 247.0
DEFAULT_DPI = 600

# ---- typography floors (points) ----------------------------------------------
FONT_BASE = 7.0      # axis/label default
FONT_TICK = 6.0
FONT_PANEL = 8.0     # bold panel letters (a, b, c)
FONT_MIN = 5.0       # hard floor - never render text smaller at final size

# Font stack: prefer Arial/Helvetica (Nature house), fall back to the always
# present DejaVu Sans so the plugin never crashes on a fresh machine.
FONT_STACK = ["Arial", "Helvetica", "Helvetica Neue", "DejaVu Sans"]

# ---- palettes ----------------------------------------------------------------
# Okabe-Ito: the reference colourblind-safe qualitative set. Default because it
# is the safest choice for any journal figure.
OKABE_ITO = [
    "#000000", "#E69F00", "#56B4E9", "#009E73",
    "#F0E442", "#0072B2", "#D55E00", "#CC79A7",
]
# A curated "nature"-flavoured qualitative set (muted, print-friendly).
NATURE_QUAL = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
]
PALETTES = {"okabe-ito": OKABE_ITO, "nature": NATURE_QUAL}
DEFAULT_PALETTE = "okabe-ito"

# Neutral greys used for boxes, spines, gridlines.
INK = "#222222"
SPINE = "#444444"
GRID = "#D9D9D9"
BOX_FILL = "#F4F4F4"
BOX_EDGE = "#333333"


def _resolve_font():
    """Return the first font in FONT_STACK actually available, else DejaVu."""
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONT_STACK:
        if name in have:
            return name
    return "DejaVu Sans"


def apply_style(palette: str = DEFAULT_PALETTE, dpi: int = DEFAULT_DPI):
    """Install Nature-style rcParams. Returns the active colour list."""
    fam = _resolve_font()
    colors = PALETTES.get(palette, OKABE_ITO)
    plt.rcParams.update({
        # editable-text SVG: keep <text> as text, never outline to paths
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": dpi,
        "savefig.dpi": dpi,
        "font.family": fam,
        "font.size": FONT_BASE,
        "axes.titlesize": FONT_BASE,
        "axes.labelsize": FONT_BASE,
        "xtick.labelsize": FONT_TICK,
        "ytick.labelsize": FONT_TICK,
        "legend.fontsize": FONT_TICK,
        "axes.linewidth": 0.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "lines.linewidth": 1.0,
        "patch.linewidth": 0.5,
        "axes.edgecolor": SPINE,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": SPINE,
        "ytick.color": SPINE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.4,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": None,   # we manage layout ourselves for exact geometry
        "axes.prop_cycle": plt.cycler(color=colors),
    })
    return colors


def figsize(width: str | float = "single", height_mm: float | None = None,
            ratio: float = 0.75):
    """Return (w_in, h_in). `width` is a keyword or an explicit mm value."""
    if isinstance(width, str):
        w_mm = WIDTHS_MM.get(width.lower(), WIDTHS_MM["single"])
    else:
        w_mm = float(width)
    if height_mm is None:
        h_mm = min(w_mm * ratio, MAX_HEIGHT_MM)
    else:
        h_mm = min(float(height_mm), MAX_HEIGHT_MM)
    return (w_mm * MM, h_mm * MM)


def panel_letter(ax, letter: str, dx: float = -0.02, dy: float = 1.0):
    """Bold lower-case panel tag at the top-left, Nature convention."""
    ax.text(dx, dy, letter, transform=ax.transAxes,
            fontsize=FONT_PANEL, fontweight="bold", va="bottom", ha="right",
            clip_on=False)
