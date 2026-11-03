# V17: Local application, API, and deployment

V17 adds Review Studio, a browser interface and asynchronous JSON API around the V16 workflow. It preserves the V12 trusted corpus, V13 bounded tools, V14 task schemas, V15 metrics, and V16 native LangGraph review checkpoints. Earlier example files remain separate.

## Run

Use a current checkout or the published source archive. Install the release baseline into the virtual environment before the first run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-v17.lock
.\.venv\Scripts\python.exe -m pip check
```

Then run the V17 tests and application:

```powershell
.\.venv\Scripts\python.exe .\test_v17_app.py
.\.venv\Scripts\python.exe .\study_guide_v17_app.py
```

Open http://127.0.0.1:8000. Keep the terminal running. There is no frontend build or additional package. Change the port with `--port 8001`; use the matching printed URL.

Offline planning is selected initially. Clear the checkbox to use Ollama at http://127.0.0.1:11434 with qwen3.5:4b. Set OLLAMA_BASE_URL before starting the service to use a different Ollama address. Model calls run in a background worker, so the API can respond while planning is pending. A model failure can trigger V14's deterministic fallback; inspect trace and events to distinguish an accepted model plan from fallback.

## Browser workflow

Create a session with up to four requests separated by semicolons. Review the selected agents and their arguments. Approving the plan permits tool execution. Content review shows each original task request, current task arguments, result, and reference labels. Final review adds evidence questions. These questions are prompts for the human reviewer, not scored quizzes.

Approve advances one gate. Revise opens a complete JSON plan editor and requires a reason. V16 validates the replacement plan, invalidates affected results and all approvals, and returns to plan review. Unchanged successful tasks can retain their results. The original instruction is preserved as context; current arguments determine the approved task label. Reject ends the session and records the reason. Failed or uncited content cannot pass content approval.

Leave workspace closes the current view. The gate is already saved; no special pause mutation is needed. Reopen from the sidebar to continue. Refreshing the page or reading a session never invokes the workflow. One process owns the database; run one V17 server per data directory. A single worker serializes all session mutations, with at most 16 queued/running jobs, so a slow model job can delay another session's approval.

Session activity reports completed tasks, tool attempts, model attempts, and revisions. The details panel contains the plan, approvals, audit, and trace. Phase timings describe observed processing segments and can overlap; they do not measure time spent waiting for human review. Reference-ID integrity does not establish semantic entailment or factual coverage.

## API

All responses use JSON except the three static assets. Session IDs and request IDs are 32 lowercase hexadecimal characters. A snapshot contains the V16 state, current review payload, and V15 metrics. State and error text may include user content or local paths.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | /api/bootstrap | V17 version and process-local write token |
| GET | /api/sessions | Saved session summaries, newest update first |
| POST | /api/sessions | Queue a new session; body has goal and offline |
| GET | /api/sessions/{id} | Latest saved view and job status; no execution |
| POST | /api/sessions/{id}/review | Queue a decision for the current review ID |
| POST | /api/sessions/{id}/recover | Inspect a failed/interrupted session's checkpoint; body is an empty object |
| GET | /api/sessions/{id}/export | Download the local session record as JSON |

Creation and review return 202 after queuing, not after workflow completion. Poll GET for awaiting_review, approved, rejected, or error. Unknown sessions return 404, malformed input 400, stale/conflicting decisions 409, oversized bodies 413, unsupported content type 415, and a full queue 429. Review IDs identify exact gates. Each review submission supplies a request_id; retrying the identical payload with that ID returns the recorded session without another resume. Reusing that ID with another decision returns 409. Creation has no idempotency key: inspect the session list after a lost creation response before creating another session.

An example API session from a separate PowerShell terminal:

```powershell
$base = "http://127.0.0.1:8000"
$bootstrap = Invoke-RestMethod "$base/api/bootstrap"
$headers = @{ "X-Review-Token" = $bootstrap.token }
$body = @{ goal = "Calculate 6 * 7"; offline = $true } | ConvertTo-Json
$created = Invoke-RestMethod "$base/api/sessions" `
  -Method Post -Headers $headers -ContentType "application/json" -Body $body

# Repeat this GET until job_status is awaiting_review.
$session = Invoke-RestMethod "$base/api/sessions/$($created.id)"
$session.job_status

# Inspect the plan before sending approval.
$session.snapshot.state.plan | ConvertTo-Json -Depth 10
$decision = @{
  request_id = [guid]::NewGuid().ToString("N")
  decision = @{
    review_id = $session.snapshot.review.review_id
    action = "approve"
  }
} | ConvertTo-Json -Depth 10
Invoke-RestMethod "$base/api/sessions/$($created.id)/review" `
  -Method Post -Headers $headers -ContentType "application/json" -Body $decision
```

Refresh the bootstrap token after restarting the service. Browser POST requests must have an allowed local Origin and the X-Review-Token header. The token helps prevent cross-site writes; it is not a user login. Host headers are restricted to localhost or 127.0.0.1 with the listening port. The service serves only the explicit HTML, JS, and CSS assets; it does not expose arbitrary project files or its SQLite file. JSON input is bounded to 64 KiB. All user and model content in the interface is rendered as text.

## Persistence and recovery

The default directory is v17_data alongside the application. Set V17_DATA_DIR before starting to choose another directory. sessions.sqlite contains native LangGraph checkpoints and a web_sessions metadata table. It is independent of V16's CLI database; there is no automatic import or migration of earlier sessions.

Add `v17_data/` to .gitignore before creating sessions. The directory includes generated state, goals, review notes, sources, local paths, and database sidecar files. Git tracks the code and trusted reference documents. Keep local session history through an intentional backup or JSON export. Exports are read-only records; V17 does not import them as runnable sessions. Exporting does not modify learner memory.

After a process stops during a queued/running job, startup marks that session recovery_required. Inspect saved checkpoint restores only a completed review gate or terminal snapshot, without executing workflow nodes. If no checkpoint exists, create a new session. If the checkpoint stopped outside a review gate, V17 refuses automatic execution replay. Corpus/version validation blocks incompatible resumes. An error during recovery leaves the session available for inspection/export. There is no exactly-once execution guarantee across abrupt process failure during a tool operation.

Stop the service before copying the entire data directory for backup. Preserve the SQLite database and any sidecars together. Do not copy a live database file alone or edit checkpoint tables manually. This app does not automatically save generated material into trusted documents or update learner memory.

## Verified local Docker deployment

The original recipe was built and runtime-verified on the Windows laptop using Docker Desktop 4.17.0 and Docker Engine 20.10.23 with Linux/amd64 containers. That first build completed in about 61.9 seconds. The later release baseline pins both the Python image digest and 43 package versions; it rebuilt successfully on the laptop in 24.4 seconds and passed the container persistence smoke test. It also passed the hosted release verification. These timings record different individual builds, not comparable performance benchmarks. The recorded older engine is not a recommendation to retain that release. The authoring environment did not run Docker.

Start Docker Desktop and confirm docker version shows both Client and Server. Use Linux containers. Stop the direct Python web server before using the same host port. From the existing repository:

```powershell
docker build -f Dockerfile.v17 -t study-guide:v17 .
docker run -d --name study-guide-v17 `
  -p 127.0.0.1:8000:8000 `
  --mount type=volume,source=study-guide-v17-data,target=/data `
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 `
  study-guide:v17
```

The service runs in the background. Keep Docker Desktop running. Check readiness:

```powershell
docker ps --filter "name=study-guide-v17"
docker inspect --format '{{.State.Health.Status}}' study-guide-v17
docker logs --tail 30 study-guide-v17
```

The health check runs every 30 seconds. A new container can initially report starting; wait for healthy before testing. Open http://127.0.0.1:8000, reload the page, and click New session. The named volume has its own session history and does not automatically contain the direct Python server's sessions. Repeat the offline calculation/conversion workflow and inspect both results before completing the three approvals.

The Dockerfile specifies the non-root appuser (UID 10001), explicitly copies the required version modules, assets, and trusted documents, and stores sessions in the named volume. Existing dependency ranges are used rather than a lockfile. Model weights are not included.

Dockerfile.v17.dockerignore declares build-specific exclusion rules. The recorded older builder reported a 2-byte .dockerignore transfer, so enforcement of the build-specific ignore file was not established by this test. The explicit COPY instructions determine the files included in the image; successful runtime verification does not establish build-context isolation. Review ignore-file behavior separately before using a build context containing sensitive material.

The run command configures the container to reach the host's Ollama through host.docker.internal. This path was verified on the laptop without changing the host Ollama binding. Probe it before starting a model session:

```powershell
docker exec study-guide-v17 python -c "import json,urllib.request; r=urllib.request.urlopen('http://host.docker.internal:11434/api/tags',timeout=10); print([m['name'] for m in json.load(r)['models']])"
```

The verified response included qwen3.5:4b. This checks model availability without running inference. In the browser, create a new conversion session with Offline planning unchecked, approve each gate after inspection, and export JSON. Check snapshot.state.events for model_plan and the accepted attempt, and metrics for deterministic_plan_rounds. A correct tool result alone does not prove that the model plan was accepted. Host firewall and binding requirements can differ on another machine.

The application binds to 0.0.0.0 inside the container, with the host port bound to 127.0.0.1. Keep the same host/container port because allowed Host and Origin values use the service's listening port. The Host allowlist restricts accepted HTTP Host values; it is not authentication. LAN isolation was not tested. Docker's port-publishing documentation notes that releases before 28.0.0 can expose loopback-published ports to peers on the same network segment; the recorded engine predates that fix. Do not treat this functional test as proof of network isolation.

The recipe does not implement public hosting, HTTPS, authentication, multi-user isolation, multiple workers, or production supervision. Those require a separate deployment design. The Python standard-library server is intended for this local, single-user project.

### Verify retention across container replacement

Use a completed session while no workflow operation is running. In one PowerShell window, capture its current view and the current container ID. The verified session ID below is specific to the recorded run; replace it with a session from your own volume when repeating this check.

```powershell
$v17Url = "http://127.0.0.1:8000/api/sessions/382dd7d5a50b4b2094aab903dacc7664"
$v17Before = Invoke-RestMethod $v17Url -ErrorAction Stop
$v17OldContainer = docker inspect --format '{{.Id}}' study-guide-v17

docker stop study-guide-v17
docker rm study-guide-v17

docker run -d --name study-guide-v17 `
  -p 127.0.0.1:8000:8000 `
  --mount type=volume,source=study-guide-v17-data,target=/data `
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 `
  study-guide:v17
```

Keep this PowerShell window open so the captured variables remain available. Wait until docker inspect reports healthy, then compare:

```powershell
$v17After = Invoke-RestMethod $v17Url -ErrorAction Stop
$v17NewContainer = docker inspect --format '{{.Id}}' study-guide-v17

[PSCustomObject]@{
    ContainerReplaced = ($v17OldContainer -ne $v17NewContainer)
    Status = $v17After.job_status
    ToolExecutions = $v17After.snapshot.state.executions
    Approvals = @($v17After.snapshot.state.approvals.PSObject.Properties).Count
    SnapshotUnchanged = (
        ($v17Before.snapshot | ConvertTo-Json -Depth 100 -Compress) -eq
        ($v17After.snapshot | ConvertTo-Json -Depth 100 -Compress)
    )
}
```

The recorded result was ContainerReplaced=True, Status=approved, ToolExecutions=1, Approvals=3, and SnapshotUnchanged=True. The container ID changed from 4cf9517d8efe to 102d7f87fd78 while the same study-guide-v17-data volume remained mounted at /data. Reload the browser after replacement to obtain a new write token.

This proves retention of the completed session across removal and recreation. It does not prove manually resumed pending-gate behavior inside Docker or recovery after interruption midway through a tool. Automated API tests cover gate resume and service restart separately. The later Docker smoke test also verifies pending-gate resume across actual container replacement, as described below. Removing the named volume would remove that persisted history; retain it when replacing the container.

References for the recipe:

- [Docker Desktop networking how-tos](https://docs.docker.com/desktop/features/networking/networking-how-tos/)
- [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/)
- [Docker build context and ignore files](https://docs.docker.com/build/concepts/context/#dockerignore-files)
- [Ollama configuration FAQ](https://docs.ollama.com/faq)
- [Ollama model-list API](https://docs.ollama.com/api/tags)
- [Docker volumes and their lifecycle](https://docs.docker.com/engine/storage/volumes/)

## Verification

The initial V17 suite passes 25 tests using real loopback HTTP requests, native SQLite checkpoints, synthetic local trusted text, and a scripted model. It covers all three approvals, revision, rejection, incomplete-content blocking, stale IDs, duplicate decisions, record persistence, recovery inspection, corpus mismatch, API validation, origin/token/host checks, static asset routing, export, background model planning, offline operation, reference integrity, and connection cleanup. The existing 90 V14-V16 tests also pass. Python compilation and JavaScript syntax checks pass.

A separate service smoke test loaded the actual two published trusted documents (14 chunks), completed the three-task conservation/calculation/conversion goal through all three approvals, used three tool executions, and passed reference-ID integrity checks with three retrieved sources.

Windows browser screenshots now verify the offline calculation/conversion session reaching approved with two executions, and a fresh correction session reaching approved at revision 1 with `1 / 2 = 0.5 [T2]` and two cumulative executions. The initial correction session exhausted its revision limit while retaining the zero denominator and was rejected. These are manual browser checks; automated browser interaction tests were not run. The authoring managed-preview environment could not launch Python, while the separate local service and HTTP integration tests ran successfully.

The exported live-model session `3262c50a54284b5aa3b9bb03aeebc730` verifies Ollama planning with offline=false. Its first model response raised OutputParserException and recorded plan_retry. The second attempt recorded model_plan, with one accepted plan and zero deterministic planning rounds. The converter returned `5 km = 5000 m [T1]` in one tool execution. The final record has all three human approvals, revision 0, approved status, no pending review, and no session error.

Planning duration was 526872.357 ms, about 8 minutes 47 seconds. The first model call took 161803.512 ms and the second 365038.602 ms. Their sum is nested inside planning and must not be added to it. The observed specialist phase took 6.273 ms. These phase timings exclude human review and do not establish representative latency or per-tool performance.

Report model acceptance using the explicit counts: one accepted plan from two model attempts, with one retry and no fallback. The inherited model_plan_acceptance_rate field is round-based: accepted model plans divided by accepted-model plus deterministic planning rounds. Its value of 1.0 in this export does not mean both attempts succeeded. The per-attempt acceptance fraction for this run is 1/2. Read events and counts alongside the ratio.

All 25 V17 tests passed on Windows in 3.849 seconds. Those are host-run tests; they were not run inside the container image. Docker deployment was verified separately through the build log, healthy status, manual browser execution, container-to-host Ollama probe, live session export, and before/after API snapshot comparison across container replacement.

The Docker-hosted model session `382dd7d5a50b4b2094aab903dacc7664` accepted model attempt 2 after an OutputParserException on attempt 1. It recorded zero deterministic planning rounds and returned `5 km = 5000 m [T1]` with one execution, revision 0, all three approvals, approved status, and no pending review. Planning took 479237.247 ms, about 7 minutes 59 seconds; the specialist phase took 6.726 ms. These phase timings exclude human review and are not representative performance benchmarks.

The completed-session snapshot was unchanged after container replacement. Pending-gate resume inside Docker, arbitrary crash recovery, LAN isolation, build-specific ignore enforcement on the older builder, and public deployment were not established by this manual test. The local application and functional local Docker deployment are verified within that scope.

## Final CI and release evidence

The pinned baseline passed all eight offline regression scripts on the Windows laptop in 33.13 seconds. Its Docker build took 24.4 seconds. The actual probe reached approved with three executions, zero model attempts, three approvals, an unchanged pending snapshot, stale-decision rejection, duplicate-decision preservation, a changed container ID, a retained volume, and healthy status.

The [Release V17 workflow](https://github.com/anne500/multi-agent-study-guide/actions/runs/41609663282) passed four Windows/Linux and Python 3.12/3.14 regression jobs, the Docker integration job, and publication at commit `34e0c4005f8de02fd26e13e79f022c6b489ba85e`. The [v17.0.0 release](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0) contains source, dependency pins, release evidence, and SHA-256 checksums. All three asset checksum checks passed during assembly. See [project status](PROJECT_STATUS.md) for the completed scope.

These automated Docker results supplement the earlier manual completed-session comparison. Crash-time exactly-once execution, live model quality, public multi-user hosting, and LAN isolation are outside the verified scope. A later [audit-time browser check](FINAL_AUDIT.md) exercised offline approval, leave/reopen, reload, revision, rejection, and JSON download with no page errors; a maintained browser CI job is still outside the implemented scope.
