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



\## Lessons Learned



\- A multi-agent system can be built using regular Python and focused LLM calls.

\- LangGraph makes state, branching, parallel execution, interrupts, and loops explicit.

\- More agents do not automatically produce better results.

\- Smaller local models benefit from focused prompts and constrained responsibilities.

\- Review nodes need strict output formats and safe handling of malformed responses.

\- Human review is useful when approval matters more than speed.

\- Local LLM output should still be checked for factual accuracy.



\## Acknowledgements



Inspired by the freeCodeCamp tutorial:



\[How to Build Your First Multi-Agent AI System in Python and LangGraph](https://www.freecodecamp.org/news/how-to-build-your-first-multi-agent-ai-system-in-python-and-langgraph/)



This project extends the original sequential example with simplification, parallel execution, dynamic delegation, routing, human approval, and automated review loops.

