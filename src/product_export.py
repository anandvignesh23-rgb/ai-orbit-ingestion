from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from src.models import Entity, Relationship
from src.normalization.names import normalize_name
from src.query.dataset import inverse_relationship_type


class ProductRelationshipSummary(BaseModel):
    entity_id: str
    relationship_type: str
    direction: str


class ProductCatalogRecord(BaseModel):
    id: str
    entity_type: str
    name: str
    description: str | None = None
    url: HttpUrl | None = None
    categories: list[str] = Field(default_factory=list)
    provider: str | None = None
    logo_url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    recently_added: bool = False
    related_entity_ids: list[str] = Field(default_factory=list)
    relationships: list[ProductRelationshipSummary] = Field(default_factory=list)
    search_text: str = ""
    completeness_score: float = Field(ge=0.0, le=1.0)


def build_product_catalog(
    entities: list[Entity],
    relationships: list[Relationship],
) -> list[dict[str, Any]]:
    relationship_summaries = _relationship_summaries_by_entity(relationships)
    records = [
        _product_record(entity, relationship_summaries.get(entity.id, []))
        for entity in sorted(entities, key=lambda item: (str(item.entity_type), item.name))
    ]
    return [ProductCatalogRecord.model_validate(record).model_dump(mode="json") for record in records]


def _product_record(entity: Entity, relationships: list[ProductRelationshipSummary]) -> dict[str, Any]:
    provider = _provider_name(entity)
    search_text = _search_text(entity, provider)
    related_entity_ids = sorted({relationship.entity_id for relationship in relationships})
    return {
        "id": entity.id,
        "entity_type": str(entity.entity_type),
        "name": entity.name,
        "description": entity.display.short_description if entity.display and entity.display.short_description else entity.description,
        "url": str(entity.url) if entity.url else None,
        "categories": entity.categories,
        "provider": provider,
        "logo_url": str(entity.display.logo_url) if entity.display and entity.display.logo_url else None,
        "image_url": str(entity.display.image_url) if entity.display and entity.display.image_url else None,
        "recently_added": bool(entity.display.recently_added) if entity.display else bool(entity.metadata.get("recently_added")),
        "related_entity_ids": related_entity_ids,
        "relationships": [relationship.model_dump(mode="json") for relationship in relationships],
        "search_text": search_text,
        "completeness_score": _completeness_score(entity, related_entity_ids),
    }


def _relationship_summaries_by_entity(
    relationships: list[Relationship],
) -> dict[str, list[ProductRelationshipSummary]]:
    summaries: dict[str, list[ProductRelationshipSummary]] = {}
    for relationship in relationships:
        summaries.setdefault(relationship.source_id, []).append(
            ProductRelationshipSummary(
                entity_id=relationship.target_id,
                relationship_type=str(relationship.relationship_type),
                direction="outgoing",
            )
        )
        summaries.setdefault(relationship.target_id, []).append(
            ProductRelationshipSummary(
                entity_id=relationship.source_id,
                relationship_type=inverse_relationship_type(str(relationship.relationship_type)),
                direction="incoming",
            )
        )
    return {
        entity_id: sorted(items, key=lambda item: (item.relationship_type, item.entity_id))
        for entity_id, items in summaries.items()
    }


def _provider_name(entity: Entity) -> str | None:
    if entity.display and entity.display.provider_name:
        return entity.display.provider_name
    for key in ["provider", "company", "developer", "publisher"]:
        value = entity.metadata.get(key)
        if value:
            return str(value)
    return None


def _search_text(entity: Entity, provider: str | None) -> str:
    parts = [
        entity.name,
        entity.description or "",
        " ".join(entity.categories),
        provider or "",
        str(entity.metadata.get("pipeline_task", "")),
        " ".join(str(tag) for tag in entity.metadata.get("tags", []) if tag),
    ]
    return normalize_name(" ".join(part for part in parts if part))


def _completeness_score(entity: Entity, related_entity_ids: list[str]) -> float:
    provider = _provider_name(entity)
    checks = [
        True,
        bool(entity.description),
        bool(entity.url),
        bool(entity.categories),
        bool(provider),
        bool(entity.sources),
        bool(entity.display and (entity.display.logo_url or entity.display.image_url or entity.display.short_description)),
        bool(related_entity_ids),
    ]
    return round(sum(1 for check in checks if check) / len(checks), 3)
