from __future__ import annotations

import ast
import json
import re
from typing import Any


def extract_payload_triples(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    triples = payload.get("triples")
    if isinstance(triples, list):
        return [item for item in triples if isinstance(item, dict)]
    if {"subject", "predicate", "object"} <= set(payload.keys()):
        return [payload]
    return []


def coerce_payload_to_standard_shape(payload: Any) -> dict[str, Any]:
    meta = payload.get("__meta__") if isinstance(payload, dict) else None
    if isinstance(payload, dict) and isinstance(payload.get("triples"), list):
        result = {
            "triples": [item for item in payload.get("triples", []) if isinstance(item, dict)],
        }
        if isinstance(meta, dict):
            result["__meta__"] = meta
        return result
    triples = extract_payload_triples(payload)
    if triples:
        result = {"triples": triples}
        if isinstance(meta, dict):
            result["__meta__"] = meta
        return result
    if isinstance(payload, dict):
        return payload
    return {"triples": []}


def extract_balanced_json_candidate(text: str) -> str | None:
    for start, opener in enumerate(text):
        if opener not in "{[":
            continue
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
    return None


def parse_json_candidate(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    normalized = re.sub(r",(\s*[}\]])", r"\1", candidate)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        pass

    try:
        parsed = ast.literal_eval(normalized)
    except (SyntaxError, ValueError):
        raise ValueError("llm_response_not_json") from None
    if isinstance(parsed, (dict, list)):
        return parsed
    raise ValueError("llm_response_not_json")


def extract_json_block(text: str) -> Any:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates: list[str] = []
    if cleaned:
        candidates.append(cleaned)
    balanced = extract_balanced_json_candidate(cleaned)
    if balanced and balanced not in candidates:
        candidates.append(balanced)
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match and match.group(1) not in candidates:
        candidates.append(match.group(1))

    for candidate in candidates:
        try:
            parsed = parse_json_candidate(candidate)
            if len(extract_payload_triples(parsed)) <= 1:
                recovered = recover_triples_payload_from_text(cleaned)
                if recovered and len(extract_payload_triples(recovered)) > len(extract_payload_triples(parsed)):
                    return recovered
            return parsed
        except ValueError:
            continue
    recovered = recover_triples_payload_from_text(cleaned)
    if recovered:
        return recovered
    raise ValueError("llm_response_not_json")


def extract_all_json_blocks(text: str) -> list[Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    candidates: list[tuple[int, int, str]] = []
    seen_spans: set[tuple[int, int]] = set()

    for start, char in enumerate(cleaned):
        if char not in "{[":
            continue
        candidate = extract_balanced_json_candidate(cleaned[start:])
        if not candidate:
            continue
        candidate = candidate.strip()
        if not candidate:
            continue
        end = start + len(candidate)
        span = (start, end)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        candidates.append((start, end, candidate))

    kept: list[tuple[int, int, Any]] = []
    for start, end, candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
        try:
            parsed = parse_json_candidate(candidate)
        except ValueError:
            continue
        if not extract_payload_triples(parsed):
            continue
        if any(start >= kept_start and end <= kept_end for kept_start, kept_end, _ in kept):
            continue
        kept.append((start, end, parsed))
    return [parsed for _, _, parsed in kept]


def decode_jsonish_value(raw: str) -> Any:
    candidate = str(raw).strip()
    if not candidate:
        return ""
    try:
        return json.loads(candidate)
    except Exception:
        pass
    try:
        return ast.literal_eval(candidate)
    except Exception:
        lowered = candidate.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in {"null", "none"}:
            return None
        return candidate.strip("\"'")


def extract_jsonish_field(fragment: str, field_name: str) -> Any:
    pattern = re.compile(
        rf"""["']{re.escape(field_name)}["']\s*:\s*(
            "(?:\\.|[^"\\])*"
            |'(?:\\.|[^'\\])*'
            |-?\d+(?:\.\d+)?
            |true|false|null|None
        )""",
        re.IGNORECASE | re.VERBOSE | re.DOTALL,
    )
    match = pattern.search(fragment)
    if not match:
        return None
    return decode_jsonish_value(match.group(1))


def recover_triples_from_field_fragments(text: str) -> list[dict[str, Any]]:
    subject_key_pattern = re.compile(r"""["']subject["']\s*:""", re.IGNORECASE)
    matches = list(subject_key_pattern.finditer(text))
    if not matches:
        return []

    recovered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        start = match.start()
        brace_start = text.rfind("{", max(0, start - 200), start)
        previous_subject_start = matches[index - 1].start() if index > 0 else -1
        if brace_start != -1 and brace_start > previous_subject_start:
            start = brace_start
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        brace_end = text.find("}", match.end(), end)
        if brace_end != -1:
            end = brace_end + 1
        fragment = text[start:end]
        subject = extract_jsonish_field(fragment, "subject")
        predicate = extract_jsonish_field(fragment, "predicate")
        obj = extract_jsonish_field(fragment, "object")
        if not all(isinstance(item, str) and item.strip() for item in (subject, predicate, obj)):
            continue
        triple = {
            "subject": str(subject).strip(),
            "predicate": str(predicate).strip(),
            "object": str(obj).strip(),
        }
        subject_type = extract_jsonish_field(fragment, "subject_type")
        object_type = extract_jsonish_field(fragment, "object_type")
        source_text = extract_jsonish_field(fragment, "source_text")
        confidence = extract_jsonish_field(fragment, "confidence")
        if isinstance(subject_type, str) and subject_type.strip():
            triple["subject_type"] = subject_type.strip()
        if isinstance(object_type, str) and object_type.strip():
            triple["object_type"] = object_type.strip()
        if isinstance(source_text, str) and source_text.strip():
            triple["source_text"] = source_text.strip()
        if isinstance(confidence, (int, float)):
            triple["confidence"] = float(confidence)
        elif isinstance(confidence, str):
            try:
                triple["confidence"] = float(confidence.strip())
            except ValueError:
                pass
        signature = json.dumps(triple, ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        recovered.append(triple)
    return recovered


def recover_triples_payload_from_text(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    recovered: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()

    def add_triples_from_payload(payload: Any) -> None:
        for item in extract_payload_triples(payload):
            try:
                signature = json.dumps(item, ensure_ascii=False, sort_keys=True)
            except TypeError:
                signature = repr(sorted(item.items()))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            recovered.append(item)

    for start, char in enumerate(cleaned):
        if char not in "{[":
            continue
        candidate = extract_balanced_json_candidate(cleaned[start:])
        if not candidate:
            continue
        try:
            parsed = parse_json_candidate(candidate)
        except ValueError:
            continue
        add_triples_from_payload(parsed)

    for item in recover_triples_from_field_fragments(cleaned):
        try:
            signature = json.dumps(item, ensure_ascii=False, sort_keys=True)
        except TypeError:
            signature = repr(sorted(item.items()))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        recovered.append(item)

    if recovered:
        return {"triples": recovered}
    return None
