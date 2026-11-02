"""V17: localhost web UI and asynchronous API for the V16 review workflow."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import study_guide_v16_human_approval as v16

VERSION = "v17.1"
ROOT = Path(__file__).resolve().parent
MAX_BODY = 65536
ID = re.compile(r"^[a-f0-9]{32}$")


class APIError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def public_snapshot(state, pending):
    state = {k: v for k, v in state.items() if not k.startswith("__")}
    # Independent serializable view: never expose native Interrupt objects.
    return {"state": state, "review": pending,
            "metrics": v16.v15.execution_metrics(state, state["trace"]) if state["plan"] else {}}


class SessionService:
    """One worker per service. Durable review state is owned by LangGraph."""

    def __init__(self, data_dir, chunks, model_factory=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database = self.data_dir / "sessions.sqlite"
        self.chunks = chunks
        self.model_factory = model_factory
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v17-workflow")
        self.closed = False
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS web_sessions "
                                   "(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self.records = {key: json.loads(payload) for key, payload in
                            connection.execute("SELECT id,payload FROM web_sessions")}
        for record in self.records.values():
            if record["job_status"] in ("queued", "running"):
                record.update(job_status="recovery_required",
                              error="Process stopped during a job. Inspect the saved checkpoint before continuing.")
                self._save(record)

    def _save(self, record):
        with closing(sqlite3.connect(self.database, timeout=30)) as connection:
            with connection:
                connection.execute("INSERT INTO web_sessions VALUES (?,?) ON CONFLICT(id) "
                                   "DO UPDATE SET payload=excluded.payload",
                                   (record["id"], json.dumps(record, allow_nan=False)))

    def get(self, session):
        with self.lock:
            if session not in self.records:
                raise APIError(404, "Session not found")
            return copy.deepcopy(self.records[session])

    def list_sessions(self):
        with self.lock:
            return [{key: r[key] for key in ("id", "goal", "offline", "job_status", "updated_at")}
                    for r in sorted(self.records.values(), key=lambda r: r["updated_at"], reverse=True)]

    def _capacity(self):
        if self.closed:
            raise APIError(503, "Service is stopping")
        if sum(r["job_status"] in ("queued", "running") for r in self.records.values()) >= 16:
            raise APIError(429, "Local job queue is full")

    def create(self, payload):
        if set(payload) != {"goal", "offline"}:
            raise APIError(400, "Provide exactly goal and offline")
        goal, offline = payload["goal"], payload["offline"]
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000 or type(offline) is not bool:
            raise APIError(400, "Goal must contain 1 to 2000 characters; offline must be boolean")
        with self.lock:
            self._capacity()
            record = {"id": uuid4().hex, "goal": goal.strip(), "offline": offline,
                      "job_status": "queued", "updated_at": now(), "snapshot": None,
                      "error": "", "request_ids": {}}
            self._save(record)
            self.records[record["id"]] = record
            self.pool.submit(self._run, record["id"], None)
            return copy.deepcopy(record)

    def review(self, session, payload):
        required = {"request_id", "decision"}
        if set(payload) != required or not isinstance(payload["request_id"], str) or not ID.fullmatch(payload["request_id"]):
            raise APIError(400, "Provide a unique 32-character hexadecimal request_id and decision")
        try:
            decision = v16.ReviewDecision.model_validate(payload["decision"])
            if decision.plan is not None:
                v16.v14.Plan.model_validate(decision.plan)
        except (ValueError, TypeError) as error:
            raise APIError(400, str(error)) from error
        fingerprint = hashlib.sha256(json.dumps(decision.model_dump(), sort_keys=True,
                                                allow_nan=False).encode()).hexdigest()
        with self.lock:
            record = self.get(session)
            if payload["request_id"] in record["request_ids"]:
                if record["request_ids"][payload["request_id"]] != fingerprint:
                    raise APIError(409, "Request ID was already used for a different decision")
                return record  # A browser retry does not resume a gate twice.
            if record["job_status"] in ("queued", "running"):
                raise APIError(409, "A session job is already pending")
            if record["job_status"] != "awaiting_review":
                raise APIError(409, "Session has no actionable review gate")
            pending = record["snapshot"]["review"]
            if pending is None or pending["review_id"] != decision.review_id:
                raise APIError(409, "Stale decision; refresh the current review")
            self._capacity()
            record["request_ids"][payload["request_id"]] = fingerprint
            record.update(job_status="queued", error="", updated_at=now())
            self._save(record)
            self.records[session] = record
            self.pool.submit(self._run, session, decision.model_dump())
            return copy.deepcopy(record)

    def _graph(self, connection, offline):
        from langgraph.checkpoint.sqlite import SqliteSaver
        parent = self
        class LazyModel:
            def with_structured_output(self, schema):
                if parent.model_factory is not None:
                    model = parent.model_factory()
                else:
                    from langchain_ollama import ChatOllama
                    model = ChatOllama(model="qwen3.5:4b", temperature=0,
                                       base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
                return model.with_structured_output(schema)
        return v16.build_review_graph(self.chunks, SqliteSaver(connection), None if offline else LazyModel())

    def _checkpoint(self, app, config):
        snapshot = app.get_state(config)
        if not snapshot.values:
            raise APIError(409, "No checkpoint available; create a new session")
        v16.validate_resume(snapshot.values, self.chunks, snapshot.values["offline"])
        pending = v16.current_interrupt(snapshot)
        if snapshot.next and pending is None:
            raise APIError(409, "Interrupted outside a review gate. Automatic execution replay is disabled")
        return public_snapshot(snapshot.values, pending)

    def _run(self, session, decision):
        try:
            with self.lock:
                record = self.records[session]
                record.update(job_status="running", updated_at=now())
                self._save(record)
                offline, goal = record["offline"], record["goal"]
            from langgraph.types import Command
            config = {"configurable": {"thread_id": session}, "recursion_limit": 32}
            with closing(sqlite3.connect(self.database, check_same_thread=False, timeout=30)) as connection:
                app = self._graph(connection, offline)
                if decision is None:
                    app.invoke(v16.initial_state(goal, self.chunks, offline), config, durability="sync")
                else:
                    before = self._checkpoint(app, config)
                    if before["review"] is None or before["review"]["review_id"] != decision["review_id"]:
                        raise APIError(409, "Saved review changed; refresh the session")
                    app.invoke(Command(resume=decision), config, durability="sync")
                snapshot = self._checkpoint(app, config)
            with self.lock:
                record = self.records[session]
                record.update(snapshot=snapshot, job_status=("awaiting_review" if snapshot["review"]
                              else snapshot["state"]["status"]), error="", updated_at=now())
                self._save(record)
        except Exception as error:
            with self.lock:
                record = self.records[session]
                record.update(job_status="error", error=f"{type(error).__name__}: {error}", updated_at=now())
                self._save(record)

    def recover(self, session):
        with self.lock:
            record = self.get(session)
            if record["job_status"] not in ("error", "recovery_required"):
                raise APIError(409, "Only an interrupted or failed session needs recovery inspection")
            # Never execute nodes while recovering. Only restore a saved gate/terminal view.
            with closing(sqlite3.connect(self.database, check_same_thread=False, timeout=30)) as connection:
                app = self._graph(connection, record["offline"])
                try:
                    snapshot = self._checkpoint(app, {"configurable": {"thread_id": session}})
                except ValueError as error:
                    if isinstance(error, APIError):
                        raise
                    raise APIError(409, str(error)) from error
            record.update(snapshot=snapshot, job_status="awaiting_review" if snapshot["review"]
                          else snapshot["state"]["status"], error="", updated_at=now())
            self._save(record)
            self.records[session] = record
            return record

    def close(self):
        with self.lock:
            self.closed = True
        self.pool.shutdown(wait=True)


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, service, asset_dir=None):
        self.service = service
        self.asset_dir = Path(asset_dir or ROOT / "web_v17")
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "StudyGuideV17"
    def log_message(self, *args):
        pass

    def send_data(self, status, data, content_type="application/json; charset=utf-8", filename=None):
        body = data if isinstance(data, bytes) else json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; "
                         "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def check_host(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host", "") not in allowed:
            raise APIError(403, "Use the localhost URL printed by the server")

    def check_write(self):
        self.check_host()
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}",
                                     f"http://localhost:{self.server.server_port}"}:
            raise APIError(403, "Cross-origin writes are not allowed")
        if not secrets.compare_digest(self.headers.get("X-Review-Token", ""), self.server.token):
            raise APIError(403, "Missing or invalid local review token")

    def body(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise APIError(400, "Invalid content length") from error
        if not 0 < size <= MAX_BODY:
            raise APIError(413, "JSON body must contain 1 to 65536 bytes")
        if self.headers.get_content_type() != "application/json":
            raise APIError(415, "Use application/json")
        try:
            def reject_constant(value):
                raise ValueError(f"Nonfinite JSON value: {value}")
            data = json.loads(self.rfile.read(size), parse_constant=reject_constant)
        except (ValueError, UnicodeDecodeError) as error:
            raise APIError(400, "Invalid JSON") from error
        if not isinstance(data, dict):
            raise APIError(400, "JSON body must be an object")
        return data

    def do_GET(self):
        try:
            self.check_host()
            path = urlsplit(self.path).path
            if path in ("/", "/app.js", "/style.css"):
                name, content_type = {"/": ("index.html", "text/html; charset=utf-8"),
                                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                                      "/style.css": ("style.css", "text/css; charset=utf-8")}[path]
                self.send_data(200, (self.server.asset_dir / name).read_bytes(), content_type)
            elif path == "/api/bootstrap":
                self.send_data(200, {"version": VERSION, "token": self.server.token})
            elif path == "/api/sessions":
                self.send_data(200, self.server.service.list_sessions())
            else:
                match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})(/export)?", path)
                if not match:
                    raise APIError(404, "Route not found")
                record = self.server.service.get(match[1])
                self.send_data(200, record, filename=f"study-session-{match[1]}.json" if match[2] else None)
        except APIError as error:
            self.send_data(error.status, {"error": str(error)})
        except Exception:
            self.send_data(500, {"error": "Local server error. Check file access and restart if needed."})

    def do_POST(self):
        try:
            self.check_write()
            path = urlsplit(self.path).path
            data = self.body()
            if path == "/api/sessions":
                self.send_data(202, self.server.service.create(data))
                return
            match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/(review|recover)", path)
            if not match:
                raise APIError(404, "Route not found")
            if match[2] == "review":
                record = self.server.service.review(match[1], data)
                self.send_data(202, record)
            else:
                if data:
                    raise APIError(400, "Recovery inspection takes an empty object")
                self.send_data(200, self.server.service.recover(match[1]))
        except APIError as error:
            self.send_data(error.status, {"error": str(error)})
        except Exception:
            self.send_data(500, {"error": "Local server error. Refresh the session before retrying."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    chunks = v16.v14.v12.load_trusted_chunks(ROOT / "trusted_documents")
    service = SessionService(os.environ.get("V17_DATA_DIR", str(ROOT / "v17_data")), chunks)
    try:
        server = AppServer((args.host, args.port), service)
        print(f"V17 Review Studio: http://127.0.0.1:{server.server_port}")
        print("Local single-user application. Keep this terminal open; Ctrl+C stops the server.")
        print("Model sessions use Ollama; offline sessions do not invoke a model.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping; waiting for any active workflow operation to finish.")
        finally:
            server.server_close()
    finally:
        service.close()


if __name__ == "__main__":
    main()
