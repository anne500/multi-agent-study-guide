# Final V1-V17 source and architecture audit

Audit date: November 3, 2026. The implemented local, single-user V1-V17 roadmap is complete within the verification scope recorded here. The published baseline is [v17.0.0](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0). This audit reviewed main at `0ceed9072c4b1d07810ca0390f14bd9ed6900f03`, then corrected documentation and SQLite ignore patterns. No application behavior, source corpus, dependency baseline, model configuration, or release tag was changed.

## Source inventory and runtime checks

- Reconstructed all 53 tracked files from GitHub and verified every file against its Git blob SHA before review.
- Confirmed the canonical V1-V17 sequence in README and architecture documentation, all 17 Python implementations, and an explicit command-line entry point for each.
- Imported all 17 version modules without inference. Compiled all 15 graph-based workflows V2-V16 and compared their builder nodes, fixed edges, and conditional mappings with the diagrams. V1 uses plain Python calls; V17 composes the V16 graph behind its HTTP service.
- Installed the 43 pinned dependencies in a fresh Linux CPython 3.12.14 environment; pip check passed.
- Compiled all 27 project/test/tool Python files and reran all eight regression scripts. All 172 unittest cases across V11-V17 and the V10 assertion-based regression passed in 14.21 seconds in this audit environment.
- Verified the two trusted Markdown documents retain one title, one source ID, and seven sections each. Their contents were preserved.
- Checked Markdown fences, relative file links, architecture anchors, version coverage, and whitespace after the corrections.

## Diagram coverage and source comparison

| Version and diagram | Implementation | Compared flow |
| --- | --- | --- |
| [V1](ARCHITECTURE.md#v1-plain-python-sequential-agents) | [study_guide_v1.py](../study_guide_v1.py) | Sequential planner, teacher, and quiz function calls |
| [V2](ARCHITECTURE.md#v2-langgraph-sequential-workflow) | [study_guide_v2.py](../study_guide_v2.py) | Sequential shared-state graph |
| [V3](ARCHITECTURE.md#v3-sequential-simplification) | [study_guide_v3_simplifier.py](../study_guide_v3_simplifier.py) | Simplifier precedes quiz writing |
| [V4](ARCHITECTURE.md#v4-parallel-specialist-workers) | [study_guide_v4_parallel.py](../study_guide_v4_parallel.py) | Three parallel specialists feed one merger |
| [V5](ARCHITECTURE.md#v5-orchestrator-and-delegated-subagents) | [study_guide_v5_orchestrator.py](../study_guide_v5_orchestrator.py) | Dynamic Send assignments feed deterministic synthesis |
| [V6](ARCHITECTURE.md#v6-supervisor-routing) | [study_guide_v6_router.py](../study_guide_v6_router.py) | One selected beginner/advanced teacher feeds quiz writing |
| [V7](ARCHITECTURE.md#v7-human-approval-loop) | [study_guide_v7_human_loop.py](../study_guide_v7_human_loop.py) | Native human interrupt; rejection revises the outline |
| [V8](ARCHITECTURE.md#v8-automated-review-and-refinement) | [study_guide_v8_review_loop.py](../study_guide_v8_review_loop.py) | Reviewer approval or revision cap ends the loop |
| [V9](ARCHITECTURE.md#v9-structured-multi-agent-workflow) | [study_guide_v9_structured_outputs.py](../study_guide_v9_structured_outputs.py) | Reviewer parsing retry requests revision; revision cap terminates |
| [V10](ARCHITECTURE.md#v10-persistent-checkpointing-and-recovery) | [study_guide_v10_checkpointing.py](../study_guide_v10_checkpointing.py) | Persistent graph; fallback_approved preserves the nonblank quiz |
| [V11](ARCHITECTURE.md#v11-cross-session-learner-memory) | [study_guide_v11_long_term_memory.py](../study_guide_v11_long_term_memory.py) | Separate learner memory and session checkpoints |
| [V12](ARCHITECTURE.md#v12-retrieval-with-trusted-documents-and-citations) | [study_guide_v12_rag_citations.py](../study_guide_v12_rag_citations.py) | Trusted retrieval, bounded section fallback, final citation block |
| [V13](ARCHITECTURE.md#v13-tool-using-study-agents) | [study_guide_v13_tool_using_agents.py](../study_guide_v13_tool_using_agents.py) | Every observation returns to selection; budget prevents further tools |
| [V14](ARCHITECTURE.md#v14-dynamic-planning-and-agent-selection) | [study_guide_v14_dynamic_planning.py](../study_guide_v14_dynamic_planning.py) | Validated specialist plan with bounded replanning and dependencies |
| [V15](ARCHITECTURE.md#v15-evaluation-and-observability) | [study_guide_v15_evaluation_observability.py](../study_guide_v15_evaluation_observability.py) | Observed V14 execution, integrity checks, and fixed-case reports |
| [V16](ARCHITECTURE.md#v16-multi-stage-human-approval) | [study_guide_v16_human_approval.py](../study_guide_v16_human_approval.py) | Three persistent review gates, revision invalidation, rejection |
| [V17](ARCHITECTURE.md#v17-application-and-deployment) | [study_guide_v17_app.py](../study_guide_v17_app.py) | Queued writes, HTTP reads, saved views, and native checkpoints |

There are 20 diagrams in ARCHITECTURE.md: one per version plus V9 reviewer detail, V10 persistence detail, and the version relationship overview. The V14, V15, and V16 usage guides contain another three diagrams, for 23 Mermaid blocks in total.

All 23 definitions parsed and rendered in a headless Chromium 153.0.8010.0 browser using Mermaid 12.3.0. SVG text bounds were checked for clipping; no clipped text or rendering failures were detected. Rendered layouts were inspected as an overview and at full size for the changed retry, citation, tool-loop, and HTTP diagrams. This checks these definitions and layouts in the recorded renderer; GitHub can use a different Mermaid version or theme.

The diagrams show application-level control and data relationships. The source remains authoritative for individual helpers, exception details, and schema fields. Compilation and diagram comparison are not live-model evaluations of every historical example.

## Corrections made

| Finding | Correction |
| --- | --- |
| V9 documentation attributed later fallback improvements to the V9 file | Moved quiz preservation, fallback_approved, and blank-reviser protection to the V10 description; documented V9's actual reviewer revision/cap behavior |
| V9 retry detail implied a generic retry for every structured component | Scoped the retry diagram to the reviewer; documented router errors and orchestrator assignment fallback separately |
| V12 diagram lacked the explicit failure exits | Added no-matching-source exit and invalid-final-citation path that blocks learner-memory saving |
| V13 diagram skipped selection once two tools had run | Showed every observation returning to select_tool; the selector routes to finalization when execution budget is exhausted |
| V13 final box implied every terminal result was successful | Included completed and safe_failure statuses, matching finalization logic |
| V17 GET arrow bypassed the HTTP API | Routed status/export through the HTTP endpoint and cached session view |
| V3's six-step horizontal diagram was unnecessarily wide | Switched to a vertical layout |
| One V14 publication sentence still referred to a future audit | Replaced it with the published-baseline status |
| V11-V13 database rules did not cover sidecar suffixes | Extended the existing ignore patterns to include journal, WAL, and SHM files; source, trusted documents, requirements, and docs remain trackable |

## Actual browser workflow check

A fresh temporary V17 service was exercised through its HTML/JavaScript interface in Chromium 153.0.8010.0 with offline planning selected:

1. Created a compound trusted-research, arithmetic, and unit-conversion session. Tools remained at zero before plan approval; approval produced three results and retrieved sources.
2. Left the workspace, reopened the saved session, and reloaded the browser. The full pending snapshot stayed unchanged.
3. Completed content and final approval, then downloaded and parsed the exported JSON. The session had three executions, three approvals, and zero model attempts.
4. Submitted division by zero, confirmed incomplete content could not be approved, revised the expression to 1 / 2 with a reason, confirmed approvals were cleared, and finished with 0.5, revision 1, and two cumulative tool executions.
5. Rejected a new conversion session at plan review and confirmed terminal rejected status with zero executions.

All scenarios passed with no uncaught browser page errors. This was an audit-time browser check against a temporary local service, not a maintained browser job in CI. It complements the existing API tests, manual Windows/live-Ollama observations, and actual Docker persistence checks.

## Existing delivery evidence

- [Latest pre-audit CI](https://github.com/anne500/multi-agent-study-guide/actions/runs/41612289922): all four Windows/Linux and Python 3.12/3.14 jobs and the Docker job passed at 0ceed90.
- [Release V17](https://github.com/anne500/multi-agent-study-guide/actions/runs/41609663282): all five verification jobs and publication passed at 34e0c40.
- [Published assets](https://github.com/anne500/multi-agent-study-guide/releases/tag/v17.0.0): source ZIP, dependency pins, release evidence, and checksums; the three assembly checksum checks passed.

## Completion boundary

No additional V1-V17 implementation or publication task is required. This audit makes the architecture descriptions more accurate; it does not assert that every possible input, hardware configuration, failure mode, or model response has been tested.

Public multi-user hosting/authentication, a maintained browser CI suite, broad semantic/model-quality evaluation, learner-outcome research, signed or bit-for-bit builds, and crash-time exactly-once execution remain optional future scope. The intentionally open ReleaseTruth fixture issue is explained in [project status](PROJECT_STATUS.md). Routine dependency maintenance and session backups continue as normal project upkeep.
