from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from study_guide_v11_long_term_memory import (
    LearnerMemoryStore,
    LearnerProfile,
    LearningOutcome,
)


class LearnerMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = str(
            Path(self.temporary_directory.name) / "test_learner_memory.sqlite"
        )
        self.store = LearnerMemoryStore(self.database_path)

    def tearDown(self) -> None:
        self.store.close()
        self.temporary_directory.cleanup()

    def test_profile_is_normalized_saved_and_updated(self) -> None:
        profile = LearnerProfile(
            learner_id="  ishani  ",
            preferred_level="beginner",
            learning_preferences=[
                "Diagrams",
                " diagrams ",
                "Hands-on examples",
                "",
            ],
        )
        self.store.save_profile(profile)

        saved = self.store.get_profile("ishani")
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.learner_id, "ishani")
        self.assertEqual(saved.preferred_level, "beginner")
        self.assertEqual(
            saved.learning_preferences,
            ["Diagrams", "Hands-on examples"],
        )

        self.store.save_profile(
            LearnerProfile(
                learner_id="ishani",
                preferred_level="advanced",
                learning_preferences=["Concise notes"],
            )
        )
        updated = self.store.get_profile("ishani")
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.preferred_level, "advanced")
        self.assertEqual(updated.learning_preferences, ["Concise notes"])

    def test_memory_persists_after_store_is_reopened(self) -> None:
        self.store.save_profile(
            LearnerProfile(
                learner_id="ishani",
                preferred_level="advanced",
                learning_preferences=["Visual explanations"],
            )
        )
        self.store.save_outcome(
            LearningOutcome(
                learner_id="ishani",
                topic="Newton's Laws of Motion",
                quiz_score=90,
                recurring_mistakes=["Confusing mass and weight"],
            )
        )

        self.store.close()
        self.store = LearnerMemoryStore(self.database_path)

        profile = self.store.get_profile("ishani")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.preferred_level, "advanced")
        self.assertEqual(
            self.store.completed_topics("ishani"),
            ["Newton's Laws of Motion"],
        )
        outcomes = self.store.recent_outcomes("ishani")
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].quiz_score, 90)

    def test_completed_topics_are_deduplicated(self) -> None:
        self.store.save_profile(LearnerProfile(learner_id="ishani"))
        for score in (80, 95):
            self.store.save_outcome(
                LearningOutcome(
                    learner_id="ishani",
                    topic="Kubernetes",
                    quiz_score=score,
                )
            )
        self.store.save_outcome(
            LearningOutcome(
                learner_id="ishani",
                topic="Terraform",
                completed=False,
            )
        )

        self.assertEqual(self.store.completed_topics("ishani"), ["Kubernetes"])

    def test_recent_outcomes_and_summary_use_saved_facts(self) -> None:
        self.store.save_profile(
            LearnerProfile(
                learner_id="ishani",
                preferred_level="advanced",
                learning_preferences=["Diagrams", "Practice"],
            )
        )
        self.store.save_outcome(
            LearningOutcome(
                learner_id="ishani",
                topic="Docker",
                quiz_score=80,
                recurring_mistakes=["Image versus container"],
            )
        )
        self.store.save_outcome(
            LearningOutcome(
                learner_id="ishani",
                topic="Kubernetes",
                quiz_score=100,
                recurring_mistakes=[
                    " image versus container ",
                    "Service versus Ingress",
                ],
            )
        )

        recent = self.store.recent_outcomes("ishani", limit=1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].topic, "Kubernetes")

        summary = self.store.memory_summary("ishani")
        self.assertIn("Preferred level: advanced", summary)
        self.assertIn("Learning preferences: Diagrams, Practice", summary)
        self.assertIn("Recently completed topics: Docker, Kubernetes", summary)
        self.assertIn("Recent average quiz score: 90.0%", summary)
        self.assertEqual(summary.lower().count("image versus container"), 1)
        self.assertIn("Service versus Ingress", summary)

    def test_learner_records_are_isolated(self) -> None:
        for learner_id, level, topic in (
            ("ishani", "advanced", "MLOps"),
            ("aashir", "beginner", "Python"),
        ):
            self.store.save_profile(
                LearnerProfile(
                    learner_id=learner_id,
                    preferred_level=level,
                )
            )
            self.store.save_outcome(
                LearningOutcome(learner_id=learner_id, topic=topic)
            )

        self.assertEqual(self.store.completed_topics("ishani"), ["MLOps"])
        self.assertEqual(self.store.completed_topics("aashir"), ["Python"])
        self.assertNotIn("Python", self.store.memory_summary("ishani"))
        self.assertNotIn("MLOps", self.store.memory_summary("aashir"))

    def test_outcome_requires_an_existing_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "Save the learner profile"):
            self.store.save_outcome(
                LearningOutcome(learner_id="unknown", topic="Docker")
            )

    def test_invalid_models_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            LearnerProfile(learner_id="   ")

        with self.assertRaises(ValidationError):
            LearningOutcome(
                learner_id="ishani",
                topic="Docker",
                quiz_score=101,
            )

        with self.assertRaises(ValidationError):
            LearnerProfile(
                learner_id="ishani",
                preferred_level="intermediate",  # type: ignore[arg-type]
            )

    def test_unknown_learner_has_no_memory(self) -> None:
        self.assertIsNone(self.store.get_profile("unknown"))
        self.assertEqual(
            self.store.memory_summary("unknown"),
            "No saved learner memory.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
