# Multi-Agent Study Guide with Python, LangGraph, Ollama, and Qwen

A versioned learning project that builds local multi-agent study-guide workflows with Python, LangGraph, Ollama, and the `qwen3.5:4b` model.

The repository starts with a simple sequential pipeline and progressively adds graph orchestration, parallel workers, routing, human approval, automated review, structured outputs, safe fallback behavior, and persistent checkpoint recovery.

All LLM calls run locally through Ollama. No paid API key is required.

## Version Roadmap

| Version | Capability introduced |
|---|---|
| V1 | Plain Python sequential agents |
| V2 | LangGraph sequential workflow |
| V3 | Notes simplification |
| V4 | Parallel specialist workers |
| V5 | Orchestrator and subagent delegation |
| V6 | Supervisor routing |
| V7 | Human-in-the-loop approval |
| V8 | Automated review and refinement |
| V9 | Structured outputs, retry handling, orchestration, and safe fallback |
| V10 | Persistent SQLite checkpointing and workflow recovery |

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

## Requirements

- Python
- [Ollama](https://ollama.com/)
- Ollama model `qwen3.5:4b`
- `langchain-ollama`
- `langgraph`
- `langgraph-checkpoint-sqlite`

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

## Workflow Architecture

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

The long V10 diagnostic run identified a reliability problem inherited from the V9 review loop. The tested fallback correction now prevents parser failure from triggering repeated quiz revisions.

## Lessons Learned

- A multi-agent system can be built with regular Python and focused LLM calls.
- LangGraph makes state, branching, parallel execution, interrupts, and loops explicit.
- More agents do not automatically produce better results.
- Smaller local models benefit from focused prompts and constrained responsibilities.
- Structured output still requires retry and fallback behavior.
- Parser failure is not proof that generated content is invalid.
- Durable checkpoints prevent completed work from being repeated.
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
| Extended learning project | V3-V10 | New implementations developed for this repository |
| Future development | V11 and later | Planned extensions that build on the completed V1-V10 foundation |

The versioned structure makes it possible to compare architectures, observe the reason for each extension, and retain working examples from every stage.

## Acknowledgements

Inspired by Darsh Shah's freeCodeCamp tutorial, [How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/).
