from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval_service.chroma_case_store import (
    ChromaCaseQASettings,
    ChromaCaseQAStore,
    _CollectionDescriptor,
)


class ChromaCaseQAStorePlanningTests(unittest.TestCase):
    def _make_store(self) -> ChromaCaseQAStore:
        tmpdir = Path(tempfile.mkdtemp())
        settings = ChromaCaseQASettings(
            db_path=tmpdir / "db",
            mirror_path=tmpdir / "mirror",
            query_workers=2,
            initial_shard_limit=3,
            max_loaded_collections=2,
            batch_load_target_bytes=150,
        )
        return ChromaCaseQAStore(settings)

    @staticmethod
    def _descriptor(name: str, *, metadata_segment_id: str, estimated_bytes: int) -> _CollectionDescriptor:
        return _CollectionDescriptor(
            name=name,
            collection_id=f"col-{name}",
            vector_segment_id=f"vec-{name}",
            metadata_segment_id=metadata_segment_id,
            dimension=1024,
            vector_dir=Path("."),
            estimated_elements=100,
            estimated_bytes=estimated_bytes,
        )

    def test_build_query_waves_respects_worker_and_byte_limits(self) -> None:
        store = self._make_store()
        descriptors = [
            self._descriptor("tcm_shard_0", metadata_segment_id="m0", estimated_bytes=80),
            self._descriptor("tcm_shard_1", metadata_segment_id="m1", estimated_bytes=90),
            self._descriptor("tcm_shard_2", metadata_segment_id="m2", estimated_bytes=70),
        ]

        waves = store._build_query_waves(descriptors)

        self.assertEqual([[item.name for item in wave] for wave in waves], [["tcm_shard_0"], ["tcm_shard_1"], ["tcm_shard_2"]])

    def test_order_descriptors_prioritizes_lexical_hits(self) -> None:
        store = self._make_store()
        descriptors = [
            self._descriptor("tcm_shard_0", metadata_segment_id="m0", estimated_bytes=120),
            self._descriptor("tcm_shard_1", metadata_segment_id="m1", estimated_bytes=90),
            self._descriptor("tcm_shard_2", metadata_segment_id="m2", estimated_bytes=70),
        ]

        ordered = store._order_descriptors_for_query(
            descriptors,
            lexical_scores={"m1": 4.2, "m0": 0.0},
        )

        self.assertEqual([item.name for item in ordered][:2], ["tcm_shard_1", "tcm_shard_2"])

    def test_should_stop_after_stage_one_when_remaining_have_no_lexical_hits(self) -> None:
        store = self._make_store()
        selected = [
            {"selection_score": 0.82},
            {"selection_score": 0.79},
            {"selection_score": 0.76},
        ]
        remaining = [
            self._descriptor("tcm_shard_7", metadata_segment_id="m7", estimated_bytes=100),
            self._descriptor("tcm_shard_8", metadata_segment_id="m8", estimated_bytes=100),
        ]

        should_stop = store._should_stop_after_stage_one(
            selected=selected,
            candidate_count=7,
            top_k=3,
            remaining_descriptors=remaining,
            lexical_scores={"m0": 5.0},
        )

        self.assertTrue(should_stop)


if __name__ == "__main__":
    unittest.main()
