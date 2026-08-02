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
    d = (os.environ.get("CLAUDE_PLUGIN_DATA")
         or os.environ.get("MEMO_GUARD_HOME")
         or str(Path.home() / ".claude" / "memo-guard"))
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


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
    # inject a 3-line pointer on plain session startup if a recent RESUME exists
    "inject_on_startup": True,
    "startup_max_age_h": 48,
    # per-source cap when harvesting tool outputs from the transcript (chars)
    "source_cap_chars": 200000,
    # enforce cross-session claim verdicts (claims.py) during compression
    "enforce_verdicts": True,
    # A-MEM style: let the model decide when to archive instead of firing at
    # fixed checkpoints. The checkpoints become advisory; hard_floor still
    # fires unconditionally so a session can never end up with nothing.
    "adaptive": False,
    "hard_floor": 90,
    # Long-term memory (memory.py). Promotion is explicit by default: a memory
    # that fills itself is a memory you cannot trust. Turning this on takes only
    # claims at or above auto_promote_utility, and only from the local-model
    # pipeline where a utility score actually exists.
    # Core memory blocks (blocks.py) injected on every SessionStart. These cost
    # tokens every turn, which is the price of not having to know to ask.
    "core_memory": True,
    "core_memory_max_chars": 2000,
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
                         start_new_session=True, env=dict(os.environ))


def est_tokens(text_or_bytes) -> int:
    n = len(text_or_bytes)
    return max(1, n // 4)


def append_metrics(row: dict) -> None:
    row = dict(row, ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with (data_dir() / "metrics.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
