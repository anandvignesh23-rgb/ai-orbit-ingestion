from __future__ import annotations

from src.models import Entity, EntityType, Relationship, RelationshipType, SourceReference
from src.product_export import build_product_catalog
from src.utils.ids import generate_entity_id, generate_relationship_id


def make_entity(entity_type: EntityType, name: str, *, metadata: dict | None = None) -> Entity:
    return Entity(
        id=generate_entity_id(str(entity_type), name),
        entity_type=entity_type,
        name=name,
        url=f"https://example.com/{name.lower().replace(' ', '-')}",
        categories=["developer-tools"] if entity_type == EntityType.TOOL else [],
        sources=[
            SourceReference(
                name="Official source",
                url=f"https://example.com/{name.lower().replace(' ', '-')}",
                source_type="official_site",
                is_official=True,
            )
        ],
        metadata=metadata or {},
    )


def test_product_catalog_includes_inverse_relationship_summaries() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    tool = make_entity(EntityType.TOOL, "ChatGPT", metadata={"provider": "OpenAI"})
    relationship = Relationship(
        id=generate_relationship_id(company.id, "develops", tool.id),
        source_id=company.id,
        relationship_type=RelationshipType.DEVELOPS,
        target_id=tool.id,
        confidence=0.95,
    )

    catalog = build_product_catalog([company, tool], [relationship])
    tool_record = next(record for record in catalog if record["id"] == tool.id)
    company_record = next(record for record in catalog if record["id"] == company.id)

    assert company_record["relationships"] == [
        {
            "entity_id": tool.id,
            "relationship_type": "develops",
            "direction": "outgoing",
        }
    ]
    assert tool_record["relationships"] == [
        {
            "entity_id": company.id,
            "relationship_type": "developed_by",
            "direction": "incoming",
        }
    ]
    assert tool_record["provider"] == "OpenAI"
