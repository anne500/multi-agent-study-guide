from __future__ import annotations

import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TRUSTED_DOCUMENTS_DIRECTORY = Path("trusted_documents")
SOURCE_ID_PATTERN = re.compile(r"^Source ID:\s*`([a-z0-9][a-z0-9-]*)`\s*$")
CITATION_PATTERN = re.compile(r"\[S(\d+)\]")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "with",
}


class TrustedDocumentError(ValueError):
    """Raised when a trusted document violates the required local format."""


@dataclass(frozen=True)
class TrustedChunk:
    source_id: str
    title: str
    heading: str
    text: str
    path: Path
    chunk_index: int

    @property
    def stable_id(self) -> str:
        return f"{self.source_id}#{self.chunk_index}"


@dataclass(frozen=True)
class RetrievedChunk:
    citation_id: str
    chunk: TrustedChunk
    score: int


@dataclass(frozen=True)
class CitationReport:
    valid: bool
    cited_ids: tuple[str, ...]
    unknown_ids: tuple[str, ...]
    message: str


def normalize_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(value.lower()):
        if token in STOP_WORDS:
            continue
        if len(token) > 4 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


def parse_trusted_document(path: Path) -> list[TrustedChunk]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise TrustedDocumentError(f"{path}: first line must be a level-one title")

    title = lines[0][2:].strip()
    if not title:
        raise TrustedDocumentError(f"{path}: title cannot be blank")

    source_ids = [
        match.group(1)
        for line in lines
        if (match := SOURCE_ID_PATTERN.fullmatch(line.strip()))
    ]
    if len(source_ids) != 1:
        raise TrustedDocumentError(
            f"{path}: expected exactly one valid Source ID, found {len(source_ids)}"
        )
    source_id = source_ids[0]

    sections: list[tuple[str, list[str]]] = []
    heading: str | None = None
    body: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, body))
            heading = line[3:].strip()
            body = []
        elif heading is not None:
            body.append(line)
    if heading is not None:
        sections.append((heading, body))

    if not sections:
        raise TrustedDocumentError(f"{path}: no level-two sections were found")

    chunks: list[TrustedChunk] = []
    for index, (section_heading, section_lines) in enumerate(sections, start=1):
        text = " ".join(
            line.strip() for line in section_lines if line.strip()
        ).strip()
        if not section_heading or not text:
            raise TrustedDocumentError(
                f"{path}: section {index} must have a heading and nonblank text"
            )
        chunks.append(
            TrustedChunk(
                source_id=source_id,
                title=title,
                heading=section_heading,
                text=text,
                path=path,
                chunk_index=index,
            )
        )
    return chunks


def load_trusted_chunks(directory: Path | str) -> list[TrustedChunk]:
    root = Path(directory)
    if not root.is_dir():
        raise TrustedDocumentError(f"Trusted document directory not found: {root}")

    paths = sorted(root.glob("*.md"), key=lambda item: item.name.lower())
    if not paths:
        raise TrustedDocumentError(f"No Markdown sources found in: {root}")

    chunks: list[TrustedChunk] = []
    source_paths: dict[str, Path] = {}
    for path in paths:
        document_chunks = parse_trusted_document(path)
        source_id = document_chunks[0].source_id
        if source_id in source_paths:
            raise TrustedDocumentError(
                f"Duplicate Source ID '{source_id}' in {source_paths[source_id]} and {path}"
            )
        source_paths[source_id] = path
        chunks.extend(document_chunks)
    return chunks


def score_chunk(query_tokens: list[str], chunk: TrustedChunk) -> int:
    if not query_tokens:
        return 0
    title_tokens = normalize_tokens(chunk.title)
    heading_tokens = normalize_tokens(chunk.heading)
    text_tokens = normalize_tokens(chunk.text)
    score = 0
    for token in query_tokens:
        score += title_tokens.count(token) * 5
        score += heading_tokens.count(token) * 4
        score += min(text_tokens.count(token), 3)
    return score


def retrieve_chunks(
    query: str,
    chunks: Iterable[TrustedChunk],
    top_k: int = 4,
) -> list[RetrievedChunk]:
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20")
    query_tokens = normalize_tokens(query)
    if not query_tokens:
        return []

    ranked = [
        (score_chunk(query_tokens, chunk), chunk)
        for chunk in chunks
    ]
    ranked = [item for item in ranked if item[0] > 0]
    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].source_id,
            item[1].chunk_index,
        )
    )
    return [
        RetrievedChunk(citation_id=f"S{index}", chunk=chunk, score=score)
        for index, (score, chunk) in enumerate(ranked[:top_k], start=1)
    ]


def format_grounded_context(results: Iterable[RetrievedChunk]) -> str:
    items = list(results)
    if not items:
        raise ValueError("At least one retrieved chunk is required")
    blocks = []
    for item in items:
        blocks.append(
            f"[{item.citation_id}] {item.chunk.title} | {item.chunk.heading}\n"
            f"{item.chunk.text}"
        )
    return "\n\n".join(blocks)


def verify_citations(
    answer: str,
    results: Iterable[RetrievedChunk],
    require_citation: bool = True,
) -> CitationReport:
    allowed = {item.citation_id for item in results}
    cited = tuple(dict.fromkeys(f"S{value}" for value in CITATION_PATTERN.findall(answer)))
    unknown = tuple(citation_id for citation_id in cited if citation_id not in allowed)

    if unknown:
        return CitationReport(
            valid=False,
            cited_ids=cited,
            unknown_ids=unknown,
            message=f"Unknown citation IDs: {', '.join(unknown)}",
        )
    if require_citation and not cited:
        return CitationReport(
            valid=False,
            cited_ids=(),
            unknown_ids=(),
            message="At least one citation is required",
        )
    return CitationReport(
        valid=True,
        cited_ids=cited,
        unknown_ids=(),
        message="Citations are valid",
    )


def format_source_list(results: Iterable[RetrievedChunk]) -> str:
    lines = ["## Retrieved Sources"]
    for item in results:
        relative_path = item.chunk.path.as_posix()
        lines.append(
            f"- [{item.citation_id}] {item.chunk.title}, "
            f"{item.chunk.heading} ({relative_path})"
        )
    return "\n".join(lines)


def retrieve_trusted_context(
    query: str,
    directory: Path | str = TRUSTED_DOCUMENTS_DIRECTORY,
    top_k: int = 4,
) -> list[RetrievedChunk]:
    return retrieve_chunks(query, load_trusted_chunks(directory), top_k=top_k)


def _substantive_text(value: str, minimum_words: int = 8) -> bool:
    return len(TOKEN_PATTERN.findall(value)) >= minimum_words


def verify_sections(
    notes: str,
    results: Iterable[RetrievedChunk],
) -> CitationReport:
    items = list(results)
    matches = list(re.finditer(r"(?m)^SECTION\s+(\d+)\s*$", notes))
    if len(matches) != 3 or [match.group(1) for match in matches] != ["1", "2", "3"]:
        return CitationReport(False, (), (), "Notes must contain SECTION 1, SECTION 2, and SECTION 3")

    cited: list[str] = []
    unknown: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(notes)
        block = notes[match.end():end].strip()
        content_lines = [
            line for line in block.splitlines()
            if line.strip() and not line.startswith("Assignment:")
        ]
        content = "\n".join(content_lines).strip()
        if not _substantive_text(content):
            return CitationReport(
                False,
                tuple(dict.fromkeys(cited)),
                tuple(dict.fromkeys(unknown)),
                f"Section {match.group(1)} lacks substantive content",
            )
        report = verify_citations(content, items)
        cited.extend(report.cited_ids)
        unknown.extend(report.unknown_ids)
        if not report.valid:
            return CitationReport(
                False,
                tuple(dict.fromkeys(cited)),
                tuple(dict.fromkeys(unknown)),
                f"Section {match.group(1)} citation check failed: {report.message}",
            )
    return CitationReport(
        True,
        tuple(dict.fromkeys(cited)),
        (),
        "All three sections contain substantive, validly cited content",
    )


def verify_quiz_questions(
    quiz: str,
    results: Iterable[RetrievedChunk],
) -> CitationReport:
    items = list(results)
    questions = [
        match.group(2).strip()
        for match in re.finditer(r"(?ms)^\s*(\d+)[.)]\s+(.+?)(?=^\s*\d+[.)]\s+|\Z)", quiz)
    ]
    if len(questions) != 3:
        return CitationReport(False, (), (), "Quiz must contain exactly 3 numbered questions")

    cited: list[str] = []
    unknown: list[str] = []
    for number, question in enumerate(questions, start=1):
        if not _substantive_text(question, minimum_words=4) or "?" not in question:
            return CitationReport(
                False,
                tuple(dict.fromkeys(cited)),
                tuple(dict.fromkeys(unknown)),
                f"Quiz question {number} is incomplete",
            )
        report = verify_citations(question, items)
        cited.extend(report.cited_ids)
        unknown.extend(report.unknown_ids)
        if not report.valid:
            return CitationReport(
                False,
                tuple(dict.fromkeys(cited)),
                tuple(dict.fromkeys(unknown)),
                f"Quiz question {number} citation check failed: {report.message}",
            )
    return CitationReport(
        True,
        tuple(dict.fromkeys(cited)),
        (),
        "All three quiz questions contain valid citations",
    )


def deterministic_section_fallback(
    task_number: int,
    results: list[RetrievedChunk],
) -> str:
    if not results:
        raise ValueError("At least one retrieved chunk is required")
    result_index = -1 if task_number == 3 else min(max(task_number - 1, 0), len(results) - 1)
    result = results[result_index]
    return f"{result.chunk.text} [{result.citation_id}]"


def verify_final_output(
    notes: str,
    quiz: str,
    results: Iterable[RetrievedChunk],
) -> CitationReport:
    items = list(results)
    notes_report = verify_sections(notes, items)
    quiz_report = verify_quiz_questions(quiz, items)
    cited = tuple(dict.fromkeys(notes_report.cited_ids + quiz_report.cited_ids))
    unknown = tuple(
        dict.fromkeys(notes_report.unknown_ids + quiz_report.unknown_ids)
    )
    if not notes_report.valid:
        return CitationReport(
            valid=False,
            cited_ids=cited,
            unknown_ids=unknown,
            message=f"Notes section check failed: {notes_report.message}",
        )
    if not quiz_report.valid:
        return CitationReport(
            valid=False,
            cited_ids=cited,
            unknown_ids=unknown,
            message=f"Quiz question check failed: {quiz_report.message}",
        )
    return CitationReport(
        valid=True,
        cited_ids=cited,
        unknown_ids=(),
        message="Every section and quiz question contains substantive, validly cited content",
    )


def build_grounded_graph(
    preferred_level: str,
    learning_preferences: list[str],
    results: list[RetrievedChunk],
    checkpointer=None,
):
    import study_guide_v11_long_term_memory as v11
    from langgraph.graph import END, START, StateGraph

    context = format_grounded_context(results)
    allowed_ids = ", ".join(f"[{item.citation_id}]" for item in results)
    preference_text = ", ".join(learning_preferences) or "none recorded"

    def memory_router(state: v11.v10.ReviewState) -> dict:
        print(f"\nLearner memory route: {preferred_level}\n")
        return {"learner_level": preferred_level}

    def grounded_subagent(state: v11.v10.WorkerState) -> dict:
        messages = [
                (
                    "system",
                    f"You are a {state['learner_level']}-level study-guide "
                    "specialist. Use only the trusted context supplied by the "
                    "user. Complete only the assigned task in no more than 120 "
                    "words. Cite every factual paragraph with one or more of "
                    f"these exact source markers: {allowed_ids}. Do not invent "
                    "source markers or use outside facts. "
                    f"Learner preferences: {preference_text}.",
                ),
                (
                    "human",
                    f"Topic: {state['topic']}\n"
                    f"Assignment: {state['task']}\n\n"
                    f"Trusted context:\n{context}",
                ),
            ]
        response = v11.v10.MODEL.invoke(messages)
        content = response.content.strip()
        report = verify_citations(content, results)
        if not _substantive_text(content) or not report.valid:
            print(
                f"\nWorker {state['task_number']} returned blank, short, or uncited "
                "content; retrying once."
            )
            messages.append(("assistant", content or "[blank response]"))
            messages.append(
                (
                    "human",
                    "Correct the response. Return a substantive paragraph of at least "
                    "8 words and include at least one allowed citation marker.",
                )
            )
            response = v11.v10.MODEL.invoke(messages)
            content = response.content.strip()
            report = verify_citations(content, results)
        if not _substantive_text(content) or not report.valid:
            print(
                f"Worker {state['task_number']} retry was invalid; using a "
                "deterministic trusted-source fallback."
            )
            content = deterministic_section_fallback(state["task_number"], results)
        section = (
            f"SECTION {state['task_number']}\n"
            f"Assignment: {state['task']}\n"
            f"{content}"
        )
        return {"completed_sections": [section]}

    def grounded_quiz_producer(state: v11.v10.ReviewState) -> dict:
        quiz = v11.v10.run_node(
            "grounded_quiz_producer",
            (
                "Write exactly 3 short review questions based only on the "
                "supplied notes. Add at least one exact source marker from the "
                f"notes to every question. Allowed markers: {allowed_ids}. "
                "Do not include answers, hints, or outside facts."
            ),
            f"Topic: {state['topic']}\n\nNotes:\n{state['notes']}",
        )
        return {"quiz": quiz}

    def grounded_quiz_reviser(state: v11.v10.ReviewState) -> dict:
        revised = v11.v10.run_node(
            "grounded_quiz_reviser",
            (
                "Revise the quiz using the reviewer feedback. Return exactly "
                "3 complete questions based only on the supplied notes. Every "
                "question must retain at least one valid source marker. "
                f"Allowed markers: {allowed_ids}. Do not include answers, "
                "hints, commentary, or outside facts."
            ),
            (
                f"Topic: {state['topic']}\n\n"
                f"Notes:\n{state['notes']}\n\n"
                f"Current quiz:\n{state['quiz']}\n\n"
                f"Reviewer feedback:\n{state['reviewer_feedback']}"
            ),
        ).strip()
        if not revised:
            print("\nGrounded quiz reviser returned blank output; preserving quiz.")
            revised = state["quiz"]
        return {
            "quiz": revised,
            "revision_count": state["revision_count"] + 1,
        }

    def citation_verifier(state: v11.v10.ReviewState) -> dict:
        report = verify_final_output(state["notes"], state["quiz"], results)
        print("\nDeterministic citation verification:")
        print(f"Citation status: {'valid' if report.valid else 'invalid'}")
        print(f"Citation details: {report.message}\n")
        if report.valid:
            return {}
        return {
            "review_status": "citation_failed",
            "reviewer_feedback": (
                f"{state['reviewer_feedback']} Citation verification failed: "
                f"{report.message}"
            ).strip(),
        }

    graph = StateGraph(v11.v10.ReviewState)
    graph.add_node("router", memory_router)
    graph.add_node("orchestrator", v11.v10.orchestrator)
    graph.add_node("subagent", grounded_subagent)
    graph.add_node("synthesizer", v11.v10.synthesizer)
    graph.add_node("quiz_producer", grounded_quiz_producer)
    graph.add_node("reviewer", v11.v10.reviewer)
    graph.add_node("quiz_reviser", grounded_quiz_reviser)
    graph.add_node("citation_verifier", citation_verifier)

    graph.add_edge(START, "router")
    graph.add_edge("router", "orchestrator")
    graph.add_conditional_edges(
        "orchestrator", v11.v10.assign_workers, ["subagent"]
    )
    graph.add_edge("subagent", "synthesizer")
    graph.add_edge("synthesizer", "quiz_producer")
    graph.add_edge("quiz_producer", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        v11.v10.route_after_review,
        {
            "approved": "citation_verifier",
            "fallback_approved": "citation_verifier",
            "revise": "quiz_reviser",
            "max_iterations": "citation_verifier",
        },
    )
    graph.add_edge("quiz_reviser", "reviewer")
    graph.add_edge("citation_verifier", END)
    return graph.compile(checkpointer=checkpointer)


def main() -> None:
    import study_guide_v11_long_term_memory as v11

    print("V12: Trusted retrieval, learner memory, and citations\n")
    memory_store = v11.LearnerMemoryStore(v11.MEMORY_DATABASE)
    checkpoint_database = "study_guide_v12_checkpoints.sqlite"
    checkpoint_connection = sqlite3.connect(
        checkpoint_database, check_same_thread=False
    )
    try:
        profile = v11.load_or_create_profile(memory_store)
        thread_id = input(
            "Enter V12 session ID, or press Enter to create one automatically: "
        ).strip()
        if not thread_id:
            thread_id = (
                f"{profile.learner_id}-v12-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            )
        print(f"Session ID: {thread_id}")

        topic = input("Enter a study topic: ").strip() or "Conservation of Energy"
        results = retrieve_trusted_context(topic)
        if not results:
            print("No trusted source chunks matched the topic. No workflow started.")
            return

        print("\nRetrieved trusted context:\n")
        print(format_grounded_context(results))
        print()
        print(format_source_list(results))
        print("\nSession plan:")
        print(f"Topic: {topic}")
        print(f"Learner memory route: {profile.preferred_level}")
        print(f"Retrieved chunks: {len(results)}")
        confirm = input("Start grounded study-guide generation? [y/N]: ").strip().lower()
        if confirm != "y":
            print("No workflow was started.")
            return

        checkpointer = v11.v10.SqliteSaver(checkpoint_connection)
        app = build_grounded_graph(
            preferred_level=profile.preferred_level,
            learning_preferences=profile.learning_preferences,
            results=results,
            checkpointer=checkpointer,
        )
        config = {"configurable": {"thread_id": thread_id}}
        existing_state = app.get_state(config)
        started = time.time()
        if existing_state.values:
            print("\nAn existing V12 checkpoint was found for this session.")
            action = input("Enter R to load or resume it, or anything else to exit: ")
            if action.strip().lower() != "r":
                print("No workflow was started.")
                return
            result = (
                app.invoke(None, config)
                if existing_state.next
                else existing_state.values
            )
        else:
            result = app.invoke(
                {
                    "topic": topic,
                    "learner_level": profile.preferred_level,
                    "tasks": [],
                    "completed_sections": [],
                    "demo_mode": "--demo-revision" in sys.argv,
                    "notes": "",
                    "quiz": "",
                    "review_status": "",
                    "reviewer_feedback": "",
                    "revision_count": 0,
                },
                config,
            )

        elapsed = time.time() - started
        report = verify_final_output(result["notes"], result["quiz"], results)
        print(
            f"\n# Grounded Study Guide: {result['topic']}\n\n"
            f"## Notes\n{result['notes']}\n\n"
            f"## Final Quiz\n{result['quiz']}\n\n"
            f"{format_source_list(results)}\n\n"
            f"Final review status: {result['review_status']}\n"
            f"Citation status: {'valid' if report.valid else 'invalid'}\n"
            f"Citation details: {report.message}\n"
            f"Total workflow time: {elapsed:.1f}s"
        )

        if not report.valid or result["review_status"] == "citation_failed":
            print("\nInvalidly cited output cannot be saved as trusted memory.")
            return

        save_result = input(
            "\nSave validated learning outcome to long-term memory? [y/N]: "
        ).strip().lower()
        if save_result == "y":
            outcome = v11.LearningOutcome(
                learner_id=profile.learner_id,
                topic=result["topic"],
                quiz_score=v11.prompt_optional_score(),
                recurring_mistakes=v11.prompt_list("Recurring mistakes"),
                completed=True,
            )
            memory_store.save_outcome(outcome)
            print("\nValidated grounded outcome saved to long-term memory.")
            print(memory_store.memory_summary(profile.learner_id))
        else:
            print("Generated content was not written to long-term memory.")
    except KeyboardInterrupt:
        print("\nV12 interrupted. Checkpoint data already written remains available.")
    finally:
        checkpoint_connection.close()
        memory_store.close()


if __name__ == "__main__":
    main()
