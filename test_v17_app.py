"""V17 API integration tests. No Ollama, network service, or persistent user data."""
from __future__ import annotations

import copy
import http.client
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import study_guide_v17_app as v17


def corpus():
    return [v17.v16.v14.v12.TrustedChunk("energy", "Conservation of Energy", "Conservation",
            "Total energy remains conserved as energy moves between different forms.",
            Path("trusted_documents/energy.md"), 1)]


class WebApplicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.service = v17.SessionService(self.directory.name, corpus())
        self.server = v17.AppServer(("127.0.0.1", 0), self.service)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.service.close()
        self.directory.cleanup()

    def request(self, path, payload=None, headers=None, raw=None):
        method = "GET" if payload is None and raw is None else "POST"
        base = {"Content-Type": "application/json", "X-Review-Token": self.server.token}
        if headers:
            base.update(headers)
        body = raw if raw is not None else json.dumps(payload) if payload is not None else None
        with closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as connection:
            connection.request(method, path, body=body, headers=base)
            response = connection.getresponse()
            data, meta = response.read(), dict(response.getheaders())
            if "application/json" in meta.get("Content-Type", ""):
                data = json.loads(data)
            return response.status, data, meta

    def wait(self, session):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            record = self.service.get(session)
            if record["job_status"] not in ("running", "queued"):
                self.assertNotEqual(record["job_status"], "error", record["error"])
                return record
            time.sleep(.01)
        self.fail("Background workflow did not reach a review gate")

    def create(self, goal="Calculate 6 * 7; Convert 5 km to m", offline=True):
        status, record, _ = self.request("/api/sessions", {"goal": goal, "offline": offline})
        self.assertEqual(status, 202, record)
        return self.wait(record["id"])

    def decision(self, record, action="approve", **extra):
        return {"request_id": uuid4().hex, "decision": {
            "review_id": record["snapshot"]["review"]["review_id"], "action": action, **extra}}

    def decide(self, record, action="approve", **extra):
        status, data, _ = self.request(f"/api/sessions/{record['id']}/review", self.decision(record, action, **extra))
        self.assertEqual(status, 202, data)
        return self.wait(record["id"])

    def test_bootstrap_and_static_assets(self):
        code, data, headers = self.request("/api/bootstrap")
        self.assertEqual((code, data["version"], data["token"]), (200, v17.VERSION, self.server.token))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        for path in ("/", "/app.js", "/style.css"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 200)

    def test_no_execution_before_plan_approval(self):
        record = self.create()
        self.assertEqual(record["snapshot"]["state"]["executions"], 0)
        self.assertEqual(record["snapshot"]["review"]["gate"], "plan_review")

    def test_three_approvals_complete_and_export(self):
        record = self.create()
        for stage in ("content_review", "final_review", None):
            record = self.decide(record)
            review = record["snapshot"]["review"]
            self.assertEqual(review["gate"] if review else None, stage)
        state = record["snapshot"]["state"]
        self.assertEqual(record["job_status"], "approved")
        self.assertEqual(state["executions"], 2)
        self.assertIn("42", state["results"]["task1"]["content"])
        self.assertEqual(len(state["approvals"]), 3)
        code, exported, headers = self.request(f"/api/sessions/{record['id']}/export")
        self.assertEqual(code, 200)
        self.assertEqual(exported, record)
        self.assertIn("attachment;", headers["Content-Disposition"])

    def test_revision_corrects_failure_and_returns_to_plan_gate(self):
        record = self.decide(self.create("Calculate 1 / 0"))
        self.assertEqual(record["snapshot"]["state"]["results"]["task1"]["status"], "failed")
        plan = copy.deepcopy(record["snapshot"]["state"]["plan"])
        plan["tasks"][0]["arguments"] = {"expression": "1 / 2"}
        record = self.decide(record, "revise", note="Correct zero denominator", plan=plan)
        self.assertEqual(record["snapshot"]["review"]["gate"], "plan_review")
        self.assertEqual(record["snapshot"]["state"]["results"], {})
        self.assertEqual(record["snapshot"]["state"]["approvals"], {})
        record = self.decide(record)
        self.assertIn("0.5", record["snapshot"]["state"]["results"]["task1"]["content"])
        self.assertEqual(record["snapshot"]["state"]["executions"], 2)

    def test_failed_result_cannot_be_approved_as_content(self):
        record = self.decide(self.create("Calculate 1 / 0"))
        record = self.decide(record)
        self.assertEqual(record["job_status"], "awaiting_review")
        self.assertEqual(record["snapshot"]["review"]["gate"], "content_review")
        self.assertNotIn("content_review", record["snapshot"]["state"]["approvals"])

    def test_rejection_is_terminal_without_tool_execution(self):
        record = self.decide(self.create(), "reject", note="Wrong goal")
        self.assertEqual(record["job_status"], "rejected")
        self.assertEqual(record["snapshot"]["state"]["executions"], 0)

    def test_duplicate_request_does_not_repeat_tools(self):
        record = self.create()
        payload = self.decision(record)
        route = f"/api/sessions/{record['id']}/review"
        self.assertEqual(self.request(route, payload)[0], 202)
        first = self.wait(record["id"])
        self.assertEqual(self.request(route, payload)[0], 202)
        second = self.service.get(record["id"])
        self.assertEqual(second["snapshot"], first["snapshot"])
        self.assertEqual(second["snapshot"]["state"]["executions"], 2)

    def test_request_id_cannot_be_reused_for_different_decision(self):
        record = self.create()
        payload = self.decision(record)
        route = f"/api/sessions/{record['id']}/review"
        self.assertEqual(self.request(route, payload)[0], 202)
        self.wait(record["id"])
        payload["decision"].update(action="reject", note="Different action")
        self.assertEqual(self.request(route, payload)[0], 409)

    def test_stale_gate_is_rejected(self):
        old = self.create()
        record = self.decide(old)
        status, _, _ = self.request(f"/api/sessions/{record['id']}/review", self.decision(old))
        self.assertEqual(status, 409)

    def test_terminal_session_cannot_be_reviewed(self):
        record = self.create()
        payload = self.decision(record)
        record = self.decide(record, "reject", note="Stop")
        self.assertEqual(self.request(f"/api/sessions/{record['id']}/review", payload)[0], 409)

    def test_refresh_and_list_do_not_execute_tools(self):
        record = self.decide(self.create())
        for _ in range(3):
            code, read, _ = self.request(f"/api/sessions/{record['id']}")
            self.assertEqual((code, read["snapshot"]["state"]["executions"]), (200, 2))
        code, items, _ = self.request("/api/sessions")
        self.assertEqual((code, items[0]["id"]), (200, record["id"]))

    def test_service_restart_preserves_review_without_reexecuting_tools(self):
        record = self.decide(self.create())
        self.service.close()
        replacement = v17.SessionService(self.directory.name, corpus())
        self.service = self.server.service = replacement
        restored = self.service.get(record["id"])
        self.assertEqual(restored, record)
        restored = self.decide(restored)
        self.assertEqual(restored["snapshot"]["review"]["gate"], "final_review")
        self.assertEqual(restored["snapshot"]["state"]["executions"], 2)

    def test_recovery_inspects_native_checkpoint_without_executing(self):
        record = self.decide(self.create())
        with self.service.lock:
            self.service.records[record["id"]]["job_status"] = "error"
            self.service.records[record["id"]]["snapshot"] = None
        code, restored, _ = self.request(f"/api/sessions/{record['id']}/recover", {})
        self.assertEqual(code, 200)
        self.assertEqual(restored["snapshot"], record["snapshot"])

    def test_restart_marks_unfinished_jobs_for_inspection(self):
        record = self.create()
        self.service.close()
        record["job_status"] = "running"
        self.service._save(record)
        self.service = self.server.service = v17.SessionService(self.directory.name, corpus())
        self.assertEqual(self.service.get(record["id"])["job_status"], "recovery_required")
        self.assertEqual(self.request(f"/api/sessions/{record['id']}/recover", {})[0], 200)

    def test_corpus_change_blocks_resume(self):
        record = self.create()
        self.service.chunks = []
        status, _, _ = self.request(f"/api/sessions/{record['id']}/review", self.decision(record))
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 5
        while self.service.get(record["id"])["job_status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(self.service.get(record["id"])["job_status"], "error")
        self.assertEqual(self.request(f"/api/sessions/{record['id']}/recover", {})[0], 409)

    def test_unknown_session_and_path(self):
        self.assertEqual(self.request(f"/api/sessions/{uuid4().hex}")[0], 404)
        for path in ("/../study_guide_v17_app.py", "/v17_data/sessions.sqlite", "/api/unknown"):
            self.assertEqual(self.request(path)[0], 404)

    def test_cross_origin_write_rejected(self):
        code, _, _ = self.request("/api/sessions", {"goal": "Calculate 1+1", "offline": True}, {"Origin": "https://other.example"})
        self.assertEqual(code, 403)
        self.assertEqual(self.service.list_sessions(), [])

    def test_missing_write_token_rejected(self):
        self.assertEqual(self.request("/api/sessions", {}, {"X-Review-Token": ""})[0], 403)

    def test_unexpected_host_rejected(self):
        self.assertEqual(self.request("/api/bootstrap", headers={"Host": "other.example"})[0], 403)

    def test_json_shape_size_and_content_type(self):
        for raw in ("{", "[]", '{"goal":NaN,"offline":true}'):
            self.assertEqual(self.request("/api/sessions", raw=raw)[0], 400)
        self.assertEqual(self.request("/api/sessions", raw="x" * (v17.MAX_BODY + 1))[0], 413)
        self.assertEqual(self.request("/api/sessions", {}, {"Content-Type": "text/plain"})[0], 415)

    def test_invalid_creation_and_revision_payloads(self):
        for payload in ({}, {"goal": " ", "offline": True}, {"goal": "x", "offline": 1}, {"goal": "x" * 2001, "offline": True}):
            self.assertEqual(self.request("/api/sessions", payload)[0], 400)
        record = self.create()
        route = f"/api/sessions/{record['id']}/review"
        for payload in ({}, self.decision(record, "reject"), self.decision(record, "revise", note="Fix", plan={"tasks": []})):
            self.assertEqual(self.request(route, payload)[0], 400)

    def test_model_planning_is_background_and_only_runs_once(self):
        entered, release = threading.Event(), threading.Event()
        class Model:
            calls = 0
            def with_structured_output(inner, schema):
                return inner
            def invoke(inner, messages):
                inner.calls += 1
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Test model was not released")
                return v17.v16.v14.deterministic_plan("Calculate 6*7")
        model = Model()
        self.service.model_factory = lambda: model
        try:
            code, pending, _ = self.request("/api/sessions", {"goal": "Calculate 6*7", "offline": False})
            self.assertEqual(code, 202)
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.request("/api/sessions")[0], 200)
            self.assertIn(self.service.get(pending["id"])["job_status"], ("running", "queued"))
        finally:
            release.set()
        record = self.wait(pending["id"])
        for _ in range(3):
            record = self.decide(record)
        self.assertEqual(model.calls, 1)

    def test_trusted_search_references_survive_api_serialization(self):
        record = self.decide(self.create("Explain conservation of energy"))
        state = record["snapshot"]["state"]
        self.assertIn("[S1]", state["results"]["task1"]["content"])
        self.assertTrue(v17.v16.v15.citation_integrity(state)["passed"])

    def test_offline_session_never_constructs_model(self):
        self.service.model_factory = lambda: self.fail("Offline workflow constructed a model")
        self.assertEqual(self.create()["job_status"], "awaiting_review")

    def test_database_connections_release_file_on_close(self):
        self.create()
        self.service.close()
        database = self.service.database
        renamed = database.with_suffix(".renamed")
        database.rename(renamed)
        renamed.rename(database)
        with closing(sqlite3.connect(database)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
