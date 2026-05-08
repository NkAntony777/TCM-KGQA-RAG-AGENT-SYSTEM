from __future__ import annotations

from types import SimpleNamespace

from services.retrieval_service.vector_compatibility import maybe_fuse_files_first_with_vector


class ReadyEmbedding:
    def is_ready(self) -> bool:
        return True

    def embed(self, texts, model):
        return [[0.1, 0.2]]


class NotReadyEmbedding:
    def is_ready(self) -> bool:
        return False


class FakeMilvus:
    def has_collection(self) -> bool:
        return False


class FakeLocalStore:
    def search(self, **kwargs):
        return ([{"chunk_id": "v1", "score": 0.8}], "dense_local_fallback")


class FakeFilesFirstStore:
    def get_docs_by_chunk_ids(self, chunk_ids):
        return [
            {"chunk_id": "v1", "section_key": "s2", "text": "vector", "score": 0.7},
        ]


def test_vector_fusion_disabled_when_embedding_unavailable() -> None:
    warnings: list[str] = []
    docs = [{"chunk_id": "f1", "section_key": "s1", "text": "files", "score": 0.9}]

    fused, mode = maybe_fuse_files_first_with_vector(
        settings=SimpleNamespace(vector_compatibility_enabled=True, embedding_model="emb", leaf_retrieve_level=3),
        files_first_store=FakeFilesFirstStore(),
        milvus=FakeMilvus(),
        local_store=FakeLocalStore(),
        embedding_client=NotReadyEmbedding(),
        query="六味地黄丸 出处",
        query_context=None,
        docs=docs,
        top_k=3,
        candidate_k=6,
        warnings=warnings,
    )

    assert fused == docs
    assert mode is None
    assert warnings == []


def test_vector_fusion_merges_hydrated_vector_candidates() -> None:
    warnings: list[str] = []
    docs = [{"chunk_id": "f1", "section_key": "s1", "text": "files", "score": 0.9}]

    fused, mode = maybe_fuse_files_first_with_vector(
        settings=SimpleNamespace(vector_compatibility_enabled=True, embedding_model="emb", leaf_retrieve_level=3),
        files_first_store=FakeFilesFirstStore(),
        milvus=FakeMilvus(),
        local_store=FakeLocalStore(),
        embedding_client=ReadyEmbedding(),
        query="六味地黄丸 出处",
        query_context={"expanded_query": "六味地黄丸 小儿药证直诀"},
        docs=docs,
        top_k=3,
        candidate_k=6,
        warnings=warnings,
    )

    assert mode == "files_first_vector_fused"
    assert warnings == ["files_first_vector_fusion_applied"]
    assert {item["section_key"] for item in fused} == {"s1", "s2"}
