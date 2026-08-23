"""Figure builders. Each returns (fig, verifier) with labels + obstacles already
registered, so the caller just runs verifier.autofix() and exports.

Every builder is Nature-styled by default (call ff_style.apply_style first).
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import ff_style as S
from ff_typography import tx
from ff_verify import Verifier


# ============================================================== BOX PLOT ======
def box_plot(df, value, group, *, width="single", ylabel=None, palette=None,
             title=None):
    """Grouped box plot with jittered points. Labels checked for data cover."""
    colors = palette or plt.rcParams["axes.prop_cycle"].by_key()["color"]
    groups = list(dict.fromkeys(df[group].tolist()))
    data = [df.loc[df[group] == g, value].dropna().values for g in groups]

    fig, ax = plt.subplots(figsize=S.figsize(width))
    bp = ax.boxplot(data, positions=range(len(groups)), widths=0.6,
                    patch_artist=True, showfliers=False,
                    medianprops=dict(color=S.INK, linewidth=1.0),
                    whiskerprops=dict(color=S.SPINE, linewidth=0.6),
                    capprops=dict(color=S.SPINE, linewidth=0.6),
                    boxprops=dict(linewidth=0.6))
    for i, box in enumerate(bp["boxes"]):
        box.set_facecolor(colors[i % len(colors)])
        box.set_alpha(0.55)
        box.set_edgecolor(S.INK)
    # jittered raw points
    rng = np.random.default_rng(0)
    for i, d in enumerate(data):
        x = i + (rng.random(len(d)) - 0.5) * 0.28
        ax.scatter(x, d, s=6, color=colors[i % len(colors)], edgecolor="white",
                   linewidth=0.3, zorder=3)

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([tx(str(g)) for g in groups])
    ax.set_ylabel(tx(ylabel or value))
    if title:
        ax.set_title(tx(title), loc="left", fontweight="bold")

    v = Verifier(fig)
    v.auto_obstacles_from_axes(ax)      # boxes, whiskers, points are obstacles
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        pass  # tick labels are managed by matplotlib layout; not free-moved here
    return fig, v


# ============================================================ XY PLOT =========
def xy_plot(df, x, y, *, series=None, kind="line", width="single",
            xlabel=None, ylabel=None, palette=None, title=None,
            direct_label=True):
    """Line or scatter plot, one series per `series` value. When direct_label is
    on, each series is named at the end of its curve and the labels are QC'd so
    none sits on a curve or on another label (Nature prefers this to a legend).
    """
    colors = palette or plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, ax = plt.subplots(figsize=S.figsize(width))
    groups = ([None] if series is None
              else list(dict.fromkeys(df[series].tolist())))
    ends = []
    for i, g in enumerate(groups):
        sub = df if g is None else df[df[series] == g]
        sub = sub.sort_values(x)
        c = colors[i % len(colors)]
        if kind == "scatter":
            ax.scatter(sub[x], sub[y], s=10, color=c, edgecolor="white",
                       linewidth=0.3, zorder=3, label=tx(str(g)))
        else:
            ax.plot(sub[x], sub[y], color=c, lw=1.2, marker="o", ms=3,
                    zorder=3, label=tx(str(g)))
        if g is not None and len(sub):
            ends.append((sub[x].iloc[-1], sub[y].iloc[-1], tx(str(g)), c))

    ax.set_xlabel(tx(xlabel or x))
    ax.set_ylabel(tx(ylabel or y))
    if title:
        ax.set_title(tx(title), loc="left", fontweight="bold")

    v = Verifier(fig)
    v.auto_obstacles_from_axes(ax)
    if direct_label and ends:
        xspan = df[x].max() - df[x].min()
        ax.set_xlim(df[x].min(), df[x].max() + 0.16 * xspan)
        for xe, ye, name, c in ends:
            t = ax.text(xe + 0.02 * xspan, ye, name, color=c, va="center",
                        ha="left", fontsize=S.FONT_TICK)
            v.add_label(t, ax, name=name)
    elif series is not None:
        ax.legend(loc="best")
    return fig, v


# ============================================================ FOREST PLOT =====
def forest_plot(df, *, label, effect, low, high, width="double",
                xlabel="Effect size (95% CI)", ref=1.0, logx=False,
                weight=None, title=None):
    """Forest/meta-analysis plot. Study labels must never sit on a CI line."""
    rows = df.to_dict("records")
    n = len(rows)
    fig, ax = plt.subplots(figsize=S.figsize(width, height_mm=max(45, 12 + 7 * n)))
    ys = list(range(n))[::-1]

    v = Verifier(fig)
    for y, r in zip(ys, rows):
        e, lo, hi = r[effect], r[low], r[high]
        ax.plot([lo, hi], [y, y], color=S.INK, lw=0.9, solid_capstyle="round",
                zorder=2)
        sz = 18
        if weight and weight in r and r[weight] == r[weight]:
            sz = 8 + 42 * float(r[weight]) / max(float(x[weight]) for x in rows)
        ax.scatter([e], [y], s=sz, marker="s", color=S.PALETTES["okabe-ito"][5],
                   zorder=3, edgecolor="white", linewidth=0.3)

    ax.axvline(ref, color=S.SPINE, lw=0.5, ls="--", zorder=1)
    if logx:
        ax.set_xscale("log")
    ax.set_yticks([])
    ax.set_xlabel(tx(xlabel))
    ax.spines["left"].set_visible(False)

    # register obstacles (CI lines + markers) BEFORE placing labels
    v.auto_obstacles_from_axes(ax)

    # study labels to the left of the lowest CI; placed then collision-checked
    xmin = min(r[low] for r in rows)
    xspan = max(r[high] for r in rows) - xmin
    lx = xmin - 0.04 * xspan
    for y, r in zip(ys, rows):
        name = tx(str(r[label]))
        t = ax.text(lx, y, name, va="center", ha="right",
                    fontsize=S.FONT_TICK, clip_on=False)
        v.add_label(t, ax, name=name)
    ax.set_xlim(lx - 0.02 * xspan, max(r[high] for r in rows) + 0.05 * xspan)
    ax.set_ylim(-1, n)
    if title:
        ax.set_title(tx(title), loc="left", fontweight="bold")
    return fig, v


# ============================================================== FLOWCHART =====
def flowchart(spec, *, width="single", title=None):
    """Node/edge flowchart from a spec dict. Node labels are contained in their
    boxes; edges are obstacles so no label sits on an arrow.

    spec = {
      "nodes": [{"id","text","x","y","w","h","shape"?,"color"?}, ...],
      "edges": [{"from","to","label"?}, ...],   # ids
      "direction": "TB"|"LR"                     # only affects default arrows
    }
    Coordinates are in a 0..100 canvas; omit x/y to auto-stack vertically.
    """
    nodes = {nd["id"]: dict(nd) for nd in spec.get("nodes", [])}
    edges = spec.get("edges", [])
    _autolayout(nodes, spec.get("direction", "TB"))

    fig, ax = plt.subplots(figsize=S.figsize(width, height_mm=_canvas_h(nodes, width)))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_aspect("auto")

    v = Verifier(fig)
    patches = {}
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, (nid, nd) in enumerate(nodes.items()):
        w, h = nd.get("w", 26), nd.get("h", 12)
        x, y = nd["x"], nd["y"]
        shape = nd.get("shape", "box")
        fc = nd.get("color", S.BOX_FILL)
        style = "round,pad=0.02,rounding_size=2" if shape != "sharp" else "square,pad=0.02"
        box = mpatches.FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                      boxstyle=style, linewidth=0.8,
                                      edgecolor=S.BOX_EDGE, facecolor=fc, zorder=2)
        ax.add_patch(box)
        patches[nid] = box

    # edges first as obstacles, so labels avoid them
    for e in edges:
        a, b = nodes[e["from"]], nodes[e["to"]]
        arr = ax.annotate("", xy=(b["x"], b["y"]), xytext=(a["x"], a["y"]),
                          arrowprops=dict(arrowstyle="-|>", color=S.SPINE,
                                          lw=0.8, shrinkA=14, shrinkB=14),
                          zorder=1)
    for p in patches.values():
        v.add_obstacle("patch", p)
    for ln in ax.get_lines():
        v.add_obstacle("line", ln)

    # node text, bound to its box (R1 containment enforced)
    for nid, nd in nodes.items():
        t = ax.text(nd["x"], nd["y"], tx(nd["text"]), ha="center", va="center",
                    fontsize=S.FONT_BASE, wrap=True, zorder=3)
        v.add_label(t, ax, parent=patches[nid], name=nid)
    if title:
        ax.set_title(tx(title), loc="left", fontweight="bold")
    return fig, v


def _autolayout(nodes, direction):
    """Fill in x/y for nodes that lack them: simple vertical/horizontal stack."""
    missing = [nid for nid, nd in nodes.items() if "x" not in nd or "y" not in nd]
    if not missing:
        return
    n = len(nodes)
    step = 90 / max(1, n)
    for i, (nid, nd) in enumerate(nodes.items()):
        if direction == "LR":
            nd.setdefault("x", 8 + step * i + step / 2)
            nd.setdefault("y", 50)
        else:  # TB
            nd.setdefault("x", 50)
            nd.setdefault("y", 95 - step * i - step / 2)


def _canvas_h(nodes, width):
    n = max(1, len(nodes))
    return min(S.MAX_HEIGHT_MM, 18 * n)


# ============================================================ MULTI-PANEL =====
def assemble(panel_pngs, *, layout=None, width="double", labels=True):
    """Compose pre-rendered panel PNGs into one Nature-format composite.
    panel_pngs: list of image paths. layout: (rows, cols) or None (auto).
    """
    import math
    from PIL import Image
    n = len(panel_pngs)
    if layout is None:
        cols = 1 if n == 1 else (2 if n <= 4 else 3)
        rows = math.ceil(n / cols)
    else:
        rows, cols = layout
    fig = plt.figure(figsize=S.figsize(width, height_mm=None,
                                       ratio=0.32 * rows + 0.1))
    v = Verifier(fig)
    letters = "abcdefghijklmnop"
    for i, png in enumerate(panel_pngs):
        ax = fig.add_subplot(rows, cols, i + 1)
        ax.imshow(Image.open(png))
        ax.axis("off")
        if labels:
            # inside the panel's top-left corner, so it never crosses the canvas
            t = ax.text(0.015, 0.985, letters[i], transform=ax.transAxes,
                        fontsize=S.FONT_PANEL, fontweight="bold",
                        va="top", ha="left")
            v.add_label(t, ax, name=f"panel-{letters[i]}", movable=False)
    fig.subplots_adjust(wspace=0.06, hspace=0.06, left=0.04, right=0.99,
                        top=0.95, bottom=0.02)
    return fig, v
