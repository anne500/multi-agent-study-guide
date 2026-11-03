# Verify the completed CI baseline

CI is installed and verified. The [v17.0.0 release run](https://github.com/anne500/multi-agent-study-guide/actions/runs/41609663282) passed the four offline matrix jobs, Docker persistence checks, and publication at commit `34e0c40`. This guide uses the current repository; the earlier CI starter ZIP was a one-time installation handoff.

From the repository, install the exact package baseline and run the checks:

```powershell
python -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements-v17.lock
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
.\.venv-release\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
.\.venv-release\Scripts\python.exe scripts/ci_checks.py
```

Expected: 27 Python files compile and all eight regression scripts pass. V11-V17 contain 172 unittest cases; V10 has an additional assertion-based script. No live Ollama service is required.

With Docker Desktop running, rebuild from the tracked Dockerfile and use a free port:

```powershell
docker build -f Dockerfile.v17 -t study-guide:v17-baseline .
if ($LASTEXITCODE -ne 0) { throw "Image build failed" }
.\.venv-release\Scripts\python.exe scripts/docker_smoke.py --image study-guide:v17-baseline --port 8001
```

The probe creates and removes its own fixture container and volume. Expected output is approved status, three executions, three approvals, zero model attempts, unchanged pending state across replacement, stale-decision rejection, duplicate-decision preservation, a new container ID, a retained volume, and healthy status.

Regular CI runs on pushes to main and pull requests targeting main; it can also be dispatched or called by another workflow. See [CI details](docs/CI_GUIDE.md) for the supported matrix, diagnostics, and limits, and [project status](docs/PROJECT_STATUS.md) for the completed release evidence. The fixed-version release workflow has already published v17.0.0 and does not need to be run again.
