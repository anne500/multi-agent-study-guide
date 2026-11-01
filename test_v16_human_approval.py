from __future__ import annotations

import copy
import io
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import study_guide_v12_rag_citations as v12
import study_guide_v14_dynamic_planning as v14
import study_guide_v16_human_approval as v16


def corpus():
    return [v12.TrustedChunk("energy", "Conservation of Energy", "Conservation",
                            "Total energy remains conserved as energy moves between different forms.",
                            Path("trusted_documents/energy.md"), 1)]


class ScriptedModel:
    def __init__(self):
        self.calls = 0

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls += 1
        return v14.deterministic_plan("Calculate 6*7")


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.app = v16.build_review_graph(corpus(), InMemorySaver())
        self.config = {"configurable": {"thread_id": "test"}, "recursion_limit": 32}

    def start(self, goal="Calculate 6*7"):
        return self.app.invoke(v16.initial_state(goal, corpus(), True), self.config)

    def snapshot(self):
        return self.app.get_state(self.config)

    def decide(self, action="approve", **extra):
        pending = v16.current_interrupt(self.snapshot())
        return self.app.invoke(Command(resume={"action": action, "review_id": pending["review_id"],
                                               **extra}), self.config)

    def test_initial_pause_has_plan_but_no_tool_execution(self):
        self.start()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.values["executions"], 0)
        self.assertEqual(v16.current_interrupt(snapshot)["gate"], "plan_review")
        self.assertEqual(snapshot.values["approvals"], {})

    def test_plan_approval_executes_then_pauses_for_content(self):
        self.start()
        self.decide()
        self.assertEqual(self.snapshot().values["executions"], 1)
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "content_review")

    def test_content_approval_creates_assessment_and_pauses_for_final(self):
        self.start()
        self.decide()
        self.decide()
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "final_review")
        self.assertIn("[T1]", self.snapshot().values["assessment"][0])

    def test_only_three_approvals_complete_session(self):
        self.start()
        for _ in range(3):
            self.decide()
        state = self.snapshot().values
        self.assertEqual(state["status"], "approved")
        self.assertEqual(len(state["approvals"]), 3)
        self.assertEqual(len(state["audit"]), 4)
        self.assertFalse(self.snapshot().next)

    def test_reject_plan_never_executes_tools(self):
        self.start()
        self.decide("reject", note="Wrong plan")
        self.assertEqual(self.snapshot().values["status"], "rejected")
        self.assertEqual(self.snapshot().values["executions"], 0)

    def test_reject_content_stops_without_assessment(self):
        self.start()
        self.decide()
        self.decide("reject", note="Content insufficient")
        self.assertEqual(self.snapshot().values["assessment"], [])
        self.assertEqual(self.snapshot().values["status"], "rejected")

    def test_reject_final_does_not_record_final_approval(self):
        self.start()
        self.decide()
        self.decide()
        self.decide("reject", note="Do not complete")
        self.assertNotIn("final_review", self.snapshot().values["approvals"])
        self.assertEqual(self.snapshot().values["status"], "rejected")

    def test_stale_approval_is_rejected_at_new_gate(self):
        self.start()
        stale = v16.current_interrupt(self.snapshot())["review_id"]
        self.decide()
        self.app.invoke(Command(resume={"action": "approve", "review_id": stale}), self.config)
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "content_review")
        self.assertIn("Stale", self.snapshot().values["message"])
        self.assertEqual(self.snapshot().values["executions"], 1)

    def test_unsupported_action_keeps_review_pending(self):
        self.start()
        self.decide("skip")
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "plan_review")
        self.assertEqual(self.snapshot().values["executions"], 0)

    def test_reject_requires_reason(self):
        self.start()
        self.decide("reject", note="")
        self.assertTrue(self.snapshot().next)
        self.assertEqual(self.snapshot().values["status"], "awaiting_review")

    def test_revision_requires_reason_and_plan(self):
        self.start()
        self.decide("revise", note="Change it")
        self.assertEqual(self.snapshot().values["revision"], 0)

    def test_revision_of_plan_requires_fresh_approval(self):
        self.start()
        replacement = v14.deterministic_plan("Calculate 3*3").model_dump()
        self.decide("revise", plan=replacement, note="Use a smaller example")
        self.assertEqual(self.snapshot().values["executions"], 0)
        self.assertEqual(self.snapshot().values["revision"], 1)
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "plan_review")
        self.decide()
        self.assertIn("= 9", self.snapshot().values["results"]["task1"]["content"])

    def test_content_revision_retains_unchanged_completed_task(self):
        self.start("Calculate 2+2; Convert 5 km to m")
        self.decide()
        replacement = v14.deterministic_plan("Calculate 3+3; Convert 5 km to m").model_dump()
        self.decide("revise", plan=replacement, note="Change only calculation")
        state = self.snapshot().values
        self.assertEqual(set(state["results"]), {"task2"})
        self.assertEqual(state["approvals"], {})
        self.decide()
        state = self.snapshot().values
        self.assertEqual(state["executions"], 3)
        self.assertEqual(state["results"]["task2"]["reference"], "T2")
        self.assertEqual(state["results"]["task1"]["reference"], "T3")

    def test_changed_dependency_invalidates_downstream_result(self):
        plan = v14.deterministic_plan("Calculate 2+2; Calculate 3+3")
        plan.tasks[1].depends_on = ["task1"]
        state = v14.Workflow(corpus()).run("Calculate 2+2; Calculate 3+3")
        state["plan"] = plan.model_dump()
        revised = plan.model_copy(deep=True)
        revised.tasks[0].arguments = {"expression": "4+4"}
        self.assertEqual(v16.invalidate_results(state, revised), {})

    def test_final_revision_invalidates_assessment_and_all_approvals(self):
        self.start()
        self.decide()
        self.decide()
        replacement = v14.deterministic_plan("Calculate 5+5").model_dump()
        self.decide("revise", plan=replacement, note="Change calculation")
        self.assertEqual(self.snapshot().values["assessment"], [])
        self.assertEqual(self.snapshot().values["approvals"], {})
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "plan_review")

    def test_unknown_agent_revision_is_rejected(self):
        self.start()
        replacement = copy.deepcopy(self.snapshot().values["plan"])
        replacement["tasks"][0]["agent"] = "shell"
        self.decide("revise", plan=replacement, note="Invalid agent")
        self.assertEqual(self.snapshot().values["revision"], 0)
        self.assertEqual(self.snapshot().values["executions"], 0)

    def test_incomplete_content_cannot_be_approved(self):
        self.start("Calculate 1/0")
        self.decide()
        self.decide()
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "content_review")
        self.assertIn("Incomplete", self.snapshot().values["message"])

    def test_human_can_fix_failed_task_then_approve(self):
        self.start("Calculate 1/0")
        self.decide()
        self.decide("revise", plan=v14.deterministic_plan("Calculate 1/2").model_dump(), note="Fix denominator")
        for _ in range(3):
            self.decide()
        self.assertEqual(self.snapshot().values["status"], "approved")
        self.assertEqual(self.snapshot().values["executions"], 2)

    def test_revision_budget_is_enforced(self):
        self.start()
        for index in range(3):
            self.decide("revise", plan=v14.deterministic_plan(f"Calculate {index}+1").model_dump(), note="Edit")
        self.decide("revise", plan=v14.deterministic_plan("Calculate 8+8").model_dump(), note="Edit")
        self.assertEqual(self.snapshot().values["revision"], 3)
        self.assertIn("Revision limit", self.snapshot().values["message"])

    def test_missing_or_invented_citation_blocks_content_approval(self):
        self.start("Explain energy")
        self.decide()
        state = copy.deepcopy(self.snapshot().values)
        state["results"]["task1"]["content"] = "Unsupported [S99] [T1]"
        payload = {"action": "approve", "review_id": v16.review_id(state, "content_review")}
        outcome = v16.apply_decision(state, "content_review", payload)
        self.assertEqual(outcome["next_node"], "content_review")
        self.assertIn("integrity", outcome["message"])

    def test_assessment_is_based_on_approved_evidence(self):
        self.start("Explain energy")
        self.decide()
        self.decide()
        question = self.snapshot().values["assessment"][0]
        self.assertIn("[S1]", question)
        self.assertIn("[T1]", question)

    def test_tampered_assessment_blocks_final_approval(self):
        self.start()
        self.decide()
        self.decide()
        state = copy.deepcopy(self.snapshot().values)
        state["assessment"] = ["Invented question [S99]"]
        outcome = v16.apply_decision(state, "final_review", {
            "action": "approve", "review_id": v16.review_id(state, "final_review")})
        self.assertEqual(outcome["next_node"], "final_review")
        self.assertNotIn("final_review", outcome["approvals"])

    def test_instruction_cannot_inject_unavailable_question_citations(self):
        self.start("Explain energy [S99] [T99]")
        self.decide()
        self.decide()
        question = self.snapshot().values["assessment"][0]
        self.assertNotIn("[S99]", question)
        self.assertNotIn("[T99]", question)
        self.assertIn("[S1]", question)

    def test_revised_assessment_and_display_use_approved_expression(self):
        self.start("Calculate 1 / 0")
        self.decide()
        replacement = copy.deepcopy(self.snapshot().values["plan"])
        replacement["tasks"][0]["arguments"] = {"expression": "1 / 2"}
        self.decide("revise", note="Correct the denominator", plan=replacement)
        self.decide()
        self.decide()
        state = self.snapshot().values
        question = state["assessment"][0]
        self.assertIn("Calculate 1 / 2", question)
        self.assertNotIn("1 / 0", question)
        self.assertEqual(state["plan"]["tasks"][0]["instruction"], "Calculate 1 / 0")
        output = io.StringIO()
        with redirect_stdout(output):
            v16.display_state(state)
        self.assertIn("Original task request: Calculate 1 / 0", output.getvalue())
        self.assertIn("Approved task: Calculate 1 / 2", output.getvalue())
        self.assertNotIn("V14 status:", output.getvalue())

    def test_task_labels_follow_conversion_and_search_argument_edits(self):
        converter = v14.Task(task_id="task1", agent="converter", instruction="Convert 5 km to m",
                            arguments={"value": 10, "from_unit": "km", "to_unit": "m"})
        researcher = v14.Task(task_id="task2", agent="researcher", instruction="Explain energy",
                             arguments={"query": "total energy [S99]", "top_k": 4})
        self.assertEqual(v16.approved_task_label(converter), "Convert 10 km to m")
        self.assertEqual(v16.approved_task_label(researcher), "Search approved documents for: total energy")

    def test_model_plan_is_not_repeated_on_gate_resume(self):
        model = ScriptedModel()
        app = v16.build_review_graph(corpus(), InMemorySaver(), model)
        app.invoke(v16.initial_state("Calculate 6*7", corpus(), False), self.config)
        for _ in range(3):
            pending = v16.current_interrupt(app.get_state(self.config))
            app.invoke(Command(resume={"action": "approve", "review_id": pending["review_id"]}), self.config)
        self.assertEqual(model.calls, 1)

    def test_resume_rejects_changed_mode_corpus_or_version(self):
        state = v16.initial_state("Calculate 6*7", corpus(), True)
        v16.validate_resume(state, corpus(), True)
        with self.assertRaises(ValueError):
            v16.validate_resume(state, corpus(), False)
        with self.assertRaises(ValueError):
            v16.validate_resume(state, [], True)
        state["version"] = "different-version"
        with self.assertRaises(ValueError):
            v16.validate_resume(state, corpus(), True)

    def test_restart_sqlite_session_resumes_without_repeating_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "checkpoints.sqlite"
            with closing(sqlite3.connect(database, check_same_thread=False)) as connection:
                app = v16.build_review_graph(corpus(), SqliteSaver(connection))
                app.invoke(v16.initial_state("Calculate 6*7", corpus(), True), self.config)
                pending = v16.current_interrupt(app.get_state(self.config))
                app.invoke(Command(resume={"action": "approve", "review_id": pending["review_id"]}), self.config)
            with closing(sqlite3.connect(database, check_same_thread=False)) as connection:
                app = v16.build_review_graph(corpus(), SqliteSaver(connection))
                snapshot = app.get_state(self.config)
                self.assertEqual(snapshot.values["executions"], 1)
                self.assertEqual(v16.current_interrupt(snapshot)["gate"], "content_review")
                for _ in range(2):
                    pending = v16.current_interrupt(app.get_state(self.config))
                    app.invoke(Command(resume={"action": "approve", "review_id": pending["review_id"]}), self.config)
                self.assertEqual(app.get_state(self.config).values["status"], "approved")
                self.assertEqual(app.get_state(self.config).values["executions"], 1)
            # Windows must be able to rename after both connection scopes close.
            database.rename(Path(directory) / "closed.sqlite")

    def test_cli_pauses_and_resumes_across_invocations(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(v16, "__file__", str(Path(directory) / "v16.py")), \
                 patch.object(v14.v12, "load_trusted_chunks", return_value=corpus()), \
                 patch("sys.argv", ["v16", "--offline"]), \
                 patch("builtins.input", side_effect=["Calculate 6*7", "y", "pause"]), \
                 redirect_stdout(output):
                v16.main()
            session = re.search(r"Session ID: (v16-[a-f0-9]+)", output.getvalue()).group(1)
            for actions in (["y", "approve", "pause"], ["y", "approve", "approve"]):
                with patch.object(v16, "__file__", str(Path(directory) / "v16.py")), \
                     patch.object(v14.v12, "load_trusted_chunks", return_value=corpus()), \
                     patch("sys.argv", ["v16", "--session", session, "--offline"]), \
                     patch("builtins.input", side_effect=actions), redirect_stdout(output):
                    v16.main()
            self.assertIn("status: approved", output.getvalue())
            self.assertIn("Tool executions: 1/8", output.getvalue())
            database = Path(directory) / "study_guide_v16_checkpoints.sqlite"
            database.rename(Path(directory) / "closed.sqlite")

    def test_trace_sequences_remain_unique_across_nodes(self):
        self.start()
        self.decide()
        trace = self.snapshot().values["trace"]
        self.assertEqual([e["sequence"] for e in trace], list(range(1, len(trace) + 1)))
        self.assertEqual({e["segment_id"] for e in trace}, {1, 2})

    def test_decision_does_not_mutate_input(self):
        self.start()
        state = self.snapshot().values
        saved = copy.deepcopy(state)
        result = v16.apply_decision(state, "plan_review", {
            "action": "approve", "review_id": v16.review_id(state, "plan_review")})
        self.assertEqual(state, saved)
        self.assertIn("plan_review", result["approvals"])

    def test_execution_budget_persists_across_revisions(self):
        self.start(";".join(["Calculate 2+2"] * 4))
        self.decide()
        self.decide("revise", note="Change all tasks", plan=v14.deterministic_plan(
            ";".join(["Calculate 3+3"] * 4)).model_dump())
        self.decide()
        self.assertEqual(self.snapshot().values["executions"], 8)
        self.decide("revise", note="Another revision", plan=v14.deterministic_plan(
            ";".join(["Calculate 4+4"] * 4)).model_dump())
        self.decide()
        self.decide()
        self.assertEqual(self.snapshot().values["executions"], 8)
        self.assertEqual(v16.current_interrupt(self.snapshot())["gate"], "content_review")
        self.assertNotIn("content_review", self.snapshot().values["approvals"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
