from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

from services.common.evidence_payloads import normalize_book_label


@dataclass(frozen=True)
class EvidencePath:
    raw: str
    normalized: str
    scheme: str
    head: str
    tail: str

    @property
    def body(self) -> str:
        if not self.scheme:
            return ""
        return self.normalized.split("://", 1)[1]

    def is_scheme(self, *schemes: str) -> bool:
        return self.scheme in {str(item).strip().lower() for item in schemes}


def normalize_path(path: str) -> str:
    return unquote((path or "").strip())


def parse_evidence_path(path: str) -> EvidencePath:
    normalized = normalize_path(path)
    if "://" not in normalized:
        return EvidencePath(raw=path or "", normalized=normalized, scheme="", head="", tail="")
    scheme, body = normalized.split("://", 1)
    head, _, tail = body.partition("/")
    return EvidencePath(
        raw=path or "",
        normalized=normalized,
        scheme=scheme.strip().lower(),
        head=head.strip(),
        tail=tail.strip(),
    )


def path_priority(path: str) -> tuple[int, str]:
    parsed = parse_evidence_path(path)
    priorities = {
        "entity": 0,
        "alias": 1,
        "chapter": 2,
        "book": 3,
        "symptom": 4,
        "qa": 5,
        "caseqa": 6,
    }
    return (priorities.get(parsed.scheme, 7), parsed.normalized)


def ordered_unique_paths(paths: list[str]) -> list[str]:
    deduped = list(dict.fromkeys(path for path in (normalize_path(item) for item in paths) if path))
    return sorted(deduped, key=path_priority)


def source_scope_specs(paths: list[str]) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for path in paths:
        parsed = parse_evidence_path(path)
        if parsed.scheme != "book":
            continue
        book_name = normalize_book_label(parsed.head)
        hint_text = parsed.tail.replace("*", "").strip("/")
        if book_name:
            specs.append((book_name, hint_text))

    deduped: list[tuple[str, str]] = []
    seen = set()
    for spec in specs:
        if spec in seen:
            continue
        seen.add(spec)
        deduped.append(spec)
    return deduped
