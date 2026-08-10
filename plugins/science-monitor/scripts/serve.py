#!/usr/bin/env python3
"""Loopback-only web server that makes the dashboard's buttons actually write.

Without this the dashboard is a report: its buttons copy the command you would
have typed. With it, ticking a checklist item, flipping a cover-letter state or
marking a submission sent goes straight into the SQLite store.

Bound to 127.0.0.1 and gated on a per-run token that only the served page
carries. Cross-origin pages cannot send the required custom header without a
CORS preflight, which is refused.
"""

import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dashboard as D  # noqa: E402
import sm_lib as L  # noqa: E402

TOKEN = secrets.token_urlsafe(24)

# Fields a button is allowed to change, and what counts as a legal value.
SUBMISSION_FIELDS = {
    "submitted": lambda v: 1 if v in (1, True, "1", "true") else 0,
    "cover_letter_state": lambda v: v if v in L.COVER_STATES else None,
    "status": lambda v: v if v in L.STATUSES else None,
    "submitted_at": lambda v: str(v)[:10],
    "due_at": lambda v: str(v)[:10],
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # the console belongs to the user, not to request noise

    # -- helpers ------------------------------------------------------------

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _local(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _authed(self):
        return (self.headers.get("X-SM-Token") == TOKEN
                and self._local()
                and not self.headers.get("Origin", "").startswith("http://localhost:0"))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 64_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    # -- routes -------------------------------------------------------------

    def do_GET(self):
        if not self._local():
            return self._send(403, '{"error":"forbidden"}')
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            conn = L.connect()
            try:
                html = D.build(conn, api_token=TOKEN)
            finally:
                conn.close()
            return self._send(200, html, "text/html; charset=utf-8")
        self._send(404, '{"error":"not found"}')

    def do_POST(self):
        if not self._authed():
            return self._send(403, '{"error":"forbidden"}')
        path = self.path.split("?")[0]
        data = self._body()
        conn = L.connect()
        try:
            result = self._dispatch(conn, path, data)
        except Exception as exc:  # a bad click must not kill the server
            conn.rollback()
            return self._send(400, json.dumps({"error": str(exc)}))
        finally:
            conn.close()
        if result is None:
            return self._send(404, '{"error":"not found"}')
        self._send(200, json.dumps(result, ensure_ascii=False))

    def _dispatch(self, conn, path, data):
        if path == "/api/checklist":
            row = conn.execute("SELECT * FROM checklist WHERE id = ?",
                               (int(data["id"]),)).fetchone()
            if not row:
                raise ValueError("nincs ilyen checklist-tétel")
            if data.get("na"):
                done, na = 0, 0 if row["na"] else 1
            else:
                done, na = (0 if row["done"] else 1), 0
            conn.execute("UPDATE checklist SET done = ?, na = ? WHERE id = ?",
                         (done, na, row["id"]))
            conn.commit()
            sub = conn.execute("SELECT * FROM submissions WHERE id = ?",
                               (row["submission_id"],)).fetchone()
            d, t = L.checklist_progress(conn, row["submission_id"])
            return {"ok": True, "done": done, "na": na, "progress": [d, t],
                    "submission_id": sub["id"]}

        if path == "/api/point":
            row = conn.execute("SELECT * FROM review_points WHERE id = ?",
                               (int(data["id"]),)).fetchone()
            if not row:
                raise ValueError("nincs ilyen bírálói pont")
            state = data.get("state")
            if state not in L.POINT_STATES:
                state = "open" if row["state"] == "done" else "done"
            conn.execute("UPDATE review_points SET state = ? WHERE id = ?",
                         (state, row["id"]))
            conn.commit()
            d, t = L.point_progress(conn, row["review_id"])
            return {"ok": True, "state": state, "progress": [d, t]}

        if path == "/api/submission":
            sid = int(data["id"])
            field = data.get("field")
            if field not in SUBMISSION_FIELDS:
                raise ValueError(f"nem módosítható mező: {field}")
            value = SUBMISSION_FIELDS[field](data.get("value"))
            if value is None:
                raise ValueError(f"érvénytelen érték a(z) {field} mezőhöz")
            sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (sid,)).fetchone()
            if not sub:
                raise ValueError("nincs ilyen beadás")
            conn.execute(f"UPDATE submissions SET {field} = ? WHERE id = ?", (value, sid))
            # Any status inside the submission process implies the package went
            # out — that is what "beadva" means, and it is what starts the track.
            if field == "status" and L.stage_index(value) >= 0 and not sub["submitted"]:
                conn.execute(
                    "UPDATE submissions SET submitted = 1, "
                    "submitted_at = COALESCE(NULLIF(submitted_at, ''), ?) WHERE id = ?",
                    (L.today(), sid))
            # An editorial verdict is a dated fact, not just a status word.
            if field == "status" and value in (
                    L.REJECTED | L.NEEDS_ACTION | {"accepted"}):
                conn.execute(
                    "UPDATE submissions SET decision = ?, decision_at = ? WHERE id = ?",
                    (value, sub["decision_at"] or L.today(), sid))
            # Marking it sent without a date would leave the record half-built.
            if field == "submitted" and value == 1:
                if not sub["submitted_at"]:
                    conn.execute("UPDATE submissions SET submitted_at = ? WHERE id = ?",
                                 (L.today(), sid))
                if sub["status"] in ("drafting", "ready"):
                    conn.execute("UPDATE submissions SET status = 'submitted' WHERE id = ?",
                                 (sid,))
            L.log_event(conn, sub["project_id"], "dashboard_edit",
                        f"{field} = {value}", sid)
            conn.commit()
            return {"ok": True, "reload": True}

        if path == "/api/task":
            row = conn.execute("SELECT * FROM tasks WHERE id = ?",
                               (int(data["id"]),)).fetchone()
            if not row:
                raise ValueError("nincs ilyen részfeladat")
            state = data.get("state")
            if state not in L.TASK_STATES:
                state = "open" if row["state"] == "done" else "done"
            conn.execute("UPDATE tasks SET state = ?, done_at = ? WHERE id = ?",
                         (state, L.today() if state == "done" else "", row["id"]))
            conn.commit()
            d, t = L.task_progress(conn, row["project_id"])
            return {"ok": True, "state": state, "progress": [d, t]}

        if path == "/api/project/new":
            title = str(data.get("title", "")).strip()
            if not title:
                raise ValueError("cím nélkül nem lehet kéziratot felvenni")
            kind = data.get("kind") or "article"
            category = data.get("category") or "kutatas"
            if category not in L.CATEGORIES:
                raise ValueError(f"ismeretlen kategória: {category}")
            root = os.path.abspath(os.path.expanduser(data["path"])) if data.get("path") else ""
            slug = base = L.slugify(title)
            n = 2
            while conn.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,)).fetchone():
                slug = f"{base}-{n}"
                n += 1
            conn.execute(
                "INSERT INTO projects (slug, title, kind, root_path, category, created_at) "
                "VALUES (?,?,?,?,?,?)", (slug, title, kind, root, category, L.now()))
            pid = conn.execute("SELECT id FROM projects WHERE slug = ?",
                               (slug,)).fetchone()["id"]
            L.log_event(conn, pid, "project_added", f"{title} (dashboard)")
            conn.commit()
            return {"ok": True, "reload": True, "slug": slug}

        if path == "/api/project":
            pid = int(data["id"])
            field = data.get("field")
            value = data.get("value")
            if field == "state":
                if value not in L.PROJECT_STATES:
                    raise ValueError(f"ismeretlen állapot: {value}")
            elif field == "archived":
                value = 1 if value in (1, True, "1", "true") else 0
            elif field == "category":
                if value not in L.CATEGORIES:
                    raise ValueError(f"ismeretlen kategória: {value}")
            else:
                raise ValueError(f"nem módosítható mező: {field}")
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
            if not row:
                raise ValueError("nincs ilyen kézirat")
            conn.execute(f"UPDATE projects SET {field} = ? WHERE id = ?", (value, pid))
            L.log_event(conn, pid, field, f"{row[field]} → {value} (dashboard)")
            conn.commit()
            return {"ok": True, "reload": True}

        if path == "/api/checklist/init":
            sid = int(data["id"])
            sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (sid,)).fetchone()
            if not sub:
                raise ValueError("nincs ilyen beadás")
            p = conn.execute("SELECT * FROM projects WHERE id = ?",
                             (sub["project_id"],)).fetchone()
            L.seed_checklist(conn, sid, p["kind"], p["category"])
            conn.commit()
            return {"ok": True, "reload": True}

        return None


def run(port=8787, open_browser=True):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Science Monitor él: {url}")
    print("A gombok és a checklist közvetlenül írnak az adatbázisba.")
    print("Leállítás: Ctrl-C\n")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nleállítva")
    finally:
        server.server_close()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8787)
