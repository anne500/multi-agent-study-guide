from __future__ import annotations

import ast
import math
import operator
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator

import study_guide_v12_rag_citations as v12


MAX_TOOL_CALLS = 2
MAX_CALCULATION_OPERATIONS = 20
MAX_CALCULATION_ABSOLUTE_VALUE = 1_000_000_000_000
TOOL_REFERENCE_PATTERN = re.compile(r"\[T(\d+)\]")


class ToolInputError(ValueError):
    """Raised when a requested tool receives invalid or unsafe arguments."""


class ToolCall(BaseModel):
    tool_name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, str | int | float] = Field(default_factory=dict)


class ToolDecision(BaseModel):
    action: Literal["tool", "final"]
    reason: str = Field(min_length=1, max_length=300)
    tool_call: ToolCall | None = None
    final_response: str | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "ToolDecision":
        if self.action == "tool" and self.tool_call is None:
            raise ValueError("A tool action requires tool_call")
        if self.action == "final" and not (self.final_response or "").strip():
            raise ValueError("A final action requires final_response")
        if self.action == "tool" and self.final_response is not None:
            raise ValueError("A tool action cannot include final_response")
        return self


class ToolObservation(BaseModel):
    observation_id: str = Field(pattern=r"^T[1-9][0-9]*$")
    tool_name: str
    ok: bool
    content: str
    source_citations: tuple[str, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[[dict[str, str | int | float], str], ToolObservation]


class ToolRegistry:
    """A closed registry. Only explicitly registered local tools can run."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", spec.name):
            raise ValueError(f"Invalid tool name: {spec.name}")
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool name: {spec.name}")
        self._tools[spec.name] = spec

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def prompt_catalog(self) -> str:
        return "\n".join(
            f"- {spec.name}: {spec.description}"
            for spec in sorted(self._tools.values(), key=lambda item: item.name)
        )

    def execute(self, call: ToolCall, observation_number: int) -> ToolObservation:
        observation_id = f"T{observation_number}"
        spec = self._tools.get(call.tool_name)
        if spec is None:
            return ToolObservation(
                observation_id=observation_id,
                tool_name=call.tool_name,
                ok=False,
                content=(
                    f"Tool '{call.tool_name}' is not approved "
                    f"[{observation_id}]."
                ),
                error_code="unknown_tool",
            )
        try:
            observation = spec.handler(call.arguments, observation_id)
        except ToolInputError as error:
            return ToolObservation(
                observation_id=observation_id,
                tool_name=call.tool_name,
                ok=False,
                content=f"{error} [{observation_id}].",
                error_code="invalid_arguments",
            )
        except Exception as error:
            return ToolObservation(
                observation_id=observation_id,
                tool_name=call.tool_name,
                ok=False,
                content=(
                    f"Tool execution failed safely: {type(error).__name__} "
                    f"[{observation_id}]."
                ),
                error_code="execution_failed",
            )
        if observation.observation_id != observation_id:
            raise RuntimeError("Tool returned an unexpected observation ID")
        return observation


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _bounded_number(value: float) -> float:
    if not math.isfinite(value):
        raise ToolInputError("Calculation result must be finite")
    if abs(value) > MAX_CALCULATION_ABSOLUTE_VALUE:
        raise ToolInputError("Calculation result exceeds the allowed magnitude")
    return value


def safe_calculate(expression: str) -> int | float:
    expression = expression.strip()
    if not expression or len(expression) > 200:
        raise ToolInputError("Expression must contain 1 to 200 characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ToolInputError("Expression is not valid arithmetic") from error

    operation_count = 0

    def evaluate(node: ast.AST) -> float:
        nonlocal operation_count
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ToolInputError("Only numeric literals are allowed")
            return _bounded_number(float(node.value))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            operation_count += 1
            value = _UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
            return _bounded_number(value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            operation_count += 1
            if operation_count > MAX_CALCULATION_OPERATIONS:
                raise ToolInputError("Expression contains too many operations")
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ToolInputError("Exponent exceeds the allowed magnitude")
            try:
                value = _BINARY_OPERATORS[type(node.op)](left, right)
            except ZeroDivisionError as error:
                raise ToolInputError("Division by zero is not allowed") from error
            return _bounded_number(float(value))
        raise ToolInputError("Only numeric arithmetic operators are allowed")

    result = evaluate(tree)
    if result.is_integer():
        return int(result)
    return round(result, 12)


def calculator_handler(
    arguments: dict[str, str | int | float],
    observation_id: str,
) -> ToolObservation:
    expression = arguments.get("expression")
    if not isinstance(expression, str):
        raise ToolInputError("calculator requires a string 'expression'")
    result = safe_calculate(expression)
    return ToolObservation(
        observation_id=observation_id,
        tool_name="calculator",
        ok=True,
        content=f"{expression} = {result} [{observation_id}]",
    )


_UNIT_FACTORS: dict[str, tuple[str, float]] = {
    "mm": ("length", 0.001),
    "cm": ("length", 0.01),
    "m": ("length", 1.0),
    "km": ("length", 1000.0),
    "in": ("length", 0.0254),
    "ft": ("length", 0.3048),
    "yd": ("length", 0.9144),
    "mi": ("length", 1609.344),
    "mg": ("mass", 0.000001),
    "g": ("mass", 0.001),
    "kg": ("mass", 1.0),
    "oz": ("mass", 0.028349523125),
    "lb": ("mass", 0.45359237),
    "s": ("time", 1.0),
    "min": ("time", 60.0),
    "h": ("time", 3600.0),
}


def convert_units(value: int | float, from_unit: str, to_unit: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolInputError("value must be numeric")
    numeric_value = _bounded_number(float(value))
    source = from_unit.strip().lower()
    target = to_unit.strip().lower()
    if source not in _UNIT_FACTORS or target not in _UNIT_FACTORS:
        raise ToolInputError("Unknown unit. Use an approved length, mass, or time unit")
    source_dimension, source_factor = _UNIT_FACTORS[source]
    target_dimension, target_factor = _UNIT_FACTORS[target]
    if source_dimension != target_dimension:
        raise ToolInputError("Cannot convert between different measurement dimensions")
    return round(numeric_value * source_factor / target_factor, 12)


def unit_converter_handler(
    arguments: dict[str, str | int | float],
    observation_id: str,
) -> ToolObservation:
    value = arguments.get("value")
    from_unit = arguments.get("from_unit")
    to_unit = arguments.get("to_unit")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ToolInputError("unit_converter requires numeric 'value'")
    if not isinstance(from_unit, str) or not isinstance(to_unit, str):
        raise ToolInputError("unit_converter requires string 'from_unit' and 'to_unit'")
    result = convert_units(value, from_unit, to_unit)
    return ToolObservation(
        observation_id=observation_id,
        tool_name="unit_converter",
        ok=True,
        content=(
            f"{value} {from_unit.lower()} = {result:g} {to_unit.lower()} "
            f"[{observation_id}]"
        ),
    )


def build_trusted_search_handler(
    trusted_chunks: list[v12.TrustedChunk],
) -> Callable[[dict[str, str | int | float], str], ToolObservation]:
    def trusted_search_handler(
        arguments: dict[str, str | int | float],
        observation_id: str,
    ) -> ToolObservation:
        query = arguments.get("query")
        top_k = arguments.get("top_k", 3)
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("trusted_search requires a nonblank string 'query'")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 4:
            raise ToolInputError("trusted_search top_k must be an integer from 1 to 4")
        results = v12.retrieve_chunks(query, trusted_chunks, top_k=top_k)
        if not results:
            return ToolObservation(
                observation_id=observation_id,
                tool_name="trusted_search",
                ok=False,
                content=f"No approved local source matched the query [{observation_id}].",
                error_code="no_results",
            )
        context = v12.format_grounded_context(results)
        citations = tuple(item.citation_id for item in results)
        report = v12.verify_citations(context, results)
        if not report.valid:
            raise RuntimeError("Trusted search produced invalid citation metadata")
        return ToolObservation(
            observation_id=observation_id,
            tool_name="trusted_search",
            ok=True,
            content=f"{context}\n[{observation_id}]",
            source_citations=citations,
        )

    return trusted_search_handler


def build_default_registry(
    trusted_chunks: list[v12.TrustedChunk],
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="calculator",
            description=(
                "Evaluate bounded arithmetic. Arguments: "
                "{'expression': 'numeric expression'}"
            ),
            handler=calculator_handler,
        )
    )
    registry.register(
        ToolSpec(
            name="unit_converter",
            description=(
                "Convert approved length, mass, or time units. Arguments: "
                "{'value': number, 'from_unit': unit, 'to_unit': unit}"
            ),
            handler=unit_converter_handler,
        )
    )
    registry.register(
        ToolSpec(
            name="trusted_search",
            description=(
                "Search approved local study documents. Arguments: "
                "{'query': 'question', 'top_k': 1 to 4}"
            ),
            handler=build_trusted_search_handler(trusted_chunks),
        )
    )
    return registry


def verify_observation(observation: ToolObservation) -> bool:
    expected_reference = f"[{observation.observation_id}]"
    if expected_reference not in observation.content:
        return False
    if observation.ok and observation.error_code is not None:
        return False
    if not observation.ok and observation.error_code is None:
        return False
    if observation.tool_name == "trusted_search" and observation.ok:
        if not observation.source_citations:
            return False
        cited = tuple(dict.fromkeys(f"S{value}" for value in v12.CITATION_PATTERN.findall(observation.content)))
        if not cited or any(item not in observation.source_citations for item in cited):
            return False
    return True


def verify_tool_answer(
    answer: str,
    observations: list[ToolObservation],
) -> bool:
    allowed_tools = {item.observation_id for item in observations}
    cited_tools = {f"T{value}" for value in TOOL_REFERENCE_PATTERN.findall(answer)}
    if not cited_tools or not cited_tools.issubset(allowed_tools):
        return False
    allowed_sources = {
        citation
        for observation in observations
        for citation in observation.source_citations
    }
    cited_sources = {f"S{value}" for value in v12.CITATION_PATTERN.findall(answer)}
    if not cited_sources.issubset(allowed_sources):
        return False
    if any(item.tool_name == "trusted_search" and item.ok for item in observations):
        if not cited_sources:
            return False
    return True


def render_observation_answer(observations: list[ToolObservation]) -> str:
    if not observations:
        return "No approved tool observation is available."
    successful = [item for item in observations if item.ok]
    selected = successful or observations
    return "\n\n".join(item.content for item in selected)


_CONVERSION_PATTERN = re.compile(
    r"(?i)\bconvert\s+(-?\d+(?:\.\d+)?)\s+([a-z]+)\s+(?:to|into)\s+([a-z]+)\b"
)
_CALCULATION_PATTERN = re.compile(r"(?i)\b(?:calculate|compute|evaluate)\s+(.+?)(?:\?|$)")


def deterministic_tool_decision(
    question: str,
    observations: list[ToolObservation],
) -> ToolDecision:
    if observations:
        return ToolDecision(
            action="final",
            reason="A validated local tool observation is available.",
            final_response=render_observation_answer(observations),
        )
    conversion = _CONVERSION_PATTERN.search(question)
    if conversion:
        value, from_unit, to_unit = conversion.groups()
        return ToolDecision(
            action="tool",
            reason="The request is an approved unit conversion.",
            tool_call=ToolCall(
                tool_name="unit_converter",
                arguments={
                    "value": float(value),
                    "from_unit": from_unit,
                    "to_unit": to_unit,
                },
            ),
        )
    calculation = _CALCULATION_PATTERN.search(question)
    if calculation:
        return ToolDecision(
            action="tool",
            reason="The request contains an explicit arithmetic expression.",
            tool_call=ToolCall(
                tool_name="calculator",
                arguments={"expression": calculation.group(1).strip()},
            ),
        )
    return ToolDecision(
        action="tool",
        reason="Use the approved local corpus for a factual study question.",
        tool_call=ToolCall(
            tool_name="trusted_search",
            arguments={"query": question, "top_k": 3},
        ),
    )


def choose_tool_decision(
    model: Any,
    question: str,
    observations: list[ToolObservation],
    registry: ToolRegistry,
) -> ToolDecision:
    observation_text = render_observation_answer(observations) if observations else "none"
    messages = [
        (
            "system",
            "You are a tool-selection controller. Choose only an approved tool or "
            "return a final response grounded entirely in validated observations. "
            "Never invent a tool, argument, result, [T#] reference, or [S#] citation. "
            f"Approved tools:\n{registry.prompt_catalog()}",
        ),
        (
            "human",
            f"Question: {question}\n\nValidated observations:\n{observation_text}",
        ),
    ]
    structured_model = model.with_structured_output(ToolDecision)
    for attempt in range(2):
        try:
            decision = structured_model.invoke(messages)
            if decision.action == "tool":
                assert decision.tool_call is not None
                if decision.tool_call.tool_name not in registry.names():
                    raise ValueError("Model selected an unapproved tool")
            return decision
        except Exception as error:
            if attempt == 0:
                messages.append(("human", f"Return a valid decision. Error: {type(error).__name__}."))
    return deterministic_tool_decision(question, observations)


class ToolAgentState(TypedDict):
    question: str
    observations: list[ToolObservation]
    decision: ToolDecision | None
    tool_call_count: int
    final_answer: str
    status: str


def build_tool_graph(model: Any, registry: ToolRegistry, checkpointer=None):
    from langgraph.graph import END, START, StateGraph

    def select_tool(state: ToolAgentState) -> dict:
        decision = choose_tool_decision(
            model,
            state["question"],
            state["observations"],
            registry,
        )
        return {"decision": decision}

    def route_decision(state: ToolAgentState) -> str:
        decision = state["decision"]
        if decision is None:
            return "finalize"
        if decision.action == "tool" and state["tool_call_count"] < MAX_TOOL_CALLS:
            return "execute_tool"
        return "finalize"

    def execute_tool(state: ToolAgentState) -> dict:
        decision = state["decision"]
        assert decision is not None and decision.tool_call is not None
        number = state["tool_call_count"] + 1
        observation = registry.execute(decision.tool_call, number)
        if not verify_observation(observation):
            observation = ToolObservation(
                observation_id=f"T{number}",
                tool_name=decision.tool_call.tool_name,
                ok=False,
                content=f"Tool observation failed deterministic validation [T{number}].",
                error_code="invalid_observation",
            )
        return {
            "observations": state["observations"] + [observation],
            "tool_call_count": number,
        }

    def finalize(state: ToolAgentState) -> dict:
        decision = state["decision"]
        candidate = (
            decision.final_response
            if decision is not None and decision.action == "final"
            else render_observation_answer(state["observations"])
        )
        if state["observations"] and not verify_tool_answer(candidate or "", state["observations"]):
            candidate = render_observation_answer(state["observations"])
        status = "completed" if any(item.ok for item in state["observations"]) else "safe_failure"
        return {"final_answer": candidate or "No validated answer is available.", "status": status}

    graph = StateGraph(ToolAgentState)
    graph.add_node("select_tool", select_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "select_tool")
    graph.add_conditional_edges(
        "select_tool",
        route_decision,
        {"execute_tool": "execute_tool", "finalize": "finalize"},
    )
    graph.add_edge("execute_tool", "select_tool")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def main() -> None:
    import study_guide_v11_long_term_memory as v11

    print("V13: Controlled tool-using study agent\n")
    trusted_chunks = v12.load_trusted_chunks(v12.TRUSTED_DOCUMENTS_DIRECTORY)
    registry = build_default_registry(trusted_chunks)
    print("Approved tools:")
    print(registry.prompt_catalog())

    question = input("\nEnter a study question: ").strip()
    if not question:
        print("A nonblank question is required. No workflow started.")
        return
    confirm = input("Start the controlled tool workflow? [y/N]: ").strip().lower()
    if confirm != "y":
        print("No workflow was started.")
        return

    connection = sqlite3.connect(
        "study_guide_v13_checkpoints.sqlite",
        check_same_thread=False,
    )
    try:
        checkpointer = v11.v10.SqliteSaver(connection)
        app = build_tool_graph(v11.v10.MODEL, registry, checkpointer=checkpointer)
        thread_id = input("V13 session ID, or press Enter for a default: ").strip()
        thread_id = thread_id or "v13-controlled-tool-session"
        result = app.invoke(
            {
                "question": question,
                "observations": [],
                "decision": None,
                "tool_call_count": 0,
                "final_answer": "",
                "status": "running",
            },
            {"configurable": {"thread_id": thread_id}},
        )
        print("\nTool observations:")
        for observation in result["observations"]:
            print(
                f"- [{observation.observation_id}] {observation.tool_name}: "
                f"{'ok' if observation.ok else observation.error_code}"
            )
        print(f"\nFinal status: {result['status']}")
        print(f"\nFinal answer:\n{result['final_answer']}")
    except KeyboardInterrupt:
        print("\nV13 interrupted. Saved checkpoint data remains available.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
