# Architecture Guide

This guide shows how the multi-agent study guide evolves from a simple Python pipeline into a complete application architecture. Each diagram uses the actual project components and routing behavior.

- V1-V10 are implemented.
- V11-V17 are planned designs. Their diagrams will be checked and updated when each version is implemented.
- Solid arrows show the normal execution path.
- Labeled branches show conditional routing, review decisions, or recovery behavior.

## Architecture evolution

| Stage | Versions | Main idea |
|---|---|---|
| Foundations | V1-V3 | Sequential generation and clearer notes |
| Coordination | V4-V6 | Parallel work, delegation, and routing |
| Control | V7-V8 | Human approval and automated refinement |
| Reliability | V9-V10 | Structured outputs, fallbacks, and persistent recovery |
| Context | V11-V13 | Long-term memory, retrieval, and tools |
| Adaptation | V14-V16 | Dynamic planning, evaluation, and human control |
| Delivery | V17 | Application, API, persistence, and deployment |

## V1: Plain Python sequential agents

**Status:** Implemented

V1 passes ordinary Python return values from one focused LLM call to the next. There is no graph runtime or shared state object.

```mermaid
flowchart LR
    A[Topic] --> B[Planner]
    B -->|Outline| C[Teacher]
    C -->|Notes| D[Quiz writer]
    D --> E[Study guide]
```

## V2: LangGraph sequential workflow

**Status:** Implemented

V2 preserves the V1 sequence but moves orchestration into a LangGraph state graph. Each node reads and updates shared `StudyState`.

```mermaid
flowchart LR
    A([START]) --> B[Planner node]
    B --> C[Teacher node]
    C --> D[Quiz writer node]
    D --> E([END])
```

## V3: Sequential simplification

**Status:** Implemented

V3 adds a simplifier between teaching and quiz generation so the quiz is based on the clearer notes.

```mermaid
flowchart LR
    A([START]) --> B[Planner]
    B --> C[Teacher]
    C --> D[Simplifier]
    D --> E[Quiz writer]
    E --> F([END])
```

## V4: Parallel specialist workers

**Status:** Implemented

Three specialists receive the same topic at the same time. LangGraph waits for all branches before the merger creates the final guide.

```mermaid
flowchart TD
    A([START]) --> B[Concepts agent]
    A --> C[Examples agent]
    A --> D[Quiz agent]
    B --> E[Merger]
    C --> E
    D --> E
    E --> F([END])
```

## V5: Orchestrator and delegated subagents

**Status:** Implemented

The orchestrator creates task assignments. `Send` dynamically launches a subagent for each assignment, and the synthesizer combines their results.

```mermaid
flowchart TD
    A([START]) --> B[Orchestrator]
    B -->|Assignment 1| C[Subagent]
    B -->|Assignment 2| D[Subagent]
    B -->|Assignment 3| E[Subagent]
    C --> F[Synthesizer]
    D --> F
    E --> F
    F --> G([END])
```

## V6: Supervisor routing

**Status:** Implemented

The router classifies the requested learning level. Only the selected teacher branch runs before the shared quiz writer.

```mermaid
flowchart TD
    A([START]) --> B[Router]
    B -->|Beginner| C[Beginner teacher]
    B -->|Advanced| D[Advanced teacher]
    C --> E[Quiz writer]
    D --> E
    E --> F([END])
```

## V7: Human approval loop

**Status:** Implemented

The graph interrupts after an outline is prepared. Approval continues to teaching, while rejection stores feedback and loops through outline revision.

```mermaid
flowchart TD
    A([START]) --> B[Planner]
    B --> C[Human review interrupt]
    C -->|Approve| D[Teacher]
    C -->|Reject with feedback| E[Revise outline]
    E --> C
    D --> F[Quiz writer]
    F --> G([END])
```

## V8: Automated review and refinement

**Status:** Implemented

The reviewer checks the generated quiz. A rejected quiz goes to the reviser and returns for another review. Approval or the revision limit ends the graph.

```mermaid
flowchart TD
    A([START]) --> B[Teacher]
    B --> C[Quiz producer]
    C --> D[Reviewer]
    D -->|Approved| E([END])
    D -->|Revision required| F[Quiz reviser]
    F --> D
    D -->|Maximum revisions| E
```

## V9: Structured multi-agent workflow

**Status:** Implemented

V9 combines validated routing, structured assignment planning, dynamic parallel workers, synthesis, quiz generation, structured review, retry controls, and safe termination.

```mermaid
flowchart TD
    A([START]) --> B[Structured router]
    B --> C[Structured orchestrator]
    C -->|Three validated assignments| D[Parallel subagents]
    D --> E[Synthesizer]
    E --> F[Quiz producer]
    F --> G[Structured reviewer]
    G -->|Approved| H([END])
    G -->|Revision required| I[Quiz reviser]
    I --> G
    G -->|Retry or fallback| H
```

### V9 reliability controls

```mermaid
flowchart LR
    A[Model response] --> B{Schema valid?}
    B -->|Yes| C[Use structured result]
    B -->|No| D[Retry once]
    D --> E{Retry valid?}
    E -->|Yes| C
    E -->|No| F[Safe fallback]
```

## V10: Persistent checkpointing and recovery

**Status:** Implemented

V10 compiles the V9 graph with `SqliteSaver`. A thread ID connects each session to durable graph state, allowing pause, resume, completed-session loading, and recovery without repeating completed nodes.

```mermaid
flowchart TD
    A[Session ID] --> B{Checkpoint exists?}
    B -->|No| C[Start V9 workflow]
    B -->|Yes, unfinished| D[Resume next node]
    B -->|Yes, complete| E[Load saved result]
    C <--> F[(SQLite checkpoints)]
    D <--> F
    E <--> F
    C --> G{Pause requested?}
    G -->|Before quiz| H[Save and exit]
    G -->|No| I[Continue to completion]
```

### V10 workflow with persistence

```mermaid
flowchart LR
    A[Router and orchestrator] --> B[Parallel workers]
    B --> C[Synthesizer]
    C --> D[Quiz and review]
    D --> E[Final result]
    A <--> F[(SQLite state)]
    B <--> F
    C <--> F
    D <--> F
```

## V11: Cross-session learner memory

**Status:** Planned

V11 will separate durable learner memory from per-run checkpoints. The workflow will read relevant preferences and progress before planning, then save verified learning outcomes after the session.

```mermaid
flowchart TD
    A[Topic and learner ID] --> B[Recall learner memory]
    B <--> C[(Learner memory store)]
    B --> D[Personalized V10 workflow]
    D --> E[Study guide and quiz result]
    E --> F[Extract verified memory]
    F --> C
```

Planned memory includes learner level, preferences, completed topics, quiz performance, recurring mistakes, and progress. Temporary model text will not be saved as trusted memory without validation.

## V12: Retrieval with trusted documents and citations

**Status:** Planned

V12 will ground study content in approved local sources. Retrieved chunks and source metadata will flow into generation so the final guide can cite its evidence.

```mermaid
flowchart TD
    A[Learning request] --> B[Retriever]
    C[(Trusted documents)] --> B
    B --> D[Relevant cited context]
    D --> E[Grounded study agents]
    E --> F[Study guide with citations]
    F --> G[Citation verifier]
```

## V13: Tool-using study agents

**Status:** Planned

V13 will let an agent choose from a controlled tool registry. Tool results return as observations before the agent produces its final response.

```mermaid
flowchart TD
    A[Study task] --> B[Tool-aware agent]
    B --> C{Tool needed?}
    C -->|No| D[Final response]
    C -->|Yes| E[Approved tool]
    E --> F[Validated observation]
    F --> B
```

## V14: Dynamic planning and agent selection

**Status:** Planned

V14 will create a plan from the request, select only the required agents and tools, evaluate intermediate progress, and replan when a task fails or new information changes the path.

```mermaid
flowchart TD
    A[Learning goal] --> B[Dynamic planner]
    B --> C[Task decomposition]
    C --> D[Agent and tool selection]
    D --> E[Execute current task]
    E --> F{Goal satisfied?}
    F -->|Yes| G[Final synthesis]
    F -->|No| B
```

## V15: Evaluation and observability

**Status:** Planned

V15 will instrument workflow execution and evaluate output quality. Traces, latency, route choices, retries, retrieval quality, and learning-quality checks will support debugging and comparison.

```mermaid
flowchart TD
    A[Instrumented workflow] --> B[Events and traces]
    A --> C[Generated artifacts]
    B --> D[(Trace and metric store)]
    C --> E[Quality evaluators]
    E --> D
    D --> F[Evaluation report]
    F --> G[Regression decision]
```

## V16: Multi-stage human approval

**Status:** Planned

V16 will expand V7 from one outline decision to several controlled review points. A learner can approve, edit, reject, or redirect important state before execution continues.

```mermaid
flowchart TD
    A[Plan] --> B{Human plan review}
    B -->|Approve or edit| C[Generate content]
    B -->|Reject| A
    C --> D{Human content review}
    D -->|Approve or edit| E[Generate assessment]
    D -->|Reject| C
    E --> F{Final approval}
    F -->|Approve| G[Complete session]
    F -->|Revise| C
```

## V17: Application and deployment

**Status:** Planned

V17 will expose the workflow through a user application and API. The service architecture will combine local model inference, checkpoint state, learner memory, trusted retrieval, tools, and observability.

```mermaid
flowchart TD
    A[Web or command-line client] --> B[Application API]
    B --> C[Workflow service]
    C --> D[Ollama model]
    C --> E[(Checkpoints and memory)]
    C --> F[(Trusted document index)]
    C --> G[Approved tools]
    C --> H[Evaluation and telemetry]
```

## Version relationships

Later versions build on earlier capabilities, but every file remains runnable as a separate learning example.

```mermaid
flowchart TD
    A[V1-V3 Foundations] --> B[V4-V6 Coordination]
    B --> C[V7-V8 Control loops]
    C --> D[V9-V10 Reliability]
    D --> E[V11-V13 Context]
    E --> F[V14-V16 Adaptation]
    F --> G[V17 Delivery]
```

The planned architecture is intentionally incremental. V11-V17 will be implemented as separate versions, tested, documented, and compared without replacing the earlier examples.
