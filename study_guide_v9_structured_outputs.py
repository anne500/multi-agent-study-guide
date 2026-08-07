from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field
import operator
import sys
import time

from langchain_ollama import ChatOllama
from langgraph.types import Send
from langgraph.graph import StateGraph, START, END

# Local Ollama model used by all AI nodes.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)

class ReviewResult(BaseModel):
    """Validated structured response from the quiz reviewer."""

    status: Literal["approved", "revise"] = Field(
        description="Whether the quiz satisfies every review requirement."
    )
    feedback: str = Field(
        description="Specific revision guidance, or a short approval explanation."
    )

class RouteResult(BaseModel):
    """Validated learner-level decision from the router."""

    learner_level: Literal["beginner", "advanced"] = Field(
        description="The appropriate learning level for the requested topic."
    )

class OrchestratorPlan(BaseModel):
    """Validated set of assignments created by the orchestrator."""

    tasks: list[str] = Field(
        min_length=3,
        max_length=3,
        description="Exactly three distinct study-guide assignments.",
    )

STRUCTURED_REVIEWER = MODEL.with_structured_output(ReviewResult)
STRUCTURED_ROUTER = MODEL.with_structured_output(RouteResult)
STRUCTURED_ORCHESTRATOR = MODEL.with_structured_output(OrchestratorPlan)

# Shared state for the review/refinement workflow.
class ReviewState(TypedDict):
    topic: str
    learner_level: Literal["beginner", "advanced"]
    tasks: list[str]
    completed_sections: Annotated[list[str], operator.add]
    demo_mode: bool
    notes: str
    quiz: str
    review_status: str
    reviewer_feedback: str
    revision_count: int

class WorkerState(TypedDict):
    topic: str
    learner_level: Literal["beginner", "advanced"]
    task: str
    task_number: int
    completed_sections: Annotated[list[str], operator.add]

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

# Create exactly three validated assignments for parallel workers.
def orchestrator(state: ReviewState) -> dict:
    plan = None

    try:
        plan = STRUCTURED_ORCHESTRATOR.invoke(
            [
                (
                    "system",
                    "Create exactly three distinct study-guide worker assignments. "
                    "Each assignment must tell a specialist what content to write. "
                    "Cover: (1) core concepts, (2) practical examples or applications, "
                    "and (3) common mistakes or misconceptions. "
                    "Do not copy these instructions. Do not use the topic, learner "
                    "level, or labels such as 'Topic' as assignments.",
                ),
                (
                    "human",
                    f"Create specialist assignments about {state['topic']} "
                    f"for a {state['learner_level']} learner.",
                ),
            ]
        )
    except Exception as error:
        print(
            "\nStructured orchestrator output was invalid; "
            "validated fallback assignments will be used."
        )
        print(f"Orchestrator error: {type(error).__name__}: {error}")

    forbidden_tasks = {
        state["topic"].strip().lower(),
        state["learner_level"].strip().lower(),
    }

    tasks_are_valid = (
        plan is not None
        and len(plan.tasks) == 3
        and len({task.strip().lower() for task in plan.tasks}) == 3
        and all(len(task.split()) >= 4 for task in plan.tasks)
        and all(task.strip().lower() not in forbidden_tasks for task in plan.tasks)
        and all(
            not task.strip().lower().startswith(
                ("topic:", "learner level:", "you are a study-guide")
            )
            for task in plan.tasks
        )
    )

    if tasks_are_valid:
        tasks = plan.tasks
    else:
        tasks = [
            f"Explain the core concepts and principles of {state['topic']}.",
            f"Provide practical examples and applications of {state['topic']}.",
            f"Explain common mistakes and misconceptions about {state['topic']}.",
        ]
        print(
            "\nThe model returned unsuitable assignments; "
            "validated fallback assignments were used."
        )

    print("\nValidated orchestrator assignments:")
    for number, task in enumerate(tasks, start=1):
        print(f"{number}. {task}")
    print()

    return {"tasks": tasks}

# Dispatch one parallel specialist worker for each validated assignment.
def assign_workers(state: ReviewState) -> list[Send]:
    return [
        Send(
            "subagent",
            {
                "topic": state["topic"],
                "learner_level": state["learner_level"],
                "task": task,
                "task_number": number,
                "completed_sections": [],
            },
        )
        for number, task in enumerate(state["tasks"], start=1)
    ]

# Complete one orchestrator assignment in a parallel specialist worker.
def subagent(state: WorkerState) -> dict:
    response = MODEL.invoke(
        [
            (
                "system",
                f"You are a {state['learner_level']}-level study-guide specialist. "
                "Complete only the assigned task accurately and concisely. "
                "Keep the section under 120 words.",
            ),
            (
                "human",
                f"Topic: {state['topic']}\n"
                f"Assignment: {state['task']}",
            ),
        ]
    )

    section = (
        f"SECTION {state['task_number']}\n"
        f"Assignment: {state['task']}\n"
        f"{response.content.strip()}"
    )

    return {"completed_sections": [section]}

# Combine the three parallel specialist sections into ordered study notes.
def synthesizer(state: ReviewState) -> dict:
    ordered_sections = sorted(
        state["completed_sections"],
        key=lambda section: int(section.splitlines()[0].split()[1]),
    )
    notes = "\n\n".join(ordered_sections)

    print("\nSynthesized specialist notes:\n")
    print(notes)
    print()

    return {"notes": notes}

# Node 0: choose the appropriate learner level using validated output.
def router(state: ReviewState) -> dict:
    route_result = STRUCTURED_ROUTER.invoke(
        [
            (
                "system",
                "Classify the requested study topic for either a beginner or "
                "an advanced learning path. Choose beginner when the request "
                "does not explicitly indicate advanced depth.",
            ),
            (
                "human",
                f"Study request: {state['topic']}",
            ),
        ]
    )

    learner_level = route_result.learner_level
    print(f"\nValidated learner route: {learner_level}\n")

    return {"learner_level": learner_level}

# Node 1: create concise source notes.
def teacher(state: ReviewState) -> dict:
    return {
        "notes": run_node(
            "teacher",
            (
                f"Write accurate {state['learner_level']}-level study notes about the topic. "
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


# Node 3: evaluate the quiz against the notes.
def reviewer(state: ReviewState) -> dict:
    messages = [
        (
            "system",
            "Act as a strict quiz quality reviewer. Check all criteria:\n"
            "1. The quiz contains exactly 3 questions.\n"
            "2. Every question is fully answerable from the notes.\n"
            "3. No question is incomplete or truncated.\n"
            "4. No unsupported facts or topics are introduced.\n"
            "5. The quiz does not contain answers or hints.\n"
            "Approve only when every criterion is satisfied.",
        ),
        (
            "human",
            f"Topic: {state['topic']}\n\n"
            f"Notes:\n{state['notes']}\n\n"
            f"Quiz:\n{state['quiz']}",
        ),
    ]

    review_result = None
    last_error = ""

    # Retry once if Ollama returns empty or invalid structured JSON.
    for attempt in range(1, 3):
        try:
            review_result = STRUCTURED_REVIEWER.invoke(messages)
            break
        except Exception as error:
            last_error = f"{type(error).__name__}: {error}"
            print(
                f"\nStructured reviewer attempt {attempt} failed. "
                "Retrying..." if attempt == 1
                else f"\nStructured reviewer attempt {attempt} failed."
            )

    if review_result is not None:
        status = review_result.status
        feedback = review_result.feedback
    else:
        # Recover safely instead of crashing the LangGraph workflow.
        status = "revise"
        feedback = (
            "The structured reviewer returned invalid or empty JSON after "
            "two attempts. Revise the quiz so it contains exactly three "
            "complete questions, uses only the supplied notes, and contains "
            "no answers or hints. "
            f"Parser error: {last_error}"
        )
        print("\nSafe reviewer fallback activated.")

    # Stop safely instead of allowing an infinite model loop.
    if status == "revise" and state["revision_count"] >= 2:
        status = "max_iterations"
        feedback = (
            "Maximum of two quiz revisions reached. "
            f"Last reviewer feedback: {feedback}"
        )

    print("\nValidated reviewer response:")
    print(f"Review status: {status}")
    print(f"Reviewer feedback: {feedback}\n")

    return {
        "review_status": status,
        "reviewer_feedback": feedback,
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
            f"Reviewer feedback:\n{state['reviewer_feedback']}"
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

    graph.add_node("router", router)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("subagent", subagent)
    graph.add_node("synthesizer", synthesizer)
    graph.add_node("quiz_producer", quiz_producer)
    graph.add_node("reviewer", reviewer)
    graph.add_node("quiz_reviser", quiz_reviser)

    graph.add_edge(START, "router")
    graph.add_edge("router", "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        assign_workers,
        ["subagent"],
    )
    graph.add_edge("subagent", "synthesizer")
    graph.add_edge("synthesizer", "quiz_producer")
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
	"learner_level": "beginner",
	"tasks": [],
        "completed_sections": [],
        "demo_mode": demo_mode,
	"notes": "",
        "quiz": "",
        "review_status": "",
        "reviewer_feedback": "",
        "revision_count": 0,
    })

    total_time = time.time() - workflow_start

    print(
        f"\n# Reviewed Study Guide: {topic}\n\n"
        f"## Notes\n{result['notes']}\n\n"
        f"## Final Quiz\n{result['quiz']}\n\n"
        f"Final review status: {result['review_status']}\n"
        f"Quiz revisions performed: {result['revision_count']}\n"
        f"Final reviewer feedback: {result['reviewer_feedback']}\n\n"
        f"Total workflow time: {total_time:.1f}s"
    )