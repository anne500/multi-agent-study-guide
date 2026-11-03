# V17: Review Studio

Install this bundle into the existing V16 repository. Earlier version files and the existing virtual environment are required. V17 uses the same requirements.txt; no new package is needed.

For a current repository checkout that already contains V17, use the tracked source and current docs/V17_GUIDE.md. The original starter ZIP is an earlier source handoff; keep the repository's newer documentation when following the historical installation steps below.

## Install on Windows

Download V17_REVIEW_STUDIO_STARTER.zip, then run these commands from the repository:

```powershell
cd "$HOME\multi-agent-study-guide"

Expand-Archive `
  -Path "$HOME\Downloads\V17_REVIEW_STUDIO_STARTER.zip" `
  -DestinationPath "$HOME\Downloads\V17_REVIEW_STUDIO_STARTER" `
  -Force

$v17Source = "$HOME\Downloads\V17_REVIEW_STUDIO_STARTER"

Copy-Item "$v17Source\study_guide_v17_app.py" . -Force
Copy-Item "$v17Source\test_v17_app.py" . -Force
Copy-Item "$v17Source\Dockerfile.v17" . -Force
Copy-Item "$v17Source\Dockerfile.v17.dockerignore" . -Force

New-Item -ItemType Directory -Path .\web_v17 -Force | Out-Null
Copy-Item "$v17Source\web_v17\*" .\web_v17\ -Force

New-Item -ItemType Directory -Path .\docs -Force | Out-Null
Copy-Item "$v17Source\docs\V17_GUIDE.md" .\docs\V17_GUIDE.md -Force

if (-not (Select-String -Path .\.gitignore -Pattern '^v17_data/$' -Quiet)) {
    Add-Content -Path .\.gitignore -Value "`nv17_data/"
}

.\.venv\Scripts\python.exe -m py_compile `
  .\study_guide_v17_app.py `
  .\test_v17_app.py

.\.venv\Scripts\python.exe .\test_v17_app.py
```

Expected: 25 tests, OK. Tests use temporary databases and a loopback HTTP server. They do not call Ollama.

## First browser run

```powershell
.\.venv\Scripts\python.exe .\study_guide_v17_app.py
```

Keep the terminal open. Open http://127.0.0.1:8000 in your browser.

1. Leave Offline planning checked.
2. Enter `Calculate 6 * 7; Convert 5 km to m`.
3. Click Create a plan. Confirm both tasks are present and Tool attempts is 0 / 8.
4. Approve the plan. Confirm results show `42 [T1]` and `5000 m [T2]`; Tool attempts is 2 / 8.
5. Click Leave workspace. Select the saved session in the sidebar. Confirm results remain and tools have not repeated.
6. Approve content, then approve the final evidence review. Confirm Session approved.
7. Click Export JSON to download the session record.

Next, verify revision with `Calculate 1 / 0`: approve its plan, click Revise plan at the failed content gate, give a reason, and change only the expression argument to `1 / 2`. Submit, approve the revised plan, and confirm `0.5` with 2 total tool attempts. Then finish the remaining gates.

For Ollama validation, create a new session, uncheck Offline planning, and enter `Convert 5 km to m`. Planning may take several minutes. Confirm the review workflow completes and Model attempts is at least 1. Export JSON and inspect snapshot.state.events for model_plan or deterministic_plan. Model mode and a correct final result alone do not prove a successful model-selected plan.

Ctrl+C stops the server. Restarting it and selecting a saved review session should retain its gate and results. The browser page may need Refresh after a server restart to reload its local write token.

V17 data stays in v17_data/sessions.sqlite. Do not commit v17_data or session exports containing personal content. Do not delete the directory to stop the server.

The guide in docs/V17_GUIDE.md records verified Windows and Docker results. The direct Windows conversion accepted model attempt 2 after an initial parser error, used no deterministic fallback, and reached approved with one execution and all three approvals. Planning took about 8 minutes 47 seconds. The Docker-hosted conversion also accepted attempt 2 with no fallback, with planning taking about 7 minutes 59 seconds.

Docker build, healthy startup, offline browser execution, host Ollama access, live model planning, and retention of an unchanged approved-session snapshot across container replacement are verified. The image built in about 61.9 seconds. The named volume is study-guide-v17-data, mounted at /data. See the current guide for build/run commands and the before/after comparison. Public deployment, LAN isolation, and manual pending-gate resume inside Docker were not verified.
