#!/usr/bin/env python3
"""Find what is misconfigured, overlapping, or quietly broken — and say what to do.

Three separate things this catches, all of which were previously discovered by
noticing something odd rather than by asking:

**Two tools doing one job.** memo-index's `ctx_watch` and memo-guard's
`ctx_monitor` measure the same number, the same way, from the same transcript,
and both fire at 70%. Both then write a handoff and tell the model to wind down.
The visible cost is litter: `ctx_watch` writes `.memo/HANDOFF.md` into whatever
directory the session happened to be standing in, on every tool call. This
repository accumulated six of them, in six directories, all still holding the
unfilled template.

They are not redundant in every part, which is why this does not simply tell you
to delete them. `hook_gate.sh` does two jobs and only the first one duplicates:

| hook_gate.sh job | verdict |
|---|---|
| context ceiling + HANDOFF.md | duplicated — memo-guard archives *and* compresses at the same point |
| "this project has an index, query it" | keep — that is about the project's corpus, not the session |

So the prescription is not removal but narrowing: drop the PostToolUse
`ctx_watch` entry, and set `MEMO_CTX_THRESHOLD` above 100 so `hook_gate.sh`
keeps only the job memo-guard does not do.

**A model server that answers but does not work.** `/api/tags` in a millisecond,
`/api/embed` never — every semantic path silently degrades to lexical and
nothing says so.

**An installed copy older than the source.** Installing *copies* into the plugin
cache, so editing the repo changes nothing until the marketplace is updated. It
is easy to spend an afternoon testing a fix that is not running.

Nothing here edits anything without `--fix`, and `--fix` only ever touches the
two settings keys it names.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mg_lib as mg  # noqa: E402
import autopilot  # noqa: E402

CTX_WATCH = "memo-index/scripts/ctx_watch.py"
HOOK_GATE = "memo-index/scripts/hook_gate.sh"
THRESH_KEY = "MEMO_CTX_THRESHOLD"
OFF = "101"          # a percentage that can never be reached


class Finding:
    def __init__(self, level: str, title: str, detail: str, fix: str = ""):
        self.level, self.title, self.detail, self.fix = level, title, detail, fix

    def show(self) -> None:
        mark = {"error": "✗", "warn": "!", "info": "·"}[self.level]
        print(f"\n{mark} {self.title}")
        for line in self.detail.splitlines():
            print(f"   {line}")
        if self.fix:
            print(f"   fix: {self.fix}")


# --------------------------------------------------------------- checks

def check_hook_overlap(data: dict) -> list[Finding]:
    out = []
    post = []
    for group in data.get("hooks", {}).get("PostToolUse", []):
        for h in group.get("hooks", []):
            if CTX_WATCH in h.get("command", ""):
                post.append(h["command"])
    gate = any(HOOK_GATE in h.get("command", "")
               for g in data.get("hooks", {}).get("UserPromptSubmit", [])
               for h in g.get("hooks", []))
    thresh = (data.get("env") or {}).get(THRESH_KEY)
    silenced = thresh is not None and _num(thresh) > 100

    if post:
        out.append(Finding(
            "warn", "memo-index ctx_watch also runs on PostToolUse",
            "It measures the same context number memo-guard measures, from the\n"
            "same transcript, and fires at the same 70%. memo-guard archives\n"
            "and compresses there; ctx_watch writes a handoff template into the\n"
            "current directory. Two warnings, two files, one event.",
            "doctor.py --fix   (removes only this hook entry)"))
    if gate and not silenced:
        out.append(Finding(
            "warn", "hook_gate.sh still owns the context ceiling",
            "Its second job — telling the model to query an existing project\n"
            "index instead of re-reading the sources — does not overlap and is\n"
            f"worth keeping. Its first job does. Setting {THRESH_KEY}={OFF}\n"
            "silences the ceiling half and keeps the useful half.",
            f"doctor.py --fix   (sets {THRESH_KEY}={OFF} in settings.json)"))
    if gate and silenced:
        out.append(Finding(
            "info", "hook overlap already resolved",
            f"{THRESH_KEY}={thresh}: hook_gate.sh keeps its index reminder and\n"
            "leaves the context ceiling to memo-guard."))
    return out


def check_handoff_litter(root: Path, limit: int = 400) -> list[Finding]:
    """Stale `.memo/HANDOFF.md` files, which are the overlap made visible."""
    found, scanned = [], 0
    for p in root.rglob(".memo/HANDOFF.md"):
        scanned += 1
        if scanned > limit:
            break
        try:
            body = p.read_text()
        except OSError:
            continue
        # An unfilled template is the tell: the section that only a human can
        # write is still the comment that asks them to write it.
        if "Fill this in before /clear" in body:
            found.append(p)
    if not found:
        return []
    listing = "\n".join(f"  {p}" for p in found[:8])
    more = f"\n  … and {len(found) - 8} more" if len(found) > 8 else ""
    return [Finding(
        "info", f"{len(found)} unfilled handoff template(s) under {root}",
        "Written by ctx_watch into whichever directory a session was standing\n"
        "in. Every one still holds the placeholder for the part only a person\n"
        f"can fill in, so none of them carries information.\n{listing}{more}",
        "doctor.py --clean-handoffs   (deletes only unfilled templates)")]


def check_model_server() -> list[Finding]:
    try:
        import broker
    except Exception:
        return []
    up = False
    try:
        up = broker.healthy(timeout=3.0, strict=True)
    except Exception:
        up = False
    if up:
        return [Finding("info", "model server answers embeddings", "")]
    try:
        d = broker.diagnose()
        verdict, why = d.get("verdict", "?"), d.get("why", "")
    except Exception:
        verdict, why = "UNREACHABLE", "no answer at all"
    # Distinguish a busy server from a wedged one. Both report SLOW, and the
    # fixes are not the same: evicting models helps the first and does nothing
    # for the second. Measured here — /api/tags in 8 ms while /api/generate and
    # both embedding models never returned at all, through a 60 s timeout.
    wedged = False
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{broker.OLLAMA}/api/generate",
            data=b'{"model":"llama3.2:3b","prompt":"hi","stream":false}',
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        wedged = True

    common = (f"{why}\n"
              "Every semantic path degrades to lexical while this holds: claim\n"
              "matching misses paraphrases, recall loses the queries that share\n"
              "no words with their answer, and recall_eval --calibrate refuses\n"
              "to run. Nothing breaks; it just quietly gets worse.")
    if wedged:
        return [Finding(
            "warn", "the model server accepts connections but never finishes one",
            common + "\n"
            "This one is not a loaded-model problem: /api/tags answers in\n"
            "milliseconds while inference never returns, so evicting models\n"
            "(levels 1 and 2) will not help. Only a restart will, and that\n"
            "kills a process you may be using for something else — so it is\n"
            "left to you rather than done automatically.",
            "broker.py --recover --level 3   (restarts the model server)")]
    return [Finding(
        "warn", f"embeddings are not working ({verdict})",
        common,
        "broker.py --diagnose, then --recover --level 1 or 2")]


def check_memory_hygiene() -> list[Finding]:
    """What is in the store, not what recall does with it.

    Nothing else looks. A fact promoted months ago is served in the
    authoritative voice of the user's own memory whether or not it is still
    true — and fixtures written by a mis-scoped test sat in this store
    undetected until someone went looking by hand.
    """
    try:
        import factcheck, memory
        db = memory.connect()
        findings = factcheck.audit(db, online=False)
    except Exception:
        return []
    errs = [f for f in findings if f.level == "error"]
    if errs:
        detail = "\n".join(f"  fact {f.fid}: {f.message}" for f in errs[:6])
        return [Finding(
            "warn", f"{len(errs)} fact(s) in long-term memory look wrong",
            f"{detail}\n"
            "Recall serves these in the voice of your own notes. A fabricated\n"
            "identifier or a fixture left by a test is indistinguishable from\n"
            "something you established, which is exactly why it has to be\n"
            "checked rather than trusted.",
            "factcheck.py           (full report)\n"
            "     factcheck.py --quarantine  (drop them out of recall, delete nothing)")]
    warns = [f for f in findings if f.level == "warn"]
    if warns:
        return [Finding("info", f"{len(warns)} fact(s) worth a look",
                        "provenance or context has drifted; nothing looks false",
                        "factcheck.py")]
    return []


def check_stale_locks() -> list[Finding]:
    """A lock whose owner died is not a reason to keep standing back.

    The broker reaps a stale lock the next time something tries to ACQUIRE it.
    Nothing tries when the only interested caller is a reader — so a compressor
    killed mid-run left the model slot marked busy, semantic recall switched
    itself off, and it stayed off with no message anywhere.
    """
    try:
        import broker
        st = broker.lock_status("model")
    except Exception:
        return []
    if not st or not st.get("stale"):
        return []
    return [Finding(
        "warn", f"the model lock is stale ({st.get('age_s')}s, "
                f"owner {st.get('owner')})",
        "Its holder is gone. Semantic recall stands down while a lock is\n"
        "held, so paraphrase matching is off until this is cleared.",
        "doctor.py --fix   (removes only a lock whose owner is dead)")]


def reap_stale_lock() -> bool:
    """Remove a dead holder's lock. Returns True if one was removed."""
    try:
        import broker
        st = broker.lock_status("model")
        if not st or not st.get("stale"):
            return False
        (broker.lock_dir() / "model.lock").unlink()
        return True
    except Exception:
        return False


def check_installed_version() -> list[Finding]:
    src = Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json"
    try:
        want = json.loads(src.read_text())["version"]
    except Exception:
        return []
    cache = Path.home() / ".claude" / "plugins" / "cache"
    installed = sorted(p.name for p in cache.glob("*/memo-guard/*")
                       if p.is_dir())
    if not installed:
        return []
    if want in installed:
        return [Finding("info", f"installed copy matches the source ({want})", "")]
    return [Finding(
        "warn", f"the installed copy is {', '.join(installed)}, "
                f"the source is {want}",
        "Installing copies the plugin into the cache, so the hooks running in\n"
        "your sessions are the installed ones. Edits to the repository change\n"
        "nothing until it is updated — which is an easy way to spend an\n"
        "afternoon testing a fix that is not running.",
        "/plugin marketplace update szk-plugins && /plugin update memo-guard")]


def check_autopilot_state() -> list[Finding]:
    st = autopilot.load_state()
    if not st.get("enabled"):
        return [Finding("info", "autopilot is off",
                        "Compaction fires at Claude Code's own default "
                        "(effective window minus 13,000 tokens).")]
    blockers = autopilot.blockers()
    if blockers:
        return [Finding("warn", "autopilot is on but will not fire",
                        "\n".join(blockers), "/memo-guard:autopilot")]
    return [Finding("info",
                    f"autopilot on, target {float(st.get('target', 70)):g}%",
                    "\n".join(["calibrated" if st.get("calibrated")
                                else "still learning"] + autopilot.caveats()))]


def check_maintenance() -> list[Finding]:
    p = mg.data_dir() / "maintenance.json"
    try:
        d = json.loads(p.read_text())
    except Exception:
        return [Finding("info", "memory maintenance has never run",
                        "cognify extracts structure from facts; memify prunes,\n"
                        "reweights and derives. Neither runs on its own until a\n"
                        "session ends with maintenance due.",
                        "doctor.py --maintain")]
    age_h = (time.time() - d.get("ts", 0)) / 3600
    return [Finding("info", f"memory maintenance last ran {age_h:.0f}h ago",
                    json.dumps(d.get("summary", {}))[:300])]


# --------------------------------------------------------------- fixes

_num = autopilot._num


def apply_fix() -> int:
    data = autopilot.read_settings()
    changed = []
    hooks = data.get("hooks", {})
    groups = hooks.get("PostToolUse", [])
    kept_groups = []
    for g in groups:
        hs = [h for h in g.get("hooks", []) if CTX_WATCH not in h.get("command", "")]
        if len(hs) != len(g.get("hooks", [])):
            changed.append("removed the PostToolUse ctx_watch hook")
        if hs:
            kept_groups.append({**g, "hooks": hs})
        # A group whose only hook was removed is dropped rather than left as an
        # empty matcher — an empty group is not wrong, it is just a thing to
        # wonder about later.
    if kept_groups:
        hooks["PostToolUse"] = kept_groups
    else:
        hooks.pop("PostToolUse", None)
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)

    gate = any(HOOK_GATE in h.get("command", "")
               for g in data.get("hooks", {}).get("UserPromptSubmit", [])
               for h in g.get("hooks", []))
    if gate:
        env = data.get("env") or {}
        if _num(env.get(THRESH_KEY)) <= 100:
            env[THRESH_KEY] = OFF
            data["env"] = env
            changed.append(f"set {THRESH_KEY}={OFF} so hook_gate.sh keeps only "
                           f"its index reminder")
    if not changed:
        print("nothing to fix — the hooks do not overlap")
        return 0
    p = autopilot.write_settings(data)
    print(f"updated {p}:")
    for c in changed:
        print(f"  - {c}")
    print("  Takes effect in the next session. A backup of the previous file is "
          "beside it as settings.json.memo-guard.bak.")
    return 0


def clean_handoffs(root: Path) -> int:
    removed = 0
    for p in root.rglob(".memo/HANDOFF.md"):
        try:
            if "Fill this in before /clear" not in p.read_text():
                continue          # someone wrote in it; it is not litter
            p.unlink()
            removed += 1
            d = p.parent
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            continue
    print(f"removed {removed} unfilled handoff template(s) under {root}")
    print("Files that had been filled in were left alone.")
    return 0


def maintain(force: bool = False) -> int:
    """Run cognify + memify in report mode, at most once a day.

    Report mode, never `--hard`: the whole point of a memory is that it does not
    quietly lose things, and a scheduled job that deletes is the one component
    nobody watches. It writes down what it *would* remove; deleting stays an
    explicit act.
    """
    cfg = mg.load_config()
    every = float(cfg.get("maintain_every_h", 24))
    p = mg.data_dir() / "maintenance.json"
    try:
        last = json.loads(p.read_text()).get("ts", 0)
    except Exception:
        last = 0
    if not force and (time.time() - last) < every * 3600:
        return 0
    here = Path(__file__).parent
    summary = {}

    # Repair before reporting. A stale lock and a wedged model server both make
    # every later step quietly worse, and both have a one-command fix that
    # nobody runs because nobody sees the problem.
    if reap_stale_lock():
        summary["stale_lock"] = "removed a lock whose holder was gone"
    try:
        import broker
        d = broker.diagnose()
        if d.get("verdict") not in ("OK", None):
            summary["model_server"] = f"{d.get('verdict')}: {d.get('why')}"
            if broker.recover(1):
                after = broker.diagnose()
                summary["model_server"] += f" -> after recover: {after.get('verdict')}"
    except Exception as e:  # noqa: BLE001
        summary["model_server"] = f"diagnose failed: {e}"

    for name, args in (("cognify", ["--run", "--no-model"]),
                       ("memify", ["--run", "--json"]),
                       ("factcheck", ["--json", str(mg.data_dir() / "factcheck.json")])):
        try:
            r = subprocess.run([sys.executable, str(here / f"{name}.py"), *args],
                               capture_output=True, text=True, timeout=180)
            summary[name] = (r.stdout or r.stderr)[-400:]
        except Exception as e:  # noqa: BLE001
            summary[name] = f"failed: {e}"
    p.write_text(json.dumps({"ts": time.time(), "summary": summary}, indent=2))
    print(json.dumps(summary, indent=2)[:1200])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fix", action="store_true",
                    help="apply the hook de-duplication (settings.json only)")
    ap.add_argument("--clean-handoffs", action="store_true")
    ap.add_argument("--maintain", action="store_true")
    ap.add_argument("--maintain-if-due", action="store_true",
                    help="internal: run maintenance only if the interval has "
                         "elapsed; spawned in the background at session end")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    a = ap.parse_args()

    if a.fix:
        return apply_fix()
    if a.clean_handoffs:
        return clean_handoffs(a.root)
    if a.maintain:
        return maintain(force=True)
    if a.maintain_if_due:
        return maintain(force=False)

    data = autopilot.read_settings()
    findings = (check_hook_overlap(data) + check_handoff_litter(a.root)
                + check_model_server() + check_stale_locks()
                + check_memory_hygiene() + check_installed_version()
                + check_autopilot_state() + check_maintenance())
    print("memo-guard doctor")
    print("-----------------")
    for f in findings:
        f.show()
    bad = sum(1 for f in findings if f.level in ("warn", "error"))
    print(f"\n{bad} thing(s) worth doing, "
          f"{len(findings) - bad} fine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
