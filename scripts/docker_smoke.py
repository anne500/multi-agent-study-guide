"""Exercise the V17 Docker API and resume a saved review after replacement.

Uses a uniquely named fixture container and volume. Only those test resources
are removed. The host Python interpreter needs no third-party packages.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class API:
    def __init__(self, base_url, timeout=30):
        self.base_url = base_url
        self.timeout = timeout
        self.token = None

    def request(self, path, payload=None, expected=200):
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers.update({"Content-Type": "application/json", "X-Review-Token": self.token,
                            "Origin": self.base_url})
        request = Request(self.base_url + path, data=data, headers=headers)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            code = response.code
            body = json.loads(response.read())
            require(code == expected, f"{request.get_method()} {path}: expected {expected}, got {code}: {body}")
            return body, dict(response.headers)

    def bootstrap(self):
        body, _ = self.request("/api/bootstrap")
        require(body["version"].startswith("v17."), "Unexpected application version")
        self.token = body["token"]

    def get(self, session):
        return self.request(f"/api/sessions/{session}")[0]

    def wait(self, session):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            record = self.get(session)
            if record["job_status"] not in ("queued", "running"):
                require(record["job_status"] != "error", f"Workflow failed: {record['error']}")
                return record
            time.sleep(.1)
        raise RuntimeError(f"Session {session} did not reach a review gate within {self.timeout}s")

    def approve(self, record):
        payload = {"request_id": uuid4().hex, "decision": {
            "action": "approve", "review_id": record["snapshot"]["review"]["review_id"]}}
        self.request(f"/api/sessions/{record['id']}/review", payload, 202)
        return self.wait(record["id"]), payload


def exercise_review(api, replace_container):
    """Real HTTP scenario; replacement callback owns the container lifecycle."""
    api.bootstrap()
    page = urlopen(api.base_url + "/", timeout=10)
    with page:
        require(page.status == 200 and b"Review Studio" in page.read(), "Browser asset is unavailable")
    record, _ = api.request("/api/sessions", {
        "goal": "Explain conservation of energy; Calculate (12 + 8) * 3; Convert 5 km to m",
        "offline": True,
    }, 202)
    record = api.wait(record["id"])
    require(record["snapshot"]["review"]["gate"] == "plan_review", "Missing initial plan gate")
    require(record["snapshot"]["state"]["executions"] == 0, "Tools ran before plan approval")
    record, decision = api.approve(record)
    state = record["snapshot"]["state"]
    require(record["snapshot"]["review"]["gate"] == "content_review", "Missing content gate")
    require(state["executions"] == 3 and len(state["results"]) == 3, "Unexpected execution count")
    require(all(r["status"] == "completed" for r in state["results"].values()), "A specialist failed")
    require("60 [T2]" in state["results"]["task2"]["content"], "Calculator result mismatch")
    require("5000 m [T3]" in state["results"]["task3"]["content"], "Conversion result mismatch")
    require(state["sources"] and "[S1]" in state["results"]["task1"]["content"],
            "Trusted corpus evidence is missing")
    require(record["snapshot"]["metrics"]["model_attempts"] == 0, "Offline run attempted a model")

    # Retrying an accepted request must not advance a second gate or repeat tools.
    api.request(f"/api/sessions/{record['id']}/review", decision, 202)
    require(api.get(record["id"])["snapshot"] == record["snapshot"], "Duplicate approval changed state")
    before = record["snapshot"]
    previous_token = api.token
    replacement = replace_container()
    api.bootstrap()
    require(api.token != previous_token, "Server token did not change after replacement")
    record = api.get(record["id"])
    require(record["snapshot"] == before, "Saved pending review changed across replacement")
    require(record["snapshot"]["review"]["gate"] == "content_review", "Pending gate was lost")

    stale = {"request_id": uuid4().hex, "decision": decision["decision"]}
    api.request(f"/api/sessions/{record['id']}/review", stale, 409)
    record, _ = api.approve(record)
    require(record["snapshot"]["review"]["gate"] == "final_review", "Content approval did not resume")
    record, _ = api.approve(record)
    final = record["snapshot"]
    require(record["job_status"] == "approved" and final["review"] is None, "Final approval failed")
    require(final["state"]["executions"] == 3 and len(final["state"]["approvals"]) == 3,
            "Resume repeated tools or lost approvals")
    exported, headers = api.request(f"/api/sessions/{record['id']}/export")
    require(exported["snapshot"] == final, "Export changed the approved state")
    require("attachment" in headers.get("Content-Disposition", ""), "Export is not a download")
    return {"session_id": record["id"], "status": record["job_status"], "tool_executions": 3,
            "model_attempts": final["metrics"]["model_attempts"], "approvals": 3,
            "pending_snapshot_unchanged": True, "stale_decision_rejected": True,
            "duplicate_decision_preserved_state": True, "replacement": replacement}


class DockerFixture:
    def __init__(self, image, port, timeout):
        self.image, self.port, self.timeout = image, port, timeout
        self.name = "study-guide-ci-" + uuid4().hex[:12]
        self.volume = self.name + "-data"
        self.container_id = None

    def docker(self, *args, check=True):
        result = subprocess.run(["docker", *args], capture_output=True, text=True,
                                timeout=120, check=False)
        if check and result.returncode:
            raise RuntimeError(f"docker {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
        if args[0] == "logs":
            return (result.stdout + result.stderr).strip()
        return result.stdout.strip()

    def start(self):
        args = ["run", "-d", "--name", self.name, "--publish", f"127.0.0.1:{self.port}:{self.port}",
                "--mount", f"type=volume,source={self.volume},target=/data",
                "--health-interval", "1s", "--health-timeout", "5s", "--health-retries", "30"]
        if self.port != 8000:
            # Keep Host/Origin checks and the health probe aligned with the
            # overridden listening port for local tests beside the main app.
            probe = ("python -c \"import urllib.request; "
                     f"urllib.request.urlopen('http://127.0.0.1:{self.port}/api/bootstrap', timeout=3).close()\"")
            args += ["--health-cmd", probe]
        args.append(self.image)
        if self.port != 8000:
            args += ["python", "study_guide_v17_app.py", "--host", "0.0.0.0", "--port", str(self.port)]
        self.container_id = self.docker(*args)
        self.wait_healthy()

    def wait_healthy(self):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            state = json.loads(self.docker("inspect", "--format", "{{json .State}}", self.name))
            require(state["Running"], f"Container exited: {state}")
            health = state.get("Health", {}).get("Status")
            if health == "healthy":
                return
            require(health != "unhealthy", f"Container is unhealthy: {state.get('Health')}")
            time.sleep(1)
        raise RuntimeError(f"Container did not become healthy within {self.timeout}s")

    def replace(self):
        original = self.container_id
        self.docker("stop", "--time", "10", self.name)
        self.docker("rm", self.name)
        self.start()
        require(original != self.container_id, "Container ID did not change")
        mounts = json.loads(self.docker("inspect", "--format", "{{json .Mounts}}", self.name))
        require(any(m.get("Name") == self.volume and m["Destination"] == "/data" for m in mounts),
                "Replacement did not retain the test volume")
        return {"container_changed": True, "volume_retained": True, "health": "healthy"}

    def cleanup(self):
        print("Fixture container logs:", flush=True)
        print(self.docker("logs", "--tail", "100", self.name, check=False), flush=True)
        self.docker("rm", "--force", self.name, check=False)
        self.docker("volume", "rm", self.volume, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="study-guide:ci")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    require(1 <= args.port <= 65535 and args.timeout > 0, "Invalid port or timeout")
    require(shutil.which("docker") is not None, "Docker CLI is not installed or not on PATH")
    fixture = DockerFixture(args.image, args.port, args.timeout)
    try:
        fixture.docker("volume", "create", fixture.volume)
        fixture.start()
        report = exercise_review(API(f"http://127.0.0.1:{args.port}"), fixture.replace)
        print(json.dumps(report, indent=2), flush=True)
        destination = os.environ.get("GITHUB_STEP_SUMMARY")
        if destination:
            with Path(destination).open("a", encoding="utf-8") as stream:
                stream.write("Docker smoke test passed.\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n")
    finally:
        fixture.cleanup()


if __name__ == "__main__":
    main()
