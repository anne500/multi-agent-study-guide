from __future__ import annotations

import copy
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import study_guide_v12_rag_citations as v12
import study_guide_v14_dynamic_planning as v14
import study_guide_v15_evaluation_observability as v15


def corpus():
    return [v12.TrustedChunk("energy", "Conservation of Energy", "Energy",
                            "Total energy remains conserved as energy moves between different forms.",
                            Path("trusted_documents/energy.md"), 1)]


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls += 1
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


class ObservabilityTests(unittest.TestCase):
    def test_observation_preserves_v14_state(self):
        goal = "Explain conservation of energy; Calculate (12+8)*3; Convert 5 km to m"
        observed = v15.observe_run(goal, corpus())
        original = v14.Workflow(corpus()).run(goal)
        self.assertEqual(observed["state"], original)

    def test_offline_metrics_have_no_model_calls(self):
        metrics = v15.observe_run("Calculate 6*7", corpus())["metrics"]
        self.assertEqual(metrics["model_attempts"], 0)
        self.assertEqual(metrics["tasks_completed"], 1)
        self.assertEqual(metrics["tool_attempts"], 1)
        self.assertEqual(metrics["deterministic_plan_rounds"], 1)
        self.assertIsNone(metrics["model_plan_acceptance_rate"])
        self.assertIsNone(metrics["model_tokens"])

    def test_model_acceptance_counted_from_actual_attempt(self):
        model = ScriptedModel([v14.deterministic_plan("Calculate 6*7")])
        run = v15.observe_run("Calculate 6*7", corpus(), model)
        self.assertEqual(model.calls, 1)
        self.assertEqual(run["metrics"]["model_attempts"], 1)
        self.assertEqual(run["metrics"]["accepted_model_plans"], 1)
        self.assertEqual(run["metrics"]["model_plan_acceptance_rate"], 1)

    def test_parser_failure_and_fallback_are_distinguished(self):
        model = ScriptedModel([ValueError("bad response"), {"tasks": []}])
        metrics = v15.observe_run("Calculate 6*7", corpus(), model)["metrics"]
        self.assertEqual(model.calls, 2)
        self.assertEqual(metrics["model_attempts"], 2)
        self.assertEqual(metrics["model_call_errors"], 1)
        self.assertEqual(metrics["rejected_model_attempts"], 2)
        self.assertEqual(metrics["deterministic_plan_rounds"], 1)
        self.assertEqual(metrics["model_plan_acceptance_rate"], 0)

    def test_model_configuration_errors_are_traced(self):
        class BrokenModel:
            def with_structured_output(self, schema):
                raise ValueError("Unsupported schema")
        metrics = v15.observe_run("Calculate 2+2", corpus(), BrokenModel())["metrics"]
        self.assertEqual(metrics["model_attempts"], 2)
        self.assertEqual(metrics["model_call_errors"], 2)

    def test_failure_counts_attempts_and_expected_replan(self):
        run = v15.observe_run("Calculate 1/0", corpus())
        metrics = run["metrics"]
        self.assertEqual(metrics["tasks_completed"], 0)
        self.assertEqual(metrics["tool_attempts"], 2)
        self.assertEqual(metrics["replans"], 1)
        outcomes = [e for e in run["trace"] if e["kind"] == "task_outcome"]
        self.assertEqual([e["status"] for e in outcomes], ["failed", "failed"])

    def test_trace_has_ordered_unique_sequences(self):
        trace = v15.observe_run("Calculate 2+2", corpus())["trace"]
        self.assertEqual([e["sequence"] for e in trace], list(range(1, len(trace)+1)))
        self.assertEqual([e["offset_ms"] for e in trace], sorted(e["offset_ms"] for e in trace))

    def test_stage_durations_are_measured_not_assumed(self):
        ticks = iter(range(100))
        recorder = v15.TraceRecorder(clock=lambda: next(ticks))
        result = recorder.call("test", lambda: 42)
        self.assertEqual(result, 42)
        end = recorder.events[-1]
        self.assertEqual(end["duration_ms"], 2000)
        self.assertEqual(end["outcome"], "ok")

    def test_unhandled_stage_error_is_recorded_and_propagated(self):
        recorder = v15.TraceRecorder()
        def fail():
            raise RuntimeError("failure")
        with self.assertRaises(RuntimeError):
            recorder.call("test", fail)
        self.assertEqual(recorder.events[-1]["outcome"], "error")
        self.assertEqual(recorder.events[-1]["error_type"], "RuntimeError")

    def test_phase_metrics_disclose_overlap(self):
        run = v15.observe_run("Calculate 2+2", corpus())
        self.assertTrue(run["metrics"]["phase_durations_overlap"])
        self.assertEqual(set(run["metrics"]["phase_duration_ms"]),
                         {"planning", "specialists", "evaluation"})
        self.assertGreaterEqual(run["elapsed_ms"], 0)

    def test_known_citations_pass_without_claiming_semantic_grounding(self):
        report = v15.observe_run("Explain energy", corpus())["citation_integrity"]
        self.assertTrue(report["passed"])
        self.assertEqual(report["citation_occurrences"], 1)
        self.assertFalse(report["semantic_entailment_evaluated"])

    def test_unknown_source_label_is_rejected(self):
        state = v15.observe_run("Explain energy", corpus())["state"]
        state["results"]["task1"]["content"] = "Claim [S99] [T1]"
        report = v15.citation_integrity(state)
        self.assertFalse(report["passed"])
        self.assertTrue(any("unknown source" in i for i in report["issues"]))

    def test_citation_with_wrong_evidence_text_is_rejected(self):
        state = v15.observe_run("Explain energy", corpus())["state"]
        state["results"]["task1"]["content"] = "Unrelated sentence [S1] [T1]"
        self.assertFalse(v15.citation_integrity(state)["passed"])

    def test_missing_tool_reference_is_rejected(self):
        state = v15.observe_run("Calculate 2+2", corpus())["state"]
        state["results"]["task1"]["content"] = "2+2=4"
        self.assertFalse(v15.citation_integrity(state)["passed"])

    def test_reference_exceeding_executions_is_rejected(self):
        state = v15.observe_run("Calculate 2+2", corpus())["state"]
        state["results"]["task1"].update(reference="T9", content="2+2=4 [T9]")
        self.assertFalse(v15.citation_integrity(state)["passed"])

    def test_duplicate_source_mapping_is_rejected(self):
        state = v15.observe_run("Explain energy", corpus())["state"]
        state["sources"]["S2"] = copy.deepcopy(state["sources"]["S1"])
        self.assertFalse(v15.citation_integrity(state)["passed"])

    def test_five_case_benchmark_passes_including_expected_failures(self):
        suite = v15.run_benchmark(corpus())
        self.assertEqual(suite["cases_total"], 5)
        self.assertEqual(suite["cases_passed"], 5)
        self.assertEqual(suite["case_pass_rate"], 1)
        self.assertEqual(suite["runs"][3]["state"]["status"], "incomplete")

    def test_benchmark_detects_wrong_arithmetic_result(self):
        case = v15.benchmark_cases()[0]
        run = v15.observe_run(case["goal"], corpus())
        run["state"]["results"]["task1"]["content"] = "6 * 7 = 43 [T1]"
        evaluation = v15.evaluate_case(case, run)
        self.assertFalse(evaluation["passed"])
        self.assertFalse(evaluation["checks"]["expected_result_task1"])

    def test_failed_check_is_visible_in_formatted_benchmark(self):
        suite = v15.run_benchmark([])
        self.assertEqual(suite["cases_passed"], 4)
        self.assertIn("compound: FAIL", v15.format_report(suite))

    def test_case_evaluation_rechecks_current_citations_instead_of_cached_pass(self):
        case = v15.benchmark_cases()[2]
        run = v15.observe_run(case["goal"], corpus())
        self.assertTrue(run["citation_integrity"]["passed"])
        run["state"]["results"]["task1"]["content"] = "False claim [S99] [T1]"
        evaluation = v15.evaluate_case(case, run)
        self.assertFalse(evaluation["passed"])
        self.assertFalse(evaluation["checks"]["citation_integrity"])

    def test_budget_violation_is_reported(self):
        run = v15.observe_run("Calculate 2+2", corpus())
        run["state"]["executions"] = 9
        metrics = v15.execution_metrics(run["state"], run["trace"])
        self.assertFalse(metrics["budget_respected"])

    def test_distinct_runs_have_distinct_ids(self):
        first = v15.observe_run("Calculate 2+2", corpus())
        second = v15.observe_run("Calculate 2+2", corpus())
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["corpus_digest"], second["corpus_digest"])

    def test_persistence_roundtrip_duplicate_and_readonly_missing(self):
        run = v15.observe_run("Calculate 2+2", corpus())
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "reports.sqlite"
            identifier = v15.persist_report(database, run)
            self.assertEqual(v15.read_report(database, identifier), run)
            with self.assertRaises(sqlite3.IntegrityError):
                v15.persist_report(database, run)
            with self.assertRaisesRegex(ValueError, "not found"):
                v15.read_report(database, "missing")
            missing = Path(directory) / "missing.sqlite"
            with self.assertRaises(sqlite3.OperationalError):
                v15.read_report(missing, "missing")
            self.assertFalse(missing.exists())

    def test_all_database_connections_close_on_success_and_error(self):
        run = v15.observe_run("Calculate 2+2", corpus())
        real_connect, opened = sqlite3.connect, []
        def tracked(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            opened.append(connection)
            return connection
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "reports.sqlite"
            try:
                with patch.object(v15.sqlite3, "connect", side_effect=tracked):
                    v15.persist_report(database, run)
                    v15.read_report(database, run["run_id"])
                    with self.assertRaises(sqlite3.IntegrityError):
                        v15.persist_report(database, run)
                    with self.assertRaises(ValueError):
                        v15.read_report(database, "missing")
                self.assertEqual(len(opened), 4)
                for connection in opened:
                    with self.assertRaises(sqlite3.ProgrammingError):
                        connection.execute("SELECT 1")
            finally:
                for connection in opened:
                    connection.close()

    def test_declining_confirmation_avoids_sources_model_and_database(self):
        with patch("sys.argv", ["v15", "--benchmark"]), \
             patch("builtins.input", return_value="n"), \
             patch.object(v15, "run_benchmark") as benchmark, \
             patch.object(v15, "persist_report") as save, \
             patch.object(v14.v12, "load_trusted_chunks") as load:
            v15.main()
        benchmark.assert_not_called()
        save.assert_not_called()
        load.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "LangGraph not installed")
    def test_observed_graph_preserves_v14_execution(self):
        goal = "Explain energy; Calculate 6*7; Convert 5 km to m"
        run = v15.observe_run(goal, corpus(), use_graph=True)
        self.assertEqual(run["state"], v14.Workflow(corpus()).run(goal))
        self.assertEqual(run["engine"], "langgraph")
        self.assertEqual(run["metrics"]["tool_attempts"], 3)

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "LangGraph not installed")
    def test_graph_model_replan_is_measured_and_completed_task_retained(self):
        first = v14.deterministic_plan("Calculate 2+2; Explain nomatchzzz")
        second = v14.deterministic_plan("Calculate 9+9; Explain energy")
        run = v15.observe_run("Do arithmetic and find a topic", corpus(),
                              ScriptedModel([first, second]), use_graph=True)
        self.assertEqual(run["state"]["status"], "completed")
        self.assertEqual(run["metrics"]["model_attempts"], 2)
        self.assertEqual(run["metrics"]["replans"], 1)
        self.assertIn("= 4 [T1]", run["state"]["results"]["task1"]["content"])
        self.assertEqual(run["metrics"]["tool_attempts"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
