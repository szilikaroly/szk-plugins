#!/usr/bin/env python3
"""Close the loop: archive, compress, and let compaction fire on its own.

Until now memo-guard's README said flatly that "no script can open a new
context" — /compact was yours to run. Half of that is still true: a hook cannot
execute a slash command, and this file does not pretend otherwise. But Claude
Code *itself* compacts automatically, and where that trigger sits is readable
from the environment:

    CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=<1..100>

Verified against the shipped binary (2.1.211 and 2.1.237), which computes

    threshold = min(floor(effective_window * pct / 100), effective_window - 13000)

and fires between turns, never inside one — which is exactly the "when the
current step has finished" the operator wants, and something no percentage
watcher of ours could have achieved on its own.

So autopilot does not trigger compaction. It *aims* the trigger the product
already has, and memo-guard's PreCompact hook then guarantees that nothing is
lost when it fires.

Two things this deliberately does not assume
--------------------------------------------
1. **The two percentages are not the same percentage.** Ours is measured against
   the model's real window; Claude Code's is against an *effective* window —
   the real one minus a reserve, and shrunk further by the `autoCompactWindow`
   setting if present. Writing 70 into the override therefore does NOT mean
   compaction at the 70% this plugin reports. Rather than reimplement the
   product's arithmetic (which would break the first time it changed), autopilot
   measures where compaction actually landed and corrects the override toward
   the target. One or two compactions and it converges.

2. **The environment is read at process start.** Writing settings.json cannot
   change the running session's `process.env`; the new value applies from the
   next session. Saying otherwise would be the kind of claim that looks true
   until someone depends on it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

ENV_KEY = "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
# Below this the product's own floor (window - 13000) wins and the override
# stops meaning anything; above it there is no room left to compact into.
OVERRIDE_MIN, OVERRIDE_MAX = 5.0, 95.0
# How far off target a firing has to land before the override is moved. Small
# drifts are noise — the token count at a turn boundary is not continuous.
TOLERANCE_PCT = 2.5


def settings_path() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(d) / "settings.json"


def state_path() -> Path:
    return mg.data_dir() / "autopilot.json"


def load_state() -> dict:
    try:
        return json.loads(state_path().read_text())
    except Exception:
        return {}


def save_state(st: dict) -> None:
    try:
        state_path().write_text(json.dumps(st, indent=2) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- settings

def read_settings() -> dict:
    p = settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception as e:
        raise SystemExit(f"memo-guard: {p} is not valid JSON ({e}); "
                         "refusing to touch it")


def write_settings(data: dict) -> Path:
    """Rewrite settings.json, keeping one backup and never leaving it half-written.

    This is the user's own configuration file and other tools read it on every
    session start, so a truncated write is worse than no write at all.
    """
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        bak = p.with_suffix(".json.memo-guard.bak")
        bak.write_text(p.read_text())
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, p)
    return p


def apply_override(value: float | None) -> Path:
    """Set (or remove) the override in settings.json's env block."""
    data = read_settings()
    env = data.get("env")
    if not isinstance(env, dict):
        env = {}
    if value is None:
        env.pop(ENV_KEY, None)
    else:
        # Whole numbers stay whole: "70", not "70.0". parseFloat takes either,
        # but a config file a human reads should not look machine-generated.
        env[ENV_KEY] = f"{value:g}"
    if env:
        data["env"] = env
    else:
        data.pop("env", None)
    return write_settings(data)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return -1.0


def blockers() -> list[str]:
    """Reasons compaction genuinely would not fire. Nothing else belongs here.

    `autoCompactWindow` used to be on this list and should not have been: it
    changes where compaction fires, it does not prevent it, and calibration
    already corrects for it. Listing a handled caveat as a blocker teaches the
    reader to skim the list, which is how the real entries stop being read.
    """
    out = []
    if os.environ.get("DISABLE_AUTO_COMPACT"):
        out.append("DISABLE_AUTO_COMPACT is set in the environment — "
                   "auto-compaction is off regardless of any threshold")
    data = read_settings()
    if data.get("autoCompactEnabled") is False:
        out.append('settings.json has "autoCompactEnabled": false')
    # The state file and settings.json are two files that have to agree, and
    # nothing kept them agreeing. They drifted here during development — state
    # written with one CLAUDE_CONFIG_DIR, settings with another — leaving
    # autopilot reporting ON while nothing at all would fire. Silent and
    # complete failure; worth one comparison.
    st = load_state()
    if st.get("enabled"):
        written = (data.get("env") or {}).get(ENV_KEY)
        if not written:
            out.append(f"autopilot's own state says ON, but {ENV_KEY} is not in "
                       f"settings.json — nothing will fire early. Re-run "
                       f"--enable to make them agree.")
        elif abs(_num(written) - float(st.get("override", -1))) > 0.05:
            out.append(f"settings.json says {ENV_KEY}={written} but autopilot "
                       f"last wrote {st.get('override')} — a correction did not "
                       f"reach the file. Re-run --enable.")
    return out


def caveats() -> list[str]:
    """True, worth knowing, and not a reason it will fail."""
    out = []
    acw = read_settings().get("autoCompactWindow")
    if acw:
        out.append(f'settings.json sets "autoCompactWindow": {acw} — Claude '
                   f"Code measures against that, not the model's real window, "
                   f"so the override percentage is of {acw}, not of the window "
                   f"/memo-guard:status reports. Calibration corrects for this.")
    return out


# --------------------------------------------------------------------------- calibration

def record_firing(measured_pct: float, cfg: dict) -> dict:
    """A compaction just fired at `measured_pct` of our window. Learn from it.

    Called from the PreCompact hook with trigger=auto. Manual compactions are
    not samples: the user chose the moment, so they say nothing about where the
    threshold sits.
    """
    st = load_state()
    if not st.get("enabled"):
        return st
    target = float(st.get("target", cfg.get("auto_compact_at", 70)))
    override = float(st.get("override", target))

    samples = st.get("samples", [])
    samples.append({"measured": round(measured_pct, 1),
                    "override": override,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
    st["samples"] = samples[-20:]

    drift = measured_pct - target
    if abs(drift) <= TOLERANCE_PCT or measured_pct <= 0:
        st["calibrated"] = True
        save_state(st)
        return st

    # The relationship is linear — both sides are a fraction of a fixed window —
    # so one proportional step lands on target rather than crawling toward it.
    new = override * target / measured_pct
    new = max(OVERRIDE_MIN, min(OVERRIDE_MAX, new))
    if abs(new - override) < 0.5:
        st["calibrated"] = True
        save_state(st)
        return st

    st["override"] = round(new, 1)
    st["calibrated"] = False
    st["last_correction"] = {
        "from": override, "to": st["override"],
        "fired_at_pct": round(measured_pct, 1), "target": target,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        apply_override(st["override"])
        st["pending_since"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    except SystemExit as e:
        st["error"] = str(e)
    save_state(st)
    return st


# --------------------------------------------------------------------------- commands

def cmd_enable(target: float) -> int:
    st = load_state()
    # Keep a learned override across a re-enable at the same target; throw it
    # away when the target moves, because it was calibrated for the old one.
    keep = (st.get("calibrated") and float(st.get("target", -1)) == target)
    override = float(st["override"]) if keep else target
    st.update({"enabled": True, "target": target, "override": override,
               "calibrated": bool(keep),
               "enabled_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    if not keep:
        st["samples"] = []
    p = apply_override(override)
    save_state(st)

    print(f"autopilot ▸ ON, target {target:g}% of the measured context window")
    print(f"  {ENV_KEY}={override:g} written to {p}")
    if not keep:
        print("  Not calibrated yet: the first automatic compaction will "
              "almost certainly land off target. memo-guard records where it "
              "actually fired and corrects the override — expect one or two "
              "compactions before it settles.")
    else:
        print(f"  Reusing the calibrated override from an earlier run.")
    for b in blockers():
        print(f"  ! {b}")
    for c in caveats():
        print(f"  · {c}")
    print("  Takes effect in the NEXT session: the environment is read at "
          "process start, so this one keeps its old threshold.")
    return 0


def cmd_disable() -> int:
    st = load_state()
    st["enabled"] = False
    p = apply_override(None)
    save_state(st)
    print(f"autopilot ▸ OFF. {ENV_KEY} removed from {p}.")
    print("  Claude Code returns to its own default threshold "
          "(effective window minus 13,000 tokens) in the next session.")
    print("  The archive/compress hooks are untouched — nothing stops being "
          "preserved, compaction just stops happening early.")
    return 0


def cmd_status(as_json: bool = False) -> int:
    st = load_state()
    cur = os.environ.get(ENV_KEY)
    data = read_settings()
    in_settings = (data.get("env") or {}).get(ENV_KEY)
    info = {
        "enabled": bool(st.get("enabled")),
        "target_pct": st.get("target"),
        "override_written": in_settings,
        "override_active_in_this_process": cur,
        "calibrated": bool(st.get("calibrated")),
        "samples": st.get("samples", [])[-5:],
        "last_correction": st.get("last_correction"),
        "blockers": blockers(),
        "caveats": caveats(),
    }
    if as_json:
        print(json.dumps(info, indent=2))
        return 0
    print(f"autopilot        : {'ON' if info['enabled'] else 'off'}")
    if not info["enabled"]:
        print("  enable with: autopilot.py --enable --at 70")
        return 0
    print(f"target           : {info['target_pct']:g}% of the measured window")
    print(f"override written : {in_settings or '(none)'}")
    print(f"override active  : {cur or '(not in this process — set before it started)'}")
    print(f"calibrated       : {'yes' if info['calibrated'] else 'no (learning)'}")
    for s in info["samples"]:
        print(f"  fired at {s['measured']:.1f}% with override {s['override']:g} ({s['ts']})")
    lc = info["last_correction"]
    if lc:
        print(f"last correction  : {lc['from']:g} -> {lc['to']:g} "
              f"after firing at {lc['fired_at_pct']:.1f}%")
    for b in info["blockers"]:
        print(f"  ! {b}")
    for c in info["caveats"]:
        print(f"  · {c}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--disable", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--at", type=float, default=None,
                    help="target context %% at which compaction should fire")
    ap.add_argument("--record", type=float, default=None,
                    help="internal: a compaction fired at this measured %%")
    args = ap.parse_args()

    cfg = mg.load_config()
    if args.record is not None:
        st = record_firing(args.record, cfg)
        print(json.dumps({"override": st.get("override"),
                          "calibrated": st.get("calibrated")}))
        return 0
    if args.disable:
        return cmd_disable()
    if args.enable:
        at = args.at if args.at is not None else float(cfg.get("auto_compact_at", 70))
        if not (OVERRIDE_MIN <= at <= OVERRIDE_MAX):
            raise SystemExit(f"--at must be between {OVERRIDE_MIN:g} and "
                             f"{OVERRIDE_MAX:g}; got {at:g}")
        return cmd_enable(at)
    return cmd_status(args.json)


if __name__ == "__main__":
    sys.exit(main())
