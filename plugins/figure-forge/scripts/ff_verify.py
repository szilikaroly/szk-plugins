"""The QC engine — the reason this plugin exists.

Works at the matplotlib-artist level so the geometry is *exact*: every label's
bounding box comes from the very renderer that draws the final figure, so what
we check is what will be printed.

Rules enforced (each a named check so the report is auditable):
  R1 CONTAINMENT   a label bound to a box must sit fully inside that box (+pad)
  R2 COVER         a label must not overlap any data mark / curve / arrow / box
  R3 COLLISION     no two labels may overlap
  R4 CANVAS        no label may cross the figure edge

`autofix()` runs check -> nudge -> re-check until clean or the iteration budget
is spent, then returns the residual violations so nothing is hidden.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------- geometry ----
def _rect(bb):
    return (bb.x0, bb.y0, bb.x1, bb.y1)


def _expand(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def _overlap(a, b):
    """AABB overlap area (0 if disjoint)."""
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    if dx <= 0 or dy <= 0:
        return 0.0
    return dx * dy


def _inside(inner, outer):
    """True if inner rect fully within outer rect."""
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def _sample_polyline(pts, step=3.0):
    """Densify a list of display-space points to <= `step` px spacing."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / step))
        for i in range(n + 1):
            t = i / n
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    if not out and pts:
        out = list(pts)
    return out


def _rect_hits_points(r, pts):
    for x, y in pts:
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
            return True
    return False


# ------------------------------------------------------------- registries -----
@dataclass
class Label:
    artist: object                     # matplotlib Text
    ax: object
    parent: object = None              # patch the label must stay inside, or None
    movable: bool = True
    min_fontsize: float = 5.0
    name: str = ""


@dataclass
class Obstacle:
    kind: str                          # 'line' | 'patch' | 'marks'
    artist: object
    ignore_labels: set = field(default_factory=set)  # labels allowed to touch it


class Verifier:
    def __init__(self, fig, margin_px=2.0):
        self.fig = fig
        self.margin = margin_px
        self.labels: list[Label] = []
        self.obstacles: list[Obstacle] = []

    # -- registration ---------------------------------------------------------
    def add_label(self, artist, ax, parent=None, movable=True, name=""):
        self.labels.append(Label(artist, ax, parent, movable, name=name or artist.get_text()))

    def add_obstacle(self, kind, artist, ignore_labels=None):
        self.obstacles.append(Obstacle(kind, artist, set(ignore_labels or [])))

    def auto_obstacles_from_axes(self, ax, ignore=None):
        """Register every drawn data element on an Axes as an obstacle."""
        ignore = ignore or []
        for ln in ax.get_lines():
            self.add_obstacle("line", ln, ignore)
        for pc in ax.collections:
            self.add_obstacle("marks", pc, ignore)
        for p in ax.patches:
            self.add_obstacle("patch", p, ignore)

    # -- measurement ----------------------------------------------------------
    def _renderer(self):
        self.fig.canvas.draw()
        return self.fig.canvas.get_renderer()

    def _label_rect(self, lab, rnd):
        return _rect(lab.artist.get_window_extent(rnd))

    def _obstacle_geom(self, ob, rnd):
        """Return ('rect', r) or ('pts', [..]) in display space."""
        if ob.kind == "line":
            xy = ob.artist.get_xydata()
            if xy is None or len(xy) == 0:
                return None
            disp = ob.artist.get_transform().transform(xy)
            return ("pts", _sample_polyline([tuple(p) for p in disp]))
        try:
            bb = ob.artist.get_window_extent(rnd)
            return ("rect", _rect(bb))
        except Exception:
            return None

    # -- checking -------------------------------------------------------------
    def check(self):
        rnd = self._renderer()
        fig_bb = _rect(self.fig.bbox)
        viols = []
        lab_rects = [(lab, self._label_rect(lab, rnd)) for lab in self.labels]

        for lab, r in lab_rects:
            # R4 canvas
            if not _inside(r, _expand(fig_bb, -1)):
                viols.append(_v("R4", "CANVAS", lab, "label crosses the figure edge"))
            # R1 containment
            if lab.parent is not None:
                try:
                    pr = _rect(lab.parent.get_window_extent(rnd))
                    if not _inside(r, _expand(pr, -self.margin)):
                        viols.append(_v("R1", "CONTAINMENT", lab,
                                        "label extends outside its box"))
                except Exception:
                    pass
            # R2 cover data / curves / arrows / other boxes
            for ob in self.obstacles:
                if lab.name in ob.ignore_labels or ob.artist is lab.parent:
                    continue
                g = self._obstacle_geom(ob, rnd)
                if not g:
                    continue
                er = _expand(r, self.margin)
                if g[0] == "rect":
                    if _overlap(er, g[1]) > 0:
                        viols.append(_v("R2", "COVER", lab,
                                        f"label overlaps a {ob.kind}"))
                        break
                elif _rect_hits_points(er, g[1]):
                    viols.append(_v("R2", "COVER", lab,
                                    "label covers a curve/line"))
                    break

        # R3 label-label
        for i in range(len(lab_rects)):
            for j in range(i + 1, len(lab_rects)):
                (la, ra), (lb, rb) = lab_rects[i], lab_rects[j]
                if _overlap(_expand(ra, self.margin), rb) > 0:
                    viols.append(_v("R3", "COLLISION", la,
                                    f"labels '{la.name}' and '{lb.name}' overlap"))
        return viols

    # -- fixing ---------------------------------------------------------------
    def _nudge_candidates(self, radius):
        """Spiral of (dx,dy) display offsets at a given radius (px)."""
        out = []
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            out.append((radius * math.cos(a), radius * math.sin(a)))
        return out

    def _move(self, lab, dx, dy):
        t = lab.artist.get_transform()
        x, y = t.transform(lab.artist.get_position())
        nd = t.inverted().transform((x + dx, y + dy))
        lab.artist.set_position((nd[0], nd[1]))

    def _center_in_parent(self, lab, rnd):
        pr = _rect(lab.parent.get_window_extent(rnd))
        cx, cy = (pr[0] + pr[2]) / 2, (pr[1] + pr[3]) / 2
        lab.artist.set_ha("center")
        lab.artist.set_va("center")
        nd = lab.artist.get_transform().inverted().transform((cx, cy))
        lab.artist.set_position((nd[0], nd[1]))

    def _label_ok(self, lab, rnd, fig_bb):
        r = _label_rect = _rect(lab.artist.get_window_extent(rnd))
        er = _expand(r, self.margin)
        if not _inside(r, _expand(fig_bb, -1)):
            return False
        if lab.parent is not None:
            pr = _rect(lab.parent.get_window_extent(rnd))
            if not _inside(r, _expand(pr, -self.margin)):
                return False
        for ob in self.obstacles:
            if lab.name in ob.ignore_labels or ob.artist is lab.parent:
                continue
            g = self._obstacle_geom(ob, rnd)
            if not g:
                continue
            if g[0] == "rect" and _overlap(er, g[1]) > 0:
                return False
            if g[0] == "pts" and _rect_hits_points(er, g[1]):
                return False
        for other in self.labels:
            if other is lab:
                continue
            orr = _rect(other.artist.get_window_extent(rnd))
            if _overlap(er, orr) > 0:
                return False
        return True

    def autofix(self, max_iter=40):
        """check -> correct -> re-check loop. Returns (residual, log)."""
        log = []
        for it in range(max_iter):
            viols = self.check()
            if not viols:
                log.append(f"clean after {it} iteration(s)")
                return [], log
            rnd = self._renderer()
            fig_bb = _rect(self.fig.bbox)
            moved = False
            for lab in self.labels:
                if not lab.movable:
                    continue
                if self._label_ok(lab, rnd, fig_bb):
                    continue
                # containment first: recentre in parent box
                if lab.parent is not None:
                    self._center_in_parent(lab, rnd)
                    rnd = self._renderer()
                    if self._label_ok(lab, rnd, fig_bb):
                        moved = True
                        continue
                    # box too small for text -> shrink font to the floor
                    fs = lab.artist.get_fontsize()
                    while fs > lab.min_fontsize and not self._label_ok(lab, rnd, fig_bb):
                        fs = max(lab.min_fontsize, fs - 0.5)
                        lab.artist.set_fontsize(fs)
                        rnd = self._renderer()
                    if self._label_ok(lab, rnd, fig_bb):
                        moved = True
                        continue
                # free-space search: spiral outward
                base = lab.artist.get_position()
                placed = False
                for radius in (4, 8, 12, 18, 26, 36, 50):
                    for dx, dy in self._nudge_candidates(radius):
                        lab.artist.set_position(base)
                        self._move(lab, dx, dy)
                        rnd = self._renderer()
                        if self._label_ok(lab, rnd, fig_bb):
                            placed = True
                            moved = True
                            break
                    if placed:
                        break
                if not placed:
                    lab.artist.set_position(base)
            if not moved:
                log.append(f"stalled at iteration {it}; {len(viols)} unresolved")
                return viols, log
        return self.check(), log


def _v(rule, kind, lab, msg):
    return {"rule": rule, "kind": kind, "label": lab.name, "message": msg}


# -------------------------------------------------- annotated overlay (proof) -
def annotate_overlay(fig, verifier, path, dpi=150):
    """Save a low-res proof PNG with a box drawn round every label so a human
    can SEE that each was checked; residual violations drawn in red."""
    import matplotlib.patches as mpatches
    rnd = verifier._renderer()
    viol_labels = {v["label"] for v in verifier.check()}
    inv = fig.transFigure.inverted()
    for lab in verifier.labels:
        r = _rect(lab.artist.get_window_extent(rnd))
        (x0, y0) = inv.transform((r[0], r[1]))
        (x1, y1) = inv.transform((r[2], r[3]))
        bad = lab.name in viol_labels
        fig.add_artist(mpatches.Rectangle(
            (x0, y0), x1 - x0, y1 - y0, transform=fig.transFigure,
            fill=False, lw=0.6, ec=("#D55E00" if bad else "#009E73"),
            ls=("-" if bad else ":"), zorder=1000))
    fig.savefig(path, dpi=dpi, bbox_inches=fig.get_tightbbox(rnd).padded(0.03))
