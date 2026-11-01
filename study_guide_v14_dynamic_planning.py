"""V14: bounded planning, specialist selection, evaluation, and replanning.

Run with --offline for deterministic execution without Ollama or LangGraph.
Earlier versions are imported for their local tools, never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

import study_guide_v12_rag_citations as v12
import study_guide_v13_tool_using_agents as v13

VERSION = "v14.1"
MAX_TASKS = 4
MAX_REPLANS = 1
MAX_EXECUTIONS = 8
AGENTS = {
    "researcher": "trusted_search",
    "calculator": "calculator",
    "converter": "unit_converter",
}


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: str = Field(pattern=r"^task[1-4]$")
    agent: Literal["researcher", "calculator", "converter"]
    instruction: str = Field(min_length=1, max_length=500)
    arguments: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_arguments(self):
        expected = {
            "researcher": {"query", "top_k"},
            "calculator": {"expression"},
            "converter": {"value", "from_unit", "to_unit"},
        }[self.agent]
        if set(self.arguments) != expected:
            raise ValueError(f"{self.agent} requires exactly {sorted(expected)}")
        if self.agent == "researcher":
            query, k = self.arguments["query"], self.arguments["top_k"]
            if not isinstance(query, str) or not query.strip() or len(query) > 500:
                raise ValueError("Search query must be nonblank and at most 500 characters")
            if type(k) is not int or not 1 <= k <= 4:
                raise ValueError("top_k must be an integer from 1 to 4")
        elif self.agent == "calculator":
            expression = self.arguments["expression"]
            if not isinstance(expression, str) or not expression.strip() or len(expression) > 200:
                raise ValueError("Expression must be a nonblank string of at most 200 characters")
        else:
            value = self.arguments["value"]
            if type(value) not in (int, float):
                raise ValueError("Conversion value must be numeric")
            if not math.isfinite(value) or abs(value) > v13.MAX_CALCULATION_ABSOLUTE_VALUE:
                raise ValueError("Conversion value must be finite and within the tool magnitude limit")
            for key in ("from_unit", "to_unit"):
                if not isinstance(self.arguments[key], str) or not self.arguments[key].strip():
                    raise ValueError(f"{key} must be a nonblank unit")
        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tasks: list[Task] = Field(min_length=1, max_length=MAX_TASKS)

    @model_validator(mode="after")
    def validate_dependencies(self):
        seen = set()
        for task in self.tasks:
            if task.task_id in seen:
                raise ValueError("Duplicate task ID")
            if len(set(task.depends_on)) != len(task.depends_on):
                raise ValueError("Duplicate dependency")
            if not set(task.depends_on).issubset(seen):
                raise ValueError("Dependencies must refer to earlier tasks; cycles are forbidden")
            seen.add(task.task_id)
        return self


def task_fingerprint(task: Task) -> str:
    return json.dumps(task.model_dump(), sort_keys=True, allow_nan=False)


def deterministic_plan(goal: str) -> Plan:
    """Explicit compound syntax: separate independent requests with semicolons."""
    parts = [part.strip() for part in goal.split(";") if part.strip()]
    if not parts or len(parts) > MAX_TASKS:
        raise ValueError("Enter one to four requests separated by semicolons")
    tasks = []
    for index, part in enumerate(parts, 1):
        decision = v13.deterministic_tool_decision(part, [])
        call = decision.tool_call
        if call is None:
            raise ValueError("Could not create a tool task")
        agent = {value: key for key, value in AGENTS.items()}[call.tool_name]
        tasks.append(Task(task_id=f"task{index}", agent=agent,
                          instruction=part, arguments=call.arguments))
    return Plan(tasks=tasks)


def choose_plan(goal: str, model=None, previous: Plan | None = None,
                feedback: str = "", events: list | None = None) -> Plan:
    """Two model attempts maximum per planning round; validated fallback."""
    events = events if events is not None else []
    if model is not None:
        messages = [
            ("system", "Plan one to four study tasks. Agents: researcher uses "
             "arguments query (string), top_k (integer 1-4); calculator uses "
             "expression (string arithmetic); converter uses value (number), "
             "from_unit and to_unit (strings). Use task1 through task4. Select "
             "only agents needed for the goal. Dependencies refer only to earlier "
             "tasks. Arguments are literal values, never placeholders or code. "
             "A dependency orders execution; it does not substitute its result. "
             "When replanning preserve completed tasks and fix failed tasks."),
            ("human", f"Goal: {goal}\nPrevious plan: "
             f"{previous.model_dump_json() if previous else 'none'}\nFeedback: {feedback}"),
        ]
        for attempt in range(2):
            try:
                candidate = model.with_structured_output(Plan).invoke(messages)
                plan = Plan.model_validate(candidate.model_dump() if isinstance(candidate, Plan) else candidate)
                # Replanning cannot erase tasks, their IDs, or completed work.
                if previous and {t.task_id for t in plan.tasks} != {t.task_id for t in previous.tasks}:
                    raise ValueError("A replan must retain all original task IDs")
                clauses = [part.strip() for part in goal.split(";") if part.strip()]
                if previous is None and len(clauses) > 1:
                    if [t.instruction for t in plan.tasks] != clauses:
                        raise ValueError("A compound plan must retain every request in order, verbatim")
                events.append({"event": "model_plan", "attempt": attempt + 1})
                return plan
            except Exception as error:
                events.append({"event": "plan_retry", "error": type(error).__name__})
                messages.append(("human", "Return a valid Plan using the exact argument keys."))
    events.append({"event": "deterministic_plan"})
    # Retry the same failed tasks if no defensible corrected plan is available.
    return previous.model_copy(deep=True) if previous else deterministic_plan(goal)


class Workflow:
    def __init__(self, chunks: list[v12.TrustedChunk], model=None, registry=None):
        self.chunks = chunks
        self.model = model
        self.registry = registry or v13.build_default_registry(chunks)

    def initial_state(self, goal: str) -> dict:
        if not goal.strip() or len(goal) > 2000:
            raise ValueError("Goal must contain 1 to 2000 characters")
        return {"goal": goal, "plan": None, "results": {}, "sources": {},
                "executions": 0, "replans": 0, "events": [], "status": "running"}

    def plan_node(self, state: dict) -> dict:
        events = list(state["events"])
        plan = choose_plan(state["goal"], self.model, events=events)
        return {**state, "plan": plan.model_dump(), "events": events}

    def execute_node(self, state: dict) -> dict:
        # Copy state to avoid mutating graph/checkpoint input values.
        state = json.loads(json.dumps(state, allow_nan=False))
        plan = Plan.model_validate(state["plan"])
        for task in plan.tasks:
            old = state["results"].get(task.task_id)
            if old and old["status"] == "completed":
                continue
            if any(state["results"].get(dep, {}).get("status") != "completed"
                   for dep in task.depends_on):
                state["results"][task.task_id] = {"status": "blocked", "content": "Dependency incomplete"}
                continue
            if state["executions"] >= MAX_EXECUTIONS:
                break
            state["executions"] += 1
            reference = f"T{state['executions']}"
            try:
                if task.agent == "researcher":
                    results = v12.retrieve_chunks(task.arguments["query"], self.chunks,
                                                  top_k=task.arguments["top_k"])
                    if not results:
                        raise ValueError("No approved source matched this query")
                    blocks = []
                    for item in results:
                        # A session-global citation map prevents V13 search-label collisions.
                        stable_key = item.chunk.stable_id
                        existing = next((sid for sid, source in state["sources"].items()
                                         if source["stable_id"] == stable_key), None)
                        sid = existing or f"S{len(state['sources']) + 1}"
                        state["sources"][sid] = {
                            "stable_id": stable_key, "title": item.chunk.title,
                            "heading": item.chunk.heading, "path": item.chunk.path.as_posix(),
                            "text": item.chunk.text,
                        }
                        blocks.append(f"{item.chunk.text} [{sid}] [{reference}]")
                    content = "\n".join(blocks)
                else:
                    call = v13.ToolCall(tool_name=AGENTS[task.agent], arguments=task.arguments)
                    observation = self.registry.execute(call, state["executions"])
                    if not observation.ok or not v13.verify_observation(observation):
                        raise ValueError(observation.content)
                    content = observation.content
                state["results"][task.task_id] = {
                    "status": "completed", "content": content, "reference": reference,
                    "fingerprint": task_fingerprint(task),
                }
            except Exception as error:
                state["results"][task.task_id] = {
                    "status": "failed", "content": str(error), "reference": reference,
                }
            state["events"].append({"event": "task_evaluated", "task": task.task_id,
                                     "status": state["results"][task.task_id]["status"]})
        return state

    def evaluate_node(self, state: dict) -> dict:
        plan = Plan.model_validate(state["plan"])
        complete = all(state["results"].get(t.task_id, {}).get("status") == "completed"
                       for t in plan.tasks)
        status = "completed" if complete else "needs_replan"
        if not complete and (state["replans"] >= MAX_REPLANS or state["executions"] >= MAX_EXECUTIONS):
            status = "incomplete"
        return {**state, "status": status}

    def replan_node(self, state: dict) -> dict:
        previous = Plan.model_validate(state["plan"])
        events = list(state["events"])
        feedback = json.dumps(state["results"])
        candidate = choose_plan(state["goal"], self.model, previous, feedback, events)
        # Restore completed tasks even if the planner changes their contents.
        frozen = {task.task_id: task for task in previous.tasks
                  if state["results"].get(task.task_id, {}).get("status") == "completed"}
        originals = {task.task_id: task for task in previous.tasks}
        try:
            candidate = Plan(tasks=[frozen.get(t.task_id, t.model_copy(update={
                "instruction": originals[t.task_id].instruction,
            })) for t in candidate.tasks])
        except ValueError:
            candidate = previous
            events.append({"event": "invalid_replan_rejected"})
        events.append({"event": "replan", "round": state["replans"] + 1})
        return {**state, "plan": candidate.model_dump(), "events": events,
                "replans": state["replans"] + 1}

    def run(self, goal: str) -> dict:
        state = self.plan_node(self.initial_state(goal))
        while True:
            state = self.evaluate_node(self.execute_node(state))
            if state["status"] != "needs_replan":
                return state
            state = self.replan_node(state)

    def build_graph(self):
        from langgraph.graph import END, START, StateGraph
        graph = StateGraph(dict)
        graph.add_node("planner", self.plan_node)
        graph.add_node("specialists", self.execute_node)
        graph.add_node("evaluator", self.evaluate_node)
        graph.add_node("replanner", self.replan_node)
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "specialists")
        graph.add_edge("specialists", "evaluator")
        graph.add_conditional_edges("evaluator", lambda s: s["status"],
                                    {"needs_replan": "replanner", "completed": END, "incomplete": END})
        graph.add_edge("replanner", "specialists")
        return graph.compile()


def render_report(state: dict) -> str:
    plan = Plan.model_validate(state["plan"])
    blocks = [f"V14 status: {state['status']}",
              f"Tool executions: {state['executions']}; replans: {state['replans']}"]
    for task in plan.tasks:
        result = state["results"].get(task.task_id, {"status": "blocked", "content": "Execution limit"})
        blocks.append(f"\n{task.task_id} | {task.agent} | {result['status']}\n"
                      f"Request: {task.instruction}\n{result['content']}")
    if state["sources"]:
        blocks.append("\nRetrieved Sources")
        for sid, source in state["sources"].items():
            blocks.append(f"[{sid}] {source['title']} | {source['heading']} "
                          f"({source['path']}; {source['stable_id']})")
    return "\n".join(blocks)


def corpus_digest(chunks: list[v12.TrustedChunk]) -> str:
    payload = [(c.stable_id, c.title, c.heading, c.text, c.path.as_posix()) for c in chunks]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def save_run(database: Path, session: str, state: dict, digest: str) -> None:
    # V14 stores a completed/incomplete run snapshot, not resumable node checkpoints.
    with closing(sqlite3.connect(database)) as connection:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS runs "
                               "(session TEXT PRIMARY KEY, version TEXT, corpus TEXT, state TEXT)")
            connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?)",
                               (session, VERSION, digest, json.dumps(state, allow_nan=False)))


def load_run(database: Path, session: str, goal: str, digest: str) -> dict | None:
    if not database.exists():
        return None
    with closing(sqlite3.connect(database)) as connection:
        exists = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'").fetchone()
        if not exists:
            return None
        row = connection.execute("SELECT version, corpus, state FROM runs WHERE session=?", (session,)).fetchone()
    if not row:
        return None
    state = json.loads(row[2])
    if row[0] != VERSION or row[1] != digest or state["goal"] != goal:
        raise ValueError("Session belongs to a different goal, corpus, or V14 version; use a new session ID")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print("V14: Dynamic planning and agent selection")
    print("Up to 4 tasks, 1 replan, and 8 tool executions.")
    print("Separate independent requests with semicolons. Example:")
    print("Explain conservation of energy; Calculate (12 + 8) * 3; Convert 5 km to m")
    goal = input("Study goal: ").strip()
    if not goal:
        print("No goal provided. No workflow started.")
        return
    session = input("Session ID [automatic]: ").strip() or f"v14-{uuid4().hex[:12]}"
    print(f"Session: {session}; mode: {'offline' if args.offline else 'Ollama + LangGraph'}")
    if input("Start planning and execution? [y/N]: ").strip().lower() != "y":
        print("No workflow was started.")
        return
    root = Path(__file__).resolve().parent
    try:
        chunks = v12.load_trusted_chunks(root / "trusted_documents")
        database = root / "study_guide_v14_runs.sqlite"
        digest = corpus_digest(chunks)
        existing = load_run(database, session, goal, digest)
        if existing is not None:
            print("Loaded saved run without model or tool calls.")
            print(render_report(existing))
            return
        model = None
        if not args.offline:
            from langchain_ollama import ChatOllama
            model = ChatOllama(model="qwen3.5:4b", temperature=0)
        workflow = Workflow(chunks, model)
        state = (workflow.run(goal) if args.offline else
                 workflow.build_graph().invoke(workflow.initial_state(goal), {"recursion_limit": 16}))
        save_run(database, session, state, digest)
        print(render_report(state))
        print("\nRun snapshot saved. Learner memory was not updated.")
    except (ValueError, sqlite3.Error) as error:
        print(f"V14 stopped: {error}")
    except KeyboardInterrupt:
        print("\nInterrupted. This run was not saved; use a new session to retry.")


if __name__ == "__main__":
    main()
