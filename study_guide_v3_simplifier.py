from typing import TypedDict
import time

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# Local Ollama model used by all nodes.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


# Shared state passed between nodes.
class StudyState(TypedDict):
    topic: str
    outline: str
    notes: str
    simplified_notes: str
    quiz: str


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


# Node 1: create the outline
def planner(state: StudyState) -> dict:
    return {
        "outline": run_node(
            "planner",
            "Break this topic into 3 short study sections.",
            state["topic"],
        )
    }


# Node 2: create the original notes
def teacher(state: StudyState) -> dict:
    return {
        "notes": run_node(
            "teacher",
            "Write short study notes using the outline. Keep them accurate and concise.",
            f"Topic: {state['topic']}\n\nOutline:\n{state['outline']}",
        )
    }


# Node 3: rewrite the notes using simpler language
def simplifier(state: StudyState) -> dict:
    return {
        "simplified_notes": run_node(
            "simplifier",
            (
                "Rewrite these notes in simpler language for a beginner. "
                "Preserve all important facts and the three-section structure. "
                "Do not introduce new facts."
            ),
            f"Topic: {state['topic']}\n\nOriginal notes:\n{state['notes']}",
        )
    }


# Node 4: create questions from the simplified notes
def quiz_writer(state: StudyState) -> dict:
    return {
        "quiz": run_node(
            "quiz_writer",
            "Write exactly 3 short review questions based only on the supplied notes.",
            (
                f"Topic: {state['topic']}\n\n"
                f"Simplified notes:\n{state['simplified_notes']}"
            ),
        )
    }


def build_graph():
    graph = StateGraph(StudyState)

    # Add the four nodes
    graph.add_node("planner", planner)
    graph.add_node("teacher", teacher)
    graph.add_node("simplifier", simplifier)
    graph.add_node("quiz_writer", quiz_writer)

    # Define the sequential execution order
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "teacher")
    graph.add_edge("teacher", "simplifier")
    graph.add_edge("simplifier", "quiz_writer")
    graph.add_edge("quiz_writer", END)

    return graph.compile()


if __name__ == "__main__":
    print("Warming up model...")
    MODEL.invoke("Say ready.")
    print("Model ready.\n")

    app = build_graph()
    topic = input("Enter a study topic: ").strip()

    result = app.invoke({
        "topic": topic,
        "outline": "",
        "notes": "",
        "simplified_notes": "",
        "quiz": "",
    })

    print(
        f"\n# Study Guide: {topic}\n\n"
        f"## Outline\n{result['outline']}\n\n"
        f"## Original Notes\n{result['notes']}\n\n"
        f"## Simplified Notes\n{result['simplified_notes']}\n\n"
        f"## Review Questions\n{result['quiz']}\n"
    )