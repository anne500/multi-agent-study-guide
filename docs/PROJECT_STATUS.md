# Project completion and verified evidence

Status as of November 3, 2026: V1-V17 are implemented and the documented local, single-user learning project is complete. [V17.0.0 is published](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0) at commit `34e0c4005f8de02fd26e13e79f022c6b489ba85e`. The [release run](https://github.com/anne500/multi-agent-study-guide/actions/runs/41609663282) passed all five verification jobs and publication. No additional implementation or release step remains for the agreed V1-V17 scope.

## Completion record

| Area | Verified result | Evidence |
| --- | --- | --- |
| V1-V17 implementation | All roadmap versions are present with architecture and usage documentation | [README](../README.md), [architecture](ARCHITECTURE.md) |
| Python compilation | 27 project/test/tool Python files compile | Release verification jobs, [CI runner](../scripts/ci_checks.py) |
| Offline regressions | All eight scripts pass; 172 unittest cases across V11-V17 plus V10 assertions | Four Windows/Linux and Python 3.12/3.14 jobs in the release run |
| Dependency baseline | 43 fixed package versions; consistency checks pass | [requirements-v17.lock](../requirements-v17.lock), CI and Docker install logs |
| Browser workflows | Offline approval, pause/reopen, revision, rejection, and model-mode review were exercised | [V16 evidence](V16_GUIDE.md), [V17 evidence](V17_GUIDE.md) |
| Live Ollama | Direct and Docker conversion sessions accepted model plans, completed once, and saved all three approvals | Exported-session observations in the V17 guide |
| Local Docker | Pinned image rebuilt in 24.4 seconds; real persistence probe passed | Recorded laptop build and smoke output, [Docker recipe](../Dockerfile.v17) |
| Pending review recovery | Entire pending snapshot survived actual container replacement with the same volume; resume reached approved without repeating completed tools | Hosted and laptop [Docker smoke probe](../scripts/docker_smoke.py) |
| Review integrity | Stale decisions rejected; duplicate decisions preserved state; three total executions and approvals, zero model attempts | Docker verification JSON and existing API tests |
| Release assets | Source ZIP, package pins, evidence JSON, and checksums uploaded; all three assembly checksum checks passed | Published v17.0.0 release and publish job |
| Documentation | Current main documentation records completed CI, Docker, and release results; historical planned/pending labels were corrected | This completion record and linked guides |

The last full laptop regression run took 33.13 seconds. The fresh authoring Linux/Python 3.12.14 run took 6.38 seconds. These are separate environment observations, not controlled performance comparisons. Compilation is not runtime coverage for every LLM path in V1-V9. The eight automated scripts cover the named V10-V17 regression scope, not general model quality or learner outcomes.

## Fixed verification references

| Milestone | Commit | Result |
| --- | --- | --- |
| [Initial CI](https://github.com/anne500/multi-agent-study-guide/actions/runs/41578448362) | `01c1b24` | Five jobs passed; environment logs supplied the package baseline |
| [Pinned baseline CI](https://github.com/anne500/multi-agent-study-guide/actions/runs/41601567884) | `7d3e75c` | Five jobs passed |
| [Release workflow correction CI](https://github.com/anne500/multi-agent-study-guide/actions/runs/41602659785) | `34e0c40` | Five jobs passed |
| [Release V17](https://github.com/anne500/multi-agent-study-guide/actions/runs/41609663282) | `34e0c40` | Five verification jobs and publication passed |

The first release workflow definition failed validation because runner.temp appeared in the job environment. Commit 34e0c40 moved it to the two step environments. The successful release run used that corrected commit. The earlier failed entry remains in Actions history and does not indicate a failed publication of v17.0.0.

The published tag and assets capture the tested code and its documentation at release time. Later documentation corrections live on main; they do not move the tag, replace assets, or imply that a new code release was tested. The fixed-version Release V17 workflow has completed its purpose; a future code release requires a new version and its own verified evidence.

## Known limits and optional future work

These items define the boundary of this completed learning project. They are not unfinished V1-V17 requirements:

- Public multi-user hosting, user authentication, and production availability operations.
- Automated browser interaction, broad live-model evaluation, semantic entailment, and measured learner outcomes.
- Crash-time exactly-once tool execution, tamper-proof audits, and import/migration of exported sessions.
- Bit-for-bit reproducible builds, package hashes, signed attestations, and automatic dependency/base-image updates. The current baseline pins versions and a Docker digest and requires maintenance.
- LAN isolation or build-specific ignore enforcement on the older recorded local Docker engine. Functional Docker verification is not evidence for those separate properties.

Routine future maintenance includes dependency review, rerunning CI after changes, and deliberate backups of local session data. Those activities do not prevent the current scope from being complete. The release publishes source and checksums, not model weights or a prebuilt registry image.

## Existing open ReleaseTruth fixture issue

[Issue #1](https://github.com/anne500/multi-agent-study-guide/issues/1) is titled "ReleaseTruth production integrations incomplete." Its body explicitly says it is intentionally open so ReleaseTruth can detect a contradiction between a delivery commitment and current implementation status. It names HydraDB, Pipeshift, InsForge, and a separate production workflow.

That is an intentional ReleaseTruth evidence fixture, not an outstanding V17 roadmap item. It has been preserved rather than closed automatically. Its existence means the repository's raw open-issue count should not be used as a measure of V1-V17 completion. Work on the separate ReleaseTruth production integrations must be assessed in that project's own scope.
