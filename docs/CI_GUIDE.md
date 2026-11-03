# Continuous integration

CI protects the implemented V1-V17 project. It does not introduce a V18 workflow or publish an image or website. Regular CI does not publish releases. The separate manual Release V17 workflow calls this CI workflow and publishes v17.0.0 only after all five jobs succeed for its commit.

## Triggers and jobs

The workflow in .github/workflows/ci.yml runs on pushes to main, pull requests targeting main, workflow_dispatch, and workflow_call. It has read-only contents permission. Action revisions are pinned to verified full commit SHAs, and checkout does not persist Git credentials. A newer run on the same ref cancels an older run. Public pull-request code runs with pull_request, not pull_request_target.

| Job | Environment | Verification |
| --- | --- | --- |
| Offline tests | Ubuntu 24.04, Python 3.12 | Compilation and all root regression scripts |
| Offline tests | Ubuntu 24.04, Python 3.14 | Same checks on the laptop's Python minor version |
| Offline tests | Windows 2025, Python 3.12 | Windows file handling and offline regressions |
| Offline tests | Windows 2025, Python 3.14 | Windows and Python minor matching the development environment |
| Docker smoke | Ubuntu 24.04, Python 3.12 host | Image build, configured health probe, real HTTP API, persisted pending review, and resume |

The Docker job starts only after every offline matrix job succeeds. Matrix fail-fast is disabled so one failure does not suppress results from other operating systems or Python versions. Offline jobs have a 15-minute limit; Docker has a 20-minute limit.

## Offline checks

scripts/ci_checks.py compiles study_guide_v*.py, root test_v*.py, and Python files in scripts. It then imports the required clients and SQLite checkpointer to detect missing dependencies before running tests. Client construction is not a model request.

Each root test_v*.py runs in its own subprocess using the selected Python interpreter. This includes test_v10_reviewer_fallback.py, which uses top-level assertions rather than unittest. Independent processes prevent its deliberate reviewer patch from leaking into later suites. Assertions are enabled and each script has a 180-second timeout. Any nonzero exit, compilation failure, missing dependency, or timeout fails the job. The runner fails if it finds no tests.

V11-V17 currently contain 172 unittest cases in total; V10 additionally runs its assertion-based regression script. The runner discovers scripts rather than freezing that count, so adding a root test_v*.py includes it in future runs. Existing tests use synthetic data, scripted model responses, temporary databases, and local HTTP requests. A live Ollama service is not required. Package installation needs network access; this is not an air-gapped build.

From the repository with its requirements installed:

```powershell
.\.venv\Scripts\python.exe scripts/ci_checks.py
```

For the same two phases used by Actions:

```powershell
.\.venv\Scripts\python.exe scripts/ci_checks.py --compile-only
.\.venv\Scripts\python.exe scripts/ci_checks.py --tests-only
```

The workflow installs requirements-v17.lock, which includes the supported direct requirement ranges and pins 43 package versions captured from the first green matrix. It runs pip check, caches pip downloads using both requirement files, and records python --version and pip freeze in logs. requirements.txt remains the deliberate update input. See RELEASE_GUIDE.md for the baseline scope and update procedure.

## Docker smoke scenario

The Docker job builds Dockerfile.v17 with the Python base digest captured from the first green Docker job. The host probe uses Python's standard library and the Docker CLI; it does not install project packages on the host. The image installs requirements-v17.lock and runs pip check. Dockerfile.v17.dockerignore includes both requirement files.

scripts/docker_smoke.py creates a fixture named study-guide-ci followed by a random identifier, with a similarly unique named volume mounted at /data. It does not use study-guide-v17 or study-guide-v17-data. Its finally block attempts to print container logs and remove only its fixture container and volume on success or failure. A forcibly cancelled job may prevent finally from finishing; hosted runner resources are ephemeral, while a locally interrupted run may leave uniquely named test resources to inspect.

The probe uses the actual HTTP API to:

1. Read bootstrap and static HTML.
2. Create an offline compound goal covering trusted research, arithmetic, and unit conversion.
3. Confirm plan review is pending and tool executions are zero.
4. Approve the plan, verify the three completed results and source references, and pause at content review.
5. Replay the accepted approval with the same request ID and verify the state is unchanged.
6. Replace the container using the same fixture volume, require a new container ID and healthy state, and obtain the replacement server's token.
7. Compare the complete pending snapshot and gate across replacement.
8. Reject a stale review decision, resume content review, then complete final approval.
9. Confirm three approvals and exactly three cumulative tool executions, with no model attempts.
10. Check that JSON export matches the final approved snapshot and uses a download response.

The default probe uses port 8000 and the Dockerfile's original command and health-probe command. It shortens the health-check interval to one second for CI. Readiness has a bounded wait. Use a different port to run locally beside the normal application; the probe then overrides the container listening port and health URL together to keep V17's Host/Origin checks consistent.

```powershell
docker build -f Dockerfile.v17 -t study-guide:v17 .
.\.venv\Scripts\python.exe scripts/docker_smoke.py --image study-guide:v17 --port 8001
```

If the existing study-guide:v17 image matches current application source, the probe can use it directly. Choose a free port. For direct parity with the hosted job, build with tag study-guide:ci and run the probe without --image or --port, with host port 8000 available.

Successful output is a JSON report with approved status, three executions, three approvals, zero model attempts, pending_snapshot_unchanged=true, stale_decision_rejected=true, and container_changed/volume_retained/health evidence. This is API integration coverage, not browser automation, model-quality evaluation, LAN isolation testing, or crash-time exactly-once proof. The live Ollama runtime evidence remains documented separately in V17_GUIDE.md.

## First hosted run

After committing and pushing the new files, open [the CI workflow](https://github.com/anne500/multi-agent-study-guide/actions/workflows/ci.yml). Confirm all four matrix combinations and the Docker job complete successfully. The README badge reflects GitHub's actual status; it does not establish that a run has succeeded before the workflow is committed.

Inspect the first failing step and its logs before rerunning. Dependency failures appear in Install dependencies; test failures name the script being run; Docker failures include the API assertion or readiness error and container logs. If GitHub Actions is disabled for the repository, enable it under repository settings before expecting push-triggered execution. No secrets, registry login, model download, or cloud model key are configured by this workflow.

## Validation status

Workflow YAML, action inputs and pinned revisions, and Python syntax were checked in the authoring environment. On Linux with Python 3.12.14, all eight regression scripts passed in about 5.93 seconds: 172 unittest cases plus V10's assertion-based fallback script. A fresh task virtual environment installed the existing requirement ranges; no project requirement file changed. The authoring host additionally needed HTTPX's optional SOCKS dependency for its ambient proxy configuration. That environment-specific addition is not part of the workflow's dependency requirements.

The smoke scenario passed against the real V17 HTTP API and native SQLite checkpoints with service replacement standing in for container replacement. It retained the pending snapshot, refreshed the server token, rejected a stale decision, resumed review, and reached approved with three executions, three approvals, and zero model attempts. That verifies the probe's API logic; it is not evidence that Docker commands ran here. Docker is unavailable in the authoring environment. The [first hosted run](https://github.com/anne500/multi-agent-study-guide/actions/runs/41578448362) subsequently passed all five jobs at commit 01c1b245549d09c24c82de5ccda1283cf8ec8316. All eight scripts passed in each environment: Ubuntu/Python 3.12 in 6.78 seconds, Ubuntu/3.14 in 7.58 seconds, Windows/3.12 in 14.56 seconds, and Windows/3.14 in 19.71 seconds. The actual Docker job reached approved with three executions and approvals, zero model attempts, unchanged pending state, stale-decision rejection, duplicate-decision preservation, a replaced container, a retained volume, and healthy status. The newly pinned baseline and release workflow require their own hosted verification after being pushed.

References:

- [GitHub Python CI guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [Checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1)
- [Setup Python v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0)
