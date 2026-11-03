# Install the V17 release candidate

This update is based on main commit 01c1b245549d09c24c82de5ccda1283cf8ec8316. It changes CI and Docker installation to the tested 43-package baseline, adds a manual CI-gated release workflow, and records the verified hosted results. Application code and tests are preserved.

## Apply the update

Download V17_RELEASE_BASELINE.zip into Downloads, then run from the existing repository:

```powershell
cd "$HOME\multi-agent-study-guide"
if ((git status --porcelain)) { throw "Review or commit existing changes before applying the update" }
if ((git rev-parse HEAD) -ne "01c1b245549d09c24c82de5ccda1283cf8ec8316") {
    throw "Repository head differs from the package baseline. Share git log -1 before replacing files."
}

Expand-Archive "$HOME\Downloads\V17_RELEASE_BASELINE.zip" "$HOME\Downloads\V17_RELEASE_BASELINE" -Force
$releaseSource = "$HOME\Downloads\V17_RELEASE_BASELINE"
Copy-Item "$releaseSource\*" . -Recurse -Force
```

The archive contains these eleven files only:

```text
.github/workflows/ci.yml
.github/workflows/release-v17.yml
.gitignore
Dockerfile.v17
Dockerfile.v17.dockerignore
README.md
RELEASE_START_HERE.md
requirements-v17.lock
docs/CI_GUIDE.md
docs/RELEASE_GUIDE.md
docs/releases/v17.0.0.md
```

## Verify locally

Use a fresh environment. No Ollama model run is needed for these checks:

```powershell
python -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements-v17.lock
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
.\.venv-release\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
.\.venv-release\Scripts\python.exe scripts/ci_checks.py
if ($LASTEXITCODE -ne 0) { throw "Offline regressions failed" }

docker build -f Dockerfile.v17 -t study-guide:v17-baseline .
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
.\.venv-release\Scripts\python.exe scripts/docker_smoke.py --image study-guide:v17-baseline --port 8001
if ($LASTEXITCODE -ne 0) { throw "Docker verification failed" }
```

Expect eight passing scripts, 172 unittest cases plus V10 assertions, and a Docker JSON summary with approved status, three executions, three approvals, zero model attempts, and unchanged pending state after container replacement.

## Commit and push

```powershell
git --no-pager diff --check
git status --short
git add -- .github/workflows/ci.yml .github/workflows/release-v17.yml .gitignore Dockerfile.v17 Dockerfile.v17.dockerignore README.md RELEASE_START_HERE.md requirements-v17.lock docs/CI_GUIDE.md docs/RELEASE_GUIDE.md docs/releases/v17.0.0.md
git --no-pager diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Staged whitespace check failed" }
git --no-pager diff --cached --stat
git commit -m "Pin V17 release baseline and add verified release workflow"
if ($LASTEXITCODE -eq 0) { git push origin main }
```

Open the [CI workflow](https://github.com/anne500/multi-agent-study-guide/actions/workflows/ci.yml) and confirm the new commit is green. Then open [Release V17](https://github.com/anne500/multi-agent-study-guide/actions/workflows/release-v17.yml), choose main, and select Run workflow. That manual action reruns all five CI jobs and publishes v17.0.0 only after they pass for that exact commit.

The release workflow never moves an existing tag. If it fails after creating the tag, share the failure before retrying. See docs/RELEASE_GUIDE.md for evidence, assets, maintenance policy, and limits. Do not claim the release is published until the release page and its linked verification run are confirmed.
