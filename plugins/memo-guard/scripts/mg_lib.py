#!/usr/bin/env python3
"""memo-guard shared helpers. Stdlib only; macOS/Linux.

Design notes
------------
- The context number is a MEASUREMENT, not an estimate: the last usage block the
  API returned in the session transcript (input + cache_creation + cache_read).
  Same approach as memo-index's ctx_watch.py, and the same MEMO_CTX_WINDOW env
  var controls the window size so the two tools never disagree.
- All state lives in ${CLAUDE_PLUGIN_DATA} (survives plugin updates), falling
  back to ~/.claude/memo-guard when run by hand outside a hook.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- paths

def data_dir() -> Path:
    # MEMO_GUARD_HOME wins over CLAUDE_PLUGIN_DATA, not the other way round.
    # The harness derives CLAUDE_PLUGIN_DATA from the plugin's *id*, and that id
    # changed once on this machine (memo-guard-inline -> memo-guard-szk-plugins),
    # which silently forked the store into three: archives and sessions under one
    # id, claim verdicts under the shell fallback, nothing shared. A refuted claim
    # recorded from a terminal then did not block anything inside a session.
    # An explicitly pinned location has to be authoritative or it pins nothing.
    d = (os.environ.get("MEMO_GUARD_HOME")
         or os.environ.get("CLAUDE_PLUGIN_DATA")
         or str(Path.home() / ".claude" / "memo-guard"))
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------- platform

def machine_name() -> str:
    """This machine's name. `os.uname()` does not exist on Windows at all —
    not a wrong value, an AttributeError — so it must not appear anywhere that
    a Windows user can reach, which is everywhere."""
    import platform
    return platform.node() or "unknown"


def secure_file(path: Path) -> bool:
    """Restrict a file to its owner. Returns whether that actually happened.

    `chmod(0o600)` is what protects memory.db, claims.db and keys files, and it
    does nothing useful on Windows — os.chmod there only toggles the read-only
    attribute, so the file stays readable by every account on the machine. The
    call is kept because it is correct on POSIX, but the return value is honest
    so the docs can be, too. Windows needs an ACL (icacls) to get the same
    guarantee, which is not something this should do behind the user's back.
    """
    try:
        path.chmod(0o600)
    except OSError:
        return False
    return os.name != "nt"


def detached_kwargs() -> dict:
    """Keyword arguments that detach a child process, per platform.

    `start_new_session=True` is POSIX-only and raises ValueError on Windows,
    so a background worker spawned this way would not merely fail to detach —
    it would not start.
    """
    if os.name == "nt":
        flags = 0
        for name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS"):
            flags |= getattr(subprocess, name, 0)
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def sessions_dir() -> Path:
    p = data_dir() / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_slug(cwd: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", (cwd or "").strip("/")).strip("-")
    return (s[-80:] or "root")

# --------------------------------------------------------------------------- config

DEFAULTS = {
    # context-% checkpoints at which the transcript is archived + compressed
    "checkpoints": [70, 80],
    # at this % a UserPromptSubmit nudge tells Claude to suggest /compact
    "advise_at": 85,
    # context window of the session model (tokens)
    "window": 200000,
    # where the memo-index skill lives (used for the local-model pipeline)
    "memo_index_path": str(Path.home() / ".claude" / "skills" / "memo-index"),
    # try the local-model memo pipeline; fall back to deterministic if it fails
    "use_local_model": True,
    # size cap of the RESUME injected back into a fresh context (chars).
    # Hook output is hard-capped at 10,000 chars by Claude Code.
    "resume_max_chars": 6000,
    # archives kept per project before pruning oldest
    "keep_archives": 40,
    # recall.py: put matching long-term memory in front of every prompt.
    # On by default because the alternative is a memory you have to remember to
    # ask — but the budget is deliberately small: this is paid every turn.
    "recall": True,
    "recall_max_tokens": 400,
    "recall_max_facts": 3,
    "recall_min_chars": 25,
    "recall_deadline_s": 1.5,
    # Swept against the bundled corpus (recall_eval.py --sweep), not chosen by
    # taste. Lexical-only, with the coverage damping in place: recall stays at
    # 70%, precision 74% -> 93%, false injections 12% -> 0%, 24 -> 19 tok per
    # prompt. 0.35 and 0.40 perform identically; 0.45 is a cliff where recall
    # drops to 65%, so the margin above 0.35 is one step, not three.
    "recall_min_relevance": 0.35,
    # Earns nothing once the relevance floor is in (measured: identical rows for
    # every value at 0.35). Kept because it is the knob that helps a corpus full
    # of near-duplicates, where the second-best answer is a copy of the best.
    "recall_relative_floor": 0.0,
    # autopilot.py: the context % at which compaction should fire on its own.
    # This is a target, not a setting Claude Code understands — autopilot
    # translates it into CLAUDE_AUTOCOMPACT_PCT_OVERRIDE and then corrects that
    # number from where compaction actually landed.
    "auto_compact_at": 70,
    # How long the synchronous PreCompact pass waits for the model slot before
    # giving up and leaving a stub. Bounded by the 60 s hook timeout, so this
    # cannot be generous.
    "fast_wait_s": 20,
    # inject a 3-line pointer on plain session startup if a recent RESUME exists
    "inject_on_startup": True,
    "startup_max_age_h": 48,
    # per-source cap when harvesting tool outputs from the transcript (chars)
    "source_cap_chars": 200000,
    # Model-slot budgets (broker.py). The old values were 600 s per step and
    # 1800 s overall; a 14 MB transcript sat in them for half an hour and then
    # fell back anyway. A weaker memo on time beats a better one that never
    # arrives, so these are deliberately impatient.
    "model_step_timeout_s": 240,
    # Wall clock for the whole map phase. Per-source budgets alone cannot bound
    # a transcript with forty sources in it; this is what stops the model path
    # before the session-level wait does, and whatever did not fit is named in
    # PARTIAL.json and in the RESUME rather than silently dropped.
    "model_total_s": 900,
    # doctor.py --maintain-if-due, spawned at session end.
    "maintain_every_h": 24,
    "model_wait_s": 300,
    "session_wait_s": 900,
    # enforce cross-session claim verdicts (claims.py) during compression
    "enforce_verdicts": True,
    # A-MEM style: let the model decide when to archive instead of firing at
    # fixed checkpoints. The checkpoints become advisory; hard_floor still
    # fires unconditionally so a session can never end up with nothing.
    "adaptive": False,
    "hard_floor": 90,
    # Core memory blocks (blocks.py) injected on every SessionStart. These cost
    # tokens every turn, which is the price of not having to know to ask.
    "core_memory": True,
    "core_memory_max_chars": 2000,
    # Push the knowledge base to the private data repo after every write.
    # Off until sync.py --setup has run; the worker coalesces a burst of
    # writes into one commit so "after every write" never blocks a write.
    "sync": False,
    # Long-term memory (memory.py). Promotion is explicit by default: a memory
    # that fills itself is a memory you cannot trust. Turning this on takes only
    # claims at or above auto_promote_utility, and only from the local-model
    # pipeline where a utility score actually exists.
    "auto_promote": False,
    "auto_promote_utility": 0.75,
    "auto_promote_max": 5,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg_path = data_dir() / "config.json"
    if cfg_path.exists():
        try:
            cfg.update(json.loads(cfg_path.read_text()))
        except Exception:
            pass
    else:
        try:
            cfg_path.write_text(json.dumps(DEFAULTS, indent=2) + "\n")
        except OSError:
            pass
    # env overrides
    if os.environ.get("MEMO_CTX_WINDOW"):
        try:
            cfg["window"] = int(os.environ["MEMO_CTX_WINDOW"])
        except ValueError:
            pass
    for key in ("checkpoints", "advise_at", "use_local_model", "resume_max_chars"):
        env = os.environ.get(f"MEMO_GUARD_{key.upper()}")
        if env:
            try:
                cfg[key] = json.loads(env)
            except Exception:
                pass
    return cfg

# --------------------------------------------------------------------------- window

# Kept in step with memo-index's ctx_watch.py. A missing entry here is not fatal:
# resolve_window() corrects itself from the measurement.
MODEL_WINDOWS = {
    "claude-opus-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-fable-5": 1_000_000,
    "claude-haiku-4-5": 200_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
}
TIERS = (200_000, 500_000, 1_000_000, 2_000_000)


def window_for_model(model: str | None) -> int | None:
    """Look a model id up in the table, longest prefix wins. None if unknown."""
    if not model:
        return None
    for prefix in sorted(MODEL_WINDOWS, key=len, reverse=True):
        if model.startswith(prefix):
            return MODEL_WINDOWS[prefix]
    return None


def resolve_window(ctx_tokens: int, model: str | None, cfg: dict) -> tuple[int, str]:
    """Return (window, how_it_was_determined).

    Precedence: MEMO_CTX_WINDOW > model table > config default. Then the part
    that actually matters: a context larger than the assumed window disproves
    the assumption, so the measurement wins and we step up to the smallest tier
    that can hold it. Without this last step a 1M-window session reads as 442%
    and burns every checkpoint on the first tool call.
    """
    env = os.environ.get("MEMO_CTX_WINDOW")
    if env:
        try:
            return int(env), "MEMO_CTX_WINDOW"
        except ValueError:
            pass
    window = window_for_model(model)
    source = f"model {model}" if window else "config default"
    if window is None:
        try:
            window = int(cfg.get("window") or DEFAULTS["window"])
        except (TypeError, ValueError):
            window = DEFAULTS["window"]
    if ctx_tokens > window:
        for tier in TIERS:
            if tier >= ctx_tokens:
                return tier, f"inferred from {ctx_tokens:,} observed tokens"
        return ctx_tokens, f"inferred from {ctx_tokens:,} observed tokens"
    return window, source


def context_pct(usage: dict | None, cfg: dict) -> tuple[float, int, str]:
    """(percent, window, source) — the single place the percentage is computed."""
    if not usage:
        return 0.0, int(cfg.get("window") or DEFAULTS["window"]), "no usage"
    tok = usage.get("context_tokens", 0)
    window, source = resolve_window(tok, usage.get("model"), cfg)
    return 100.0 * tok / max(1, window), window, source

# --------------------------------------------------------------------------- stdin / stdout

def read_stdin_json() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def emit(obj: dict) -> None:
    """Structured hook output. Must be the ONLY thing on stdout (exit 0)."""
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")

# --------------------------------------------------------------------------- transcript

TAIL_BYTES = 512 * 1024


def find_transcript(cwd: str | None = None) -> Path | None:
    """Fallback discovery when not called from a hook (no transcript_path)."""
    proj = Path.home() / ".claude" / "projects"
    if not proj.exists():
        return None
    cwd = cwd or os.getcwd()
    slug = "-" + str(Path(cwd)).strip("/").replace("/", "-").replace(".", "-")
    cands = list((proj / slug).glob("*.jsonl")) if (proj / slug).exists() else []
    if not cands:
        cands = list(proj.rglob("*.jsonl"))
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def last_usage(tp: Path) -> dict | None:
    """Most recent usage block from the transcript tail (measured tokens)."""
    last = None
    last_model = None
    try:
        size = tp.stat().st_size
        with tp.open("rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
                f.readline()  # drop the partial line the seek landed in
            chunk = f.read().decode("utf-8", errors="replace")
        for ln in chunk.splitlines():
            if '"usage"' not in ln:
                continue
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            u = (d.get("message") or {}).get("usage")
            if isinstance(u, dict) and "input_tokens" in u:
                last = u
                # The model id rides on the same record; needed to pick the window.
                last_model = ((d.get("message") or {}).get("model")
                              or d.get("model") or last_model)
    except OSError:
        return None
    if not last:
        return None
    ctx = (last.get("input_tokens", 0)
           + last.get("cache_creation_input_tokens", 0)
           + last.get("cache_read_input_tokens", 0))
    return {"context_tokens": ctx, "output_tokens": last.get("output_tokens", 0),
            "model": last_model}

# --------------------------------------------------------------------------- state

def _state_path(sid: str) -> Path:
    p = data_dir() / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{sid}.json"


def load_state(sid: str) -> dict:
    try:
        return json.loads(_state_path(sid).read_text())
    except Exception:
        return {}


def save_state(sid: str, st: dict) -> None:
    try:
        _state_path(sid).write_text(json.dumps(st, indent=2))
    except OSError:
        pass

# --------------------------------------------------------------------------- archive

def archive_transcript(tp: Path, sid: str, cwd: str, tag: str,
                       usage: dict | None, cfg: dict) -> Path:
    """Lossless, gzipped copy of the original context window (the transcript)."""
    out = data_dir() / "archive" / project_slug(cwd)
    out.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = out / f"{(sid or 'session')[:8]}-{tag}-{ts}.jsonl.gz"
    with tp.open("rb") as fi, gzip.open(dst, "wb", compresslevel=6) as fo:
        while True:
            chunk = fi.read(1 << 20)
            if not chunk:
                break
            fo.write(chunk)
    meta = {
        "session_id": sid, "cwd": cwd, "tag": tag, "ts": ts,
        "raw_bytes": tp.stat().st_size,
        "context_tokens": (usage or {}).get("context_tokens"),
        "transcript": str(tp),
    }
    dst.with_name(dst.name.replace(".jsonl.gz", ".meta.json")).write_text(
        json.dumps(meta, indent=2))
    _prune_archives(out, cfg.get("keep_archives", 40))
    return dst


def _prune_archives(folder: Path, keep: int) -> None:
    arcs = sorted(folder.glob("*.jsonl.gz"), key=lambda p: p.stat().st_mtime)
    for old in arcs[:-keep] if keep > 0 else []:
        try:
            old.unlink()
            m = old.with_name(old.name.replace(".jsonl.gz", ".meta.json"))
            if m.exists():
                m.unlink()
        except OSError:
            pass

# --------------------------------------------------------------------------- misc

def spawn_background(script: Path, args: list[str]) -> None:
    """Fire-and-forget worker; hooks must never block on compression."""
    logd = data_dir() / "logs"
    logd.mkdir(parents=True, exist_ok=True)
    with (logd / "compressor.log").open("ab") as lf:
        subprocess.Popen([sys.executable, str(script), *args],
                         stdout=lf, stderr=lf,
                         env=dict(os.environ), **detached_kwargs())


def est_tokens(text_or_bytes) -> int:
    n = len(text_or_bytes)
    return max(1, n // 4)


#: metrics.jsonl holds more than one kind of row. Rows written before the
#: recall hook existed carry no `event` key at all, so a reader that trusts
#: position instead of type gets whichever row happened to be appended last —
#: which is how the self test came to print a live session's compression figures
#: as its own result, and then to crash outright once a recall row landed last.
COMPRESS = "compress"

#: The one directory that must never receive test data.
PRODUCTION_HOME = Path("~/.claude/memo-guard").expanduser()


def is_production(path=None) -> bool:
    try:
        return Path(path or data_dir()).resolve() == PRODUCTION_HOME.resolve()
    except OSError:
        return False


def assert_not_production(what: str = "this") -> None:
    """Refuse to write fixtures into the user's real stores.

    The self test used to select its sandbox from MEMO_GUARD_HOME — the variable
    this plugin's own installer PINS to the production directory. So on every
    machine where memo-guard was installed, the "sandbox" was the live store,
    and the test wrote an invented PROSPERO number, an invented rejection
    reason and a REFUTED claim about a cohort's sample size into long-term
    memory, where recall then served them to real sessions as established fact.

    An environment variable is not a safety boundary. Anything that writes
    fixtures calls this first, and it fails loudly rather than degrading.
    """
    if is_production():
        raise SystemExit(
            f"refusing to run {what} against the production store "
            f"({PRODUCTION_HOME}).\n"
            "  It writes fixtures into the memory and claim stores, and recall\n"
            "  would serve them to real sessions as fact.\n"
            "  Set MEMO_GUARD_SELFTEST_HOME to a scratch directory, or unset it\n"
            "  entirely to get a fresh temporary one.")


def append_metrics(row: dict, event: str = COMPRESS) -> None:
    row = dict(row)
    row.setdefault("event", event)
    row["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with (data_dir() / "metrics.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")


def read_metrics(event: str | None = None, session: str | None = None,
                 path=None) -> list[dict]:
    """Every metrics row, filtered by type and session. The only reader.

    Legacy rows have no `event`; they are all compression rows, so they are
    labelled as such on the way out rather than migrated on disk — the file is
    append-only evidence and rewriting it would destroy the record it exists to
    be.
    """
    mf = Path(path) if path else (data_dir() / "metrics.jsonl")
    out: list[dict] = []
    if not mf.exists():
        return out
    for ln in mf.read_text(errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        row.setdefault("event", COMPRESS)
        if event is not None and row["event"] != event:
            continue
        if session is not None and row.get("session") != session:
            continue
        out.append(row)
    return out
