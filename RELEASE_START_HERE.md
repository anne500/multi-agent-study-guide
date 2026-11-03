# V17.0.0 release: start here

[V17.0.0 is published](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0). Its [release run](https://github.com/anne500/multi-agent-study-guide/actions/runs/41609663282) passed all five verification jobs and publication. The tag identifies tested commit `34e0c4005f8de02fd26e13e79f022c6b489ba85e`.

The original release-candidate ZIP was a one-time handoff. Use the current repository for updated documentation or the release source archive for the fixed code baseline. The release workflow is complete; do not dispatch it again for the existing tag.

## Download and run

On the release page, download multi-agent-study-guide-v17.0.0.zip and SHA256SUMS.txt. Compare the ZIP hash with its entry in the checksum file:

```powershell
Get-FileHash "$HOME\Downloads\multi-agent-study-guide-v17.0.0.zip" -Algorithm SHA256
```

Extract the archive and enter its multi-agent-study-guide-v17.0.0 directory. From that directory, or from an existing current checkout:

```powershell
python -m venv .venv-release
.\.venv-release\Scripts\python.exe -m pip install -r requirements-v17.lock
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
.\.venv-release\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed" }
.\.venv-release\Scripts\python.exe scripts/ci_checks.py
if ($LASTEXITCODE -ne 0) { throw "Offline regressions failed" }
.\.venv-release\Scripts\python.exe study_guide_v17_app.py
```

Open http://127.0.0.1:8000. Leave Offline planning selected for a run without model inference. See [V17 start](V17_START_HERE.md) for the browser walkthrough and Ollama configuration.

## Release assets

| Asset | Purpose |
| --- | --- |
| multi-agent-study-guide-v17.0.0.zip | Tracked source, tests, and documentation at the release commit |
| requirements-v17.lock | 43 exact package versions; also included in the ZIP, alongside requirements.txt |
| release-evidence.json | Exact commit, verification workflow URL, and scope |
| SHA256SUMS.txt | Checksums for the source ZIP, lock file, and evidence file |

To fetch the release tag into an existing clone:

```powershell
git fetch origin --tags
git show --no-patch --oneline v17.0.0
```

No additional commit, tag, or publication action is required to complete V1-V17. For Docker verification use [CI start](CI_START_HERE.md). See [project status](docs/PROJECT_STATUS.md) for completion evidence and [release maintenance](docs/RELEASE_GUIDE.md) for baseline updates and publication history. Documentation on main can be updated after release; the tag and its assets remain the recorded code snapshot.
