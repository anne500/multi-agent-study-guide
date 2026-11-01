# Multi-Agent Study Guide with Python, LangGraph, Ollama, and Qwen

A versioned learning project that builds local multi-agent study-guide workflows with Python, LangGraph, Ollama, and the `qwen3.5:4b` model.

The repository starts with a simple sequential pipeline and progressively adds graph orchestration, parallel workers, routing, human approval, automated review, structured outputs, safe fallback behavior, persistent checkpoint recovery, cross-session learner memory, trusted retrieval with verified citations, and controlled tool use.

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
| V15 | Evaluation, tracing, metrics, and observability | Planned |
| V16 | Multi-stage human approval and interactive revision | Planned |
| V17 | User application, API, and deployment | Planned |

See the [V1-V17 Architecture Guide](docs/ARCHITECTURE.md) for a detailed workflow diagram and explanation of every version.

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
| `docs/ARCHITECTURE.md` | Architecture reference | Shows implemented V1-V14 workflows and planned V15-V17 designs with detailed diagrams |

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
python -m pip install -r requirements.txt
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

## Observed Local Timings

Performance varies with hardware, prompt length, output length, and Ollama scheduling. These measurements came from one development machine.

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
- Human review remains useful when approval matters more than speed.
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
| Extended learning project | V3-V14 | New implementations developed for this repository |
| Planned extensions | V15-V17 | Evaluation, human control, and deployment |

The versioned structure makes it possible to compare architectures, observe the reason for each extension, and retain working examples from every stage.

## Acknowledgements

Inspired by Darsh Shah's freeCodeCamp tutorial, [How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/).
