from typing import TypedDict
import time
import uuid

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

# Local Ollama model used by the AI nodes.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


# Shared state for the human-in-the-loop workflow.
class HumanLoopState(TypedDict):
    topic: str
    outline: str
    approval: str
    feedback: str
    notes: str
    quiz: str


def ask(system: str, user: str) -> str:
    """Run one LLM call with a system prompt and user input."""
    response = MODEL.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return response.content


def run_node(name: str, system: str, user: str) -> str:
    """Run an AI node and report how long it takes."""
    print(f"Calling node {name}...")
    start = time.time()
    result = ask(system, user)
    print(f"Finished {name} in {time.time() - start:.1f}s")
    return result


# Node 1: create the initial outline.
def planner(state: HumanLoopState) -> dict:
    return {
        "outline": run_node(
            "planner",
            (
                "Create exactly 3 logical study sections for this topic. "
                "Return a concise numbered outline."
            ),
            state["topic"],
        )
    }


# Human review node: pause the graph and wait for approval or rejection.
def human_review(state: HumanLoopState) -> dict:
    human_response = interrupt({
        "topic": state["topic"],
        "outline": state["outline"],
        "instructions": (
            "Type approve to continue, or type "
            "reject: followed by revision feedback."
        ),
    })

    response = str(human_response).strip()
    normalized = response.lower()

    if normalized == "approve":
        return {
            "approval": "approved",
            "feedback": "",
        }

    if normalized.startswith("reject:"):
        feedback = response.split(":", 1)[1].strip()
    else:
        feedback = response

    return {
        "approval": "rejected",
        "feedback": feedback,
    }


# Revision node: improve the outline using human feedback.
def revise_outline(state: HumanLoopState) -> dict:
    return {
        "outline": run_node(
            "outline_reviser",
            (
                "Revise the study outline according to the human feedback. "
                "Keep exactly 3 numbered sections and return only the revised outline."
            ),
            (
                f"Topic: {state['topic']}\n\n"
                f"Current outline:\n{state['outline']}\n\n"
                f"Human feedback:\n{state['feedback']}"
            ),
        )
    }


# Conditional-edge function after human review.
def route_after_review(state: HumanLoopState) -> str:
    return state["approval"]


# Teacher runs only after human approval.
def teacher(state: HumanLoopState) -> dict:
    return {
        "notes": run_node(
            "teacher",
            (
                "Write concise beginner-friendly study notes using the approved "
                "outline. Preserve all three sections."
            ),
            (
                f"Topic: {state['topic']}\n\n"
                f"Approved outline:\n{state['outline']}"
            ),
        )
    }


# Quiz Writer runs after the Teacher.
def quiz_writer(state: HumanLoopState) -> dict:
    return {
        "quiz": run_node(
            "quiz_writer",
            (
                "Write exactly 3 short review questions based only on the "
                "supplied notes. Do not include answers."
            ),
            f"Topic: {state['topic']}\n\nNotes:\n{state['notes']}",
        )
    }


def build_graph():
    graph = StateGraph(HumanLoopState)

    graph.add_node("planner", planner)
    graph.add_node("human_review", human_review)
    graph.add_node("revise_outline", revise_outline)
    graph.add_node("teacher", teacher)
    graph.add_node("quiz_writer", quiz_writer)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "human_review")

    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "approved": "teacher",
            "rejected": "revise_outline",
        },
    )

    # A rejected outline returns for another human review.
    graph.add_edge("revise_outline", "human_review")

    graph.add_edge("teacher", "quiz_writer")
    graph.add_edge("quiz_writer", END)

    # Interrupts require a checkpointer.
    memory = InMemorySaver()
    return graph.compile(checkpointer=memory)


if __name__ == "__main__":
    print("Warming up model...")
    MODEL.invoke("Say ready.")
    print("Model ready.\n")

    app = build_graph()

    topic = input("Enter a study topic: ").strip()

    # The thread ID identifies the paused workflow when it resumes.
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
        }
    }

    workflow_start = time.time()

    result = app.invoke(
        {
            "topic": topic,
            "outline": "",
            "approval": "",
            "feedback": "",
            "notes": "",
            "quiz": "",
        },
        config=config,
    )

    # The graph can pause repeatedly if the human rejects multiple outlines.
    while "__interrupt__" in result:
        review_request = result["__interrupt__"][0].value

        print("\n" + "=" * 60)
        print("HUMAN REVIEW REQUIRED")
        print("=" * 60)
        print(f"Topic: {review_request['topic']}\n")
        print("Proposed outline:")
        print(review_request["outline"])
        print("\n" + review_request["instructions"])

        human_decision = input("\nYour decision: ").strip()

        result = app.invoke(
            Command(resume=human_decision),
            config=config,
        )

    total_time = time.time() - workflow_start

    print(
        f"\n# Human-Approved Study Guide: {topic}\n\n"
        f"## Approved Outline\n{result['outline']}\n\n"
        f"## Notes\n{result['notes']}\n\n"
        f"## Review Questions\n{result['quiz']}\n\n"
        f"Total elapsed time including human review: {total_time:.1f}s"
    )