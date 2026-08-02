#!/usr/bin/env python3
"""memo-guard background compressor.

Input : a gzipped transcript archive (the original context window, lossless).
Output: sessions/<sid>/
          conversation.md    the dialogue itself, tool noise stripped
          sources/*.md       heavy tool outputs, grouped by origin file/tool
          distilled/*.md     deterministic compression of each source
          .memo/             memo-index claims db (only in local-model mode)
          RESUME.md          the tiny index injected into the next context
          STATE.json         phase + mode, read by status.py

Two modes, tried in order:
  local-model   delegate to the memo-index skill (memo_gen -> verify_anchors ->
                memo_db) so every kept fact is a line-anchored, checkable
                claim. Zero API tokens; slow is fine, we are in the background.
  deterministic no model at all: head/tail + signal-line extraction. Honest
                but lossier; RESUME says which mode produced it.

Everything is measured and appended to metrics.jsonl so the >=95% reduction
target is a number you can audit, not a promise.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402

BASE64ISH = re.compile(r"[A-Za-z0-9+/=_-]{160,}")
SIGNAL = re.compile(
    r"(error|warn|fail|exception|traceback|fatal|denied|refused"
    r"|^\s*(def |class |function |async def |public |private )"
    r"|^#{1,4}\s|^\s*(SELECT|INSERT|UPDATE|CREATE|import |from .+ import)"
    r"|https?://|TODO|FIXME|p\s*[<=>]\s*0\.\d|\bCI\b|\bOR\b\s*[:=]?\s*\d)",
    re.IGNORECASE)


# ----------------------------------------------------------------- transcript

def load_lines(archive: Path):
    op = gzip.open if archive.suffix == ".gz" else open
    with op(archive, "rt", encoding="utf-8", errors="replace") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                yield json.loads(ln)
            except json.JSONDecodeError:
                continue


def _texts(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
        elif isinstance(b, str):
            out.append(b)
    return out


def harvest(archive: Path, cap: int):
    """Split the window into dialogue turns and heavy tool outputs."""
    turns: list[dict] = []          # {"role","text"}
    sources: dict[str, list[str]] = {}
    tool_origin: dict[str, str] = {}  # tool_use_id -> origin label

    for d in load_lines(archive):
        role = d.get("type")
        msg = d.get("message") or {}
        content = msg.get("content")

        if role == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    origin = (inp.get("file_path") or inp.get("path")
                              or inp.get("url") or inp.get("notebook_path"))
                    if not origin and isinstance(inp.get("command"), str):
                        origin = "bash: " + inp["command"][:60]
                    tool_origin[b.get("id", "")] = (
                        f"{b.get('name', 'tool')} :: {origin}" if origin
                        else b.get("name", "tool"))
            txt = "\n".join(t for t in _texts(content) if t.strip())
            if txt.strip():
                turns.append({"role": "assistant", "text": txt})

        elif role == "user":
            got_tool = False
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        got_tool = True
                        body = "\n".join(_texts(b.get("content")))
                        if len(body) >= 800:
                            key = tool_origin.get(b.get("tool_use_id", ""),
                                                  "tool")
                            sources.setdefault(key, []).append(body[:cap])
            if not got_tool:
                txt = "\n".join(_texts(content))
                txt = re.sub(r"<system-reminder>.*?</system-reminder>", "",
                             txt, flags=re.S).strip()
                if txt and len(txt) >= 10 and not txt.startswith(
                        ("<system-reminder", "<task-notification",
                         "[SYSTEM NOTIFICATION")):
                    turns.append({"role": "user", "text": txt})

        # some transcript versions also mirror results at the top level
        tur = d.get("toolUseResult")
        if isinstance(tur, (dict, list)):
            body = json.dumps(tur)[:cap]
            if len(body) >= 4000:
                sources.setdefault("toolUseResult", []).append(body)

    return turns, {k: "\n\n----\n\n".join(v) for k, v in sources.items()}


# ----------------------------------------------------------------- distill

def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")[:70] or "src"


def distill(text: str, head=60, tail=30, signals=60) -> str:
    lines = [BASE64ISH.sub("[base64 stripped]", ln.rstrip())
             for ln in text.splitlines()]
    lines = [ln for i, ln in enumerate(lines)
             if ln.strip() or (i and lines[i - 1].strip())]
    if len(lines) <= head + tail:
        return "\n".join(lines)
    keep_idx = set(range(head)) | set(range(len(lines) - tail, len(lines)))
    hits = [i for i in range(head, len(lines) - tail)
            if SIGNAL.search(lines[i])][:signals]
    keep_idx |= set(hits)
    out, prev = [], -1
    for i in sorted(keep_idx):
        if prev >= 0 and i > prev + 1:
            out.append(f"[... {i - prev - 1} lines omitted ...]")
        out.append(lines[i])
        prev = i
    out.insert(0, f"[distilled: kept {len(keep_idx)} of {len(lines)} lines]")
    return "\n".join(out)


def conversation_doc(turns: list[dict], sid: str) -> str:
    out = [f"# Session {sid} — dialogue", ""]
    for i, t in enumerate(turns, 1):
        body = t["text"]
        if len(body) > 3000:
            body = body[:1500] + "\n\n[... trimmed ...]\n\n" + body[-1200:]
        out += [f"## [{i}] {'USER' if t['role'] == 'user' else 'ASSISTANT'}",
                "", body, ""]
    return "\n".join(out)


# ----------------------------------------------------------------- memo-index

def run_memo_pipeline(workdir: Path, cfg: dict, log) -> bool:
    skill = Path(cfg["memo_index_path"]) / "scripts"
    if not (skill / "memo_gen.py").exists():
        log("memo-index skill not found at "
            f"{cfg['memo_index_path']} -> deterministic mode")
        return False
    try:
        import broker
        # Ask the server before queuing for it. A wedged Ollama answers /api/tags
        # but not real work, and every caller then sat in a 600 s timeout at 0%
        # CPU waiting for an answer that was never coming.
        if not broker.healthy(3.0):
            log("model server not responding -> deterministic mode")
            return False
        chk = subprocess.run([sys.executable, str(skill / "route.py"),
                              "--check"], capture_output=True, timeout=30)
        if chk.returncode != 0:
            log("local model unavailable (route.py --check failed) -> "
                "deterministic mode")
            return False
        steps = [
            [str(skill / "memo_gen.py"), "--root", str(workdir),
             "--include", "sources/*.md", "--profile", "prose",
             "--memo-dir", str(workdir / ".memo")],
            [str(skill / "verify_anchors.py"),
             "--memo-dir", str(workdir / ".memo"), "--root", str(workdir)],
            [str(skill / "memo_db.py"),
             "--memo-dir", str(workdir / ".memo"), "--build"],
            [str(skill / "index_build.py"),
             "--memo-dir", str(workdir / ".memo")],
        ]
        # One model slot for the whole pipeline, machine-wide. Waiting for it is
        # correct; the old per-session lock let a second Claude Code window run
        # a competing pipeline, and the two starved each other on one Ollama.
        step_budget = float(cfg.get("model_step_timeout_s", 240))
        with broker.slot("model", deadline_s=float(cfg.get("model_wait_s", 300)),
                         owner=f"compressor/{workdir.name[:8]}") as got:
            if not got:
                log("no model slot within deadline -> deterministic mode")
                return False
            for cmd in steps:
                log("run: " + " ".join(cmd))
                broker.beat("model")
                r = subprocess.run([sys.executable, *cmd], capture_output=True,
                                   text=True, timeout=step_budget)
                if r.returncode != 0:
                    log(f"step failed rc={r.returncode}: {r.stderr[-800:]}")
                    return False
        return True
    except Exception as e:  # noqa: BLE001 — background job must not die loudly
        log(f"memo pipeline error: {e} -> deterministic mode")
        return False


# ----------------------------------------------------------------- resume

def build_resume(workdir: Path, sid: str, archive: Path, mode: str,
                 turns: list[dict], distilled: dict[str, Path],
                 raw_tok: int, kept_tok: int, cfg: dict, cwd: str = "") -> str:
    memo_dir = workdir / ".memo"
    mq = Path(cfg["memo_index_path"]) / "scripts" / "memo_query.py"

    # Enforce past sessions' verdicts before anything reaches a fresh context.
    # The memo dir is rebuilt per session, so without this a claim refuted last
    # week is regenerated clean and looks newly true.
    blocked: list[dict] = []
    if cfg.get("enforce_verdicts", True):
        try:
            import claims as cl
            db = cl.connect()
            res = cl.apply_to_memo_dir(db, memo_dir)
            blocked = res["blocked"]
        except Exception:  # never let the verdict store break compression
            blocked = []

    # Optional, off by default: lift the few highest-utility claims into
    # long-term memory. Only SUPPORTED ones, only above the utility floor, and
    # capped — an auto-filled memory is one nobody trusts enough to consult.
    if cfg.get("auto_promote") and (memo_dir / "index.db").exists():
        try:
            import sqlite3
            import memory as ltm
            floor = float(cfg.get("auto_promote_utility", 0.75))
            cap = int(cfg.get("auto_promote_max", 5))
            idx = sqlite3.connect(memo_dir / "index.db")
            rows = idx.execute(
                "SELECT text, source, anchor_line, utility FROM claims"
                " WHERE status='SUPPORTED' AND utility>=?"
                " ORDER BY utility DESC LIMIT ?", (floor, cap)).fetchall()
            idx.close()
            mdb = ltm.connect()
            for text, source, line, util in rows:
                try:
                    ltm.promote(mdb, text, cwd, kind="finding", source=source,
                                anchor=f"{source}:{line}" if line else source,
                                session_id=sid, utility=util, by="auto")
                except ValueError:
                    continue
        except Exception:
            pass

    user_asks = [t["text"].replace("\n", " ")[:300]
                 for t in turns if t["role"] == "user"][-3:]
    last_assist = next((t["text"].replace("\n", " ")[:400]
                        for t in reversed(turns)
                        if t["role"] == "assistant"), "")

    L = [f"# memo-guard ▸ resume of session {sid[:8]} "
         f"({time.strftime('%Y-%m-%d %H:%M')})",
         "",
         f"Original context window archived losslessly: `{archive}` "
         f"(~{raw_tok:,} tok raw).",
         f"Compressed working set on disk: ~{kept_tok:,} tok "
         f"({100 - 100 * kept_tok / max(1, raw_tok):.1f}% smaller). "
         f"Mode: **{mode}**.",
         "",
         "## What was in flight (auto-extracted — verify before relying on it)"]
    L += [f"- user asked: {a}" for a in user_asks] or ["- (no user turns found)"]
    if last_assist:
        L.append(f"- last assistant status: {last_assist}")
    if blocked:
        # Cheap and load-bearing: without this the reader cannot tell that a
        # claim was already judged, and re-derives it as if it were new.
        L += ["", "## Already judged in an earlier session — do NOT reinstate"]
        for b in blocked[:8]:
            L.append(f"- [{b['status']}] {b['text']}")
        if len(blocked) > 8:
            L.append(f"- … and {len(blocked) - 8} more "
                     f"(`claims.py --list`)")
    L += ["", "## How to use this (cheap-first, in this order)"]
    if mode == "local-model" and (memo_dir / "index.db").exists():
        L += [f"1. Query the claims index (~60 tok/answer): "
              f"`python3 {mq} --memo-dir {memo_dir} --root {workdir} "
              f"'<question>'`",
              "2. Only if a claim needs its source: Read the matching file in "
              f"`{workdir}/distilled/`.",
              f"3. Ground truth, exact bytes: `gunzip -c '{archive}' | "
              "grep -n '<term>'`. Never re-read whole originals."]
    else:
        L += [f"1. Read only the relevant distilled source in "
              f"`{workdir}/distilled/` (each is a few hundred tokens).",
              f"2. Ground truth, exact bytes: `gunzip -c '{archive}' | "
              "grep -n '<term>'`. Never re-read whole originals."]
    if distilled:
        L += ["", "## Sources captured from the window"]
        for label, path in list(distilled.items())[:14]:
            L.append(f"- {label} → `{path.name}`")
        if len(distilled) > 14:
            L.append(f"- … and {len(distilled) - 14} more in "
                     f"`{workdir}/distilled/`")
    txt = "\n".join(L)
    return txt[: cfg["resume_max_chars"]]


# ----------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--cwd", default="")
    args = ap.parse_args()

    t0 = time.time()
    cfg = mg.load_config()
    archive = Path(args.archive)
    sid = args.session
    workdir = mg.sessions_dir() / sid
    workdir.mkdir(parents=True, exist_ok=True)

    # spawn_background() creates this, but compressor.py is also run by hand and
    # by archive_now.py --now; on a fresh data dir neither has made logs/ yet.
    logf = (mg.data_dir() / "logs" / "compressor.log")
    logf.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        with logf.open("a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')} {sid[:8]}] {msg}\n")

    # Single-flight per session — but WAIT, do not skip. The old code returned
    # immediately when a run was active, so the 80% checkpoint's compression was
    # silently dropped whenever the 70% one was still going: the newer archive,
    # the one with more of the session in it, was the one thrown away. Waiting
    # costs time; skipping costs the memo.
    import broker
    sess_lock = broker.slot(f"session-{workdir.name[:12]}",
                            deadline_s=float(cfg.get("session_wait_s", 900)),
                            owner=f"compressor/{archive.name[:24]}")
    sess_held = sess_lock.__enter__()
    if not sess_held:
        log("another compressor run for this session did not finish in time; "
            "skipping to avoid piling up")
        return 0
    (workdir / "STATE.json").write_text(json.dumps(
        {"phase": "running", "archive": str(archive)}))

    try:
        turns, sources = harvest(archive, cfg["source_cap_chars"])
        (workdir / "sources").mkdir(exist_ok=True)
        (workdir / "distilled").mkdir(exist_ok=True)

        conv = conversation_doc(turns, sid)
        (workdir / "sources" / "conversation.md").write_text(conv)
        # The dialogue is already compressed by construction (tool noise
        # stripped, long turns trimmed), but it must sit on the SAME retrieval
        # path as tool output — decisions live here, and a grep that only
        # covers distilled/ would miss every one of them.
        (workdir / "distilled" / "conversation.md").write_text(conv)

        distilled: dict[str, Path] = {}
        kept_chars = len(conv)
        for label, body in sources.items():
            name = slugify(label) + ".md"
            (workdir / "sources" / name).write_text(
                f"# {label}\n\n{body}")
            d = distill(body)
            dp = workdir / "distilled" / name
            dp.write_text(f"# {label} (distilled)\n\n{d}")
            distilled[label] = dp
            kept_chars += len(d)

        mode = "deterministic"
        if cfg.get("use_local_model", True):
            if run_memo_pipeline(workdir, cfg, log):
                mode = "local-model"

        raw_tok = mg.est_tokens(gzip.open(archive, "rb").read()
                                if archive.suffix == ".gz"
                                else archive.read_bytes())
        kept_tok = mg.est_tokens("x" * kept_chars)
        resume = build_resume(workdir, sid, archive, mode, turns, distilled,
                              raw_tok, kept_tok, cfg, args.cwd)
        (workdir / "RESUME.md").write_text(resume)
        resume_tok = mg.est_tokens(resume)

        mg.append_metrics({
            "session": sid, "archive": archive.name, "mode": mode,
            "raw_tokens_est": raw_tok, "kept_tokens_est": kept_tok,
            "resume_tokens_est": resume_tok,
            "reduction_resume_pct": round(100 - 100 * resume_tok
                                          / max(1, raw_tok), 2),
            "reduction_kept_pct": round(100 - 100 * kept_tok
                                        / max(1, raw_tok), 2),
            "sources": len(sources), "turns": len(turns),
            "duration_s": round(time.time() - t0, 1),
        })
        (workdir / "STATE.json").write_text(json.dumps(
            {"phase": "done", "mode": mode, "archive": str(archive),
             "resume_tokens_est": resume_tok, "raw_tokens_est": raw_tok,
             "cwd": args.cwd, "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}))
        log(f"done mode={mode} raw~{raw_tok:,} resume~{resume_tok:,} "
            f"({time.time() - t0:.1f}s)")
        return 0
    except Exception as e:  # noqa: BLE001
        (workdir / "STATE.json").write_text(json.dumps(
            {"phase": "error", "error": str(e)}))
        log(f"ERROR: {e!r}")
        return 1
    finally:
        try:
            sess_lock.__exit__(None, None, None)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
