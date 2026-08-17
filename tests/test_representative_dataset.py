from __future__ import annotations

from scripts.build_representative_dataset import build_entities
from src.relationships import RelationshipMapper
from src.validation import DatasetValidator


def test_representative_dataset_meets_phase_13_target() -> None:
    entities = build_entities()
    relationships = RelationshipMapper().map_relationships(entities)
    report = DatasetValidator(relaxed=False).validate(
        entities,
        relationships,
        raw_records=len(entities),
    )

    assert 250 <= len(entities) <= 300
    assert relationships
    assert report.success is True
    assert report.summary.critical_errors == 0
