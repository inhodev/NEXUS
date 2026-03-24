from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
SUPPORTED_TEXT_SUFFIXES = {".md", ".txt", ".log", ".json", ".jsonl"}
MAX_FILE_BYTES = 512_000


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    source_path: str
    kind: str
    title: str
    body: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryHit:
    entry: MemoryEntry
    score: int
    snippet: str
    matched_terms: list[str] = field(default_factory=list)


@dataclass
class MemoryIndex:
    entries: list[MemoryEntry] = field(default_factory=list)

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)

    def extend(self, entries: Iterable[MemoryEntry]) -> None:
        self.entries.extend(entries)

    def search(self, query: str, *, limit: int = 10) -> list[MemoryHit]:
        terms = _query_terms(query)
        if not terms:
            return []

        hits: list[MemoryHit] = []
        for entry in self.entries:
            score, matched_terms = _score_entry(entry, terms)
            if score <= 0:
                continue
            hits.append(
                MemoryHit(
                    entry=entry,
                    score=score,
                    snippet=_entry_snippet(entry.body, terms),
                    matched_terms=matched_terms,
                )
            )

        hits.sort(
            key=lambda hit: (
                -hit.score,
                hit.entry.source_path,
                hit.entry.id,
            )
        )
        return hits[:limit]


def index_workspace(
    workspace: Path,
    *,
    include_executions: bool = True,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> MemoryIndex:
    workspace = workspace.resolve()
    index = MemoryIndex()

    intent_path = workspace / "intent.md"
    if intent_path.exists():
        index.add(_entry_from_text_file(intent_path, kind="intent"))

    for path in _iter_workspace_files(
        workspace,
        include_executions=include_executions,
    ):
        if path == intent_path:
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        index.extend(_entries_from_file(path))

    return index


def search_workspace(
    workspace: Path,
    query: str,
    *,
    limit: int = 10,
    include_executions: bool = True,
) -> list[MemoryHit]:
    return index_workspace(
        workspace,
        include_executions=include_executions,
    ).search(query, limit=limit)


def _iter_workspace_files(
    workspace: Path,
    *,
    include_executions: bool,
) -> Iterable[Path]:
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if not include_executions and "executions" in path.parts:
            continue
        if path.suffix.lower() in SUPPORTED_TEXT_SUFFIXES or path.name in {
            "stdout.txt",
            "stderr.txt",
        }:
            yield path


def _entries_from_file(path: Path) -> list[MemoryEntry]:
    suffix = path.suffix.lower()
    if path.name in {"stdout.txt", "stderr.txt"}:
        return [_entry_from_text_file(path, kind="execution-output")]
    if suffix == ".jsonl":
        return _entries_from_jsonl(path)
    if suffix == ".json":
        return [_entry_from_json_file(path)]
    return [_entry_from_text_file(path, kind="artifact")]


def _entry_from_text_file(path: Path, *, kind: str) -> MemoryEntry:
    text = path.read_text(encoding="utf-8", errors="replace")
    title = _title_from_path(path)
    return MemoryEntry(
        id=str(path),
        source_path=str(path),
        kind=kind,
        title=title,
        body=text,
        metadata={"suffix": path.suffix.lower()},
    )


def _entry_from_json_file(path: Path) -> MemoryEntry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = _summarize_json_payload(payload)
    return MemoryEntry(
        id=str(path),
        source_path=str(path),
        kind="json",
        title=_title_from_path(path),
        body=summary,
        metadata={"suffix": ".json"},
    )


def _entries_from_jsonl(path: Path) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        entries.append(
            MemoryEntry(
                id=f"{path}#L{line_number}",
                source_path=str(path),
                kind="jsonl",
                title=f"{_title_from_path(path)} line {line_number}",
                body=_summarize_json_payload(payload),
                metadata={"line": str(line_number), "suffix": ".jsonl"},
            )
        )
    return entries


def _summarize_json_payload(payload: object) -> str:
    if isinstance(payload, dict):
        keys = [
            "summary",
            "detail",
            "message",
            "title",
            "intent",
            "blocking_reason",
            "action",
            "status",
            "task_title",
            "task_kind",
        ]
        parts = [str(payload[key]) for key in keys if payload.get(key)]
        if parts:
            return " | ".join(parts)
        return json.dumps(payload, sort_keys=True)
    if isinstance(payload, list):
        return " | ".join(_summarize_json_payload(item) for item in payload)
    return str(payload)


def _score_entry(entry: MemoryEntry, terms: Sequence[str]) -> tuple[int, list[str]]:
    haystack = " ".join(
        [
            entry.title,
            entry.body,
            entry.source_path,
            " ".join(f"{key}:{value}" for key, value in entry.metadata.items()),
        ]
    ).lower()
    score = 0
    matched_terms: list[str] = []
    for term in terms:
        term_score = 0
        if term in entry.title.lower():
            term_score += 5
        if term in entry.source_path.lower():
            term_score += 2
        if term in haystack:
            term_score += 3
        if term_score > 0:
            matched_terms.append(term)
            score += term_score
    return score, matched_terms


def _entry_snippet(body: str, terms: Sequence[str], *, window: int = 80) -> str:
    if not body:
        return ""
    lower_body = body.lower()
    for term in terms:
        index = lower_body.find(term.lower())
        if index != -1:
            start = max(0, index - window // 2)
            end = min(len(body), index + len(term) + window // 2)
            snippet = body[start:end].strip()
            if start > 0:
                snippet = f"...{snippet}"
            if end < len(body):
                snippet = f"{snippet}..."
            return snippet.replace("\n", " ")
    return body[:window].replace("\n", " ").strip()


def _query_terms(query: str) -> list[str]:
    return [term.lower() for term in TOKEN_PATTERN.findall(query)]


def _title_from_path(path: Path) -> str:
    if path.name == "intent.md":
        return "Run intent"
    return path.stem.replace("_", " ").replace("-", " ").strip().title() or path.name
