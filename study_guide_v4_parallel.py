from typing import TypedDict
import time

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# Local Ollama model shared by all nodes.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


# Shared state for the parallel workflow.
class ParallelStudyState(TypedDict):
    topic: str
    concepts: str
    examples: str
    quiz: str
    final_guide: str


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


# Parallel specialist 1: explain key concepts
def concepts_agent(state: ParallelStudyState) -> dict:
    return {
        "concepts": run_node(
            "concepts_agent",
            (
                "Explain exactly 3 key concepts about this topic. "
                "Keep each explanation concise and beginner-friendly."
            ),
            state["topic"],
        )
    }


# Parallel specialist 2: create examples
def examples_agent(state: ParallelStudyState) -> dict:
    return {
        "examples": run_node(
            "examples_agent",
            (
                "Give exactly 3 concrete beginner-friendly examples "
                "that illustrate this topic."
            ),
            state["topic"],
        )
    }


# Parallel specialist 3: create review questions
def quiz_agent(state: ParallelStudyState) -> dict:
    return {
        "quiz": run_node(
            "quiz_agent",
            (
                "Write exactly 3 short review questions about this topic. "
                "Do not include answers."
            ),
            state["topic"],
        )
    }


# Merger: combine all three independent outputs
def merger(state: ParallelStudyState) -> dict:
    merger_input = (
        f"Topic: {state['topic']}\n\n"
        f"Concept specialist output:\n{state['concepts']}\n\n"
        f"Example specialist output:\n{state['examples']}\n\n"
        f"Quiz specialist output:\n{state['quiz']}"
    )

    return {
        "final_guide": run_node(
            "merger",
            (
                "Combine the three specialist outputs into one clean Markdown "
                "study guide. Use exactly these headings: "
                "## Key Concepts, ## Examples, and ## Review Questions. "
                "Preserve the useful content and do not introduce unrelated facts. "
                "Do not add a title above the three required headings."
            ),
            merger_input,
        )
    }


def build_graph():
    graph = StateGraph(ParallelStudyState)

    # Add three parallel specialists and one merger.
    graph.add_node("concepts_agent", concepts_agent)
    graph.add_node("examples_agent", examples_agent)
    graph.add_node("quiz_agent", quiz_agent)
    graph.add_node("merger", merger)

    # Fan out: all three specialists start from the same input.
    graph.add_edge(START, "concepts_agent")
    graph.add_edge(START, "examples_agent")
    graph.add_edge(START, "quiz_agent")

    # Fan in: the merger waits for all specialist outputs.
    graph.add_edge("concepts_agent", "merger")
    graph.add_edge("examples_agent", "merger")
    graph.add_edge("quiz_agent", "merger")

    graph.add_edge("merger", END)

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
        "concepts": "",
        "examples": "",
        "quiz": "",
        "final_guide": "",
    })

    total_time = time.time() - workflow_start

    print(
        f"\n# Parallel Study Guide: {topic}\n\n"
        f"{result['final_guide']}\n\n"
        f"Total workflow time: {total_time:.1f}s"
    )