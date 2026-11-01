"""V16: durable plan, content, and final review gates with bounded revision."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

import study_guide_v14_dynamic_planning as v14
import study_guide_v15_evaluation_observability as v15

VERSION = "v16.2"
MAX_REVISIONS = 3


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    review_id: str
    action: Literal["approve", "revise", "reject"]
    note: str = Field(default="", max_length=1000)
    plan: dict | None = None

    @model_validator(mode="after")
    def check_payload(self):
        if self.action == "revise" and (self.plan is None or not self.note.strip()):
            raise ValueError("Revision requires a complete plan and a nonblank reason")
        if self.action != "revise" and self.plan is not None:
            raise ValueError("Only revision can supply a replacement plan")
        if self.action == "reject" and not self.note.strip():
            raise ValueError("Rejection requires a reason")
        return self


def review_id(state, gate):
    payload = {"gate": gate, "revision": state["revision"], "plan": state["plan"],
               "results": state["results"], "assessment": state["assessment"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()[:20]


def review_payload(state, gate):
    return {"gate": gate, "review_id": review_id(state, gate),
            "revision": state["revision"], "plan": state["plan"],
            "results": state["results"] if gate != "plan_review" else {},
            "assessment": state["assessment"] if gate == "final_review" else [],
            "message": state["message"], "actions": ["approve", "revise", "reject", "pause"]}


def invalidate_results(state, replacement):
    """Retain only unchanged successful tasks with unchanged dependency chains."""
    previous = {t.task_id: t for t in v14.Plan.model_validate(state["plan"]).tasks}
    retained = {}
    for task in replacement.tasks:
        result = state["results"].get(task.task_id)
        if (task.task_id in previous and result and result["status"] == "completed"
                and v14.task_fingerprint(task) == v14.task_fingerprint(previous[task.task_id])
                and all(dep in retained for dep in task.depends_on)):
            retained[task.task_id] = result
    return retained


def approved_task_label(task):
    """Describe current approved arguments; preserve original wording separately."""
    arguments = task.arguments
    if task.agent == "calculator":
        label = f"Calculate {arguments['expression']}"
    elif task.agent == "converter":
        label = (f"Convert {arguments['value']:g} {arguments['from_unit']} "
                 f"to {arguments['to_unit']}")
    else:
        label = f"Search approved documents for: {arguments['query']}"
    return re.sub(r"\[[ST]\d+\]", "", label).strip()


def make_assessment(state):
    questions = []
    for task in v14.Plan.model_validate(state["plan"]).tasks:
        result = state["results"][task.task_id]
        references = " ".join(dict.fromkeys(re.findall(r"\[[ST]\d+\]", result["content"])))
        label = approved_task_label(task)
        questions.append(f"For the approved task '{label}', what does the supplied evidence show? {references}")
    return questions


def apply_decision(state, gate, payload):
    """Pure transition: no tools, models, or persistence inside a review gate."""
    state = json.loads(json.dumps({k: v for k, v in state.items() if not k.startswith("__")},
                                  allow_nan=False))
    try:
        decision = ReviewDecision.model_validate(payload)
        if decision.review_id != review_id(state, gate):
            raise ValueError("Stale review decision; inspect the current gate")
        if decision.action == "revise":
            if state["revision"] >= MAX_REVISIONS:
                raise ValueError("Revision limit reached; reject or start a new session")
            replacement = v14.Plan.model_validate(decision.plan)
            retained = invalidate_results(state, replacement)
            state.update(plan=replacement.model_dump(), results=retained,
                         revision=state["revision"] + 1, assessment=[], approvals={},
                         stage="plan_review", next_node="plan_review", status="awaiting_review",
                         message="Revised plan requires approval. Affected results were invalidated.")
        elif decision.action == "reject":
            state.update(stage="rejected", next_node="finish", status="rejected",
                         message="Session rejected by reviewer.")
        else:
            if gate != "plan_review":
                plan = v14.Plan.model_validate(state["plan"])
                if not all(state["results"].get(t.task_id, {}).get("status") == "completed" for t in plan.tasks):
                    raise ValueError("Incomplete content cannot be approved; revise or reject")
                report = v15.citation_integrity(state)
                if not report["passed"]:
                    raise ValueError("Evidence integrity failed; revise or reject")
            if gate == "content_review" and not state["approvals"].get("plan_review"):
                raise ValueError("Plan approval is required")
            if gate == "final_review":
                if not state["approvals"].get("content_review") or not state["assessment"]:
                    raise ValueError("Content approval and assessment are required")
                if state["assessment"] != make_assessment(state):
                    raise ValueError("Assessment does not match the current evidence")
            state["approvals"][gate] = {"revision": state["revision"], "review_id": decision.review_id}
            state["next_node"] = {"plan_review": "execute", "content_review": "assessment",
                                  "final_review": "finish"}[gate]
            state["message"] = ""
            if gate == "final_review":
                state.update(stage="approved", status="approved")
        state["audit"].append({"event": "human_decision", "gate": gate,
                               "action": decision.action, "note": decision.note,
                               "revision": state["revision"], "review_id": decision.review_id,
                               "at": datetime.now(timezone.utc).isoformat()})
    except (ValueError, TypeError) as error:
        state.update(next_node=gate, message=str(error))
    return state


def initial_state(goal, chunks, offline):
    base = v14.Workflow(chunks).initial_state(goal)
    return {**base, "version": VERSION, "corpus_digest": v14.corpus_digest(chunks),
            "offline": offline, "revision": 0, "assessment": [], "approvals": {},
            "audit": [], "trace": [], "stage": "planning", "message": "", "next_node": ""}


def validate_resume(state, chunks, offline):
    if state["version"] != VERSION or state["corpus_digest"] != v14.corpus_digest(chunks):
        raise ValueError("Session version or source corpus changed; use a new session ID")
    if state["offline"] != offline:
        raise ValueError("Resume using the same offline/model mode as the saved session")


def build_review_graph(chunks, checkpointer, model=None):
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    def observed_node(state, operation):
        state = {k: v for k, v in state.items() if not k.startswith("__")}
        workflow = v15.ObservedWorkflow(chunks, model)
        result = getattr(workflow, operation)(state)
        segment = max((e["segment_id"] for e in state["trace"]), default=0) + 1
        result["trace"] = state["trace"] + [
            {**event, "sequence": len(state["trace"]) + index, "segment_id": segment,
             "operation": operation}
            for index, event in enumerate(workflow.recorder.events, 1)
        ]
        return result

    def planner(state):
        state = observed_node(state, "plan_node")
        return {**state, "stage": "plan_review", "status": "awaiting_review"}

    def execute(state):
        if not state["approvals"].get("plan_review"):
            raise ValueError("Tool execution requires plan approval")
        state = observed_node(state, "execute_node")
        return {**state, "stage": "content_review", "status": "awaiting_review",
                "audit": state["audit"] + [{"event": "execution_round", "revision": state["revision"],
                                            "executions": state["executions"]}]}

    def assessment(state):
        return {**state, "assessment": make_assessment(state), "stage": "final_review"}

    def gate_node(gate):
        def review(state):
            # Only pure payload construction precedes interrupt: node restart is safe.
            decision = interrupt(review_payload(state, gate))
            return apply_decision(state, gate, decision)
        return review

    graph = StateGraph(dict)
    graph.add_node("planner", planner)
    graph.add_node("execute", execute)
    graph.add_node("assessment", assessment)
    graph.add_node("finish", lambda state: state)
    for gate in ("plan_review", "content_review", "final_review"):
        graph.add_node(gate, gate_node(gate))
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "plan_review")
    graph.add_edge("execute", "content_review")
    graph.add_edge("assessment", "final_review")
    graph.add_edge("finish", END)
    graph.add_conditional_edges("plan_review", lambda state: state["next_node"],
                                ["execute", "plan_review", "finish"])
    graph.add_conditional_edges("content_review", lambda state: state["next_node"],
                                ["assessment", "plan_review", "content_review", "finish"])
    graph.add_conditional_edges("final_review", lambda state: state["next_node"],
                                ["finish", "plan_review", "final_review"])
    return graph.compile(checkpointer=checkpointer)


def current_interrupt(snapshot):
    return next((item.value for task in snapshot.tasks for item in task.interrupts), None)


def display_state(state):
    print(f"\nV16 stage: {state['stage']}; status: {state['status']}; revision: {state['revision']}")
    print(f"Tool executions: {state['executions']}/{v14.MAX_EXECUTIONS}")
    print("Plan:")
    print(json.dumps(state["plan"], indent=2))
    if state["results"]:
        for task in v14.Plan.model_validate(state["plan"]).tasks:
            result = state["results"].get(task.task_id)
            if result is None:
                continue
            print(f"\n{task.task_id} | {task.agent} | {result['status']}")
            print(f"Original task request: {task.instruction}")
            print(f"Approved task: {approved_task_label(task)}")
            print(result["content"])
        if state["sources"]:
            print("\nRetrieved Sources")
            for sid, source in state["sources"].items():
                print(f"[{sid}] {source['title']} | {source['heading']} "
                      f"({source['path']}; {source['stable_id']})")
    if state["assessment"]:
        print("\nEvidence review questions (not a scored quiz):")
        for index, question in enumerate(state["assessment"], 1):
            print(f"{index}. {question}")
    print("Approvals:", ", ".join(state["approvals"]) or "none")
    if state["message"]:
        print("Review message:", state["message"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--session", help="Resume or inspect an existing session")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    chunks = v14.v12.load_trusted_chunks(root / "trusted_documents")
    goal = None if args.session else input("Study goal: ").strip()
    if goal is not None and not goal:
        print("No goal provided. No session started.")
        return
    session = args.session or f"v16-{uuid4().hex[:12]}"
    print(f"Session ID: {session}")
    print("Review commands: approve, revise, reject, pause")
    print("Revisions edit task arguments. Review questions are evidence prompts, not a scored quiz.")
    if input("Open the review workflow? [y/N]: ").strip().lower() != "y":
        print("No workflow was started.")
        return
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.types import Command
    # Lazily load the local model only if a new model-backed plan is needed.
    class LazyModel:
        def with_structured_output(self, schema):
            from langchain_ollama import ChatOllama
            return ChatOllama(model="qwen3.5:4b", temperature=0).with_structured_output(schema)

    config = {"configurable": {"thread_id": session}, "recursion_limit": 32}
    with closing(sqlite3.connect(root / "study_guide_v16_checkpoints.sqlite", check_same_thread=False)) as connection:
        app = build_review_graph(chunks, SqliteSaver(connection), None if args.offline else LazyModel())
        snapshot = app.get_state(config)
        if args.session:
            if not snapshot.values:
                print("Session not found. Check the ID; no new plan was generated.")
                return
            validate_resume(snapshot.values, chunks, args.offline)
            if snapshot.next and not current_interrupt(snapshot):
                print("Execution stopped outside a review gate. Automatic replay is disabled; inspect the checkpoint.")
                return
        else:
            app.invoke(initial_state(goal, chunks, args.offline), config, durability="sync")
        while True:
            snapshot = app.get_state(config)
            state = snapshot.values
            display_state(state)
            pending = current_interrupt(snapshot)
            if pending is None:
                print("Session ended. No learner-memory update was performed.")
                return
            action = input(f"{pending['gate']} [approve/revise/reject/pause]: ").strip().lower()
            if action in ("pause", ""):
                suffix = " --offline" if args.offline else ""
                print(f"Paused. Resume: python .\\study_guide_v16_human_approval.py --session {session}{suffix}")
                return
            if action not in ("approve", "revise", "reject"):
                print("Unknown command. The review is still pending.")
                continue
            payload = {"review_id": pending["review_id"], "action": action}
            if action in ("revise", "reject"):
                payload["note"] = input("Reason: ").strip()
            if action == "revise":
                plan = json.loads(json.dumps(state["plan"]))
                task_id = input("Task to edit (for example task1): ").strip()
                target = next((t for t in plan["tasks"] if t["task_id"] == task_id), None)
                if target is None:
                    print("Unknown task. Review remains pending.")
                    continue
                try:
                    target["arguments"] = json.loads(input("Replacement arguments as JSON: "))
                except json.JSONDecodeError:
                    print("Invalid JSON. Review remains pending.")
                    continue
                payload["plan"] = plan
            app.invoke(Command(resume=payload), config, durability="sync")


if __name__ == "__main__":
    main()
