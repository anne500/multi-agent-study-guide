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
    quiz: str


def ask(system: str, user: str) -> str:
    response = MODEL.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return response.content


def run_node(name: str, system: str, user: str) -> str:
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


# Node 2: write notes from the outline
def teacher(state: StudyState) -> dict:
    return {
        "notes": run_node(
            "teacher",
            "Write short beginner-friendly notes using the outline. Keep it concise.",
            f"Topic: {state['topic']}\n\nOutline:\n{state['outline']}",
        )
    }


# Node 3: write review questions from the notes
def quiz_writer(state: StudyState) -> dict:
    return {
        "quiz": run_node(
            "quiz_writer",
            "Write 3 short review questions based on the notes.",
            f"Topic: {state['topic']}\n\nNotes:\n{state['notes']}",
        )
    }


def build_graph():
    graph = StateGraph(StudyState)

    # Add the nodes
    graph.add_node("planner", planner)
    graph.add_node("teacher", teacher)
    graph.add_node("quiz_writer", quiz_writer)

    # Define the order of execution
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "teacher")
    graph.add_edge("teacher", "quiz_writer")
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
        "quiz": "",
    })

    print(
        f"\n# Study Guide: {topic}\n\n"
        f"## Outline\n{result['outline']}\n\n"
        f"## Notes\n{result['notes']}\n\n"
        f"## Review Questions\n{result['quiz']}\n"
    )