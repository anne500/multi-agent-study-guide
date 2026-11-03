# Install and verify CI

This package adds .github/workflows/ci.yml, scripts/ci_checks.py, scripts/docker_smoke.py, docs/CI_GUIDE.md, this guide, and a README update. It preserves V1-V17 source and tests.

From the existing repository, after downloading CI_AUTOMATION_STARTER.zip into Downloads:

```powershell
cd "$HOME\multi-agent-study-guide"

Expand-Archive `
  "$HOME\Downloads\CI_AUTOMATION_STARTER.zip" `
  "$HOME\Downloads\CI_AUTOMATION_STARTER" `
  -Force

$ciSource = "$HOME\Downloads\CI_AUTOMATION_STARTER"

New-Item -ItemType Directory -Path .\.github\workflows -Force | Out-Null
New-Item -ItemType Directory -Path .\scripts -Force | Out-Null

Copy-Item "$ciSource\.github\workflows\ci.yml" .\.github\workflows\ci.yml -Force
Copy-Item "$ciSource\scripts\ci_checks.py" .\scripts\ci_checks.py -Force
Copy-Item "$ciSource\scripts\docker_smoke.py" .\scripts\docker_smoke.py -Force
Copy-Item "$ciSource\docs\CI_GUIDE.md" .\docs\CI_GUIDE.md -Force
Copy-Item "$ciSource\CI_START_HERE.md" .\CI_START_HERE.md -Force
Copy-Item "$ciSource\README.md" .\README.md -Force

.\.venv\Scripts\python.exe scripts/ci_checks.py
```

Expected: compilation succeeds, then all eight regression scripts pass. The V10 script uses assertions and the seven later scripts contain 172 unittest cases in total. No Ollama inference is required.

With Docker Desktop running and port 8001 free, use the existing verified image to exercise the new probe:

```powershell
.\.venv\Scripts\python.exe scripts/docker_smoke.py --image study-guide:v17 --port 8001
```

This creates and removes its own fixture resources; it does not replace the main application container or remove its volume. Expected: approved status, three tool executions, three approvals, zero model attempts, and unchanged pending state across replacement. Share errors if either local check fails.

Check the six intended files before staging:

```powershell
git --no-pager diff --check
git status --short
git add -- .github/workflows/ci.yml scripts/ci_checks.py scripts/docker_smoke.py docs/CI_GUIDE.md CI_START_HERE.md README.md
git --no-pager diff --cached --check
git --no-pager diff --cached --stat
```

Commit and push after those checks pass:

```powershell
git commit -m "Add offline CI matrix and Docker review persistence checks"
if ($LASTEXITCODE -eq 0) {
    git push origin main
}
```

Open https://github.com/anne500/multi-agent-study-guide/actions/workflows/ci.yml. Confirm four offline matrix jobs and the dependent Docker job pass. Send the run link or the first failing step's log so the actual hosted result can be verified. A green hosted run is required before recording CI as verified or creating the baseline release.
