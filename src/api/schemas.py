from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl

from src.models import Entity, Relationship
from src.query import RelationshipView


class HealthResponse(BaseModel):
    status: str
    entities_loaded: int = Field(ge=0)
    relationships_loaded: int = Field(ge=0)


class StatsResponse(BaseModel):
    entities: int = Field(ge=0)
    relationships: int = Field(ge=0)
    entity_types: dict[str, int] = Field(default_factory=dict)
    relationship_types: dict[str, int] = Field(default_factory=dict)
    duplicates_merged: int = Field(ge=0)
    validation_errors: int = Field(ge=0)
    recently_added_entities: int = Field(ge=0)
    average_relationships_per_entity: float = Field(ge=0.0)


class EntitySearchResult(BaseModel):
    id: str
    entity_type: str
    name: str
    description: str | None = None
    url: HttpUrl | None = None
    categories: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0)


class RelationshipViewResponse(BaseModel):
    relationship: Relationship
    effective_relationship_type: str
    direction: str
    related_entity: Entity | None = None


def search_result_from_match(match) -> EntitySearchResult:
    entity = match.entity
    return EntitySearchResult(
        id=entity.id,
        entity_type=str(entity.entity_type),
        name=entity.name,
        description=entity.description,
        url=entity.url,
        categories=entity.categories,
        score=match.score,
    )


def relationship_view_response(view: RelationshipView) -> RelationshipViewResponse:
    return RelationshipViewResponse(
        relationship=view.relationship,
        effective_relationship_type=view.effective_relationship_type,
        direction=view.direction,
        related_entity=view.related_entity,
    )
