import pytest
from pydantic import ValidationError

from src.models import (
    DisplayMetadata,
    Entity,
    EntityType,
    Evidence,
    PipelineMetadata,
    Relationship,
    RelationshipType,
    SourceReference,
)


def test_entity_accepts_valid_common_schema() -> None:
    entity = Entity(
        id="entity-1",
        entity_type=EntityType.COMPANY,
        name="OpenAI",
        description="AI research and product company.",
        url="https://openai.com",
        categories=["research", "developer-tools"],
        sources=[SourceReference(name="Official site", url="https://openai.com")],
        metadata={"official_domain": "openai.com"},
    )

    assert entity.entity_type == "company"
    assert entity.name == "OpenAI"
    assert entity.sources[0].name == "Official site"


def test_entity_accepts_product_display_and_pipeline_metadata() -> None:
    entity = Entity(
        id="entity-1",
        entity_type=EntityType.TOOL,
        name="Example Tool",
        sources=[
            SourceReference(
                name="Official site",
                url="https://example.com",
                source_type="official_site",
                is_official=True,
            )
        ],
        display=DisplayMetadata(
            short_description="Short product description",
            provider_name="Example Company",
            recently_added=True,
        ),
        pipeline_metadata=PipelineMetadata(source_count=1, needs_review=True),
    )

    assert entity.sources[0].source_type == "official_site"
    assert entity.sources[0].is_official is True
    assert entity.display.provider_name == "Example Company"
    assert entity.pipeline_metadata.needs_review is True


def test_entity_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        Entity(id="entity-1", entity_type=EntityType.TOOL, name="   ")


def test_entity_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        Entity(id="entity-1", entity_type="invalid", name="Bad Type")


def test_entity_requires_lowercase_categories() -> None:
    with pytest.raises(ValidationError):
        Entity(
            id="entity-1",
            entity_type=EntityType.TOOL,
            name="Tool",
            categories=["Developer-Tools"],
        )


def test_source_reference_requires_url() -> None:
    with pytest.raises(ValidationError):
        SourceReference(name="Official", url="not-a-url")


def test_relationship_accepts_valid_schema() -> None:
    relationship = Relationship(
        id="relationship-1",
        source_id="company-1",
        relationship_type=RelationshipType.DEVELOPS,
        target_id="tool-1",
        confidence=0.97,
        evidence=[
            Evidence(
                source_name="Official site",
                source_url="https://openai.com",
                note="Official product listing",
            )
        ],
    )

    assert relationship.relationship_type == "develops"
    assert relationship.confidence == 0.97
    assert relationship.evidence[0].source_name == "Official site"


def test_relationship_rejects_confidence_outside_range() -> None:
    with pytest.raises(ValidationError):
        Relationship(
            id="relationship-1",
            source_id="company-1",
            relationship_type=RelationshipType.DEVELOPS,
            target_id="tool-1",
            confidence=1.5,
        )
