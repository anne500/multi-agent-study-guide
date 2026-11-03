# V17: Review Studio

V17 is implemented, verified locally and in Docker, and published in [v17.0.0](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0). Use a complete repository checkout or the release source archive; the original starter ZIP is an earlier handoff.

## Install on Windows

For a new clone of the fixed release baseline:

```powershell
git clone --branch v17.0.0 https://github.com/anne500/multi-agent-study-guide.git study-guide-v17
cd study-guide-v17
```

If you already have a current checkout, enter that directory instead. Install the baseline and run the V17 tests:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-v17.lock
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
.\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
.\.venv\Scripts\python.exe test_v17_app.py
```

Expected: 25 tests, OK. They use temporary databases and a loopback HTTP server without calling Ollama. Run scripts/ci_checks.py for all eight regression scripts. The release CI passed on Windows/Linux with Python 3.12 and 3.14.

## First browser run

```powershell
.\.venv\Scripts\python.exe study_guide_v17_app.py
```

Keep the terminal open. Open http://127.0.0.1:8000 in your browser.

1. Leave Offline planning checked.
2. Enter `Calculate 6 * 7; Convert 5 km to m`.
3. Click Create a plan. Confirm both tasks are present and Tool attempts is 0 / 8.
4. Approve the plan. Confirm results show `42 [T1]` and `5000 m [T2]`; Tool attempts is 2 / 8.
5. Click Leave workspace. Select the saved session in the sidebar. Confirm results remain and tools have not repeated.
6. Approve content, then approve the final evidence review. Confirm Session approved.
7. Click Export JSON to download the session record.

Next, verify revision with `Calculate 1 / 0`: approve its plan, click Revise plan at the failed content gate, give a reason, and change the expression argument to `1 / 2`. Submit, approve the revised plan, and confirm `0.5` with two total tool attempts. Then finish the remaining gates.

For model planning, run Ollama with qwen3.5:4b available. Create a new session, clear Offline planning, and enter `Convert 5 km to m`. Planning can take several minutes. Export JSON and inspect snapshot.state.events for model_plan or deterministic_plan; model mode and a correct result alone do not prove a successful model-selected plan. See [the application guide](docs/V17_GUIDE.md) for OLLAMA_BASE_URL and Docker host access.

Ctrl+C stops the direct Python server. Restarting it and selecting a saved review session retains its gate and results. Refresh the browser after a server restart to reload its local write token. Local data stays in v17_data/sessions.sqlite, which is already ignored by Git. Keep session history through a deliberate backup or JSON export; stopping the server does not require deleting data.

## Verified Docker and release results

Docker build, health, offline browser execution, host Ollama access, live model planning, and completed-session retention were verified manually. Subsequent local and hosted Docker smoke tests also verified pending-review persistence and resume across actual container replacement, stale-decision rejection, and duplicate-decision preservation. The final probe completed with three executions, three approvals, and zero model attempts.

See [CI start](CI_START_HERE.md) to reproduce the Docker probe, [the application guide](docs/V17_GUIDE.md) for build/run commands, and [project status](docs/PROJECT_STATUS.md) for the completed release evidence and known limits. The implementation is a local, single-user application; public hosting, model-quality evaluation, and crash-time exactly-once execution are outside the completed scope.
