"""V15: local traces, execution metrics, and explicit offline evaluations."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import study_guide_v14_dynamic_planning as v14

VERSION = "v15.1"


class TraceRecorder:
    """Stage latency and model-call latency; no invented token or task timings."""

    def __init__(self, clock=None):
        self.clock = clock or time.perf_counter
        self.started = self.clock()
        self.events = []

    def record(self, kind, **details):
        self.events.append({"sequence": len(self.events) + 1, "kind": kind,
                            "offset_ms": round((self.clock() - self.started) * 1000, 3),
                            **details})

    def call(self, phase, function, *args):
        started = self.clock()
        self.record("span_start", phase=phase)
        try:
            result = function(*args)
        except Exception as error:
            self.record("span_end", phase=phase, outcome="error",
                        duration_ms=round((self.clock() - started) * 1000, 3),
                        error_type=type(error).__name__)
            raise
        self.record("span_end", phase=phase, outcome="ok",
                    duration_ms=round((self.clock() - started) * 1000, 3))
        return result


class TracedModel:
    def __init__(self, model, recorder):
        self.model = model
        self.recorder = recorder

    def with_structured_output(self, schema):
        # Keep configuration failures inside V14's bounded planning retry.
        parent = self

        class Invocation:
            def invoke(self, messages):
                def invoke_model():
                    configured = parent.model.with_structured_output(schema)
                    return configured.invoke(messages)
                return parent.recorder.call("model", invoke_model)

        return Invocation()


class ObservedWorkflow(v14.Workflow):
    def __init__(self, chunks, model=None, recorder=None, registry=None):
        self.recorder = recorder or TraceRecorder()
        super().__init__(chunks, TracedModel(model, self.recorder) if model is not None else None,
                         registry=registry)

    def plan_node(self, state):
        return self.recorder.call("planning", super().plan_node, state)

    def execute_node(self, state):
        result = self.recorder.call("specialists", super().execute_node, state)
        new_events = result["events"][len(state["events"]):]
        for event in new_events:
            if event["event"] == "task_evaluated":
                task = next(t for t in result["plan"]["tasks"] if t["task_id"] == event["task"])
                self.recorder.record("task_outcome", task=event["task"], agent=task["agent"],
                                     status=event["status"],
                                     reference=result["results"][event["task"]].get("reference"))
        return result

    def evaluate_node(self, state):
        return self.recorder.call("evaluation", super().evaluate_node, state)

    def replan_node(self, state):
        return self.recorder.call("replanning", super().replan_node, state)


def citation_integrity(state):
    """Validate IDs, source bindings, and retained source text, not entailment."""
    issues = []
    sources = state["sources"]
    stable_ids = [source["stable_id"] for source in sources.values()]
    if len(stable_ids) != len(set(stable_ids)):
        issues.append("A source chunk has multiple citation IDs")
    plan = v14.Plan.model_validate(state["plan"])
    used_source_count = 0
    for task in plan.tasks:
        result = state["results"].get(task.task_id, {})
        if result.get("status") != "completed":
            continue
        content = result.get("content", "")
        reference = result.get("reference", "")
        tool_ids = set(re.findall(r"\[T(\d+)\]", content))
        if not re.fullmatch(r"T[1-9]\d*", reference) or tool_ids != {reference[1:]}:
            issues.append(f"{task.task_id}: missing or inconsistent tool reference")
        elif int(reference[1:]) > state["executions"]:
            issues.append(f"{task.task_id}: reference exceeds execution count")
        source_ids = re.findall(r"\[(S\d+)\]", content)
        used_source_count += len(source_ids)
        for sid in source_ids:
            if sid not in sources:
                issues.append(f"{task.task_id}: unknown source {sid}")
        if task.agent == "researcher":
            if not source_ids:
                issues.append(f"{task.task_id}: researcher result has no source citation")
            for line in content.splitlines():
                line_ids = re.findall(r"\[(S\d+)\]", line)
                if not line_ids or not any(sid in sources and sources[sid]["text"] in line
                                           for sid in line_ids):
                    issues.append(f"{task.task_id}: source text does not match cited evidence")
    return {"passed": not issues, "issues": issues, "citation_occurrences": used_source_count,
            "sources_available": len(sources), "semantic_entailment_evaluated": False}


def execution_metrics(state, trace):
    plan = v14.Plan.model_validate(state["plan"])
    completed = sum(state["results"].get(t.task_id, {}).get("status") == "completed"
                    for t in plan.tasks)
    planning_events = state["events"]
    span_ends = [e for e in trace if e["kind"] == "span_end"]
    phase_totals = {}
    for event in span_ends:
        phase = event["phase"]
        phase_totals[phase] = round(phase_totals.get(phase, 0) + event["duration_ms"], 3)
    model_spans = [e for e in span_ends if e["phase"] == "model"]
    plans = sum(e["event"] == "model_plan" for e in planning_events)
    fallbacks = sum(e["event"] == "deterministic_plan" for e in planning_events)
    return {
        "status": state["status"], "tasks_planned": len(plan.tasks),
        "tasks_completed": completed, "task_completion_rate": completed / len(plan.tasks),
        "tool_attempts": state["executions"], "replans": state["replans"],
        "model_attempts": len(model_spans),
        "model_call_errors": sum(e["outcome"] == "error" for e in model_spans),
        "accepted_model_plans": plans,
        # V14 records plan_retry on each rejected attempt, including the last failure.
        "rejected_model_attempts": sum(e["event"] == "plan_retry" for e in planning_events),
        "deterministic_plan_rounds": fallbacks,
        "model_plan_acceptance_rate": (plans / (plans + fallbacks)
                                       if model_spans and plans + fallbacks else None),
        "phase_duration_ms": phase_totals,
        "phase_durations_overlap": True,
        "model_tokens": None, "model_tokens_available": False,
        "budget_respected": state["executions"] <= v14.MAX_EXECUTIONS
                             and state["replans"] <= v14.MAX_REPLANS,
    }


def observe_run(goal, chunks, model=None, use_graph=False, recorder=None):
    workflow = ObservedWorkflow(chunks, model=model, recorder=recorder)
    started = time.perf_counter()
    state = (workflow.build_graph().invoke(workflow.initial_state(goal), {"recursion_limit": 16})
             if use_graph else workflow.run(goal))
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    return {
        "version": VERSION, "run_id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "model" if model is not None else "offline",
        "engine": "langgraph" if use_graph else "python",
        "corpus_digest": v14.corpus_digest(chunks), "elapsed_ms": elapsed,
        "state": state, "trace": workflow.recorder.events,
        "metrics": execution_metrics(state, workflow.recorder.events),
        "citation_integrity": citation_integrity(state),
    }


def benchmark_cases():
    return [
        {"id": "arithmetic", "goal": "Calculate 6 * 7", "status": "completed",
         "agents": ["calculator"], "executions": 1, "replans": 0,
         "contains": {"task1": "6 * 7 = 42 [T1]"}},
        {"id": "conversion", "goal": "Convert 5 km to m", "status": "completed",
         "agents": ["converter"], "executions": 1, "replans": 0,
         "contains": {"task1": "5000 m [T1]"}},
        {"id": "compound", "goal": "Explain conservation of energy; Calculate (12 + 8) * 3; Convert 5 km to m",
         "status": "completed", "agents": ["researcher", "calculator", "converter"],
         "executions": 3, "replans": 0,
         "contains": {"task2": "= 60 [T2]", "task3": "5000 m [T3]"}},
        {"id": "division_by_zero", "goal": "Calculate 1 / 0", "status": "incomplete",
         "agents": ["calculator"], "executions": 2, "replans": 1,
         "contains": {"task1": "Division by zero"}},
        {"id": "missing_evidence", "goal": "zzzxqvnomatchzzzxqv", "status": "incomplete",
         "agents": ["researcher"], "executions": 2, "replans": 1,
         "contains": {"task1": "No approved source"}},
    ]


def evaluate_case(case, run):
    state = run["state"]
    integrity = citation_integrity(state)
    metrics = execution_metrics(state, run["trace"])
    checks = {
        "expected_status": state["status"] == case["status"],
        "selected_agents": [t["agent"] for t in state["plan"]["tasks"]] == case["agents"],
        "expected_executions": state["executions"] == case["executions"],
        "expected_replans": state["replans"] == case["replans"],
        "citation_integrity": integrity["passed"],
        "execution_budget": metrics["budget_respected"],
    }
    for task_id, expected in case["contains"].items():
        checks[f"expected_result_{task_id}"] = expected in state["results"].get(task_id, {}).get("content", "")
    return {"case_id": case["id"], "passed": all(checks.values()), "checks": checks,
            "run_id": run["run_id"], "elapsed_ms": run["elapsed_ms"]}


def run_benchmark(chunks):
    runs, evaluations = [], []
    for case in benchmark_cases():
        run = observe_run(case["goal"], chunks)
        runs.append(run)
        evaluations.append(evaluate_case(case, run))
    passed = sum(case["passed"] for case in evaluations)
    return {"version": VERSION, "suite_id": uuid4().hex, "runs": runs,
            "cases": evaluations, "cases_passed": passed,
            "cases_total": len(evaluations), "case_pass_rate": passed / len(evaluations),
            "scope": "Five fixed offline regression cases; not a model-quality benchmark"}


def persist_report(database, report):
    identifier = report.get("suite_id") or report["run_id"]
    with closing(sqlite3.connect(database)) as connection:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS reports "
                               "(id TEXT PRIMARY KEY, version TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.execute("INSERT INTO reports VALUES (?, ?, ?)",
                               (identifier, VERSION, json.dumps(report, allow_nan=False)))
    return identifier


def read_report(database, identifier):
    # Read-only SQLite URI prevents accidentally creating an empty database.
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        row = connection.execute("SELECT payload FROM reports WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise ValueError("Report ID not found")
    return json.loads(row[0])


def format_report(report):
    if "suite_id" in report:
        lines = [f"V15 benchmark: {report['cases_passed']}/{report['cases_total']} passed",
                 f"Case pass rate: {report['case_pass_rate']:.0%}", report["scope"]]
        for case in report["cases"]:
            failures = [name for name, passed in case["checks"].items() if not passed]
            lines.append(f"- {case['case_id']}: {'PASS' if case['passed'] else 'FAIL'} "
                         f"({case['elapsed_ms']:.3f} ms)" + (f"; failed checks: {failures}" if failures else ""))
        return "\n".join(lines)
    metrics = report["metrics"]
    return (f"V15 run: {report['run_id']}\nMode: {report['mode']}; engine: {report['engine']}\n"
            f"Elapsed: {report['elapsed_ms']:.3f} ms\n"
            f"Tasks completed: {metrics['tasks_completed']}/{metrics['tasks_planned']}\n"
            f"Tool attempts: {metrics['tool_attempts']}; replans: {metrics['replans']}\n"
            f"Model attempts: {metrics['model_attempts']}; accepted plans: {metrics['accepted_model_plans']}; "
            f"deterministic planning rounds: {metrics['deterministic_plan_rounds']}\n"
            f"Citation-ID integrity: {'PASS' if report['citation_integrity']['passed'] else 'FAIL'}\n"
            "Semantic entailment: not evaluated\n\n" + v14.render_report(report["state"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", action="store_true", help="Run five fixed offline regression cases")
    parser.add_argument("--offline", action="store_true", help="Observe deterministic V14 execution")
    parser.add_argument("--show", metavar="REPORT_ID", help="Read a saved report without running a workflow")
    parser.add_argument("--trace", action="store_true", help="Print saved trace events with --show")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    database = root / "study_guide_v15_reports.sqlite"
    if args.show:
        report = read_report(database, args.show)
        print(format_report(report))
        if args.trace:
            runs = report.get("runs", [report])
            for run in runs:
                print(json.dumps({"run_id": run["run_id"], "trace": run["trace"]}, indent=2))
        return
    print("V15: Evaluation, tracing, metrics, and observability")
    goal = None if args.benchmark else input("Study goal: ").strip()
    if not args.benchmark and not goal:
        print("No goal provided. No workflow started.")
        return
    mode = "offline benchmark" if args.benchmark else "offline" if args.offline else "Ollama + LangGraph"
    print(f"Mode: {mode}")
    if input("Start evaluation and save a local report? [y/N]: ").strip().lower() != "y":
        print("No workflow was started.")
        return
    chunks = v14.v12.load_trusted_chunks(root / "trusted_documents")
    if args.benchmark:
        report = run_benchmark(chunks)
    else:
        model = None
        if not args.offline:
            from langchain_ollama import ChatOllama
            model = ChatOllama(model="qwen3.5:4b", temperature=0)
        report = observe_run(goal, chunks, model=model, use_graph=not args.offline)
    identifier = persist_report(database, report)
    print(format_report(report))
    print(f"\nSaved report ID: {identifier}")
    print(f"Inspect: python .\\study_guide_v15_evaluation_observability.py --show {identifier} --trace")


if __name__ == "__main__":
    main()
