#!/usr/bin/env python3
"""The resource broker — one gate in front of every local-model use.

Why this exists, measured
-------------------------
Four separate problems turned out to be one problem:

  * Two compression runs on one Ollama instance starved each other. Observed:
    19 minutes at 0.0% CPU with the server unresponsive, recovering in 3 seconds
    the moment the competing processes were killed. The existing lock is
    per-session (`sessions/<id>/.lock`), so two Claude Code windows defeat it.
  * When that lock DID hold, it silently skipped the newer compression
    entirely — "another run is active" and the 80% memo was simply never built.
  * `route.py` documents "only one model resident at a time" as a fact about a
    16 GB machine. It is not enforced anywhere; nothing stops N processes from
    each loading a model.
  * Background work (re-embedding after a model change, reorganising a full
    memory block) has nowhere to run, so it does not exist.

All four are the same missing thing: nobody owns the local model. This does.

Design rules it follows
-----------------------
  Wait, never skip.   A caller that cannot get the lock now waits for it. The
                      old behaviour dropped work silently, which is worse than
                      slow — you cannot see it happen.
  Deadlines, not hope. Every acquisition has a deadline. Past it the caller is
                      told to degrade (deterministic mode), not left blocking.
  Stale locks die.     A lock whose owner is gone is broken automatically. A
                      crashed compressor must not wedge the machine until a
                      timeout that nobody is watching expires.
  Capacity is measured, not assumed. How many model jobs may run at once comes
                      from probed VRAM, not from a constant that happens to be
                      right on one laptop.

  broker.py --probe          hardware, backend, models, derived capacity
  broker.py --status         who holds the lock right now
  broker.py --health         is the model server actually answering
  broker.py --break-lock     force-release (only when you know it is stale)

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# A lock older than this with no heartbeat is treated as abandoned. Long enough
# that a slow-but-alive job is never stolen from, short enough that a crash does
# not block the next session for an hour.
STALE_AFTER_S = 180
HEARTBEAT_S = 30


def lock_dir() -> Path:
    p = mg.data_dir() / "locks"
    p.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------- probe

def _run(cmd: list[str], timeout: float = 4.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def probe_hardware() -> dict:
    """Vendor and usable VRAM in MB. Unknown is reported as unknown, never guessed."""
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits"])
    if out.strip():
        name, mem, drv = (x.strip() for x in out.strip().splitlines()[0].split(","))
        return {"vendor": "nvidia", "device": name, "vram_mb": int(float(mem)),
                "driver": drv, "backend": "cuda"}

    out = _run(["rocm-smi", "--showmeminfo", "vram", "--json"])
    if out.strip():
        try:
            d = json.loads(out)
            tot = max(int(v.get("VRAM Total Memory (B)", 0))
                      for v in d.values() if isinstance(v, dict))
            gfx = ""
            m = re.search(r"gfx\d+", _run(["rocminfo"]))
            if m:
                gfx = m.group(0)
            return {"vendor": "amd", "device": gfx or "radeon",
                    "vram_mb": tot // (1024 * 1024), "backend": "rocm",
                    "note": "consumer cards often need HSA_OVERRIDE_GFX_VERSION"}
        except (ValueError, KeyError):
            pass
    for p in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
        try:
            return {"vendor": "amd", "device": "radeon", "backend": "rocm",
                    "vram_mb": int(p.read_text().strip()) // (1024 * 1024)}
        except (OSError, ValueError):
            continue

    out = _run(["system_profiler", "SPHardwareDataType"])
    if "Chip:" in out:
        chip = re.search(r"Chip:\s*(.+)", out)
        mem = re.search(r"Memory:\s*(\d+)\s*GB", out)
        total = int(mem.group(1)) * 1024 if mem else 0
        return {"vendor": "apple", "device": chip.group(1).strip() if chip else "apple",
                # Unified memory is shared with the OS; ~75% is the practical ceiling.
                "vram_mb": int(total * 0.75), "backend": "metal"}

    return {"vendor": "unknown", "device": "", "vram_mb": 0, "backend": "cpu"}


def loaded_models() -> list[dict]:
    """What Ollama currently holds, and whether it actually fits on the GPU.

    size_vram/size is the only honest answer to "is this accelerated". A model
    that silently spilled to CPU still works — it is just 20x slower, and
    nothing anywhere says so.
    """
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=3) as r:
            d = json.loads(r.read())
    except Exception:
        return []
    out = []
    for m in d.get("models", []):
        size, vram = m.get("size", 0), m.get("size_vram", 0)
        out.append({"name": m.get("name", "?"), "size_mb": size // (1024 * 1024),
                    "on_gpu": round(vram / size, 3) if size else 0.0})
    return out


def capacity(hw: dict | None = None) -> int:
    """How many model jobs may run at once. Derived from VRAM, not assumed.

    The 12b escalation model is ~7.6 GB; two of those need real headroom. This
    is what `route.py` asserts as a comment and never enforces.
    """
    hw = hw or probe_hardware()
    vram = hw.get("vram_mb", 0)
    if vram >= 40_000:
        return 4
    if vram >= 24_000:
        return 2
    return 1            # includes unknown/CPU: assume the tightest case


def healthy(timeout: float = 3.0) -> bool:
    """Cheap liveness check. A wedged server answers /api/tags but not /api/embed,
    so probe the path that actually does work."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA}/api/embed",
            data=json.dumps({"model": "nomic-embed-text", "input": "ping"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return bool(json.loads(r.read()).get("embeddings"))
    except Exception:
        try:
            with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=timeout) as r:
                return bool(json.loads(r.read()).get("models"))
        except Exception:
            return False


# --------------------------------------------------------------------------- lock

def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def lock_status(name: str = "model") -> dict | None:
    p = lock_dir() / f"{name}.lock"
    if not p.exists():
        return None
    d = _read(p)
    if not d:
        # Unreadable is not the same as abandoned. Falling back to 0 here made
        # age look infinite, so a lock being written was judged stale and a
        # competing process deleted a live one — two holders at once.
        try:
            age = time.time() - p.stat().st_mtime
        except OSError:
            return None
        return {"pid": -1, "owner": "?", "age_s": round(age, 1),
                "stale": age > STALE_AFTER_S}
    age = time.time() - float(d.get("heartbeat") or d.get("since") or 0)
    return {**d, "age_s": round(age, 1),
            "stale": age > STALE_AFTER_S or not _alive(int(d.get("pid", -1)))}


@contextmanager
def slot(name: str = "model", deadline_s: float = 90.0, owner: str = ""):
    """Acquire one model slot, or yield False so the caller can degrade.

    Yields True when the slot is held. Yields False when the deadline passed —
    the caller must then take the deterministic path rather than blocking or
    silently skipping its work.
    """
    p = lock_dir() / f"{name}.lock"
    start = time.time()
    held = False
    try:
        while True:
            st = lock_status(name)
            if st is None or st["stale"]:
                if st and st["stale"]:
                    try:
                        p.unlink()
                    except OSError:
                        pass
                # Write the content FIRST, then link it into place. os.link is
                # atomic and fails if the target exists, so the lock file never
                # exists in a half-written state for another process to
                # misread. O_EXCL alone left exactly that window open.
                tmp = p.with_suffix(f".tmp.{os.getpid()}")
                try:
                    tmp.write_text(json.dumps(
                        {"pid": os.getpid(), "owner": owner,
                         "since": time.time(), "heartbeat": time.time()}))
                    os.link(tmp, p)
                    held = True
                    break
                except FileExistsError:
                    pass
                except OSError:
                    pass
                finally:
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            if time.time() - start > deadline_s:
                break
            time.sleep(0.5)
        yield held
    finally:
        if held:
            try:
                p.unlink()
            except OSError:
                pass


def beat(name: str = "model") -> None:
    """Refresh the heartbeat so a long but living job is not judged stale."""
    p = lock_dir() / f"{name}.lock"
    d = _read(p)
    if d.get("pid") == os.getpid():
        d["heartbeat"] = time.time()
        try:
            p.write_text(json.dumps(d))
        except OSError:
            pass


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--break-lock", action="store_true")
    ap.add_argument("--name", default="model")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.health:
        ok = healthy()
        print("model server: " + ("responding" if ok else "NOT responding"))
        return 0 if ok else 1

    if args.break_lock:
        p = lock_dir() / f"{args.name}.lock"
        st = lock_status(args.name)
        if not st:
            print("no lock held")
            return 1
        if not st["stale"]:
            print(f"lock is LIVE (pid {st.get('pid')}, {st['age_s']}s, "
                  f"owner {st.get('owner')}). Refusing — kill the owner first "
                  f"if you are sure.", file=sys.stderr)
            return 2
        p.unlink()
        print("stale lock removed")
        return 0

    if args.status:
        st = lock_status(args.name)
        print(json.dumps(st, indent=2) if args.json else
              (f"held by pid {st.get('pid')} ({st.get('owner')}) for {st['age_s']}s"
               f"{'  [STALE]' if st['stale'] else ''}" if st else "free"))
        return 0

    hw = probe_hardware()
    info = {**hw, "capacity": capacity(hw), "healthy": healthy(),
            "loaded": loaded_models(), "lock": lock_status()}
    if args.json:
        print(json.dumps(info, indent=2))
        return 0
    print(f"vendor    : {hw['vendor']} ({hw.get('device','')})")
    print(f"backend   : {hw['backend']}")
    print(f"vram      : {hw['vram_mb']:,} MB usable")
    print(f"capacity  : {info['capacity']} concurrent model job(s)")
    print(f"server    : {'responding' if info['healthy'] else 'NOT responding'}")
    if hw.get("note"):
        print(f"note      : {hw['note']}")
    for m in info["loaded"]:
        flag = "" if m["on_gpu"] >= 0.95 else "   <-- PARTLY ON CPU, ~20x slower"
        print(f"  loaded  : {m['name']:<24} {m['size_mb']:>6} MB  "
              f"gpu={m['on_gpu']:.0%}{flag}")
    st = info["lock"]
    print(f"lock      : {'free' if not st else ('held ' + str(st['age_s']) + 's' + (' [STALE]' if st['stale'] else ''))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
