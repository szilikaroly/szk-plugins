#!/usr/bin/env python3
"""vault - continuous, private git backup for every project under one root.

Runs the same on macOS and Windows. Nothing here blocks a Claude Code session:
the Stop hook detaches immediately and the real work happens in a child process
that cannot fail the hook, however badly the network behaves.

  vault.py init      discover projects, create repos and private remotes
  vault.py save      one autosave pass (this is what the hook calls)
  vault.py status    what is tracked, what is behind, what is held back
  vault.py pause     stop autosaving (commits and pushes both)
  vault.py resume    undo pause
  vault.py doctor    why is it not working
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
VAULT_HOME = Path(os.environ.get("VAULT_HOME") or HOME / ".claude" / "vault")
CONFIG = VAULT_HOME / "config.json"
STATE = VAULT_HOME / "state.json"
LOG = VAULT_HOME / "vault.log"

DEFAULTS = {
    # Where the projects live. One git repo per immediate subdirectory.
    "root": str(HOME / "Documents" / "claude"),
    # GitHub account that owns the private repos. Empty = gh's default account.
    "github_owner": "",
    # Prefix for the remote repo names, so they group in the GitHub listing.
    "repo_prefix": "",
    # Do not push more often than this per project (seconds).
    "interval_sec": 300,
    # Files at or above this size are excluded - GitHub hard-rejects >100 MB.
    "max_file_mb": 95,
    # A repo bigger than this is committed locally but not pushed, unless forced.
    # GitHub warns above 1 GB and serves very large repos badly.
    "max_repo_gb": 4.0,
    "paused": False,
    # Add a name here to leave a project alone entirely.
    "exclude": [".claude", ".git", "evals"],
}

IGNORE_LINES = [
    "# --- vault: generated, safe to extend below ---",
    ".DS_Store", "._*", "Thumbs.db", "desktop.ini",
    "__pycache__/", "*.py[cod]", ".ipynb_checkpoints/",
    ".venv/", "venv/", "env/", "node_modules/",
    ".Rproj.user/", ".Rhistory", ".RData",
    "*.tmp", "*.temp", "*.swp", "*.bak",
    ".memo/", ".vault/",
]

WINDOWS = os.name == "nt"
NO_WINDOW = 0x08000000 if WINDOWS else 0
DETACHED = 0x00000008 if WINDOWS else 0

GIT = shutil.which("git") or "git"
GH = shutil.which("gh")


# ---------------------------------------------------------------- plumbing

def log(msg):
    VAULT_HOME.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(stamp + " " + msg + "\n")
    except OSError:
        pass


def run(args, cwd=None, timeout=300):
    """Run a command. Never raises; returns (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            args, cwd=str(cwd) if cwd else None, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=NO_WINDOW)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after %ss" % timeout
    except (OSError, ValueError) as exc:
        return 127, "", str(exc)


def git(repo, *args, timeout=300):
    return run([GIT, "-C", str(repo)] + list(args), timeout=timeout)


def load(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(fallback) if isinstance(fallback, dict) else fallback


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def config():
    cfg = dict(DEFAULTS)
    cfg.update(load(CONFIG, {}))
    return cfg


def state():
    st = load(STATE, {"projects": {}})
    st.setdefault("projects", {})
    return st


# ---------------------------------------------------------------- discovery

def discover(cfg):
    root = Path(cfg["root"])
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if d.name in cfg["exclude"]:
            continue
        try:
            next(iter(d.iterdir()))
        except (StopIteration, OSError):
            continue  # empty directory - nothing to version
        out.append(d)
    return out


def dir_bytes(p):
    total = 0
    for dirpath, dirnames, filenames in os.walk(p):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for f in filenames:
            try:
                total += (Path(dirpath) / f).stat().st_size
            except OSError:
                pass
    return total


def oversize(p, limit_bytes):
    """Files GitHub will not take. Returned relative to the project."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(p):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for f in filenames:
            fp = Path(dirpath) / f
            try:
                sz = fp.stat().st_size
            except OSError:
                continue
            if sz >= limit_bytes:
                hits.append((fp.relative_to(p).as_posix(), sz))
    return sorted(hits, key=lambda x: -x[1])


# ---------------------------------------------------------------- repo setup

def ensure_gitignore(p, big):
    gi = p / ".gitignore"
    if gi.exists():
        existing = gi.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        existing = []
    have = set(existing)
    add = [ln for ln in IGNORE_LINES if ln not in have]
    marker = "# --- vault: too large for GitHub (see .vault/oversize.txt) ---"
    big_lines = ["/" + rel for rel, _ in big if "/" + rel not in have]
    if big_lines and marker not in have:
        add.append("")
        add.append(marker)
    add.extend(big_lines)
    if not add:
        return
    with gi.open("a", encoding="utf-8") as fh:
        if existing and existing[-1].strip():
            fh.write("\n")
        fh.write("\n".join(add) + "\n")


def record_oversize(p, big):
    """Write down exactly what was excluded, so it is never a silent loss."""
    d = p / ".vault"
    try:
        d.mkdir(exist_ok=True)
    except OSError:
        return
    lines = ["# Files excluded from git because GitHub rejects them (>=95 MB).",
             "# They are still on disk, untouched. This list is not pushed either.",
             ""]
    for rel, sz in big:
        lines.append("%14d  %s" % (sz, rel))
    if not big:
        lines.append("(none)")
    try:
        (d / "oversize.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def ensure_repo(p, cfg):
    """git init + .gitignore + first commit. Returns (ok, message)."""
    big = oversize(p, int(cfg["max_file_mb"] * 1024 * 1024))
    if not (p / ".git").is_dir():
        rc, _, err = run([GIT, "init", "-b", "main"], cwd=p)
        if rc:
            return False, "git init: " + err
        git(p, "config", "core.fileMode", "false")
        git(p, "config", "core.autocrlf", "false")
    ensure_gitignore(p, big)
    record_oversize(p, big)
    rc, out, _ = git(p, "status", "--porcelain")
    if out:
        git(p, "add", "-A", timeout=1200)
        rc, _, err = git(p, "commit", "-m", "vault: initial snapshot", timeout=1200)
        if rc and "nothing to commit" not in err.lower():
            return False, "commit: " + err[:200]
    return True, "ok"


def gh_ready():
    if not GH:
        return False, "a gh CLI nincs telepitve"
    rc, _, _ = run([GH, "auth", "status"], timeout=30)
    if rc:
        return False, "a gh nincs bejelentkezve (futtasd: gh auth login)"
    return True, "ok"


def ensure_remote(p, cfg):
    """Create the private GitHub repo and wire it as origin. (ok, message)."""
    rc, out, _ = git(p, "remote", "get-url", "origin")
    if rc == 0 and out:
        return True, out
    ok, why = gh_ready()
    if not ok:
        return False, why
    name = cfg["repo_prefix"] + p.name
    target = (cfg["github_owner"] + "/" + name) if cfg["github_owner"] else name
    rc, out, err = run([GH, "repo", "create", target, "--private",
                        "--source", str(p), "--remote", "origin"], timeout=180)
    if rc:
        blob = (err + out).lower()
        if "already exists" in blob or "name already" in blob:
            owner = cfg["github_owner"]
            if not owner:
                _, owner, _ = run([GH, "api", "user", "--jq", ".login"], timeout=30)
            url = "https://github.com/%s/%s.git" % (owner, name)
            rc2, _, err2 = git(p, "remote", "add", "origin", url)
            if rc2:
                return False, "remote add: " + err2[:160]
            return True, url
        return False, "gh repo create: " + err[:200]
    rc, out, _ = git(p, "remote", "get-url", "origin")
    return True, out or "origin"


# ---------------------------------------------------------------- the save pass

def push_allowed(p, cfg):
    if (p / ".vault" / "force-push").exists():
        return True, dir_bytes(p)
    size = dir_bytes(p)
    return size <= float(cfg["max_repo_gb"]) * 1024 ** 3, size


def autosave(p, cfg, st, force=False):
    """One project. Returns a short human-readable outcome string."""
    rec = st["projects"].setdefault(p.name, {})
    now = time.time()
    if not force and now - rec.get("last_run", 0) < float(cfg["interval_sec"]):
        return "skipped (debounce)"
    rec["last_run"] = now

    if not (p / ".git").is_dir():
        ok, msg = ensure_repo(p, cfg)
        if not ok:
            rec["error"] = msg
            return "init failed: " + msg

    # Re-check oversize every pass; new big files appear as the work goes on.
    big = oversize(p, int(cfg["max_file_mb"] * 1024 * 1024))
    if big:
        ensure_gitignore(p, big)
        record_oversize(p, big)
    rec["oversize"] = len(big)

    rc, out, _ = git(p, "status", "--porcelain")
    committed = 0
    if out:
        n = len(out.splitlines())
        git(p, "add", "-A", timeout=1200)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        rc, _, err = git(p, "commit", "-m",
                         "vault: autosave %s (%d file)" % (stamp, n), timeout=1200)
        if rc and "nothing to commit" not in err.lower():
            rec["error"] = err[:200]
            return "commit failed: " + err[:120]
        rec["last_commit"] = now
        rec.pop("error", None)
        committed = n

    allowed, size = push_allowed(p, cfg)
    rec["bytes"] = size
    if not allowed:
        rec["held"] = "too large for GitHub"
        return ("committed %d file, push visszatartva (%.1f GB > %s GB)"
                % (committed, size / 1024 ** 3, cfg["max_repo_gb"]))
    rec.pop("held", None)

    rc, url, _ = git(p, "remote", "get-url", "origin")
    if rc or not url:
        ok, msg = ensure_remote(p, cfg)
        if not ok:
            rec["error"] = msg
            return "no remote: " + msg

    rc, ahead, _ = git(p, "rev-list", "--count", "@{u}..HEAD")
    if rc:                          # no upstream branch yet
        rc, _, err = git(p, "push", "-u", "origin", "HEAD", timeout=3600)
    elif ahead and ahead != "0":
        rc, _, err = git(p, "push", "origin", "HEAD", timeout=3600)
    else:
        return "committed %d file, mar pusholva" % committed
    if rc:
        rec["error"] = err[:200]
        return "push failed: " + err[:120]
    rec["last_push"] = now
    rec.pop("error", None)
    return "committed %d file, pusholva" % committed


# ---------------------------------------------------------------- commands

def cmd_save(args):
    cfg = config()
    if cfg["paused"] and not args.force:
        if not args.quiet:
            print("vault: szunetel (/vault:resume a folytatashoz)")
        return 0
    st = state()
    names = set(args.project) if args.project else None
    results = []
    for p in discover(cfg):
        if names and p.name not in names:
            continue
        try:
            r = autosave(p, cfg, st, force=args.force)
        except Exception as exc:                # a hook must never die
            r = "error: %r" % (exc,)
        results.append((p.name, r))
        log("%s: %s" % (p.name, r))
    st["last_run"] = time.time()
    save_json(STATE, st)
    if not args.quiet:
        for name, r in results:
            if "skipped" not in r:
                print("  %-26s %s" % (name, r))
    return 0


def cmd_init(args):
    cfg = config()
    if not CONFIG.exists():
        save_json(CONFIG, cfg)
        print("config: %s" % CONFIG)
    ok, why = gh_ready()
    print("gh: %s" % why)
    projects = discover(cfg)
    print("%d projekt a(z) %s alatt\n" % (len(projects), cfg["root"]))
    st = state()
    for p in projects:
        ok_repo, msg = ensure_repo(p, cfg)
        if not ok_repo:
            print("  %-26s HIBA: %s" % (p.name, msg))
            continue
        allowed, size = push_allowed(p, cfg)
        gb = size / 1024 ** 3
        if not allowed:
            print("  %-26s git ok, %5.2f GB - push visszatartva (tul nagy)"
                  % (p.name, gb))
            st["projects"].setdefault(p.name, {})["held"] = "too large for GitHub"
            continue
        if args.no_remote:
            print("  %-26s git ok, %5.2f GB" % (p.name, gb))
            continue
        ok_rem, url = ensure_remote(p, cfg)
        tail = ("remote: " + url) if ok_rem else ("remote HIBA: " + url)
        print("  %-26s git ok, %5.2f GB - %s" % (p.name, gb, tail))
    save_json(STATE, st)
    return 0


def cmd_status(args):
    cfg = config()
    st = state()
    print("root       %s" % cfg["root"])
    print("allapot    %s   (push legfeljebb %ss-kent projektenkent)"
          % ("SZUNETEL" if cfg["paused"] else "aktiv", cfg["interval_sec"]))
    ok, why = gh_ready()
    print("gh         %s" % why)
    if st.get("last_run"):
        print("utolso kor %s"
              % datetime.fromtimestamp(st["last_run"]).strftime("%Y-%m-%d %H:%M:%S"))
    print()
    print("  %-26s %8s  %11s  allapot" % ("projekt", "meret", "nem pusholt"))
    for p in discover(cfg):
        rec = st["projects"].get(p.name, {})
        if not (p / ".git").is_dir():
            print("  %-26s %8s  %11s  nincs git repo" % (p.name, "-", "-"))
            continue
        rc, ahead, _ = git(p, "rev-list", "--count", "@{u}..HEAD")
        ahead = ahead if rc == 0 else "nincs remote"
        _, dirty, _ = git(p, "status", "--porcelain")
        gb = rec.get("bytes", 0) / 1024 ** 3
        bits = []
        if dirty:
            bits.append("%d valtozas" % len(dirty.splitlines()))
        if rec.get("held"):
            bits.append("PUSH VISSZATARTVA (tul nagy)")
        if rec.get("oversize"):
            bits.append("%d nagy fajl kihagyva" % rec["oversize"])
        if rec.get("error"):
            bits.append("HIBA: " + rec["error"][:60])
        print("  %-26s %7.2fG  %11s  %s"
              % (p.name, gb, ahead, ", ".join(bits) or "naprakesz"))
    return 0


def cmd_pause(args):
    cfg = config()
    cfg["paused"] = args.cmd == "pause"
    save_json(CONFIG, cfg)
    print("vault: " + ("szuneteltetve" if cfg["paused"] else "ujraindítva"))
    return 0


def cmd_doctor(args):
    cfg = config()
    print("git        %s" % (GIT if shutil.which("git") else "NINCS"))
    print("gh         %s" % (GH or "NINCS"))
    ok, why = gh_ready()
    print("gh auth    %s" % why)
    print("config     %s %s" % (CONFIG, "(megvan)" if CONFIG.exists() else "(alapertelmezes)"))
    print("root       %s %s" % (cfg["root"],
                                "ok" if Path(cfg["root"]).is_dir() else "NEM LETEZIK"))
    print("naplo      %s" % LOG)
    projects = discover(cfg)
    norepo = [p.name for p in projects if not (p / ".git").is_dir()]
    print("projekt    %d db, ebbol %d meg git nelkul" % (len(projects), len(norepo)))
    if norepo:
        print("           " + ", ".join(norepo[:8]) + ("..." if len(norepo) > 8 else ""))
    if LOG.exists():
        print("\nutolso 10 naploso:")
        for ln in LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-10:]:
            print("  " + ln)
    return 0


def detach_and_exit(argv):
    """Re-run ourselves detached, then hand control back at once."""
    cmd = [sys.executable, str(Path(__file__).resolve())] + argv + ["--quiet"]
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
              "stdin": subprocess.DEVNULL}
    if WINDOWS:
        kwargs["creationflags"] = DETACHED | NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        log("detach failed: %r" % (exc,))
    return 0


def main():
    ap = argparse.ArgumentParser(
        prog="vault", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("save")
    s.add_argument("project", nargs="*")
    s.add_argument("--force", action="store_true", help="ignore the debounce")
    s.add_argument("--hook", action="store_true", help="called from a hook")
    s.add_argument("--detach", action="store_true", help="fork and return at once")
    s.add_argument("--quiet", action="store_true")

    i = sub.add_parser("init")
    i.add_argument("--no-remote", action="store_true",
                   help="repos and commits only, do not touch GitHub")

    sub.add_parser("status")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("doctor")

    args = ap.parse_args()
    if args.cmd == "save" and args.detach:
        argv = ["save"] + list(args.project)
        if args.force:
            argv.append("--force")
        return detach_and_exit(argv)
    table = {"save": cmd_save, "init": cmd_init, "status": cmd_status,
             "pause": cmd_pause, "resume": cmd_pause, "doctor": cmd_doctor}
    return table[args.cmd](args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
