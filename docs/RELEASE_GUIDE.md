# V17 dependency baseline and release

The release candidate keeps the V1-V17 roadmap and application behavior. It adds a tested package baseline and an explicit, manual way to publish v17.0.0 with source, checksums, and verification evidence. No release is published by committing these files.

## Baseline

requirements.txt retains four supported direct dependency ranges. requirements-v17.lock includes that file and pins all 43 project package versions observed in the four passing offline jobs from [CI run 41578448362](https://github.com/anne500/multi-agent-study-guide/actions/runs/41578448362), commit 01c1b245549d09c24c82de5ccda1283cf8ec8316. The three lean environments had identical freezes. Windows/Python 3.12 had seven additional runner utilities, including pipx; those are excluded. This baseline is not a freeze of a personal virtual environment.

| Component | Pinned version |
| --- | --- |
| langchain-ollama | 1.1.0 |
| langgraph | 1.2.19 |
| langgraph-checkpoint-sqlite | 3.1.3 |
| pydantic | 2.14.2 |
| langchain-core | 1.7.4 |
| langgraph-checkpoint | 4.3.1 |
| Python Docker base | python:3.12-slim, digest b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 |

The Docker digest comes from the same green Docker job. Dockerfile.v17 installs the same baseline as CI and runs pip check. Its build-specific ignore file allows both requirement files. The package and Python image pins must be maintained deliberately.

Tested platform evidence covers CPython 3.12 and 3.14 on Windows and Linux x86-64. Exact package versions are fixed; package hashes, interpreter patch versions outside Docker, OS runner images, and installer versions are not. PyPI access is required. No bit-for-bit build or security-audit claim is made. The fixed Docker digest does not automatically receive base-image updates. The lock file is a pip requirements file; no additional dependency manager is required.

## Verify the baseline locally

From the repository in PowerShell, use a new environment to avoid relying on previously installed packages:

```powershell
python -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements-v17.lock
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
.\.venv-release\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
.\.venv-release\Scripts\python.exe scripts/ci_checks.py
if ($LASTEXITCODE -ne 0) { throw "Offline regressions failed" }
```

The updated .gitignore excludes .venv-*/. Rebuild the image rather than reusing the old tag when checking the baseline:

```powershell
docker build -f Dockerfile.v17 -t study-guide:v17-baseline .
if ($LASTEXITCODE -ne 0) { throw "Image build failed" }
.\.venv-release\Scripts\python.exe scripts/docker_smoke.py --image study-guide:v17-baseline --port 8001
```

The smoke test uses its own fixture container and volume. The regular study-guide-v17 container and its data volume are separate. The hosted workflow repeats these checks across the supported matrix and Docker.

## Publish v17.0.0

After committing the candidate to main and checking its CI run:

1. Open [Release V17](https://github.com/anne500/multi-agent-study-guide/actions/workflows/release-v17.yml).
2. Select Run workflow, choose main, and start it. This is the explicit publication action.
3. Wait for the reused CI workflow: four offline matrix jobs and the Docker job. All must succeed for the dispatched commit.
4. The publish job packages tracked source, calculates checksums, checks main has not advanced, creates a new v17.0.0 tag at that verified commit, and publishes the release assets. Only this job has contents: write. CI jobs remain read-only, and publication uses the workflow's built-in token without a personal token or stored registry credentials.
5. Open [the release](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0). Verify the tag commit matches release-evidence.json and its linked workflow run is green. Check the asset checksum after downloading.

Dispatch from another branch skips both jobs. This workflow is intentionally specific to v17.0.0, with serialized publication. It does not overwrite tags or releases. If main advances during verification, rerun from main. If tag creation succeeds but release upload fails, inspect the existing tag and release before recovery; a blind rerun will stop because the tag exists. Never delete or move a published tag to work around a failure. Repository rules can block tag creation or release writes; inspect the reported rule before changing repository policy.

The source ZIP is produced by git archive at GITHUB_SHA, so it contains tracked files from the tested commit. Local runtime databases and environment directories are not assets. No model weights, container registry image, or hosted application are published. Checksums detect download corruption and identify these assets; they are not signatures or artifact attestations.

For a downloaded archive, compare this PowerShell result with SHA256SUMS.txt:

```powershell
Get-FileHash .\multi-agent-study-guide-v17.0.0.zip -Algorithm SHA256
```

## Update policy

For a later dependency refresh, start from the supported ranges in requirements.txt in a clean environment. Resolve deliberately, inspect package changes, produce a new version baseline, and pass the four offline jobs and Docker checks before using it for a release. Record the source commit, workflow URL, dependency versions, and base digest. Exclude unrelated runner tools and local extras. Do not regenerate the baseline from a long-lived laptop environment or silently change the contents of v17.0.0.

## Evidence status

Verified before this candidate: the original matrix passed all five jobs, and both local and hosted Docker probes confirmed pending review retention across replacement. The candidate changes installation inputs, CI reuse, and release publication. A fresh Linux CPython 3.12.14 environment installed exactly the 43 pinned packages with no unrelated extras, and pip check passed. All eight regression scripts passed in 6.38 seconds, including 172 unittest cases plus the V10 assertions. Local checks also passed for workflow structure, Bash syntax, source ZIP assembly, and asset checksums. The offline run removed ambient proxy settings because no external service is used; no optional proxy package was added to the project baseline. Hosted verification of these new files and actual tag/publication remain pending until they are pushed and the manual release workflow runs. The workflow does not evaluate live model quality or browser interaction.

References: [reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows), [workflow permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions), and [GitHub CLI release creation](https://cli.github.com/manual/gh_release_create).
