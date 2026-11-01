from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

import study_guide_v12_rag_citations as v12
from study_guide_v13_tool_using_agents import (
    ToolCall,
    ToolDecision,
    ToolInputError,
    ToolObservation,
    ToolRegistry,
    ToolSpec,
    build_default_registry,
    calculator_handler,
    convert_units,
    deterministic_tool_decision,
    render_observation_answer,
    safe_calculate,
    unit_converter_handler,
    verify_observation,
    verify_tool_answer,
)


def trusted_chunks() -> list[v12.TrustedChunk]:
    path = Path("trusted_documents/conservation_of_energy.md")
    return [
        v12.TrustedChunk(
            source_id="energy-foundations",
            title="Conservation of Energy",
            heading="Energy Transformations",
            text=(
                "Energy can move between kinetic, potential, thermal, and other "
                "forms while total energy remains conserved in a closed system."
            ),
            path=path,
            chunk_index=1,
        ),
        v12.TrustedChunk(
            source_id="energy-foundations",
            title="Conservation of Energy",
            heading="Friction",
            text=(
                "Friction converts mechanical energy into thermal energy rather "
                "than destroying the total energy."
            ),
            path=path,
            chunk_index=2,
        ),
    ]


class ToolUsingAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = build_default_registry(trusted_chunks())

    def test_registry_contains_only_three_approved_tools(self) -> None:
        self.assertEqual(
            self.registry.names(),
            ("calculator", "trusted_search", "unit_converter"),
        )

    def test_duplicate_tool_registration_is_rejected(self) -> None:
        registry = ToolRegistry()
        spec = ToolSpec("calculator", "test", calculator_handler)
        registry.register(spec)
        with self.assertRaisesRegex(ValueError, "Duplicate tool"):
            registry.register(spec)

    def test_invalid_tool_name_is_rejected(self) -> None:
        registry = ToolRegistry()
        with self.assertRaisesRegex(ValueError, "Invalid tool name"):
            registry.register(ToolSpec("Shell Tool", "unsafe", calculator_handler))

    def test_unknown_tool_returns_safe_failure(self) -> None:
        observation = self.registry.execute(
            ToolCall(tool_name="shell", arguments={"command": "dir"}),
            1,
        )
        self.assertFalse(observation.ok)
        self.assertEqual(observation.error_code, "unknown_tool")
        self.assertIn("[T1]", observation.content)
        self.assertTrue(verify_observation(observation))

    def test_calculator_evaluates_bounded_arithmetic(self) -> None:
        self.assertEqual(safe_calculate("(12 + 8) * 3 / 2"), 30)

    def test_calculator_rejects_code_execution(self) -> None:
        with self.assertRaises(ToolInputError):
            safe_calculate("__import__('os').system('dir')")

    def test_calculator_rejects_division_by_zero(self) -> None:
        with self.assertRaisesRegex(ToolInputError, "Division by zero"):
            safe_calculate("10 / 0")

    def test_calculator_rejects_large_exponent(self) -> None:
        with self.assertRaisesRegex(ToolInputError, "Exponent"):
            safe_calculate("2 ** 100")

    def test_calculator_handler_returns_valid_observation(self) -> None:
        observation = calculator_handler({"expression": "6 * 7"}, "T1")
        self.assertTrue(observation.ok)
        self.assertEqual(observation.content, "6 * 7 = 42 [T1]")
        self.assertTrue(verify_observation(observation))

    def test_calculator_requires_string_expression(self) -> None:
        with self.assertRaisesRegex(ToolInputError, "expression"):
            calculator_handler({"expression": 42}, "T1")

    def test_length_conversion_is_correct(self) -> None:
        self.assertEqual(convert_units(5, "km", "m"), 5000)

    def test_mass_conversion_is_correct(self) -> None:
        self.assertAlmostEqual(convert_units(2.2, "lb", "kg"), 0.997903214, places=9)

    def test_cross_dimension_conversion_is_rejected(self) -> None:
        with self.assertRaisesRegex(ToolInputError, "different measurement dimensions"):
            convert_units(1, "kg", "m")

    def test_unknown_unit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ToolInputError, "Unknown unit"):
            convert_units(1, "parsec", "m")

    def test_unit_converter_handler_returns_valid_observation(self) -> None:
        observation = unit_converter_handler(
            {"value": 90, "from_unit": "min", "to_unit": "h"},
            "T2",
        )
        self.assertTrue(observation.ok)
        self.assertIn("90 min = 1.5 h [T2]", observation.content)
        self.assertTrue(verify_observation(observation))

    def test_trusted_search_returns_cited_observation(self) -> None:
        observation = self.registry.execute(
            ToolCall(
                tool_name="trusted_search",
                arguments={"query": "How does friction affect energy?", "top_k": 2},
            ),
            1,
        )
        self.assertTrue(observation.ok)
        self.assertEqual(observation.source_citations, ("S1", "S2"))
        self.assertIn("[S1]", observation.content)
        self.assertIn("[T1]", observation.content)
        self.assertTrue(verify_observation(observation))

    def test_trusted_search_no_match_fails_safely(self) -> None:
        observation = self.registry.execute(
            ToolCall(
                tool_name="trusted_search",
                arguments={"query": "photosynthesis chlorophyll", "top_k": 2},
            ),
            1,
        )
        self.assertFalse(observation.ok)
        self.assertEqual(observation.error_code, "no_results")

    def test_trusted_search_rejects_invalid_top_k(self) -> None:
        observation = self.registry.execute(
            ToolCall(
                tool_name="trusted_search",
                arguments={"query": "energy", "top_k": 8},
            ),
            1,
        )
        self.assertFalse(observation.ok)
        self.assertEqual(observation.error_code, "invalid_arguments")

    def test_observation_requires_its_tool_reference(self) -> None:
        observation = ToolObservation(
            observation_id="T1",
            tool_name="calculator",
            ok=True,
            content="The result is 42.",
        )
        self.assertFalse(verify_observation(observation))

    def test_tool_answer_accepts_known_reference(self) -> None:
        observation = calculator_handler({"expression": "6 * 7"}, "T1")
        self.assertTrue(verify_tool_answer("The result is 42 [T1].", [observation]))

    def test_tool_answer_rejects_unknown_tool_reference(self) -> None:
        observation = calculator_handler({"expression": "6 * 7"}, "T1")
        self.assertFalse(verify_tool_answer("The result is 42 [T9].", [observation]))

    def test_trusted_answer_requires_source_citation(self) -> None:
        observation = self.registry.execute(
            ToolCall(
                tool_name="trusted_search",
                arguments={"query": "friction energy", "top_k": 1},
            ),
            1,
        )
        self.assertFalse(verify_tool_answer("The search ran successfully [T1].", [observation]))
        self.assertTrue(
            verify_tool_answer(
                "Friction converts mechanical energy to thermal energy [S1] [T1].",
                [observation],
            )
        )

    def test_tool_answer_rejects_unknown_source_citation(self) -> None:
        observation = self.registry.execute(
            ToolCall(
                tool_name="trusted_search",
                arguments={"query": "friction energy", "top_k": 1},
            ),
            1,
        )
        self.assertFalse(
            verify_tool_answer("Unsupported claim [S9] [T1].", [observation])
        )

    def test_fallback_routes_unit_conversion(self) -> None:
        decision = deterministic_tool_decision("Convert 5 km to m", [])
        self.assertEqual(decision.action, "tool")
        self.assertEqual(decision.tool_call.tool_name, "unit_converter")

    def test_fallback_routes_calculation(self) -> None:
        decision = deterministic_tool_decision("Calculate (12 + 8) * 3", [])
        self.assertEqual(decision.tool_call.tool_name, "calculator")

    def test_fallback_routes_factual_question_to_trusted_search(self) -> None:
        decision = deterministic_tool_decision("Why does friction produce heat?", [])
        self.assertEqual(decision.tool_call.tool_name, "trusted_search")

    def test_fallback_finishes_after_observation(self) -> None:
        observation = calculator_handler({"expression": "2 + 2"}, "T1")
        decision = deterministic_tool_decision("Calculate 2 + 2", [observation])
        self.assertEqual(decision.action, "final")
        self.assertIn("[T1]", decision.final_response)

    def test_tool_decision_schema_requires_tool_call(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDecision(action="tool", reason="Missing payload")

    def test_tool_decision_schema_requires_final_response(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDecision(action="final", reason="Missing response")

    def test_render_prefers_successful_observations(self) -> None:
        failed = ToolObservation(
            observation_id="T1",
            tool_name="calculator",
            ok=False,
            content="Invalid expression [T1].",
            error_code="invalid_arguments",
        )
        successful = calculator_handler({"expression": "3 + 4"}, "T2")
        rendered = render_observation_answer([failed, successful])
        self.assertNotIn("Invalid expression", rendered)
        self.assertIn("3 + 4 = 7 [T2]", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
