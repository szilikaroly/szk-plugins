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
    """Machine-wide, deliberately NOT under the plugin data dir.

    The first version put locks under mg.data_dir(), which is keyed to
    CLAUDE_PLUGIN_DATA / MEMO_GUARD_HOME. Two installs — or a test run with
    MEMO_GUARD_HOME set — therefore had different lock directories and could not
    see each other. Observed: two memo_gen processes driving one Ollama at the
    same time, which is the exact starvation the lock exists to prevent.

    The resource being guarded is a single model server on this machine, so the
    lock must be keyed to that, not to whichever data dir the caller happens to
    have. MEMO_GUARD_LOCK_DIR overrides it for genuinely separate servers.
    """
    d = os.environ.get("MEMO_GUARD_LOCK_DIR")
    p = Path(d) if d else Path.home() / ".claude" / "memo-guard-locks"
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


# Task profile -> (preferred, fallback-when-tight). The tight column is not a
# lesser answer, it is the only answer on a machine that cannot hold the first
# one: a model that does not fit runs on the CPU at roughly a twentieth of the
# speed, so "smaller and resident" beats "larger and spilled" every time.
ROUTES = {
    "extract":  ("llama3.1:8b",      "llama3.2:3b"),      # cognify entity pull
    "prose":    ("llama3.1:8b",      "llama3.2:3b"),      # memo generation
    "code":     ("qwen2.5-coder:7b", "qwen2.5-coder:3b"),
    "reason":   ("gemma4:12b",       "llama3.1:8b"),      # escalation
    "embed":    ("nomic-embed-text", "nomic-embed-text"),
    "embed_hq": ("mxbai-embed-large", "nomic-embed-text"),
}


def route(profile: str, hw: dict | None = None) -> str:
    """Pick a model for a task, given what this machine can actually hold.

    Adaptive means two things at once: the task decides which family, and the
    measured hardware decides which size. `route.py` in memo-index asserts a
    16 GB assumption as a constant; this reads the number instead.
    """
    env = os.environ.get(f"MEMO_MODEL_{profile.upper()}") or os.environ.get("MEMO_MODEL")
    if env:
        return env
    pref, tight = ROUTES.get(profile, ROUTES["prose"])
    hw = hw or probe_hardware()
    have = {m.split(":")[0] for m in catalog()}
    vram = hw.get("vram_mb", 0)
    sizes = catalog()
    want_mb = sizes.get(pref) or sizes.get(f"{pref}:latest") or 0
    # Leave headroom for the KV cache; a model that exactly fills VRAM spills
    # the moment the context grows.
    if want_mb and vram and want_mb * 1.25 > vram:
        if tight.split(":")[0] in have:
            return tight
    if pref.split(":")[0] in have:
        return pref
    return tight if tight.split(":")[0] in have else pref


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


# --------------------------------------------------------------------------- fit / recovery

def catalog() -> dict[str, int]:
    """Every pulled model and its size in MB."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=4) as r:
            return {m["name"]: m.get("size", 0) // (1024 * 1024)
                    for m in json.loads(r.read()).get("models", [])}
    except Exception:
        return {}


def free_vram_mb(hw: dict | None = None) -> int:
    hw = hw or probe_hardware()
    used = sum(m["size_mb"] for m in loaded_models())
    return max(0, hw.get("vram_mb", 0) - used)


def unload(model: str, timeout: float = 10.0) -> bool:
    """Evict a model now. `keep_alive: 0` frees its VRAM immediately.

    This is the safe half of recovery: nothing is lost, the next request simply
    reloads. It is what makes room for a model that would otherwise spill.
    """
    try:
        req = urllib.request.Request(
            f"{OLLAMA}/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0,
                             "prompt": "", "stream": False}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=timeout).read()
        return True
    except Exception:
        return False


def ensure_room(model: str, hw: dict | None = None) -> dict:
    """Make room BEFORE loading, instead of discovering the spill afterwards.

    A model that does not fit still loads — Ollama silently puts the overflow on
    CPU and everything keeps working at roughly 1/20th speed. Nothing reports
    it. Evicting an idle model first is cheaper than running the next twenty
    minutes of work on the CPU.
    """
    hw = hw or probe_hardware()
    want = catalog().get(model) or catalog().get(f"{model}:latest") or 0
    if not want or not hw.get("vram_mb"):
        return {"action": "unknown", "evicted": []}
    evicted = []
    for m in sorted(loaded_models(), key=lambda x: -x["size_mb"]):
        if free_vram_mb(hw) >= want * 1.1:      # 10% headroom for KV cache
            break
        if m["name"].split(":")[0] == model.split(":")[0]:
            continue                            # already the one we want
        if unload(m["name"]):
            evicted.append(m["name"])
    fits = free_vram_mb(hw) >= want
    return {"action": "ok" if fits else "will_spill", "wanted_mb": want,
            "free_mb": free_vram_mb(hw), "evicted": evicted}


def diagnose(hw: dict | None = None) -> dict:
    """One structured verdict, with the evidence that produced it.

    WEDGED and SLOW look identical from the outside — both mean "nothing is
    coming back" — but they need opposite responses, so they are separated by
    measurement rather than guessed at.
    """
    hw = hw or probe_hardware()
    t0 = time.time()
    alive = healthy(4.0)
    probe_ms = (time.time() - t0) * 1000
    loaded = loaded_models()
    spilled = [m for m in loaded if m["on_gpu"] < 0.95]

    if not alive:
        return {"verdict": "WEDGED", "probe_ms": round(probe_ms),
                "why": "the model server did not answer a trivial request",
                "loaded": loaded, "fix": "recover --level 2, then --level 3"}
    if spilled:
        return {"verdict": "SPILLED", "probe_ms": round(probe_ms),
                "why": f"{len(spilled)} model(s) partly on CPU: " +
                       ", ".join(f"{m['name']} {m['on_gpu']:.0%}" for m in spilled),
                "loaded": loaded, "fix": "recover --level 1 (evict idle models)"}
    if probe_ms > 2500:
        return {"verdict": "SLOW", "probe_ms": round(probe_ms),
                "why": "server answers but far slower than a warm embed should",
                "loaded": loaded, "fix": "recover --level 1"}
    return {"verdict": "OK", "probe_ms": round(probe_ms), "why": "",
            "loaded": loaded, "fix": ""}


def recover(level: int = 1, hw: dict | None = None) -> dict:
    """Escalating repair. Level 3 restarts the server and is never automatic.

    Levels 1 and 2 only evict models — nothing is lost, so a hook may run them
    unattended. Level 3 kills a process the user may be using for something
    else, so it requires an explicit act.
    """
    hw = hw or probe_hardware()
    done = []
    if level >= 1:
        for m in loaded_models():
            if m["on_gpu"] < 0.95 and unload(m["name"]):
                done.append(f"evicted spilled {m['name']}")
    if level >= 2:
        for m in loaded_models():
            if unload(m["name"]):
                done.append(f"evicted {m['name']}")
        for _ in range(10):
            if healthy(3.0):
                break
            time.sleep(1.0)
    if level >= 3:
        if os.name == "nt":
            _run(["taskkill", "/IM", "ollama.exe", "/F"], timeout=10)
        elif sys.platform == "darwin":
            _run(["pkill", "-f", "ollama serve"], timeout=5)
        else:
            _run(["systemctl", "--user", "restart", "ollama"], timeout=10)
        done.append("requested model server restart")
        for _ in range(20):
            if healthy(3.0):
                break
            time.sleep(1.0)
    return {"level": level, "actions": done, "after": diagnose(hw)}


# --------------------------------------------------------------------------- lock

def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _alive(pid: int) -> bool:
    """Is this process still running? Cross-platform, and deliberately so.

    `os.kill(pid, 0)` is the POSIX idiom, but on Windows os.kill maps to
    TerminateProcess for every signal value — including 0. The liveness probe
    would have killed the process it was asking about, and a stale-lock check
    would become a process killer. OpenProcess answers the same question
    without touching anything.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            # ERROR_ACCESS_DENIED means it exists and is not ours.
            return ctypes.windll.kernel32.GetLastError() == 5
        except Exception:
            return True          # cannot tell; assume alive rather than steal
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
def slot(name: str = "model", deadline_s: float = 90.0, owner: str = "",
         model: str = "", auto_recover: bool = True):
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
                    # A stale lock means the previous holder died mid-job, and a
                    # job killed while driving the model is the most common way
                    # to be handed a degraded server. Repairing here is what
                    # makes the next run recover on its own instead of
                    # inheriting the problem.
                    if auto_recover:
                        try:
                            if diagnose()["verdict"] != "OK":
                                recover(2)
                        except Exception:
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

        # Preflight, only once the slot is held so nothing races us. Two checks,
        # in the order that matters: repair a degraded server before deciding
        # anything, then make room so the model we are about to load does not
        # spill. Both are cheap; discovering either afterwards costs the whole
        # job's runtime at CPU speed.
        if held and auto_recover:
            try:
                d = diagnose()
                if d["verdict"] in ("SPILLED", "SLOW"):
                    recover(1)          # eviction only — safe unattended
            except Exception:
                pass
        if held and model:
            try:
                ensure_room(model)
            except Exception:
                pass

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
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("--level", type=int, default=1, choices=(1, 2, 3))
    ap.add_argument("--route", action="store_true",
                    help="which model each task profile gets on this machine")
    ap.add_argument("--fit", metavar="MODEL",
                    help="would this model fit right now, and what would be evicted")
    ap.add_argument("--name", default="model")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.diagnose:
        d = diagnose()
        if args.json:
            print(json.dumps(d, indent=2))
            return 0
        print(f"verdict : {d['verdict']}   (probe {d['probe_ms']} ms)")
        if d["why"]:
            print(f"why     : {d['why']}")
            print(f"fix     : broker.py --recover --level "
                  f"{1 if d['verdict'] != 'WEDGED' else 2}")
        for m in d["loaded"]:
            print(f"  loaded: {m['name']:<24} gpu={m['on_gpu']:.0%}")
        return 0 if d["verdict"] == "OK" else 1

    if args.recover:
        if args.level >= 3:
            print("level 3 restarts the model server, which may interrupt other "
                  "work using it.", file=sys.stderr)
        r = recover(args.level)
        if args.json:
            print(json.dumps(r, indent=2))
            return 0
        for a in r["actions"] or ["(nothing to do)"]:
            print(f"  {a}")
        print(f"now     : {r['after']['verdict']}")
        return 0 if r["after"]["verdict"] == "OK" else 1

    if args.route:
        hw = probe_hardware()
        sizes = catalog()
        rows = []
        for prof in ROUTES:
            m = route(prof, hw)
            mb = sizes.get(m) or sizes.get(f"{m}:latest") or 0
            fits = (not mb) or (not hw["vram_mb"]) or mb * 1.25 <= hw["vram_mb"]
            rows.append({"profile": prof, "model": m, "size_mb": mb,
                         "pulled": bool(mb), "fits": fits})
        if args.json:
            print(json.dumps({"vram_mb": hw["vram_mb"], "routes": rows}, indent=2))
            return 0
        print(f"vram {hw['vram_mb']:,} MB — 25% headroom reserved for KV cache\n")
        for r in rows:
            note = ("" if r["fits"] else "   <-- WILL NOT FIT; pull a smaller "
                                         "model for this profile")
            if not r["pulled"]:
                note = "   <-- NOT PULLED"
            print(f"  {r['profile']:<10} {r['model']:<22} "
                  f"{r['size_mb'] or '?':>6} MB{note}")
        return 0

    if args.fit:
        hw = probe_hardware()
        before = free_vram_mb(hw)
        r = ensure_room(args.fit, hw)
        print(json.dumps({**r, "free_before_mb": before}, indent=2)
              if args.json else
              f"{args.fit}: needs {r.get('wanted_mb', '?')} MB, "
              f"{before} MB free before -> {r['free_mb']} MB after"
              f"{'  (evicted: ' + ', '.join(r['evicted']) + ')' if r['evicted'] else ''}"
              f"\nverdict: {r['action']}")
        return 0 if r["action"] == "ok" else 1

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
