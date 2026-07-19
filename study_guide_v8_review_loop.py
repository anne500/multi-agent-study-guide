from typing import TypedDict
import sys
import time

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# Local Ollama model used by all AI nodes.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


# Shared state for the review/refinement workflow.
class ReviewState(TypedDict):
    topic: str
    demo_mode: bool
    notes: str
    quiz: str
    review_status: str
    review_feedback: str
    revision_count: int


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


# Node 1: create concise source notes.
def teacher(state: ReviewState) -> dict:
    return {
        "notes": run_node(
            "teacher",
            (
                "Write accurate beginner-friendly study notes about the topic. "
                "Use exactly 3 short sections and stay under 250 words."
            ),
            state["topic"],
        )
    }


# Node 2: produce the initial quiz.
def quiz_producer(state: ReviewState) -> dict:
    if state["demo_mode"]:
        instructions = (
            "This is a controlled reviewer test. Write exactly 4 review questions. "
            "Questions 1 through 3 should use the supplied notes. Question 4 must "
            "ask about Einstein's theory of relativity even though it is not covered "
            "in the notes. Do not include answers."
        )
    else:
        instructions = (
            "Write exactly 3 short review questions based only on the supplied "
            "notes. Do not include answers, hints, or outside facts."
        )

    return {
        "quiz": run_node(
            "quiz_producer",
            instructions,
            f"Topic: {state['topic']}\n\nNotes:\n{state['notes']}",
        )
    }

def parse_review(review: str) -> tuple[str, str]:
    """Parse the Reviewer's required STATUS and FEEDBACK lines."""
    status = ""
    feedback = ""

    for line in review.splitlines():
        stripped = line.strip()

        if stripped.lower().startswith("status:"):
            status = stripped.split(":", 1)[1].strip().lower()

        if stripped.lower().startswith("feedback:"):
            feedback = stripped.split(":", 1)[1].strip()

    if status == "approved":
        return "approved", feedback or "All review criteria were satisfied."

    if status == "revise":
        return "revise", feedback or "Revise the quiz to satisfy every criterion."

    # Malformed reviewer output is treated safely as a revision request.
    return (
        "revise",
        "The Reviewer did not return the required format. "
        "Rewrite the quiz clearly with exactly three grounded questions.",
    )


# Node 3: evaluate the quiz against the notes.
def reviewer(state: ReviewState) -> dict:
    review = run_node(
        "reviewer",
        (
            "Act as a strict quiz quality reviewer. Check all criteria:\n"
            "1. The quiz contains exactly 3 questions.\n"
            "2. Every question is fully answerable from the notes.\n"
            "3. No question is incomplete or truncated.\n"
            "4. No unsupported facts or topics are introduced.\n"
            "5. The quiz does not contain answers or hints.\n\n"
            "Return exactly two lines:\n"
            "STATUS: APPROVED or STATUS: REVISE\n"
            "FEEDBACK: one concise explanation\n\n"
            "Approve only when every criterion is satisfied."
        ),
        (
            f"Topic: {state['topic']}\n\n"
            f"Notes:\n{state['notes']}\n\n"
            f"Quiz:\n{state['quiz']}"
        ),
    )

    print("\nRaw Reviewer response:")
    print(review)
    print()

    status, feedback = parse_review(review)

    # Stop safely instead of allowing an infinite model loop.
    if status == "revise" and state["revision_count"] >= 2:
        status = "max_iterations"
        feedback = (
            "Maximum of two quiz revisions reached. "
            f"Last reviewer feedback: {feedback}"
        )

    print(f"Parsed review status: {status}")
    print(f"Reviewer feedback: {feedback}\n")

    return {
        "review_status": status,
        "review_feedback": feedback,
    }


# Node 4: improve the quiz using reviewer feedback.
def quiz_reviser(state: ReviewState) -> dict:
    revised_quiz = run_node(
        "quiz_reviser",
        (
            "Revise the quiz using the Reviewer feedback. Return exactly 3 complete "
            "questions based only on the supplied notes. Do not include answers, "
            "hints, commentary, or outside facts."
        ),
        (
            f"Topic: {state['topic']}\n\n"
            f"Notes:\n{state['notes']}\n\n"
            f"Current quiz:\n{state['quiz']}\n\n"
            f"Reviewer feedback:\n{state['review_feedback']}"
        ),
    )

    return {
        "quiz": revised_quiz,
        "revision_count": state["revision_count"] + 1,
    }


# Conditional-edge function after each review.
def route_after_review(state: ReviewState) -> str:
    return state["review_status"]


def build_graph():
    graph = StateGraph(ReviewState)

    graph.add_node("teacher", teacher)
    graph.add_node("quiz_producer", quiz_producer)
    graph.add_node("reviewer", reviewer)
    graph.add_node("quiz_reviser", quiz_reviser)

    graph.add_edge(START, "teacher")
    graph.add_edge("teacher", "quiz_producer")
    graph.add_edge("quiz_producer", "reviewer")

    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "approved": END,
            "revise": "quiz_reviser",
            "max_iterations": END,
        },
    )

    # A revised quiz returns to the Reviewer.
    graph.add_edge("quiz_reviser", "reviewer")

    return graph.compile()


if __name__ == "__main__":
    print("Warming up model...")
    MODEL.invoke("Say ready.")
    print("Model ready.\n")

    app = build_graph()
    topic = input("Enter a study topic: ").strip()
    demo_mode = "--demo-revision" in sys.argv

    if demo_mode:
        print(
            "\nControlled revision demo enabled. "
            "The initial quiz will intentionally violate review criteria.\n"
        )
    workflow_start = time.time()

    result = app.invoke({
        "topic": topic,
        "demo_mode": demo_mode,
	"notes": "",
        "quiz": "",
        "review_status": "",
        "review_feedback": "",
        "revision_count": 0,
    })

    total_time = time.time() - workflow_start

    print(
        f"\n# Reviewed Study Guide: {topic}\n\n"
        f"## Notes\n{result['notes']}\n\n"
        f"## Final Quiz\n{result['quiz']}\n\n"
        f"Final review status: {result['review_status']}\n"
        f"Quiz revisions performed: {result['revision_count']}\n"
        f"Final reviewer feedback: {result['review_feedback']}\n\n"
        f"Total workflow time: {total_time:.1f}s"
    )