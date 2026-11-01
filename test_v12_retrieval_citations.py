from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from study_guide_v12_rag_citations import (
    TrustedDocumentError,
    deterministic_section_fallback,
    format_grounded_context,
    format_source_list,
    load_trusted_chunks,
    parse_trusted_document,
    retrieve_chunks,
    verify_final_output,
    verify_citations,
    verify_quiz_questions,
    verify_sections,
)


PROJECT_DOCUMENTS = Path(__file__).parent / "trusted_documents"


class TrustedRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chunks = load_trusted_chunks(PROJECT_DOCUMENTS)

    @staticmethod
    def complete_notes() -> str:
        return """SECTION 1
Assignment: Explain energy.
Energy changes form while the total remains conserved in a closed system [S1].

SECTION 2
Assignment: Give examples.
A falling object exchanges potential and kinetic energy during its motion [S2].

SECTION 3
Assignment: Explain misconceptions.
Friction changes mechanical energy into thermal energy rather than destroying it [S1]."""

    @staticmethod
    def complete_quiz() -> str:
        return """1. How does energy change form in a closed system? [S1]
2. What energy exchange occurs while an object falls? [S2]
3. Why does friction not destroy the total energy? [S1]"""

    def test_two_documents_produce_fourteen_chunks(self) -> None:
        self.assertEqual(len(self.chunks), 14)
        self.assertEqual(
            {chunk.source_id for chunk in self.chunks},
            {"energy-foundations", "newton-motion-foundations"},
        )

    def test_energy_query_ranks_energy_source_first(self) -> None:
        results = retrieve_chunks(
            "How do friction and energy transformations conserve energy?",
            self.chunks,
            top_k=4,
        )
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].chunk.source_id, "energy-foundations")
        self.assertEqual(results[0].citation_id, "S1")

    def test_newton_query_ranks_newton_source_first(self) -> None:
        results = retrieve_chunks(
            "Explain net force, acceleration, and free-body diagrams",
            self.chunks,
            top_k=3,
        )
        self.assertEqual(results[0].chunk.source_id, "newton-motion-foundations")
        self.assertIn("force", results[0].chunk.heading.lower())

    def test_retrieval_is_deterministic(self) -> None:
        first = retrieve_chunks("conservation energy friction", self.chunks, top_k=4)
        second = retrieve_chunks("conservation energy friction", self.chunks, top_k=4)
        self.assertEqual(first, second)

    def test_grounded_context_contains_only_retrieved_ids(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        context = format_grounded_context(results)
        self.assertIn("[S1]", context)
        self.assertIn("[S2]", context)
        self.assertNotIn("[S3]", context)

    def test_valid_citations_are_accepted(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        report = verify_citations("Energy changes form [S1] and remains conserved [S2].", results)
        self.assertTrue(report.valid)
        self.assertEqual(report.cited_ids, ("S1", "S2"))

    def test_unknown_citation_is_rejected(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        report = verify_citations("This claim cites an unavailable source [S9].", results)
        self.assertFalse(report.valid)
        self.assertEqual(report.unknown_ids, ("S9",))

    def test_missing_required_citation_is_rejected(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        report = verify_citations("This answer contains no source marker.", results)
        self.assertFalse(report.valid)
        self.assertEqual(report.message, "At least one citation is required")

    def test_source_list_maps_ids_to_files_and_headings(self) -> None:
        results = retrieve_chunks("energy friction", self.chunks, top_k=2)
        source_list = format_source_list(results)
        self.assertIn("## Retrieved Sources", source_list)
        self.assertIn("[S1]", source_list)
        self.assertIn("trusted_documents/", source_list)

    def test_duplicate_source_ids_are_rejected(self) -> None:
        document = """# Example

Source ID: `duplicate-source`

## Section

Trusted text.
"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "one.md").write_text(document, encoding="utf-8")
            (root / "two.md").write_text(document, encoding="utf-8")
            with self.assertRaisesRegex(TrustedDocumentError, "Duplicate Source ID"):
                load_trusted_chunks(root)

    def test_missing_source_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "invalid.md"
            path.write_text("# Example\n\n## Section\n\nTrusted text.\n", encoding="utf-8")
            with self.assertRaisesRegex(TrustedDocumentError, "Source ID"):
                parse_trusted_document(path)

    def test_invalid_top_k_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_k"):
            retrieve_chunks("energy", self.chunks, top_k=0)

    def test_final_output_requires_citations_in_notes_and_quiz(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        report = verify_final_output(
            self.complete_notes(),
            self.complete_quiz(),
            results,
        )
        self.assertTrue(report.valid)

    def test_final_output_rejects_uncited_quiz(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        report = verify_final_output(
            self.complete_notes(),
            """1. How does energy change form in a closed system? [S1]
2. What energy exchange occurs while an object falls?
3. Why does friction not destroy the total energy? [S1]""",
            results,
        )
        self.assertFalse(report.valid)
        self.assertIn("Quiz question check failed", report.message)

    def test_final_output_rejects_unknown_note_citation(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        notes = self.complete_notes().replace("[S1]", "[S8]", 1)
        report = verify_final_output(
            notes,
            self.complete_quiz(),
            results,
        )
        self.assertFalse(report.valid)
        self.assertEqual(report.unknown_ids, ("S8",))

    def test_blank_specialist_section_is_rejected(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        notes = self.complete_notes().replace(
            "Energy changes form while the total remains conserved in a closed system [S1].",
            "",
        )
        report = verify_sections(notes, results)
        self.assertFalse(report.valid)
        self.assertIn("Section 1 lacks substantive content", report.message)

    def test_each_specialist_section_requires_its_own_citation(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        notes = self.complete_notes().replace("during its motion [S2]", "during its motion")
        report = verify_sections(notes, results)
        self.assertFalse(report.valid)
        self.assertIn("Section 2 citation check failed", report.message)

    def test_each_quiz_question_requires_its_own_citation(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        quiz = self.complete_quiz().replace("object falls? [S2]", "object falls?")
        report = verify_quiz_questions(quiz, results)
        self.assertFalse(report.valid)
        self.assertIn("Quiz question 2 citation check failed", report.message)

    def test_deterministic_section_fallback_is_substantive_and_cited(self) -> None:
        results = retrieve_chunks("energy transformations", self.chunks, top_k=2)
        fallback = deterministic_section_fallback(1, results)
        self.assertGreaterEqual(len(fallback.split()), 8)
        self.assertTrue(verify_citations(fallback, results).valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
