from __future__ import annotations

from typing import Any

def search_case_qa(
    self,
    query: str,
    *,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    structured_rows = self.structured_qa.search_case(query, top_k=max(1, int(top_k)))
    if structured_rows:
        chunks = [self._normalize_structured_case_chunk(item) for item in structured_rows if isinstance(item, dict)]
        return {
            "backend": "case-qa",
            "retrieval_mode": "structured_case_qa",
            "candidate_k": candidate_k,
            "chunks": chunks,
            "total": len(chunks),
            "warnings": [],
        }

    warnings: list[str] = []
    if not self.settings.case_qa_vector_fallback_enabled:
        return {
            "backend": "case-qa",
            "retrieval_mode": "structured_case_qa_empty",
            "candidate_k": candidate_k,
            "chunks": [],
            "total": 0,
            "warnings": ["structured_case_qa_empty", "case_qa_vector_fallback_disabled"],
        }
    if not self.embedding_client.is_ready():
        return {
            "backend": "case-qa",
            "retrieval_mode": "unconfigured",
            "candidate_k": candidate_k,
            "chunks": [],
            "total": 0,
            "warnings": ["embedding_client_not_configured"],
        }

    dense_vector = self.embedding_client.embed(
        [query],
        self.settings.case_qa_embedding_model,
        dimensions=self.settings.case_qa_embedding_dimensions,
    )[0]
    case_qa_store = self.case_qa
    if case_qa_store is None:
        return {
            "backend": "case-qa",
            "retrieval_mode": "vector_compatibility_disabled",
            "candidate_k": candidate_k,
            "chunks": [],
            "total": 0,
            "warnings": ["case_qa_vector_hot_path_disabled"],
        }
    data = case_qa_store.search(
        query=query,
        query_embedding=dense_vector,
        top_k=top_k,
        candidate_k=candidate_k,
    )
    warnings.extend(data.get("warnings", []))
    chunks = [self._normalize_case_chunk(item) for item in data.get("chunks", []) if isinstance(item, dict)]

    return {
        "backend": "case-qa",
        "retrieval_mode": data.get("retrieval_mode", "case_qa"),
        "candidate_k": candidate_k,
        "embedding_model": self.settings.case_qa_embedding_model,
        "embedding_dimensions": self.settings.case_qa_embedding_dimensions,
        "collection_count": data.get("collection_count", 0),
        "per_collection_k": data.get("per_collection_k"),
        "chunks": chunks,
        "total": len(chunks),
        "warnings": warnings,
    }

def _normalize_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": item.get("chunk_id", ""),
        "embedding_id": item.get("embedding_id", ""),
        "collection": item.get("collection", ""),
        "text": str(item.get("text", "")).strip(),
        "document": str(item.get("document", "")).strip(),
        "answer": str(item.get("answer", "")).strip(),
        "source_file": item.get("source_file", "caseqa"),
        "source_page": item.get("source_page"),
        "score": float(item.get("score", 0.0) or 0.0),
        "distance": float(item.get("distance", 0.0) or 0.0),
        "rerank_score": float(item.get("rerank_score", 0.0) or 0.0),
        "metadata": item.get("metadata", {}),
    }

def _normalize_structured_case_chunk(item: dict[str, Any]) -> dict[str, Any]:
    record_id = str(item.get("record_id", "")).strip()
    collection = str(item.get("collection", "")).strip() or "qa_structured_case"
    question = str(item.get("question", "")).strip()
    answer = str(item.get("answer", "")).strip()
    symptom_text = str(item.get("symptom_text", "")).strip()
    syndrome_text = str(item.get("syndrome_text", "")).strip()
    formula_text = str(item.get("formula_text", "")).strip()
    summary_parts = [question, symptom_text, syndrome_text, formula_text]
    document = "\n".join(part for part in summary_parts if part)
    return {
        "chunk_id": record_id,
        "embedding_id": str(item.get("embedding_id", "")).strip() or record_id,
        "collection": collection,
        "text": answer or question,
        "document": document,
        "answer": answer,
        "source_file": f"caseqa:{collection}",
        "source_page": None,
        "score": float(item.get("_rerank_score", 0.0) or 0.0),
        "distance": 0.0,
        "rerank_score": float(item.get("_rerank_score", 0.0) or 0.0),
        "metadata": {
            "record_id": record_id,
            "question": question,
            "answer": answer,
            "age": str(item.get("age", "")).strip(),
            "sex": str(item.get("sex", "")).strip(),
            "chief_complaint": str(item.get("chief_complaint", "")).strip(),
            "history": str(item.get("history", "")).strip(),
            "tongue": str(item.get("tongue", "")).strip(),
            "pulse": str(item.get("pulse", "")).strip(),
            "symptom_text": symptom_text,
            "syndrome_text": syndrome_text,
            "formula_text": formula_text,
        },
    }
