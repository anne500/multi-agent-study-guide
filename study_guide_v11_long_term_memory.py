from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field, field_validator

import study_guide_v10_checkpointing as v10


CHECKPOINT_DATABASE = "study_guide_checkpoints.sqlite"
MEMORY_DATABASE = "learner_memory.sqlite"


class LearnerProfile(BaseModel):
    learner_id: str = Field(min_length=1, max_length=80)
    preferred_level: Literal["beginner", "advanced"] = "beginner"
    learning_preferences: list[str] = Field(default_factory=list)

    @field_validator("learner_id")
    @classmethod
    def normalize_learner_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("learner_id cannot be blank")
        return normalized

    @field_validator("learning_preferences")
    @classmethod
    def normalize_preferences(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            key = item.lower()
            if item and key not in seen:
                result.append(item)
                seen.add(key)
        return result[:10]


class LearningOutcome(BaseModel):
    learner_id: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=200)
    quiz_score: float | None = Field(default=None, ge=0, le=100)
    recurring_mistakes: list[str] = Field(default_factory=list)
    completed: bool = True

    @field_validator("learner_id", "topic")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized

    @field_validator("recurring_mistakes")
    @classmethod
    def normalize_mistakes(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            key = item.lower()
            if item and key not in seen:
                result.append(item)
                seen.add(key)
        return result[:10]


class LearnerMemoryStore:
    """Store validated learner facts separately from workflow checkpoints."""

    def __init__(self, database_path: str = MEMORY_DATABASE) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS learner_profiles (
                learner_id TEXT PRIMARY KEY,
                preferred_level TEXT NOT NULL
                    CHECK (preferred_level IN ('beginner', 'advanced')),
                learning_preferences TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learning_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                quiz_score REAL,
                recurring_mistakes TEXT NOT NULL DEFAULT '[]',
                completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
                completed_at TEXT NOT NULL,
                FOREIGN KEY (learner_id)
                    REFERENCES learner_profiles(learner_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_learning_sessions_learner
            ON learning_sessions(learner_id, completed_at);
            """
        )
        self.connection.commit()

    def get_profile(self, learner_id: str) -> LearnerProfile | None:
        row = self.connection.execute(
            """
            SELECT learner_id, preferred_level, learning_preferences
            FROM learner_profiles
            WHERE learner_id = ?
            """,
            (learner_id.strip(),),
        ).fetchone()
        if row is None:
            return None
        return LearnerProfile(
            learner_id=row["learner_id"],
            preferred_level=row["preferred_level"],
            learning_preferences=json.loads(row["learning_preferences"]),
        )

    def save_profile(self, profile: LearnerProfile) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO learner_profiles (
                learner_id,
                preferred_level,
                learning_preferences,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(learner_id) DO UPDATE SET
                preferred_level = excluded.preferred_level,
                learning_preferences = excluded.learning_preferences,
                updated_at = excluded.updated_at
            """,
            (
                profile.learner_id,
                profile.preferred_level,
                json.dumps(profile.learning_preferences),
                now,
                now,
            ),
        )
        self.connection.commit()

    def save_outcome(self, outcome: LearningOutcome) -> None:
        if self.get_profile(outcome.learner_id) is None:
            raise ValueError("Save the learner profile before saving an outcome.")
        self.connection.execute(
            """
            INSERT INTO learning_sessions (
                learner_id,
                topic,
                quiz_score,
                recurring_mistakes,
                completed,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                outcome.learner_id,
                outcome.topic,
                outcome.quiz_score,
                json.dumps(outcome.recurring_mistakes),
                int(outcome.completed),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.connection.commit()

    def completed_topics(self, learner_id: str) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT topic
            FROM learning_sessions
            WHERE learner_id = ? AND completed = 1
            ORDER BY completed_at
            """,
            (learner_id.strip(),),
        ).fetchall()
        return [row["topic"] for row in rows]

    def recent_outcomes(
        self, learner_id: str, limit: int = 5
    ) -> list[LearningOutcome]:
        rows = self.connection.execute(
            """
            SELECT learner_id, topic, quiz_score, recurring_mistakes, completed
            FROM learning_sessions
            WHERE learner_id = ?
            ORDER BY session_id DESC
            LIMIT ?
            """,
            (learner_id.strip(), limit),
        ).fetchall()
        return [
            LearningOutcome(
                learner_id=row["learner_id"],
                topic=row["topic"],
                quiz_score=row["quiz_score"],
                recurring_mistakes=json.loads(row["recurring_mistakes"]),
                completed=bool(row["completed"]),
            )
            for row in rows
        ]

    def memory_summary(self, learner_id: str) -> str:
        profile = self.get_profile(learner_id)
        if profile is None:
            return "No saved learner memory."

        topics = self.completed_topics(learner_id)
        outcomes = self.recent_outcomes(learner_id)
        scores = [item.quiz_score for item in outcomes if item.quiz_score is not None]
        mistakes: list[str] = []
        seen: set[str] = set()
        for item in outcomes:
            for mistake in item.recurring_mistakes:
                key = mistake.lower()
                if key not in seen:
                    mistakes.append(mistake)
                    seen.add(key)

        average_score = (
            f"{sum(scores) / len(scores):.1f}%" if scores else "not recorded"
        )
        preferences = ", ".join(profile.learning_preferences) or "none recorded"
        completed = ", ".join(topics[-5:]) or "none recorded"
        mistake_text = ", ".join(mistakes[:5]) or "none recorded"
        return (
            f"Preferred level: {profile.preferred_level}\n"
            f"Learning preferences: {preferences}\n"
            f"Recently completed topics: {completed}\n"
            f"Recent average quiz score: {average_score}\n"
            f"Recurring mistakes: {mistake_text}"
        )

    def close(self) -> None:
        self.connection.close()


def build_personalized_graph(preferred_level: Literal["beginner", "advanced"],
                             checkpointer=None, interrupt_before=None):
    """Build the V10 workflow with a memory-informed routing decision."""

    def memory_router(state: v10.ReviewState) -> dict:
        print(f"\nLearner memory route: {preferred_level}\n")
        return {"learner_level": preferred_level}

    graph = StateGraph(v10.ReviewState)
    graph.add_node("router", memory_router)
    graph.add_node("orchestrator", v10.orchestrator)
    graph.add_node("subagent", v10.subagent)
    graph.add_node("synthesizer", v10.synthesizer)
    graph.add_node("quiz_producer", v10.quiz_producer)
    graph.add_node("reviewer", v10.reviewer)
    graph.add_node("quiz_reviser", v10.quiz_reviser)

    graph.add_edge(START, "router")
    graph.add_edge("router", "orchestrator")
    graph.add_conditional_edges(
        "orchestrator", v10.assign_workers, ["subagent"]
    )
    graph.add_edge("subagent", "synthesizer")
    graph.add_edge("synthesizer", "quiz_producer")
    graph.add_edge("quiz_producer", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        v10.route_after_review,
        {
            "approved": END,
            "fallback_approved": END,
            "revise": "quiz_reviser",
            "max_iterations": END,
        },
    )
    graph.add_edge("quiz_reviser", "reviewer")
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )


def prompt_level(default: str = "beginner") -> Literal["beginner", "advanced"]:
    answer = input(
        f"Preferred level, beginner or advanced [{default}]: "
    ).strip().lower()
    selected = answer or default
    while selected not in {"beginner", "advanced"}:
        selected = input("Enter beginner or advanced: ").strip().lower()
    return selected  # type: ignore[return-value]


def prompt_list(label: str) -> list[str]:
    value = input(f"{label} (comma-separated, or press Enter for none): ").strip()
    return [item.strip() for item in value.split(",") if item.strip()]


def prompt_optional_score() -> float | None:
    value = input(
        "Quiz score from 0 to 100 (press Enter if not assessed): "
    ).strip()
    if not value:
        return None
    try:
        score = float(value)
    except ValueError:
        print("Invalid score. No score will be saved.")
        return None
    if not 0 <= score <= 100:
        print("Score outside 0 to 100. No score will be saved.")
        return None
    return score


def load_or_create_profile(store: LearnerMemoryStore) -> LearnerProfile:
    learner_id = input("Enter learner ID [ishani]: ").strip() or "ishani"
    profile = store.get_profile(learner_id)
    if profile is not None:
        print("\nSaved learner memory found:")
        print(store.memory_summary(learner_id))
        update = input("Update profile preferences? [y/N]: ").strip().lower()
        if update != "y":
            return profile

    default_level = profile.preferred_level if profile else "beginner"
    existing_preferences = profile.learning_preferences if profile else []
    level = prompt_level(default_level)
    preferences = prompt_list("Learning preferences")
    if not preferences:
        preferences = existing_preferences
    profile = LearnerProfile(
        learner_id=learner_id,
        preferred_level=level,
        learning_preferences=preferences,
    )
    store.save_profile(profile)
    print("Learner profile saved.")
    return profile


def main() -> None:
    print("V11: Long-term learner memory\n")
    memory_store = LearnerMemoryStore(MEMORY_DATABASE)
    checkpoint_connection = sqlite3.connect(
        CHECKPOINT_DATABASE, check_same_thread=False
    )
    try:
        profile = load_or_create_profile(memory_store)
        pause_before_quiz = "--pause-before-quiz" in sys.argv
        interrupt_before = ["quiz_producer"] if pause_before_quiz else None
        checkpointer = v10.SqliteSaver(checkpoint_connection)
        app = build_personalized_graph(
            preferred_level=profile.preferred_level,
            checkpointer=checkpointer,
            interrupt_before=interrupt_before,
        )

        thread_id = input(
            "Enter session ID, or press Enter to create one automatically: "
        ).strip()
        if not thread_id:
            thread_id = (
                f"{profile.learner_id}-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            )
        print(f"Session ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        existing_state = app.get_state(config)

        if existing_state.values:
            print("\nAn existing checkpoint was found for this session.")
            if existing_state.next:
                action = input("Enter R to resume, or anything else to exit: ")
                if action.strip().lower() != "r":
                    print("No workflow was started.")
                    return
                started = time.time()
                result = app.invoke(None, config)
            else:
                print("Loading the completed saved result.")
                started = time.time()
                result = existing_state.values
        else:
            topic = input("Enter a study topic: ").strip()
            if not topic:
                topic = "Newton's Laws of Motion"
            print("\nSession plan:")
            print(f"Topic: {topic}")
            print(f"Learner memory route: {profile.preferred_level}")
            confirm = input("Start study-guide generation? [y/N]: ").strip().lower()
            if confirm != "y":
                print("No workflow was started.")
                return
            started = time.time()
            try:
                result = app.invoke(
                    {
                        "topic": topic,
                        "learner_level": profile.preferred_level,
                        "tasks": [],
                        "completed_sections": [],
                        "demo_mode": "--demo-revision" in sys.argv,
                        "notes": "",
                        "quiz": "",
                        "review_status": "",
                        "reviewer_feedback": "",
                        "revision_count": 0,
                    },
                    config,
                )
            except KeyboardInterrupt:
                print(
                    "\nGeneration interrupted. Any completed checkpoint data was "
                    f"retained for session: {thread_id}"
                )
                return

        saved_state = app.get_state(config)
        print(f"\nCheckpoint saved for session: {thread_id}")
        if saved_state.next:
            print("Workflow paused at a persistent checkpoint.")
            print("Run V11 again with the same session ID to resume.")
            return

        elapsed = time.time() - started
        print(
            f"\n# Personalized Study Guide: {result['topic']}\n\n"
            f"Learner: {profile.learner_id}\n"
            f"Level: {result['learner_level']}\n\n"
            f"## Notes\n{result['notes']}\n\n"
            f"## Final Quiz\n{result['quiz']}\n\n"
            f"Final review status: {result['review_status']}\n"
            f"Quiz revisions performed: {result['revision_count']}\n"
            f"Total workflow time: {elapsed:.1f}s"
        )

        save_result = input(
            "\nSave validated learning outcome to long-term memory? [y/N]: "
        ).strip().lower()
        if save_result == "y":
            outcome = LearningOutcome(
                learner_id=profile.learner_id,
                topic=result["topic"],
                quiz_score=prompt_optional_score(),
                recurring_mistakes=prompt_list("Recurring mistakes"),
                completed=True,
            )
            memory_store.save_outcome(outcome)
            print("\nValidated outcome saved to long-term memory.")
            print(memory_store.memory_summary(profile.learner_id))
        else:
            print("Generated content was not written to long-term memory.")
    finally:
        checkpoint_connection.close()
        memory_store.close()


if __name__ == "__main__":
    main()
