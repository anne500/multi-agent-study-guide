import time
from langchain_ollama import ChatOllama

# Local Ollama model used by all three agents.
MODEL = ChatOllama(model="qwen3.5:4b", temperature=0)


def ask(system: str, user: str) -> str:
    """Run one LLM call with a system prompt and user input."""
    response = MODEL.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return response.content


def run_agent(name: str, system: str, user: str) -> str:
    """Helper that logs how long each agent takes."""
    print(f"Calling agent {name}...")
    start = time.time()
    result = ask(system, user)
    print(f"Finished {name} in {time.time() - start:.1f}s")
    return result


# Agent 1: create a short outline
def planner_agent(topic: str) -> str:
    return run_agent(
        "planner_agent",
        "Break this topic into 3 short study sections.",
        topic,
    )


# Agent 2: turn the outline into notes
def teacher_agent(topic: str, outline: str) -> str:
    return run_agent(
        "teacher_agent",
        "Write short beginner-friendly notes using the outline. Keep it concise.",
        f"Topic: {topic}\n\nOutline:\n{outline}",
    )


# Agent 3: write review questions from the notes
def quiz_agent(topic: str, notes: str) -> str:
    return run_agent(
        "quiz_agent",
        "Write 3 short review questions based on the notes.",
        f"Topic: {topic}\n\nNotes:\n{notes}",
    )


def build_study_guide(topic: str) -> str:
    """Run all three agents in sequence and combine their output."""
    outline = planner_agent(topic)
    notes = teacher_agent(topic, outline)
    quiz = quiz_agent(topic, notes)

    return (
        f"# Study Guide: {topic}\n\n"
        f"## Outline\n{outline}\n\n"
        f"## Notes\n{notes}\n\n"
        f"## Review Questions\n{quiz}\n"
    )


if __name__ == "__main__":
    print("Warming up model...")
    MODEL.invoke("Say ready.")
    print("Model ready.\n")

    topic = input("Enter a study topic: ").strip()
    print("\n" + build_study_guide(topic))