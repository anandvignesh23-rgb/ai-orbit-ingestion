from __future__ import annotations

import json
from pathlib import Path

from src.models import Entity, Relationship
from src.query import DatasetIndex, RelationshipView, load_dataset
from src.validation import ValidationReport


class DatasetService:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.index = load_dataset(self.data_dir)
        self.validation_report = self._load_validation_report()

    @property
    def entities_loaded(self) -> int:
        return len(self.index.entities)

    @property
    def relationships_loaded(self) -> int:
        return len(self.index.relationships)

    def stats(self) -> dict:
        analytics = self.index.analytics(limit=0)
        summary = self.index.summary()
        report = self.validation_report
        average_relationships = (
            report.relationship_metrics.average_relationships_per_entity
            if report
            else 0.0
        )
        if average_relationships == 0 and analytics.entity_count:
            average_relationships = round(
                analytics.relationship_count / analytics.entity_count,
                3,
            )
        return {
            "entities": analytics.entity_count,
            "relationships": analytics.relationship_count,
            "entity_types": analytics.entity_type_counts,
            "relationship_types": analytics.relationship_type_counts,
            "duplicates_merged": int(summary.get("duplicates_merged", 0) or 0),
            "validation_errors": int(summary.get("critical_errors", 0) or 0),
            "recently_added_entities": report.product_quality_metrics.recently_added_entities if report else 0,
            "average_relationships_per_entity": average_relationships,
        }

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Entity]:
        entities = self.index.entities
        if entity_type:
            entities = [entity for entity in entities if str(entity.entity_type) == entity_type]
        if category:
            entities = [entity for entity in entities if category in entity.categories]
        return sorted(entities, key=lambda entity: (str(entity.entity_type), entity.name))[offset : offset + limit]

    def get_entity(self, entity_id: str) -> Entity | None:
        return self.index.entities_by_id.get(entity_id)

    def list_relationships(
        self,
        *,
        relationship_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Relationship]:
        relationships = self.index.relationships
        if relationship_type:
            relationships = [
                relationship
                for relationship in relationships
                if str(relationship.relationship_type) == relationship_type
            ]
        if source_id:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.source_id == source_id
            ]
        if target_id:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.target_id == target_id
            ]
        return sorted(relationships, key=lambda relationship: relationship.id)[offset : offset + limit]

    def relationship_views_for_entity(
        self,
        entity_id: str,
        *,
        relationship_type: str | None = None,
    ) -> list[RelationshipView] | None:
        if entity_id not in self.index.entities_by_id:
            return None
        return self.index.get_relationship_views_for_entity(
            entity_id,
            relationship_type=relationship_type,
        )

    def _load_validation_report(self) -> ValidationReport | None:
        path = self.data_dir / "validation_report.json"
        if not path.exists():
            return None
        return ValidationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
