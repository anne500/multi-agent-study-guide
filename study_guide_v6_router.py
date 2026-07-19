from typing import TypedDict
import time

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# Local Ollama model shared by the router and specialists.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


# Shared state for the routing workflow.
class RouterState(TypedDict):
    topic: str
    audience_request: str
    route: str
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
    """Run a node and report how long it takes."""
    print(f"Calling node {name}...")
    start = time.time()
    result = ask(system, user)
    print(f"Finished {name} in {time.time() - start:.1f}s")
    return result


# Router: select the appropriate teaching specialist.
def router(state: RouterState) -> dict:
    decision = run_node(
        "router",
        (
            "Classify the requested learner audience as beginner or advanced. "
            "Return only one word: beginner or advanced."
        ),
        (
            f"Topic: {state['topic']}\n"
            f"Learner or audience request: {state['audience_request']}"
        ),
    )

    normalized = decision.strip().lower()

    if "advanced" in normalized:
        route = "advanced"
    else:
        route = "beginner"

    print(f"Router selected: {route}_teacher\n")
    return {"route": route}


# Beginner branch
def beginner_teacher(state: RouterState) -> dict:
    return {
        "notes": run_node(
            "beginner_teacher",
            (
                "Teach the topic to a complete beginner. Use plain language, "
                "short explanations, and familiar real-world examples. "
                "Avoid unnecessary technical terminology."
            ),
            state["topic"],
        )
    }


# Advanced branch
def advanced_teacher(state: RouterState) -> dict:
    return {
        "notes": run_node(
            "advanced_teacher",
            (
                "Teach the topic to an advanced learner. Use precise technical "
                "terminology, relevant equations, assumptions, and deeper analysis. "
                "Keep the explanation structured and accurate."
            ),
            state["topic"],
        )
    }


# Shared node after either teaching branch
def quiz_writer(state: RouterState) -> dict:
    return {
        "quiz": run_node(
            "quiz_writer",
            (
                f"Write exactly 3 {state['route']}-level review questions "
                "based only on the supplied notes. Do not include answers."
            ),
            f"Topic: {state['topic']}\n\nNotes:\n{state['notes']}",
        )
    }


# Conditional-edge function
def choose_teacher(state: RouterState) -> str:
    return state["route"]


def build_graph():
    graph = StateGraph(RouterState)

    graph.add_node("router", router)
    graph.add_node("beginner_teacher", beginner_teacher)
    graph.add_node("advanced_teacher", advanced_teacher)
    graph.add_node("quiz_writer", quiz_writer)

    graph.add_edge(START, "router")

    # Only one teaching branch is selected for each run.
    graph.add_conditional_edges(
        "router",
        choose_teacher,
        {
            "beginner": "beginner_teacher",
            "advanced": "advanced_teacher",
        },
    )

    graph.add_edge("beginner_teacher", "quiz_writer")
    graph.add_edge("advanced_teacher", "quiz_writer")
    graph.add_edge("quiz_writer", END)

    return graph.compile()


if __name__ == "__main__":
    print("Warming up model...")
    MODEL.invoke("Say ready.")
    print("Model ready.\n")

    app = build_graph()

    topic = input("Enter a study topic: ").strip()
    audience_request = input(
        "Describe the learner or audience (beginner or advanced): "
    ).strip()

    workflow_start = time.time()

    result = app.invoke({
        "topic": topic,
        "audience_request": audience_request,
        "route": "",
        "notes": "",
        "quiz": "",
    })

    total_time = time.time() - workflow_start

    print(
        f"\n# Routed Study Guide: {topic}\n\n"
        f"Selected route: {result['route']}\n\n"
        f"## Notes\n{result['notes']}\n\n"
        f"## Review Questions\n{result['quiz']}\n\n"
        f"Total workflow time: {total_time:.1f}s"
    )