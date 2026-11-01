from __future__ import annotations

import tempfile
import sqlite3
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

import study_guide_v12_rag_citations as v12
import study_guide_v13_tool_using_agents as v13
import study_guide_v14_dynamic_planning as v14


def corpus():
    return [v12.TrustedChunk("energy", "Energy", "Conservation",
                            "Total energy remains conserved as energy moves between different forms.",
                            Path("trusted_documents/energy.md"), 1),
            v12.TrustedChunk("motion", "Motion", "Force",
                            "Net force changes motion through acceleration of a massive object.",
                            Path("trusted_documents/motion.md"), 1)]


class ScriptedModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class DynamicPlanningTests(unittest.TestCase):
    def test_single_request_selects_only_converter(self):
        state = v14.Workflow(corpus()).run("Convert 5 km to m")
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["executions"], 1)
        self.assertEqual([t["agent"] for t in state["plan"]["tasks"]], ["converter"])
        self.assertIn("5000 m [T1]", v14.render_report(state))

    def test_compound_goal_selects_three_specialists(self):
        state = v14.Workflow(corpus()).run("Explain energy; Calculate (12 + 8) * 3; Convert 5 km to m")
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["executions"], 3)
        self.assertEqual(state["replans"], 0)
        self.assertIn("= 60 [T2]", v14.render_report(state))

    def test_two_searches_have_distinct_global_citations(self):
        state = v14.Workflow(corpus()).run("Explain energy; Explain force")
        self.assertEqual(len(state["sources"]), 2)
        self.assertEqual(state["sources"]["S1"]["stable_id"], "energy#1")
        self.assertEqual(state["sources"]["S2"]["stable_id"], "motion#1")
        self.assertIn("[S2] [T2]", state["results"]["task2"]["content"])

    def test_same_source_reuses_global_label(self):
        state = v14.Workflow(corpus()).run("Explain energy; Explain total energy")
        self.assertEqual(len(state["sources"]), 1)
        self.assertIn("[S1] [T2]", state["results"]["task2"]["content"])

    def test_unknown_source_ends_incomplete_after_one_replan(self):
        state = v14.Workflow(corpus()).run("Explain chlorophyll")
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(state["replans"], 1)
        self.assertEqual(state["executions"], 2)
        self.assertEqual(state["sources"], {})

    def test_successful_tasks_are_not_reexecuted(self):
        state = v14.Workflow(corpus()).run("Calculate 2 + 2; Explain chlorophyll")
        self.assertEqual(state["executions"], 3)
        self.assertEqual(state["results"]["task1"]["reference"], "T1")
        self.assertEqual(state["results"]["task2"]["reference"], "T3")

    def test_invalid_arithmetic_is_not_success(self):
        state = v14.Workflow(corpus()).run("Calculate __import__('os')")
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(state["results"]["task1"]["status"], "failed")

    def test_invalid_conversion_is_not_success(self):
        state = v14.Workflow(corpus()).run("Convert 5 kg to m")
        self.assertEqual(state["status"], "incomplete")

    def test_empty_goal_rejected(self):
        with self.assertRaises(ValueError):
            v14.Workflow(corpus()).run(" ")

    def test_overlarge_plan_rejected(self):
        with self.assertRaises(ValueError):
            v14.deterministic_plan(";".join(["Calculate 1 + 1"] * 5))

    def test_unknown_agent_rejected(self):
        with self.assertRaises(ValidationError):
            v14.Task(task_id="task1", agent="shell", instruction="run", arguments={})

    def test_extra_arguments_rejected(self):
        with self.assertRaises(ValidationError):
            v14.Task(task_id="task1", agent="calculator", instruction="math",
                     arguments={"expression": "1+1", "command": "dir"})

    def test_duplicate_id_rejected(self):
        task = v14.deterministic_plan("Calculate 1+1").tasks[0]
        with self.assertRaises(ValidationError):
            v14.Plan(tasks=[task, task])

    def test_forward_dependency_rejected(self):
        task = v14.deterministic_plan("Calculate 1+1").tasks[0]
        with self.assertRaises(ValidationError):
            v14.Plan(tasks=[task.model_copy(update={"depends_on": ["task2"]})])

    def test_boolean_top_k_rejected(self):
        with self.assertRaises(ValidationError):
            v14.Task(task_id="task1", agent="researcher", instruction="query",
                     arguments={"query": "energy", "top_k": True})

    def test_two_model_failures_use_fallback(self):
        model = ScriptedModel([ValueError("bad"), {"tasks": []}])
        state = v14.Workflow(corpus(), model).run("Calculate 6 * 7")
        self.assertEqual(model.calls, 2)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len([e for e in state["events"] if e["event"] == "plan_retry"]), 2)

    def test_model_selected_plan_is_executed(self):
        plan = v14.deterministic_plan("Convert 5 km to m")
        model = ScriptedModel([plan])
        state = v14.Workflow(corpus(), model).run("Convert kilometers into meters")
        self.assertEqual(state["status"], "completed")
        self.assertEqual(model.calls, 1)

    def test_model_replans_failed_query(self):
        first = v14.deterministic_plan("Explain chlorophyll")
        revised = v14.deterministic_plan("Explain energy")
        model = ScriptedModel([first, revised])
        state = v14.Workflow(corpus(), model).run("Find a topic covered in these sources")
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["replans"], 1)
        self.assertEqual(model.calls, 2)
        self.assertEqual(state["plan"]["tasks"][0]["instruction"], "Explain chlorophyll")

    def test_compound_model_plan_cannot_silently_drop_a_request(self):
        dropped = v14.deterministic_plan("Calculate 2+2")
        model = ScriptedModel([dropped, dropped])
        state = v14.Workflow(corpus(), model).run("Calculate 2+2; Convert 5 km to m")
        self.assertEqual(state["executions"], 2)
        self.assertEqual(len(state["plan"]["tasks"]), 2)

    def test_nonfinite_conversion_rejected_at_plan_validation(self):
        with self.assertRaises(ValidationError):
            v14.Task(task_id="task1", agent="converter", instruction="convert",
                     arguments={"value": float("nan"), "from_unit": "km", "to_unit": "m"})

    def test_completed_task_is_frozen_during_replan(self):
        first = v14.deterministic_plan("Calculate 2+2; Explain chlorophyll")
        changed = v14.deterministic_plan("Calculate 9+9; Explain energy")
        model = ScriptedModel([first, changed])
        state = v14.Workflow(corpus(), model).run("Do math and find a covered topic")
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["plan"]["tasks"][0]["arguments"]["expression"], "2+2")
        self.assertEqual(state["executions"], 3)

    def test_replan_cannot_remove_failed_tasks(self):
        first = v14.deterministic_plan("Calculate 2+2; Explain chlorophyll")
        dropped = v14.deterministic_plan("Calculate 2+2")
        model = ScriptedModel([first, dropped, dropped])
        state = v14.Workflow(corpus(), model).run("Do math and search")
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(len(state["plan"]["tasks"]), 2)

    def test_failed_dependency_blocks_downstream_execution(self):
        plan = v14.deterministic_plan("Explain chlorophyll; Calculate 2+2")
        plan.tasks[1].depends_on = ["task1"]
        model = ScriptedModel([plan, plan])
        state = v14.Workflow(corpus(), model).run("Find source then calculate")
        self.assertEqual(state["results"]["task2"]["status"], "blocked")
        self.assertEqual(state["executions"], 2)

    def test_execution_budget_is_global(self):
        state = v14.Workflow(corpus()).run(";".join(["Calculate 1/0"] * 4))
        self.assertEqual(state["executions"], 8)
        self.assertEqual(state["status"], "incomplete")

    def test_execute_node_does_not_mutate_input(self):
        workflow = v14.Workflow(corpus())
        initial = workflow.plan_node(workflow.initial_state("Calculate 2+2"))
        result = workflow.execute_node(initial)
        self.assertEqual(initial["results"], {})
        self.assertEqual(initial["executions"], 0)
        self.assertEqual(result["executions"], 1)

    def test_snapshot_roundtrip_and_duplicate_rejection(self):
        state = v14.Workflow(corpus()).run("Calculate 2+2")
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runs.sqlite"
            digest = v14.corpus_digest(corpus())
            self.assertIsNone(v14.load_run(database, "session", state["goal"], digest))
            v14.save_run(database, "session", state, digest)
            self.assertEqual(v14.load_run(database, "session", state["goal"], digest), state)
            with self.assertRaises(sqlite3.IntegrityError):
                v14.save_run(database, "session", state, digest)
            with self.assertRaisesRegex(ValueError, "different goal"):
                v14.load_run(database, "session", "other goal", digest)
            with self.assertRaises(ValueError):
                v14.load_run(database, "session", state["goal"], "changed corpus")

    def test_corpus_digest_detects_changed_text(self):
        chunks = corpus()
        changed = [v12.TrustedChunk("energy", "Energy", "Conservation", "Changed text",
                                   Path("trusted_documents/energy.md"), 1)]
        self.assertNotEqual(v14.corpus_digest(chunks), v14.corpus_digest(changed))

    def test_snapshot_connections_close_on_success_early_return_and_error(self):
        state = v14.Workflow(corpus()).run("Calculate 2+2")
        real_connect = sqlite3.connect
        opened = []

        def tracked_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            opened.append(connection)
            return connection

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runs.sqlite"
            with real_connect(database) as empty_database:
                pass
            empty_database.close()
            try:
                with patch.object(v14.sqlite3, "connect", side_effect=tracked_connect):
                    self.assertIsNone(v14.load_run(database, "session", state["goal"], "digest"))
                    v14.save_run(database, "session", state, "digest")
                    self.assertIsNone(v14.load_run(database, "missing", state["goal"], "digest"))
                    self.assertEqual(v14.load_run(database, "session", state["goal"], "digest"), state)
                    with self.assertRaises(ValueError):
                        v14.load_run(database, "session", "changed goal", "digest")
                    with self.assertRaises(sqlite3.IntegrityError):
                        v14.save_run(database, "session", state, "digest")
                self.assertEqual(len(opened), 6)
                for connection in opened:
                    with self.assertRaises(sqlite3.ProgrammingError):
                        connection.execute("SELECT 1")
            finally:
                for connection in opened:
                    connection.close()

    def test_declining_confirmation_creates_no_database_or_model(self):
        with patch("builtins.input", side_effect=["Calculate 2+2", "test", "n"]), \
             patch("sys.argv", ["v14", "--offline"]), \
             patch.object(v14, "save_run") as save, \
             patch.object(v14.v12, "load_trusted_chunks") as load:
            v14.main()
        save.assert_not_called()
        load.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "LangGraph not installed")
    def test_langgraph_matches_offline_executor(self):
        goal = "Explain energy; Calculate 6*7; Convert 5 km to m"
        workflow = v14.Workflow(corpus())
        expected = workflow.run(goal)
        actual = workflow.build_graph().invoke(workflow.initial_state(goal), {"recursion_limit": 16})
        self.assertEqual(actual, expected)

    @unittest.skipUnless(importlib.util.find_spec("langgraph"), "LangGraph not installed")
    def test_langgraph_failed_task_terminates_within_budget(self):
        workflow = v14.Workflow(corpus())
        state = workflow.build_graph().invoke(workflow.initial_state("Calculate 1/0"),
                                              {"recursion_limit": 16})
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(state["replans"], 1)
        self.assertEqual(state["executions"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
