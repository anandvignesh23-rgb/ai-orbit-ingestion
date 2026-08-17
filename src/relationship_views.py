from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.models import Relationship
from src.query.dataset import inverse_relationship_type


class ProductRelationshipView(BaseModel):
    view_id: str = Field(min_length=1)
    relationship_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    canonical_relationship_type: str = Field(min_length=1)
    direction: Literal["outgoing", "incoming"]
    confidence: float = Field(ge=0.0, le=1.0)
    derived: bool = False


def build_relationship_views(
    relationships: list[Relationship],
    *,
    include_inverse: bool = True,
) -> list[dict[str, Any]]:
    views: list[ProductRelationshipView] = []
    for relationship in relationships:
        canonical_type = str(relationship.relationship_type)
        views.append(
            ProductRelationshipView(
                view_id=f"{relationship.id}:outgoing",
                relationship_id=relationship.id,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                relationship_type=canonical_type,
                canonical_relationship_type=canonical_type,
                direction="outgoing",
                confidence=relationship.confidence,
                derived=False,
            )
        )
        if include_inverse:
            views.append(
                ProductRelationshipView(
                    view_id=f"{relationship.id}:incoming",
                    relationship_id=relationship.id,
                    source_id=relationship.target_id,
                    target_id=relationship.source_id,
                    relationship_type=inverse_relationship_type(canonical_type),
                    canonical_relationship_type=canonical_type,
                    direction="incoming",
                    confidence=relationship.confidence,
                    derived=True,
                )
            )
    return [
        view.model_dump(mode="json")
        for view in sorted(
            views,
            key=lambda item: (
                item.source_id,
                item.relationship_type,
                item.target_id,
                item.view_id,
            ),
        )
    ]
