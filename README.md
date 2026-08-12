\# Multi-Agent Study Guide with Python, LangGraph, Ollama, and Qwen



A collection of local multi-agent workflows that generate study guides using Python, LangGraph, Ollama, and the `qwen3.5:4b` model.



This project demonstrates six common multi-agent workflow patterns:



1\. Sequential pipeline

2\. Parallel specialists

3\. Orchestrator-subagent

4\. Supervisor/router

5\. Human-in-the-loop

6\. Review/refinement loop



All LLM calls run locally through Ollama, so no paid API key is required.



\## What Is an Agent Here?



In this project, an agent is a focused LLM call with:



\- A specific responsibility

\- Its own prompt and instructions

\- A defined position in the workflow



Agents collaborate by passing their outputs through regular Python variables or LangGraph shared state.



\## Project Files



| File | Architecture | Description |

|---|---|---|

| `study\_guide\_v1.py` | Plain Python sequential | Planner, teacher, and quiz writer coordinated with regular Python |

| `study\_guide\_v2.py` | LangGraph sequential | Reimplements V1 using nodes, edges, and shared state |

| `study\_guide\_v3\_simplifier.py` | Extended sequential | Adds a fourth agent that simplifies the notes |

| `study\_guide\_v4\_parallel.py` | Parallel specialists | Concepts, examples, and quiz agents run independently before merging |

| `study\_guide\_v5\_orchestrator.py` | Orchestrator-subagent | Creates assignments and dynamically delegates them to parallel subagents |

| `study\_guide\_v6\_router.py` | Supervisor/router | Selects either a beginner or advanced teacher |

| `study\_guide\_v7\_human\_loop.py` | Human-in-the-loop | Pauses for human outline approval or revision feedback |

| `study\_guide\_v8\_review\_loop.py` | Review/refinement loop | Reviews the quiz and sends it back for revision when necessary |



| `study_guide_v9_structured_outputs.py` | Structured outputs | Adds typed reviewer output, retry handling, safe fallback behavior, and explicit review routing |
| `study_guide_v10_checkpointing.py` | Persistent checkpointing | Adds SQLite persistence, pause/resume, completed-session loading, and recovery without repeating completed nodes |
| `test_v10_reviewer_fallback.py` | Deterministic regression test | Forces structured-review failure and verifies quiz preservation without invoking Ollama |

\## Requirements



\- Python

\- \[Ollama](https://ollama.com/)

\- Ollama model `qwen3.5:4b`

\- `langchain-ollama`

\- `langgraph`



Developed and tested on Windows with Python 3.14.



\## Installation



\### 1. Install Ollama



Download Ollama from:



https://ollama.com/download



\### 2. Pull the model



```powershell

ollama pull qwen3.5:4b

```



\### 3. Create a virtual environment



Windows PowerShell:



```powershell

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

```



macOS or Linux:



```bash

python3 -m venv .venv

source .venv/bin/activate

```



\### 4. Install dependencies



```powershell

python -m pip install -r requirements.txt

```



\## Running the Examples



| Version | Command |

|---|---|

| V1 - Plain Python | `python .\\study\_guide\_v1.py` |

| V2 - LangGraph sequential | `python .\\study\_guide\_v2.py` |

| V3 - Simplifier | `python .\\study\_guide\_v3\_simplifier.py` |

| V4 - Parallel specialists | `python .\\study\_guide\_v4\_parallel.py` |

| V5 - Orchestrator-subagent | `python .\\study\_guide\_v5\_orchestrator.py` |

| V6 - Supervisor/router | `python .\\study\_guide\_v6\_router.py` |

| V7 - Human-in-the-loop | `python .\\study\_guide\_v7\_human\_loop.py` |

| V8 - Review/refinement | `python .\\study\_guide\_v8\_review\_loop.py` |



| V9 - Structured outputs | `python .\study_guide_v9_structured_outputs.py` |
| V10 - Persistent checkpointing | `python .\study_guide_v10_checkpointing.py` |
| V10 - Pause before quiz | `python .\study_guide_v10_checkpointing.py --pause-before-quiz` |
| V10 - Fallback regression test | `python .\test_v10_reviewer_fallback.py` |

To demonstrate V8's revision branch with an intentionally flawed initial quiz:



```powershell

python .\\study\_guide\_v8\_review\_loop.py --demo-revision

```



\## Workflow Patterns



\### Sequential Pipeline



One specialist passes its output to the next in a fixed order. V1 shows that this requires very little regular Python. V2 expresses the same flow as a LangGraph graph.



\### Parallel Specialists



Multiple agents work independently on the same input. Their outputs are collected and merged after all parallel branches finish.



\### Orchestrator-Subagent



An orchestrator analyzes the topic, creates assignments, and dynamically delegates them to parallel subagents.



\### Supervisor/Router



A routing agent examines the learner description and selects either a beginner or advanced teaching branch.



\### Human-in-the-Loop



The graph pauses after preparing an outline. A human can approve it or reject it with revision feedback.



Example rejection:



```text

reject: Make each section practical and include one real-world example.

```



\### Review/Refinement Loop



A producer writes a quiz and a reviewer evaluates it against explicit requirements. Rejected quizzes return to a revision node until approved or the revision limit is reached.



### Structured Outputs and Safe Review - V9

V9 extends the V8 review/refinement workflow with a typed `ReviewResult` schema. The reviewer returns a constrained status and specific feedback rather than unrestricted text.

V9 demonstrates:

- Structured reviewer output with schema validation.
- Retry handling for malformed or empty local-model output.
- A maximum-revision safeguard.
- Explicit routing between approval, quiz revision, and termination.
- Safe handling of the malformed reviewer response encountered in V8.

### Persistent Checkpointing and Recovery - V10

V10 adds durable LangGraph state through `SqliteSaver`. Each workflow session has a thread ID and can be resumed after the Python process exits.

V10 demonstrates:

- Starting and saving a new named session.
- Persisting graph state in `study_guide_checkpoints.sqlite`.
- Pausing immediately before `quiz_producer`.
- Resuming without repeating completed nodes.
- Loading a completed session without rerunning Ollama calls.
- Reporting the next scheduled graph nodes.
- Keeping the local checkpoint database and sidecar files out of Git.

Start or load a session:

```powershell
python .\study_guide_v10_checkpointing.py
```

Pause immediately before quiz generation:

```powershell
python .\study_guide_v10_checkpointing.py --pause-before-quiz
```

Run the same command again with the same thread ID and select `R` to resume at `quiz_producer` without repeating the completed work.

A completed checkpoint reports:

```text
Checkpoint saved successfully.
Next scheduled nodes: ()
```

### V10 Reviewer-Fallback Correction

A clean V10 diagnostic run exposed an inherited V9 failure mode: malformed structured-review output could trigger repeated expensive quiz revisions, while an empty reviser response could overwrite an existing quiz.

V10 now:

- Preserves the current quiz when structured parsing fails.
- Records the explicit `fallback_approved` status.
- Routes `fallback_approved` directly to `END`.
- Preserves the previous quiz if `quiz_reviser` returns blank.
- Avoids treating parser failure as evidence that the quiz is invalid.
- Prevents repeated revision calls caused solely by parser failure.

Run the deterministic regression test:

```powershell
python .\test_v10_reviewer_fallback.py
```

Verified result:

```text
V10 deterministic fallback test passed.
Structured reviewer attempts: 2
Review status: fallback_approved
Revision count: 0
Quiz preserved: True
Route after review: fallback_approved
No Ollama reviewer or quiz-reviser call was executed.
```

### V10 Checkpoint Validation

The following persistence and recovery paths were verified:

1. A new workflow saved its state to SQLite.
2. A workflow paused before `quiz_producer`.
3. The paused workflow resumed without repeating completed nodes.
4. A completed session loaded without invoking Ollama again.
5. `Next scheduled nodes: ()` confirmed graph completion.
6. The command returned normally with exit code `0`.
7. V10 imported safely without starting its interactive command-line path.

\## Observed Local Timings



Performance varies with hardware, prompt length, generated output, and Ollama scheduling. These measurements came from one development machine.



| Version | Observed workflow time |

|---|---:|

| V1 - Plain Python sequential | About 547 seconds |

| V2 - LangGraph sequential | About 455 seconds |

| V3 - Simplifier | About 751 seconds |

| V4 - Parallel specialists | About 555 seconds |

| V5 - Orchestrator-subagent | About 611 seconds |

| V6 - Beginner route | About 475 seconds |

| V6 - Advanced route | About 788 seconds |

| V7 - Human-in-the-loop | About 897 seconds, including human review |

| V8 - Normal approval path | About 332 seconds |

| V8 - Controlled revision demo | About 2,085 seconds |



| V10 - Clean pre-fix diagnostic run | About 6,505 seconds; exposed the inherited structured-review fallback defect |
| V10 - Completed checkpoint load | About 0 seconds; no Ollama calls |
| V10 - Deterministic fallback test | Fast local test; no Ollama calls |

\## Lessons Learned



\- A multi-agent system can be built using regular Python and focused LLM calls.

\- LangGraph makes state, branching, parallel execution, interrupts, and loops explicit.

\- More agents do not automatically produce better results.

\- Smaller local models benefit from focused prompts and constrained responsibilities.

\- Review nodes need strict output formats and safe handling of malformed responses.

\- Human review is useful when approval matters more than speed.

\- Local LLM output should still be checked for factual accuracy.



## Project Origin and Extension History

This repository began as a hands-on implementation of Darsh Shah's freeCodeCamp article, [How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/), published July 14, 2026.

The source tutorial provides two working study-guide implementations:

- **V1 ΓÇö Plain Python sequential workflow:** a planner, teacher, and quiz writer coordinated with regular Python.
- **V2 ΓÇö LangGraph sequential workflow:** the same three-stage pipeline expressed with nodes, edges, and shared graph state.

The tutorial also introduces several multi-agent patterns conceptually and encourages readers to extend the example. Starting with V3, this repository goes beyond the tutorial by implementing, testing, debugging, and preserving each extension as a separate version.

| Project stage | Versions | Provenance |
|---|---|---|
| Tutorial baseline | V1ΓÇôV2 | Implementations based on the freeCodeCamp tutorial |
| Extended learning project | V3ΓÇôV9 | New implementations developed for this repository |
| Forward roadmap | V10ΓÇôV17 | Planned extensions that continue building on the accumulated project |

V3ΓÇôV9 do not replace the freeCodeCamp baseline. They preserve it and progressively add simplification, parallel execution, dynamic delegation, routing, human approval, review and revision, structured outputs, synthesis, retries, validation, and safe failure handling. This versioned structure makes it possible to compare each architecture with the one before it and understand why each new capability was added.


## Version Roadmap

| Version | Capability introduced |
|---|---|
| V1 | Plain Python sequential agents |
| V2 | LangGraph sequential workflow |
| V3 | Notes simplification |
| V4 | Parallel specialist workers |
| V5 | Orchestrator-subagent delegation |
| V6 | Supervisor routing |
| V7 | Human-in-the-loop approval |
| V8 | Automated review and refinement |
| V9 | Structured reviewer outputs, retry handling, and safe fallback |
| V10 | Persistent SQLite checkpointing and workflow recovery |

The original freeCodeCamp tutorial inspired the sequential foundation. V3 through V10 are project extensions that progressively add simplification, parallel execution, orchestration, routing, human approval, automated review, structured outputs, fallback reliability, and durable recovery.

\## Acknowledgements



Inspired by the freeCodeCamp tutorial:



\[How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/)



This project extends the original sequential example with simplification, parallel execution, dynamic delegation, routing, human approval, and automated review loops.
