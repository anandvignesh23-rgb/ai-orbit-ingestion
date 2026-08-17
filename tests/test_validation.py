from __future__ import annotations

from types import SimpleNamespace

from src.models import Entity, EntityType, Relationship, RelationshipType, SourceReference
from src.relationships import RelationshipMapper
from src.utils.ids import generate_entity_id, generate_relationship_id
from src.validation import DatasetValidator


def make_entity(
    entity_type: EntityType,
    name: str,
    *,
    url: str | None = None,
    metadata: dict | None = None,
    categories: list[str] | None = None,
    entity_id: str | None = None,
    sources: list[SourceReference] | None = None,
) -> Entity:
    return Entity(
        id=entity_id or generate_entity_id(str(entity_type), url or name),
        entity_type=entity_type,
        name=name,
        url=url,
        categories=categories or [],
        sources=sources
        if sources is not None
        else [
            SourceReference(
                name="Fixture",
                url=url or f"https://example.com/{name.lower().replace(' ', '-')}",
            )
        ],
        metadata=metadata or {},
    )


def test_validator_report_success_for_small_relaxed_dataset() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI", url="https://openai.com")
    tool = make_entity(EntityType.TOOL, "ChatGPT", metadata={"provider": "OpenAI"})
    relationships = RelationshipMapper().map_relationships([company, tool])

    report = DatasetValidator(relaxed=True).validate(
        [company, tool],
        relationships,
        raw_records=3,
        duplicates_merged=1,
    )

    assert report.success is True
    assert report.summary.raw_records == 3
    assert report.summary.canonical_entities == 2
    assert report.summary.relationships == 1
    assert report.summary.duplicates_merged == 1
    assert report.entity_counts == {"company": 1, "tool": 1}
    assert report.source_counts == {"Fixture": 2}
    assert report.warnings


def test_validator_strict_dataset_size_failure() -> None:
    entity = make_entity(EntityType.TOOL, "ChatGPT")

    report = DatasetValidator(relaxed=False).validate([entity], [])

    assert report.success is False
    assert "outside expected range" in report.errors[0]


def test_validator_detects_duplicate_entity_ids() -> None:
    duplicate_id = generate_entity_id("tool", "duplicate")
    entities = [
        make_entity(EntityType.TOOL, "Tool A", entity_id=duplicate_id),
        make_entity(EntityType.TOOL, "Tool B", entity_id=duplicate_id),
    ]

    report = DatasetValidator().validate(entities, [])

    assert any("duplicate entity id" in error for error in report.errors)


def test_validator_warns_on_duplicate_canonical_urls() -> None:
    entities = [
        make_entity(EntityType.TOOL, "Tool A", url="https://www.example.com/tool/"),
        make_entity(EntityType.TOOL, "Tool B", url="http://example.com/tool"),
    ]

    report = DatasetValidator().validate(entities, [])

    assert any("duplicate canonical URL" in warning for warning in report.warnings)


def test_validator_flags_missing_provenance_as_error() -> None:
    entity = make_entity(EntityType.TOOL, "Unprovenanced", sources=[])

    report = DatasetValidator().validate([entity], [])

    assert any("no provenance sources" in error for error in report.errors)


def test_validator_collects_high_confidence_duplicate_candidates() -> None:
    entities = [
        make_entity(EntityType.COMPANY, "OpenAI"),
        make_entity(EntityType.COMPANY, "Open AI"),
    ]

    report = DatasetValidator().validate(entities, [])

    assert report.summary.possible_duplicates == 1
    assert report.duplicate_candidates[0]["decision"] == "merge"
    assert len(report.duplicate_candidates[0]["entity_ids"]) == 2


def test_validator_detects_relationship_reference_errors() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    relationship = SimpleNamespace(
        id="relationship-1",
        source_id=company.id,
        relationship_type="develops",
        target_id="missing-target",
    )

    report = DatasetValidator().validate([company], [relationship])

    assert report.success is False
    assert any("missing target" in error for error in report.relationship_errors)


def test_validator_detects_duplicate_relationship_edges() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    tool = make_entity(EntityType.TOOL, "ChatGPT")
    relationship_id = generate_relationship_id(company.id, "develops", tool.id)
    relationships = [
        Relationship(
            id=relationship_id,
            source_id=company.id,
            relationship_type=RelationshipType.DEVELOPS,
            target_id=tool.id,
            confidence=0.95,
        ),
        Relationship(
            id=f"{relationship_id}-copy",
            source_id=company.id,
            relationship_type=RelationshipType.DEVELOPS,
            target_id=tool.id,
            confidence=0.95,
        ),
    ]

    report = DatasetValidator().validate([company, tool], relationships)

    assert any("duplicate relationship edge" in error for error in report.relationship_errors)


def test_validator_detects_self_relationship_and_invalid_type() -> None:
    entity = make_entity(EntityType.TOOL, "ChatGPT")
    relationship = SimpleNamespace(
        id="bad-relationship",
        source_id=entity.id,
        relationship_type="invalid",
        target_id=entity.id,
    )

    report = DatasetValidator().validate([entity], [relationship])

    assert any("invalid type" in error for error in report.relationship_errors)
    assert any("self-relation" in error for error in report.relationship_errors)


def test_validator_warns_on_missing_specialized_metadata() -> None:
    repository = make_entity(
        EntityType.REPOSITORY,
        "Repo",
        url="https://github.com/example/repo",
    )
    model = make_entity(EntityType.MODEL, "Model")

    report = DatasetValidator().validate([repository, model], [])

    assert any("repository" in warning and "owner" in warning for warning in report.warnings)
    assert any("model" in warning and "provider" in warning for warning in report.warnings)


def test_validation_report_is_json_serializable() -> None:
    entity = make_entity(EntityType.TOOL, "ChatGPT")

    report = DatasetValidator().validate([entity], [])

    payload = report.model_dump(mode="json")
    assert payload["summary"]["canonical_entities"] == 1
