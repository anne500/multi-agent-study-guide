from typing import Annotated, TypedDict
import operator
import re
import time

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

# Local Ollama model shared by the orchestrator, workers, and synthesizer.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


# Main graph state.
class OrchestratorState(TypedDict):
    topic: str
    tasks: list[str]
    completed_sections: Annotated[list[tuple[int, str]], operator.add]
    final_guide: str


# State sent separately to each dynamically created worker.
class WorkerState(TypedDict):
    topic: str
    task_number: int
    task: str


def ask(system: str, user: str) -> str:
    """Run one LLM call with a system prompt and user input."""
    response = MODEL.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return response.content


def run_node(name: str, system: str, user: str) -> str:
    """Run a node and report how long it takes."""
    print(f"Calling node {name}...")
    start = time.time()
    result = ask(system, user)
    print(f"Finished {name} in {time.time() - start:.1f}s")
    return result


def extract_tasks(plan: str) -> list[str]:
    """Extract three numbered tasks from the orchestrator response."""
    tasks = []

    for line in plan.splitlines():
        match = re.match(
            r"^\s*(?:Task\s*)?([1-3])[\.\):\-]\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )

        if match:
            tasks.append(match.group(2).strip())

    # Reliable fallback if the local model does not follow the format.
    if len(tasks) != 3:
        tasks = [
            "Explain exactly three key concepts in beginner-friendly language.",
            "Provide exactly three concrete real-world examples.",
            "Write exactly three review questions without answers.",
        ]

    return tasks


# Orchestrator: plan three topic-specific worker assignments.
def orchestrator(state: OrchestratorState) -> dict:
    plan = run_node(
        "orchestrator",
        (
            "Break the topic into exactly 3 non-overlapping assignments for "
            "specialist workers creating a beginner study guide. Together, the "
            "assignments must cover key concepts, concrete examples, and review "
            "questions. Return only 3 numbered lines in this format:\n"
            "1. assignment\n"
            "2. assignment\n"
            "3. assignment"
        ),
        state["topic"],
    )

    tasks = extract_tasks(plan)

    print("\nOrchestrator delegated these tasks:")
    for number, task in enumerate(tasks, start=1):
        print(f"  {number}. {task}")
    print()

    return {"tasks": tasks}


# Dynamic routing: create one worker for each orchestrator task.
def assign_workers(state: OrchestratorState):
    return [
        Send(
            "subagent",
            {
                "topic": state["topic"],
                "task_number": index,
                "task": task,
            },
        )
        for index, task in enumerate(state["tasks"])
    ]


# Worker: complete one delegated task.
def subagent(state: WorkerState) -> dict:
    task_number = state["task_number"]
    task = state["task"]

    result = run_node(
        f"subagent_{task_number + 1}",
        (
            "You are a specialist worker. Complete only the assignment delegated "
            "to you. Keep the content accurate, concise, and beginner-friendly. "
            "Return only your completed section."
        ),
        f"Topic: {state['topic']}\n\nAssignment: {task}",
    )

    return {"completed_sections": [(task_number, result)]}


# Synthesizer: deterministically combine all worker results.
def synthesizer(state: OrchestratorState) -> dict:
    print("Combining worker outputs in synthesizer...")
    start = time.time()

    ordered_sections = sorted(
        state["completed_sections"],
        key=lambda item: item[0],
    )

    final_sections = []

    for number, content in ordered_sections:
        task = state["tasks"][number]

        final_sections.append(
            f"## Delegated Section {number + 1}\n\n"
            f"**Assignment:** {task}\n\n"
            f"{content}"
        )

    final_guide = "\n\n---\n\n".join(final_sections)

    print(f"Finished synthesizer in {time.time() - start:.1f}s")
    return {"final_guide": final_guide}

def build_graph():
    graph = StateGraph(OrchestratorState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("subagent", subagent)
    graph.add_node("synthesizer", synthesizer)

    graph.add_edge(START, "orchestrator")

    # The orchestrator dynamically creates workers with Send.
    graph.add_conditional_edges(
        "orchestrator",
        assign_workers,
        ["subagent"],
    )

    # The synthesizer waits for all dynamic workers.
    graph.add_edge("subagent", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


if __name__ == "__main__":
    print("Warming up model...")
    MODEL.invoke("Say ready.")
    print("Model ready.\n")

    app = build_graph()
    topic = input("Enter a study topic: ").strip()

    workflow_start = time.time()

    result = app.invoke({
        "topic": topic,
        "tasks": [],
        "completed_sections": [],
        "final_guide": "",
    })

    total_time = time.time() - workflow_start

    print(
        f"\n# Orchestrated Study Guide: {topic}\n\n"
        f"{result['final_guide']}\n\n"
        f"Total workflow time: {total_time:.1f}s"
    )