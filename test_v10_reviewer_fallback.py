import study_guide_v10_checkpointing as v10


class AlwaysFailReviewer:
    """Deterministically simulate invalid structured reviewer output."""

    def __init__(self):
        self.call_count = 0

    def invoke(self, messages):
        self.call_count += 1
        raise ValueError("Deterministic invalid structured output")


fake_reviewer = AlwaysFailReviewer()
v10.STRUCTURED_REVIEWER = fake_reviewer

original_quiz = (
    "1. What is a Kubernetes Deployment?\n"
    "2. How does a Deployment manage ReplicaSets?\n"
    "3. What happens during a rolling update?"
)

state = {
    "topic": "Kubernetes Deployments",
    "learner_level": "beginner",
    "tasks": [],
    "completed_sections": [],
    "demo_mode": False,
    "notes": (
        "A Kubernetes Deployment manages ReplicaSets and supports "
        "declarative rolling updates."
    ),
    "quiz": original_quiz,
    "review_status": "",
    "reviewer_feedback": "",
    "revision_count": 0,
}

review_update = v10.reviewer(state)
updated_state = {**state, **review_update}
route = v10.route_after_review(updated_state)

assert fake_reviewer.call_count == 2
assert review_update["review_status"] == "fallback_approved"
assert "Safe reviewer fallback used" in review_update["reviewer_feedback"]
assert updated_state["quiz"] == original_quiz
assert updated_state["quiz"].strip()
assert updated_state["revision_count"] == 0
assert route == "fallback_approved"

print("\nV10 deterministic fallback test passed.")
print(f"Structured reviewer attempts: {fake_reviewer.call_count}")
print(f"Review status: {updated_state['review_status']}")
print(f"Revision count: {updated_state['revision_count']}")
print(f"Quiz preserved: {updated_state['quiz'] == original_quiz}")
print(f"Route after review: {route}")
print("No Ollama reviewer or quiz-reviser call was executed.")