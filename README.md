# Multi-Agent Study Guide with Python, LangGraph, Ollama, and Qwen

[![CI](https://github.com/anne500/multi-agent-study-guide/actions/workflows/ci.yml/badge.svg)](https://github.com/anne500/multi-agent-study-guide/actions/workflows/ci.yml)

A versioned learning project that builds local multi-agent study-guide workflows with Python, LangGraph, Ollama, and the `qwen3.5:4b` model.

The repository starts with a simple sequential pipeline and progressively adds graph orchestration, parallel workers, routing, human approval, automated review, structured outputs, safe fallback behavior, persistent checkpoint recovery, cross-session learner memory, trusted retrieval with verified citations, controlled tool use, dynamic planning, observability, durable review, and a local browser application with a JSON API.

All LLM calls run locally through Ollama. No paid API key is required.

## Version Roadmap

| Version | Capability introduced | Status |
|---|---|---|
| V1 | Plain Python sequential agents | Completed |
| V2 | LangGraph sequential workflow | Completed |
| V3 | Notes simplification | Completed |
| V4 | Parallel specialist workers | Completed |
| V5 | Orchestrator and subagent delegation | Completed |
| V6 | Supervisor routing | Completed |
| V7 | Human-in-the-loop approval | Completed |
| V8 | Automated review and refinement | Completed |
| V9 | Structured outputs, retry handling, orchestration, and safe fallback | Completed |
| V10 | Persistent SQLite checkpointing and workflow recovery | Completed |
| V11 | Cross-session learner memory | Completed |
| V12 | Retrieval from trusted local documents with citations | Completed |
| V13 | Controlled tool-using study agents | Completed |
| V14 | Dynamic planning and agent selection | Completed |
| V15 | Evaluation, tracing, metrics, and observability | Completed |
| V16 | Multi-stage human approval and interactive revision | Completed |
| V17 | User application, API, and local deployment | Completed locally and in Docker |

See the [V1-V17 Architecture Guide](docs/ARCHITECTURE.md) for a detailed workflow diagram and explanation of every version.

V17 is verified as a local, single-user application both directly on Windows and in a Linux Docker container. Docker build, health checks, browser execution, host Ollama access, live model planning, and completed-session retention across container replacement were verified. Public hosting is outside the implemented scope.

The [verified CI run](https://github.com/anne500/multi-agent-study-guide/actions/runs/41578448362) passed on Windows and Linux with Python 3.12 and 3.14, including Docker pending-review persistence. The V17 release candidate uses [requirements-v17.lock](requirements-v17.lock) for exact package versions and a fixed Docker base digest. See the [release guide](docs/RELEASE_GUIDE.md) for the manual, CI-gated v17.0.0 publication workflow and its verification limits.

## What Is an Agent Here?

In this project, an agent is a focused LLM call with:

- A specific responsibility
- Its own prompt and instructions
- A defined position in the workflow

Agents collaborate by passing outputs through Python variables or LangGraph shared state. Later versions add parallel state aggregation, conditional routing, validated schemas, retry controls, and durable checkpoints.

## Project Files

| File | Architecture | Description |
|---|---|---|
| `study_guide_v1.py` | Plain Python sequential | Coordinates planner, teacher, and quiz-writer calls with regular Python |
| `study_guide_v2.py` | LangGraph sequential | Reimplements V1 with nodes, edges, and shared state |
| `study_guide_v3_simplifier.py` | Extended sequential | Adds a fourth agent that simplifies the notes |
| `study_guide_v4_parallel.py` | Parallel specialists | Runs concepts, examples, and quiz agents independently before merging |
| `study_guide_v5_orchestrator.py` | Orchestrator and subagents | Creates assignments and delegates them to parallel workers |
| `study_guide_v6_router.py` | Supervisor and router | Selects a beginner or advanced teaching branch |
| `study_guide_v7_human_loop.py` | Human-in-the-loop | Pauses for outline approval or revision feedback |
| `study_guide_v8_review_loop.py` | Review and refinement | Reviews a quiz and sends it back for revision when necessary |
| `study_guide_v9_structured_outputs.py` | Structured multi-agent workflow | Adds validated routing, orchestrator assignments, parallel workers, synthesis, structured review, retries, and safe fallback |
| `study_guide_v10_checkpointing.py` | Persistent workflow | Adds SQLite persistence, pause and resume, completed-session loading, and recovery without repeating completed nodes |
| `test_v10_reviewer_fallback.py` | Deterministic regression test | Forces structured-review failure and verifies quiz preservation without invoking Ollama |
| `study_guide_v11_long_term_memory.py` | Cross-session learner memory | Reuses the tested V10 graph and adds validated learner profiles, outcomes, personalization, and a separate SQLite memory store |
| `test_v11_learner_memory.py` | Deterministic memory tests | Verifies validation, persistence, deduplication, learner isolation, summaries, and safe outcome storage without invoking Ollama |
| `study_guide_v12_rag_citations.py` | Trusted retrieval and citations | Loads approved local Markdown, retrieves deterministic chunks, grounds generation, validates citations, and integrates V11 memory with a separate V12 checkpoint store |
| `test_v12_retrieval_citations.py` | Deterministic retrieval tests | Runs 19 tests covering source loading, chunking, ranking, citations, item-level validation, retry behavior, and deterministic fallback without invoking Ollama |
| `study_guide_v13_tool_using_agents.py` | Controlled tool-using agent | Adds schema-controlled selection, an explicit local tool allowlist, validated observations, bounded tool calls, answer verification, and V13 checkpointing |
| `test_v13_tool_using_agents.py` | Deterministic tool tests | Runs 30 tests covering the registry, safe arithmetic, unit conversion, trusted search, schemas, routing, references, and failure handling without invoking Ollama |
| `trusted_documents/` | Approved local sources | Contains curated Markdown sources with stable source IDs and section headings |
| `study_guide_v14_dynamic_planning.py` | Bounded dynamic planning | Selects specialists, evaluates task completion, replans unfinished work, and saves run snapshots |
| `test_v14_dynamic_planning.py` | Planning and persistence tests | Runs 31 tests including LangGraph parity, bounded failure, citation mapping, and SQLite connection closure |
| `docs/V14_GUIDE.md` | V14 usage and limitations | Documents offline and Ollama workflows, run snapshots, execution budgets, and evaluation limits |
| `study_guide_v15_evaluation_observability.py` | Observed V14 execution and evaluation | Records phase/model timings, task outcomes, planning metrics, citation integrity, and fixed offline evaluations |
| `test_v15_evaluation_observability.py` | Observability regression tests | Runs 27 tests covering graph parity, retries, metrics, evidence checks, report persistence, and connection closure |
| `docs/V15_GUIDE.md` | V15 evaluation scope and usage | Explains metrics, the offline benchmark, saved reports, trace inspection, and evaluation limits |
| `study_guide_v16_human_approval.py` | Durable human review | Adds plan, content, and final review gates with bounded revisions and SQLite checkpoint resume |
| `test_v16_human_approval.py` | Human-review regression tests | Runs 32 tests covering approvals, rejection, revisions, stale decisions, evidence checks, display correctness, and restart behavior |
| `docs/V16_GUIDE.md` | V16 review and recovery guide | Explains review commands, approved task labels, revisions, saved sessions, and recovery limits |
| `study_guide_v17_app.py` | Local application and asynchronous API | Serves the browser UI, queues V16 workflow operations, and persists sessions in a separate SQLite store |
| `test_v17_app.py` | HTTP and persistence integration tests | Runs 25 tests covering review gates, revisions, retries, restart, recovery, validation, references, export, and background planning |
| `web_v17/` | Browser interface | Contains the HTML, CSS, and JavaScript for creating sessions and reviewing plans, results, and evidence |
| `Dockerfile.v17` and `Dockerfile.v17.dockerignore` | Verified local container deployment | Defines a non-root image, health check, and build-specific ignore rules; build, runtime, Ollama access, and named-volume persistence were verified |
| `docs/V17_GUIDE.md` | Application and API guide | Explains browser use, endpoints, persistence, recovery, verified runs, and deployment limits |
| `V17_START_HERE.md` | Installation and validation walkthrough | Provides PowerShell setup and the offline, revision, and live-model browser checks |
| `docs/ARCHITECTURE.md` | Architecture reference | Shows implemented V1-V17 workflows and their actual components and routing |
| `.github/workflows/ci.yml` | Continuous integration | Runs Python 3.12/3.14 offline tests on Windows and Linux, then a Linux Docker smoke test |
| `scripts/ci_checks.py` | Portable verification runner | Compiles project Python files and runs each root regression script in a separate process |
| `scripts/docker_smoke.py` | Container integration check | Uses temporary test resources to verify readiness, trusted retrieval, API gates, export, and pending-review resume across replacement |
| `docs/CI_GUIDE.md` | CI scope and reproduction | Explains triggers, jobs, local commands, diagnostics, and verification limits |
| `requirements-v17.lock` | Tested dependency baseline | Pins 43 package versions captured from all four passing CI environments |
| `.github/workflows/release-v17.yml` | Manual release publication | Reuses all five CI jobs, then creates v17.0.0 and publishes source, checksums, and verification evidence |
| `docs/RELEASE_GUIDE.md` | Baseline and release procedure | Documents platform evidence, publication steps, recovery, and maintenance |

## Requirements

- Python
- [Ollama](https://ollama.com/)
- Ollama model `qwen3.5:4b`
- `langchain-ollama`
- `langgraph`
- `langgraph-checkpoint-sqlite`
- `pydantic`

Developed and tested on Windows with Python 3.14.

## Installation

### 1. Install Ollama

Download Ollama from [ollama.com/download](https://ollama.com/download).

### 2. Pull the model

```powershell
ollama pull qwen3.5:4b
```

### 3. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements-v17.lock
python -m pip check
```

## Running the Examples

| Version | Command |
|---|---|
| V1 | `python .\study_guide_v1.py` |
| V2 | `python .\study_guide_v2.py` |
| V3 | `python .\study_guide_v3_simplifier.py` |
| V4 | `python .\study_guide_v4_parallel.py` |
| V5 | `python .\study_guide_v5_orchestrator.py` |
| V6 | `python .\study_guide_v6_router.py` |
| V7 | `python .\study_guide_v7_human_loop.py` |
| V8 | `python .\study_guide_v8_review_loop.py` |
| V9 | `python .\study_guide_v9_structured_outputs.py` |
| V10 | `python .\study_guide_v10_checkpointing.py` |
| V11 | `python .\study_guide_v11_long_term_memory.py` |
| V12 | `python .\study_guide_v12_rag_citations.py` |
| V13 | `python .\study_guide_v13_tool_using_agents.py` |
| V14 | `python .\study_guide_v14_dynamic_planning.py` |
| V15 | `python .\study_guide_v15_evaluation_observability.py` |
| V16 | `python .\study_guide_v16_human_approval.py` |
| V17 | `python .\study_guide_v17_app.py` |

Run the controlled V8 revision demonstration:

```powershell
python .\study_guide_v8_review_loop.py --demo-revision
```

Pause V10 before quiz generation:

```powershell
python .\study_guide_v10_checkpointing.py --pause-before-quiz
```

Run the deterministic V10 fallback regression test:

```powershell
python .\test_v10_reviewer_fallback.py
```

Run the deterministic V11 learner-memory tests:

```powershell
python .\test_v11_learner_memory.py
```

Run the deterministic V12 retrieval and citation tests:

```powershell
python .\test_v12_retrieval_citations.py
```

Run the deterministic V13 controlled-tool tests:

```powershell
python .\test_v13_tool_using_agents.py
```

Run V14 without Ollama:

```powershell
python .\study_guide_v14_dynamic_planning.py --offline
```

Run the V14 tests:

```powershell
python .\test_v14_dynamic_planning.py
```

Run the V15 offline benchmark and tests:

```powershell
python .\study_guide_v15_evaluation_observability.py --benchmark
python .\test_v15_evaluation_observability.py
```

Run V16 offline and test its review gates:

```powershell
python .\study_guide_v16_human_approval.py --offline
python .\test_v16_human_approval.py
```

Run the V17 integration tests, then start the browser application:

```powershell
python .\test_v17_app.py
python .\study_guide_v17_app.py
```

Open http://127.0.0.1:8000 and keep the terminal running. Offline planning is
selected by default. Uncheck it before creating a session to use Ollama. Review
and approve the plan, content, and final evidence questions. The existing
requirements are sufficient; V17 adds no package or frontend-build dependency.

## Continuous Integration

The CI workflow runs on pushes to main, pull requests targeting main, and manual
dispatch. Four jobs cover Python 3.12 and 3.14 on Ubuntu 24.04 and Windows 2025.
Each compiles the project and runs all root test_v*.py scripts in independent
processes, including V10's assertion-based fallback check. No Ollama model or
API key is required for these checks. Dependencies are installed from the
exact requirements-v17.lock baseline, checked with pip check, and recorded in logs.

After those jobs pass, a Linux job builds Dockerfile.v17 and checks the API
through a fixture container and named volume. It verifies that tools wait for
plan approval, trusted retrieval and arithmetic/conversion results are available,
duplicate approval retries preserve state, and a pending content-review snapshot
survives container replacement. It resumes the saved gate, rejects a stale
decision, completes final approval, and checks JSON export without repeating tools.
The fixture cleans up its own container and volume; the user's application data
is not used by this check.

Run the offline checks locally with `python scripts/ci_checks.py`. Run the Docker
probe beside the normal app with `python scripts/docker_smoke.py --image
study-guide:v17 --port 8001` after building that image. See
[the CI guide](docs/CI_GUIDE.md) for commands and limits. The first hosted run
passed all five jobs; the pinned baseline must pass a new run after it is pushed.
The separate manual Release V17 workflow reuses the full CI suite for its exact
commit before publishing the tag and source assets. The V1-V17 roadmap is preserved.

## Workflow Architecture

The [V1-V17 Architecture Guide](docs/ARCHITECTURE.md) contains the complete visual architecture reference. The summary below describes the implemented workflows.

### V1 and V2: Sequential Pipeline

A planner creates an outline, a teacher writes notes, and a quiz writer produces review questions. V1 uses regular Python. V2 expresses the same sequence as a LangGraph graph.

### V3: Simplification

A fourth agent rewrites the generated notes in clearer language.

### V4: Parallel Specialists

Multiple agents work independently on the same topic. Their outputs are collected after all parallel branches finish.

### V5: Orchestrator and Subagents

An orchestrator analyzes the topic, creates assignments, and delegates them to parallel subagents.

### V6: Supervisor and Router

A routing agent examines the learning request and selects either a beginner or advanced teaching branch.

### V7: Human-in-the-Loop

The graph pauses after preparing an outline. A human can approve it or reject it with revision feedback.

Example rejection:

```text
reject: Make each section practical and include one real-world example.
```

### V8: Review and Refinement

A producer writes a quiz and a reviewer evaluates it against explicit requirements. Rejected quizzes return to a revision node until approved or until the revision limit is reached.

## V9: Structured Outputs and Safe Review

V9 combines several advanced workflow patterns in one graph:

1. A structured router selects the learner level.
2. A structured orchestrator creates exactly three validated assignments.
3. Parallel specialist workers complete those assignments.
4. A synthesizer orders and combines the worker outputs.
5. A quiz producer creates review questions.
6. A structured reviewer returns a validated status and specific feedback.
7. Conditional routing approves, revises, or safely terminates the workflow.

V9 also includes:

- Pydantic schemas for router, orchestrator, and reviewer outputs
- Validation of orchestrator assignments
- Deterministic fallback assignments when orchestration output is unsuitable
- One retry after malformed or empty reviewer output
- A maximum of two quiz revisions
- Safe quiz preservation when structured review cannot be parsed
- Explicit `fallback_approved` routing to prevent an unnecessary revision loop
- Protection against blank quiz-reviser output

## V10: Persistent Checkpointing and Recovery

V10 extends the V9 workflow with LangGraph's `SqliteSaver`. Each session uses a thread ID and stores its graph state in `study_guide_checkpoints.sqlite`.

V10 supports:

- Starting and saving a named session
- Pausing immediately before `quiz_producer`
- Resuming an unfinished workflow without repeating completed nodes
- Loading a completed session without rerunning Ollama calls
- Reporting the next scheduled graph nodes
- Keeping the SQLite database and sidecar files out of Git
- Importing the module without starting the interactive command-line workflow

### Start or Load a Session

```powershell
python .\study_guide_v10_checkpointing.py
```

Enter a unique session ID. If that ID already exists, V10 asks whether to resume or load it.

### Pause and Resume

Start a session that pauses before quiz generation:

```powershell
python .\study_guide_v10_checkpointing.py --pause-before-quiz
```

Run V10 again without the flag, enter the same thread ID, and select `R`. The workflow resumes at `quiz_producer` without repeating the completed router, orchestrator, worker, or synthesizer work.

A completed checkpoint reports:

```text
Checkpoint saved successfully.
Next scheduled nodes: ()
```


## V11: Cross-Session Learner Memory

V11 reuses the tested V10 workflow and adds a separate `learner_memory.sqlite` store for durable learner facts across different sessions and topics. V10 checkpoints continue to preserve one workflow run, while V11 memory preserves validated learner context.

V11 stores:

- Learner ID
- Preferred beginner or advanced level
- Learning preferences
- Completed topics
- Quiz scores
- Recurring mistakes
- Recent progress across sessions

V11 also provides:

- Memory-informed routing before graph execution
- Automatic or user-supplied session IDs
- Visible session plans before generation
- Explicit confirmation before expensive model calls
- Explicit approval before saving a learning outcome
- Pydantic validation for profiles and outcomes
- Separation between generated model text and trusted learner facts
- Clean reuse of V10 checkpointing without duplicating V10 source code

Two SQLite databases serve different purposes:

| Database | Purpose |
|---|---|
| `study_guide_checkpoints.sqlite` | Saves LangGraph execution state for pause, resume, and recovery within a workflow session |
| `learner_memory.sqlite` | Saves validated learner profiles and outcomes across separate workflow sessions |

The deterministic V11 suite runs eight tests without Ollama or network calls. It verifies normalization, persistence after reopening SQLite, completed-topic deduplication, quiz history, recurring mistakes, learner isolation, validation failures, and safe behavior for unknown learners.

## V12: Trusted Retrieval with Verified Citations

V12 adds retrieval-augmented generation over approved local Markdown documents while preserving V11 learner memory and V10 workflow reliability. It does not require a vector database or network service.

The V12 flow:

1. Loads trusted documents with stable source IDs and section headings.
2. Splits each document into deterministic section-based chunks.
3. Ranks chunks with deterministic lexical retrieval.
4. Assigns stable session citation labels such as `[S1]` through `[S4]`.
5. Passes only the retrieved context into grounded specialist and quiz prompts.
6. Validates every specialist section and quiz question independently.
7. Retries an invalid specialist response once.
8. Uses a deterministic trusted-source fallback if the retry is blank, insubstantial, or uncited.
9. Rejects missing, malformed, or unknown citations before an outcome can be saved.

V12 keeps three persistence concerns separate:

| Store | Purpose |
|---|---|
| `learner_memory.sqlite` | Validated learner profile and approved outcomes across sessions |
| `study_guide_v12_checkpoints.sqlite` | V12 LangGraph state for one grounded workflow session |
| `trusted_documents/` | Approved source material used for retrieval and citations |

The deterministic V12 suite runs 19 tests without Ollama, network access, a vector database, or persistent test databases. It covers source parsing, 14-section chunking, deterministic ranking, citation mapping, duplicate and malformed source rejection, invalid retrieval limits, item-level section checks, item-level quiz checks, retry behavior, and trusted-text fallback.

The verified end-to-end Conservation of Energy run recalled the V11 beginner profile, retrieved four approved chunks, produced three substantive cited sections and three independently cited quiz questions, received `approved` structured-review status, received `valid` deterministic citation status, and completed in about 3,056 seconds. The approved outcome was then saved to learner memory without storing generated notes as trusted facts.

## V13: Controlled Tool-Using Study Agent

V13 adds a bounded tool-use loop without granting the model arbitrary execution privileges. A structured controller may choose one of three approved local tools or return a final response grounded in validated observations.

The approved tools are:

| Tool | Purpose | Safety boundary |
|---|---|---|
| `calculator` | Evaluate study-related arithmetic | Parses numeric syntax with `ast`; no Python `eval`, names, functions, imports, or shell access |
| `unit_converter` | Convert approved length, mass, and time units | Uses a fixed unit table and rejects unknown units or cross-dimension conversions |
| `trusted_search` | Search the V12 approved Markdown corpus | Reuses deterministic retrieval and returns only validated `[S#]` citations |

Each call produces a `ToolObservation` with a stable `[T#]` reference. Final answers may cite only tool observations that actually ran and source citations returned by trusted search. Unknown tools, invalid arguments, unsafe arithmetic, missing references, invented citations, and malformed final actions fail closed.

The LangGraph loop is bounded to two tool calls. Model selection receives one corrective retry, then uses deterministic routing. The workflow never exposes a shell tool, arbitrary code execution, or a network tool. Its SQLite checkpoint store is separate from V10, V11, and V12 persistence.

The deterministic V13 suite runs 30 tests without Ollama, network access, LangGraph execution, or a persistent database. A verified end-to-end run selected `unit_converter`, converted 5 kilometers to 5,000 meters, retained `[T1]`, and completed successfully. A second test against the actual V12 corpus returned approved friction and energy passages with `[S1]`, `[S2]`, and `[T1]`, and passed deterministic observation validation.

## V14: Dynamic Planning and Agent Selection

V14 plans up to four tasks and selects only the required researcher, calculator,
or converter specialists. Ollama produces a structured plan; deterministic schema
checks validate task IDs, argument keys, and dependencies. Invalid model plans
receive one retry before deterministic routing takes over. Use semicolons to
separate independent requests, for example:

```text
Explain conservation of energy; Calculate (12 + 8) * 3; Convert 5 km to m
```

The researcher uses V12 retrieval with one citation map across the entire run.
Calculator and converter tasks use V13 tools. Every result includes its tool
reference; retrieved passages also have source citations and a source list.
The final report is assembled from validated tool results without model rewriting.

The evaluator checks completion of every planned task. Failed prerequisites block
dependent tasks. One replan may correct unfinished work, while completed tasks
remain frozen and are not executed again. Eight total tool executions are allowed.
Dependencies enforce order; they do not substitute numeric results into later
arguments. Offline mode uses deterministic planning with the same execution logic.

`study_guide_v14_runs.sqlite` saves final run snapshots tied to the session ID,
goal, corpus digest, and implementation version. A matching run can be reloaded
without model or tool calls. These snapshots cannot resume an interrupted run.
The database and its sidecar files stay local through the ignore rule
`study_guide_v14_runs.sqlite*`. V14 does not update learner memory.

Task completion confirms valid tool execution. It does not prove that an arbitrary
natural-language goal was decomposed correctly, that retrieval covered every
requested concept, or that the learner mastered the topic. See
[the V14 guide](docs/V14_GUIDE.md) for usage and limitations.

## V15: Evaluation, Tracing, Metrics, and Observability

V15 instruments the V14 workflow through node wrappers and a structured-model
wrapper. It records ordered traces, elapsed offsets, phase and model-call
durations, task outcomes, model attempts, rejected plans, deterministic planning
rounds, execution budgets, and task completion. The execution engine and earlier
version files remain reusable without modifications.

The local evaluator checks source and tool references against the run's evidence
and verifies that researcher passages retain their cited source text. A five-case
offline suite checks arithmetic, conversion, a compound request, division-by-zero
handling, and missing evidence against explicit expected results. A failure case
passes the evaluation when it produces the expected incomplete outcome.

Reports and traces are stored in `study_guide_v15_reports.sqlite` under unique
report IDs. Use `--show REPORT_ID` to reload a report and add `--trace` to inspect
its saved events without rerunning the model or tools. Keep the database and
sidecars local with `study_guide_v15_reports.sqlite*` in `.gitignore`.

Metrics have explicit limits: nested model timings overlap the planning phase,
individual tool latency is not measured, and token usage is unavailable rather
than estimated. Citation-ID integrity does not measure semantic entailment,
retrieval relevance, learner mastery, or completeness of an explanation. The
five fixed cases are an offline regression suite, not a broad model-quality
benchmark. See [the V15 guide](docs/V15_GUIDE.md) for precise definitions.

## V16: Multi-stage Human Approval and Interactive Revision

V16 uses LangGraph interrupts and SQLite checkpoints for three explicit review
points: plan approval before tool execution, content approval before assessment
preparation, and final approval before marking a session approved. A reviewer can
approve, revise a task's arguments, reject with a reason, or pause and resume the
saved session in a later process. Model planning may happen before plan review;
tools run only after approval.

Revisions return to plan review, clear earlier approvals and assessment questions,
and invalidate changed tasks and their dependent results. Unchanged successful
results can be retained. Up to three human revisions and eight tool executions
are permitted across the session. Failed content cannot be approved; the reviewer
must revise or reject it. Rejection ends the session and does not execute another
tool. Stale review IDs and malformed decisions cannot advance a gate.

Version `v16.2` displays each task's original request separately from the current
approved task derived from its arguments. Evidence questions use that approved
task, fixing the stale-label defect observed after revising `1 / 0` to `1 / 2`.
Questions are deterministic evidence-review prompts, not a scored assessment or
proof of learner mastery. Final approval does not update learner memory.

The local database is `study_guide_v16_checkpoints.sqlite`; exclude it and sidecars
with `study_guide_v16_checkpoints.sqlite*`. Resume a saved review using the exact
session command printed by the CLI, preserving offline/model mode. Resume checks
the implementation version and corpus digest. Older `v16.1` sessions remain
stored but cannot resume under `v16.2` because their assessment format differs.

These are resumable review checkpoints, unlike V14/V15 final run reports. Exactly-once
execution after a crash inside a tool node is not guaranteed; the CLI refuses
automatic replay when a session stopped outside a review gate. Use one local
process per session. This is a local review workflow without authenticated reviewer
identity or tamper-proof audit storage. See [the V16 guide](docs/V16_GUIDE.md).

## V17: Review Studio, JSON API, and Local Deployment

V17 exposes V16's workflow through a local browser application and an asynchronous
JSON API. Create sessions, inspect structured plans and results, approve each gate,
revise a complete plan with a reason, reject a session, reopen a saved view, and
export the session as JSON. Each task shows its original request and the current
task derived from its approved arguments. Review questions remain unscored.

The API queues model and workflow operations on one background worker and returns
202. Reads poll the latest saved view without invoking the workflow. A slow model
call can delay queued operations, while the HTTP API remains responsive. Review
IDs reject stale decisions; request IDs prevent the same accepted submission from
resuming a gate twice. Creation is not idempotent: inspect the session list after
a lost creation response before creating another session.

`v17_data/sessions.sqlite` stores web metadata and native LangGraph checkpoints.
Ignore the entire `v17_data/` directory, including database sidecars. This store
is separate from the V16 CLI database. Recovery inspection restores a saved review
gate or terminal state without replaying interrupted execution. Corpus and version
checks still apply. V17 does not update learner memory or import exported JSON as
runnable sessions.

The server binds to localhost by default, checks Host/Origin values, requires a
process-local token for writes, limits JSON body size, and serves only its explicit
static assets. These controls support local browser use; they do not authenticate
users or provide multi-user isolation. The Docker recipe was built and run with a
named data volume, and an approved session survived container replacement without
changes to its snapshot or execution count. See
[the V17 guide](docs/V17_GUIDE.md).

The live browser conversion run accepted an Ollama plan on attempt 2 after an
`OutputParserException` on attempt 1. It used zero deterministic planning rounds,
executed the converter once, returned `5 km = 5000 m [T1]`, and retained all three
human approvals. Planning took 526.872 seconds, about 8 minutes 47 seconds. This
is one verified workflow run, not a model-quality or latency benchmark.

A separate Docker-hosted conversion session also accepted model attempt 2 after
an initial parser error, used no deterministic fallback, returned `5000 m [T1]`,
and retained all three approvals. Its planning phase took 479.237 seconds, about
7 minutes 59 seconds. Replacing that container while keeping the named volume
restored the exact saved snapshot with one execution and three approvals.

## Validation and Reliability

The following V10 paths were verified:

1. A new workflow saved its state to SQLite.
2. A workflow paused before `quiz_producer`.
3. The paused workflow resumed without repeating completed nodes.
4. A completed session loaded without invoking Ollama again.
5. `Next scheduled nodes: ()` confirmed graph completion.
6. The command returned normally with exit code 0.
7. V9 and V10 compiled and imported successfully.
8. Python dependency checks passed.
9. The checkpoint database was confirmed as ignored by Git.

The deterministic regression test simulates two failed structured-review attempts. It confirms that V10:

- Uses the `fallback_approved` status
- Preserves the existing nonblank quiz
- Performs no quiz revision
- Routes directly to the end of the graph
- Makes no Ollama reviewer or quiz-reviser call

Expected test summary:

```text
V10 deterministic fallback test passed.
Structured reviewer attempts: 2
Review status: fallback_approved
Revision count: 0
Quiz preserved: True
Route after review: fallback_approved
No Ollama reviewer or quiz-reviser call was executed.
```

The following V11 paths were also verified:

1. Learner memory persisted after closing the program and restarting the laptop.
2. A second session recalled the saved level, preferences, completed topic, score, and mistake history.
3. Recalled beginner memory selected the beginner workflow route.
4. An invalid one-task orchestrator response used three validated fallback assignments.
5. The generated session ID and pre-generation confirmation gate worked correctly.
6. Declining confirmation exited without model generation.
7. Two completed topics and two quiz scores persisted across sessions.
8. All eight deterministic learner-memory tests passed without Ollama calls.

The following V12 paths were verified:

1. Two trusted Markdown sources loaded into 14 deterministic section chunks.
2. A friction query ranked the matching Conservation of Energy section first.
3. The no-generation confirmation path retrieved and displayed four cited chunks without calling Ollama.
4. Every final specialist section contained substantive text and an allowed citation.
5. Every quiz question contained an allowed citation.
6. Invalid specialist output received one corrective retry.
7. Deterministic trusted-source fallback remained available after a failed retry.
8. Unknown or missing citations blocked final validation and trusted-memory storage.
9. All 19 deterministic tests passed without Ollama or network calls.

The following V13 paths were verified:

1. Only `calculator`, `trusted_search`, and `unit_converter` are registered.
2. Unknown tool names fail without execution.
3. The calculator accepts bounded numeric arithmetic and rejects code, functions, imports, large exponents, and division by zero.
4. The unit converter validates units and measurement dimensions.
5. Trusted search preserves only citations returned by V12 retrieval.
6. Every observation receives a stable `[T#]` reference.
7. Final answers reject unknown tool references and invented source citations.
8. The agent loop is limited to two tool calls.
9. The real unit-conversion workflow completed with `5.0 km = 5000 m [T1]`.
10. All 30 deterministic tests passed without Ollama or network calls.

The following V14 paths were verified:

1. All 31 tests passed on Windows, including both LangGraph tests with no skips.
2. The offline compound request completed three tasks with zero replans, valid energy sources, arithmetic result `60 [T2]`, and conversion result `5000 m [T3]`.
3. The live Ollama run recorded `model_plan` on attempt 1 and three completed task events, with no planner retries or deterministic fallback recorded.
4. Division by zero produced `incomplete` after two executions and one replan, then exited normally.
5. Tests verify that completed tasks remain frozen, failed dependencies block execution, and replans cannot remove failed tasks.
6. Separate searches retain consistent source labels through one session-wide citation map.
7. SQLite connections close on success, early return, and error. This fixes the Windows file-lock failure discovered during initial testing.
8. Tests verify snapshot reload, duplicate-session rejection, and goal/corpus mismatch rejection without Ollama calls.

The following V15 evidence was recorded:

1. All 27 development tests passed, including both actual LangGraph execution tests.
2. The actual-corpus offline benchmark passed all five cases, including the two expected incomplete outcomes.
3. Reloading the saved benchmark returned the identical results and recorded durations without rerunning execution.
4. A live Ollama and LangGraph run completed three tasks with three tool attempts, zero replans, one model attempt, one accepted plan, and zero deterministic planning rounds.
5. The live run recorded `234683.861 ms` elapsed time and passed citation-ID integrity. Semantic entailment was explicitly not evaluated.
6. The live arithmetic result was `60 [T2]`; conversion returned `5000 m [T3]`. The researcher returned one cited Common forms of energy passage, which does not establish a complete explanation of conservation.
7. Tests verify connection closure after successful reads/writes, missing-report errors, and duplicate-report rejection, addressing the Windows file-handle issue found in V14.

The following V16 evidence was verified:

1. All 32 tests passed on Windows in about 0.906 seconds after the revised-label correction.
2. An offline two-task session paused at content review, exited, resumed in a new process, and received final approval with the execution count unchanged at two.
3. Human revision corrected a division-by-zero task to `1 / 2`, cleared prior approvals, returned to plan review, and completed after a second execution. The runtime check exposed the stale original-task label, which was corrected in `v16.2` and covered by regression tests.
4. A corrected `v16.2` model-mode run converted 5 km to 5000 m with one execution and all three review approvals. Model acceptance versus fallback is recorded in its checkpoint events and should be inspected separately.
5. Tests cover rejection at every gate, stale review decisions, dependent-result invalidation, revision/execution budgets, evidence integrity, and model-call preservation during resume.
6. Actual SQLite reopening and CLI pause/resume are tested, with explicit connection closure and file rename after the test connections close.

The following V17 evidence was verified:

1. All 25 authoring-environment tests passed with real loopback HTTP requests and native SQLite checkpoints, without Ollama calls. The 90 existing V14-V16 tests also passed there.
2. The Windows browser offline calculation/conversion session reached approved with two completed tasks, two tool attempts, and zero model attempts.
3. A fresh Windows browser revision test corrected `1 / 0` to `1 / 2`, returned `0.5 [T2]`, and reached approved at revision 1 with two cumulative tool attempts. The earlier session that exhausted three revisions was rejected.
4. The exported live-model session recorded `plan_retry` with `OutputParserException`, then `model_plan` on attempt 2. It recorded one accepted model plan, two model attempts, and zero deterministic planning rounds.
5. That live session returned `5 km = 5000 m [T1]` with one completed task, one execution, zero human revisions, three saved approvals, no pending review, and no session error.
6. A separate service test loaded the actual two trusted documents (14 chunks), completed three tasks through all approvals, and passed reference-ID integrity checks.
7. API tests cover stale and duplicate decisions, request-ID conflicts, restart persistence, recovery inspection without execution, corpus mismatch, input limits, local write protections, export, and connection closure.
8. Browser screenshots verify rendering and interactions; automated browser tests were not run. All 25 V17 tests also passed on Windows in 3.849 seconds.
9. The Docker image built successfully in 61.9 seconds using Python 3.12-slim on Linux/amd64. The container reached healthy and served the browser application.
10. Container-to-host Ollama access returned the installed qwen3.5:4b model. The exported container session recorded one accepted model plan on attempt 2, one parser retry, zero deterministic planning rounds, one converter execution, and all three human approvals.
11. The original container was removed and recreated with the same study-guide-v17-data volume mounted at /data. The API comparison returned ContainerReplaced=True, Status=approved, ToolExecutions=1, Approvals=3, and SnapshotUnchanged=True.
12. The manual Docker runtime check verified a completed session surviving replacement. The subsequent hosted CI probe also verified an unchanged pending content-review snapshot across replacement, review resume, stale-decision rejection, and duplicate-decision preservation. These checks do not establish crash-time exactly-once execution. Public deployment, LAN isolation, and automated container browser tests were not verified. Build-specific ignore enforcement on the older tested builder was not separately established.

## Observed Local Timings

Performance varies with hardware, prompt length, output length, and Ollama scheduling. Runtime measurements were recorded on the Windows laptop, including its Linux Docker engine. Test rows identify the environment used; authoring and Windows measurements are not directly comparable.

| Version | Observed workflow time |
|---|---:|
| V1: Plain Python sequential | About 547 seconds |
| V2: LangGraph sequential | About 455 seconds |
| V3: Simplifier | About 751 seconds |
| V4: Parallel specialists | About 555 seconds |
| V5: Orchestrator and subagents | About 611 seconds |
| V6: Beginner route | About 475 seconds |
| V6: Advanced route | About 788 seconds |
| V7: Human-in-the-loop | About 897 seconds, including human review |
| V8: Normal approval path | About 332 seconds |
| V8: Controlled revision demo | About 2,085 seconds |
| V9 | No reliable end-to-end timing recorded |
| V10: Pre-fix diagnostic run | About 6,505 seconds, which exposed the inherited reviewer-fallback defect |
| V10: Completed checkpoint load | About 0 seconds, with no Ollama calls |
| V10: Deterministic fallback test | Fast local test, with no Ollama calls |
| V11: Conservation of Energy session | About 2,281 seconds |
| V11: Deterministic memory tests | Fast local tests, with no Ollama calls |
| V12: Grounded Conservation of Energy session | About 3,056 seconds |
| V12: Deterministic retrieval and citation tests | Fast local tests, with no Ollama calls |
| V13: Controlled unit-conversion session | Completed locally; exact time was not recorded |
| V13: Deterministic tool tests | About 0.008 seconds, with no Ollama calls |
| V14: Deterministic planning tests | About 0.980 seconds for 31 tests on Windows |
| V14: Offline and Ollama runtime checks | Completed; exact workflow times were not recorded |
| V15: Live compound run | 234.684 seconds, about 3 minutes 55 seconds |
| V15: Fixed offline cases | About 0.196 to 0.711 milliseconds per case in the recorded run |
| V16: Human-review tests | About 0.906 seconds for 32 tests on Windows |
| V16: Review and model-mode sessions | Completed; total time including human review was not recorded |
| V17: Direct Windows live converter planning | 526.872 seconds, about 8 minutes 47 seconds, including one model retry |
| V17: Direct Windows converter execution phase | About 6.273 milliseconds for the observed specialist phase; not a per-tool benchmark |
| V17: API integration tests | 25 tests in 3.849 seconds on Windows; about 1.733 seconds in the authoring environment |
| V17: Docker image build | About 61.9 seconds in the recorded first build |
| V17: Docker-hosted live converter planning | 479.237 seconds, about 7 minutes 59 seconds, including one model retry |
| V17: Docker-hosted converter execution phase | About 6.726 milliseconds for the observed specialist phase; not a per-tool benchmark |

The long V10 diagnostic run identified a reliability problem inherited from the V9 review loop. The tested fallback correction now prevents parser failure from triggering repeated quiz revisions.

## Lessons Learned

- A multi-agent system can be built with regular Python and focused LLM calls.
- LangGraph makes state, branching, parallel execution, interrupts, and loops explicit.
- More agents do not automatically produce better results.
- Smaller local models benefit from focused prompts and constrained responsibilities.
- Structured output still requires retry and fallback behavior.
- Parser failure is not proof that generated content is invalid.
- Durable checkpoints prevent completed work from being repeated.
- Long-term learner memory must remain separate from per-session workflow checkpoints.
- Only validated learner facts and approved outcomes should become trusted memory.
- Retrieval should expose stable source metadata and deterministic citation labels.
- Citation validity must be checked per section and per question, not only across the combined document.
- A grounded workflow needs deterministic fallback content when a local model returns blank or uncited text.
- Tool use should begin with a closed allowlist rather than arbitrary capabilities.
- Tool arguments, observations, and final references require independent validation.
- Deterministic local tools can provide exact results while the model remains responsible only for bounded selection and explanation.
- Replanning should preserve completed evidence and use an explicit execution budget.
- Distinguish model-produced plans from deterministic fallback in recorded events.
- A SQLite transaction context does not close its connection; close it explicitly for reliable Windows cleanup.
- Saved run reports and resumable workflow checkpoints have different recovery guarantees.
- Separate execution completion and citation integrity from answer quality and semantic coverage.
- Record actual model attempts and fallback events instead of inferring model success from the final result.
- Evaluation pass rates need explicit expected outcomes and a clearly stated benchmark scope.
- Keep approval gates separate from model and tool nodes so review resume does not repeat completed work.
- Human revision must invalidate earlier approvals and results affected by changed task arguments.
- Distinguish the original request from the currently approved task in result labels and assessment questions.
- Human review remains useful when approval matters more than speed.
- A responsive web API can queue slow model work while preserving explicit human execution gates.
- Model mode alone does not prove model-plan acceptance; inspect retry and fallback events.
- A process-local browser write token is not user authentication or multi-user isolation.
- A named volume must be tested across container replacement, not inferred from its mount configuration alone.
- Local LLM output should still be checked for factual accuracy.

## Project Origin and Extension History

This repository began as a hands-on implementation of Darsh Shah's freeCodeCamp article, [How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/), published July 14, 2026.

The source tutorial provides two study-guide implementations:

- V1: Plain Python sequential workflow
- V2: LangGraph sequential workflow

Starting with V3, this repository extends the tutorial by implementing, testing, debugging, and preserving each new capability as a separate version.

| Project stage | Versions | Provenance |
|---|---|---|
| Tutorial baseline | V1-V2 | Implementations based on the freeCodeCamp tutorial |
| Extended learning project | V3-V16 | New implementations developed for this repository |
| Application delivery | V17 | Local browser UI, asynchronous JSON API, persisted review sessions, and verified local Docker deployment |

The versioned structure makes it possible to compare architectures, observe the reason for each extension, and retain working examples from every stage.

## Acknowledgements

Inspired by Darsh Shah's freeCodeCamp tutorial, [How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/).
