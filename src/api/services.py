from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from typing import Any

from src.models import Entity, Relationship
from src.query import DatasetIndex, RelationshipView, load_dataset
from src.validation import ValidationReport


class DatasetService:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._validate_required_files()
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

    def landing_page_context(self) -> dict:
        stats = self.stats()
        source_names = sorted(self.validation_report.source_counts)
        return {
            "metrics": {
                "entities": stats["entities"],
                "relationships": stats["relationships"],
                "duplicates_merged": stats["duplicates_merged"],
                "validation_errors": stats["validation_errors"],
            },
            "entity_types": _selected_counts(
                stats["entity_types"],
                ["tool", "model", "company", "repository", "mcp", "device", "task", "news"],
            ),
            "relationship_types": stats["relationship_types"],
            "sources": source_names,
            "top_categories": _top_categories(self.index.entities, limit=8),
        }

    def database_page_context(
        self,
        *,
        query: str | None = None,
        entity_type: str | None = None,
        category: str | None = None,
        page: int = 1,
        limit: int = 24,
    ) -> dict:
        entity_types = sorted({str(entity.entity_type) for entity in self.index.entities})
        categories = sorted({category for entity in self.index.entities for category in entity.categories})
        page = max(page, 1)
        limit = min(max(limit, 1), 100)

        if query:
            matches = self.index.search_entities(
                query,
                entity_type=entity_type,
                category=category,
                limit=len(self.index.entities),
            )
            rows = [
                {
                    "entity": match.entity,
                    "score": match.score,
                    "relationship_count": len(
                        self.index.relationships_by_entity_id.get(match.entity.id, [])
                    ),
                }
                for match in matches
            ]
        else:
            rows = [
                {
                    "entity": entity,
                    "score": None,
                    "relationship_count": len(
                        self.index.relationships_by_entity_id.get(entity.id, [])
                    ),
                }
                for entity in _filter_entities(
                    self.index.entities,
                    entity_type=entity_type,
                    category=category,
                )
            ]
        total_results = len(rows)
        total_pages = max(1, math.ceil(total_results / limit))
        page = min(page, total_pages)
        start = (page - 1) * limit
        paginated_rows = rows[start : start + limit]

        return {
            "query": query or "",
            "selected_type": entity_type or "",
            "selected_category": category or "",
            "page": page,
            "limit": limit,
            "entity_types": entity_types,
            "categories": categories,
            "rows": paginated_rows,
            "total_entities": self.entities_loaded,
            "total_relationships": self.relationships_loaded,
            "result_count": total_results,
            "displayed_count": len(paginated_rows),
            "total_pages": total_pages,
            "start_index": start + 1 if total_results else 0,
            "end_index": min(start + limit, total_results),
        }

    def entity_detail_context(self, entity_id: str) -> dict | None:
        entity = self.get_entity(entity_id)
        if entity is None:
            return None
        views = self.index.get_relationship_views_for_entity(entity_id)
        outgoing = [view for view in views if view.direction == "outgoing"]
        incoming = [view for view in views if view.direction == "incoming"]
        return {
            "entity": entity,
            "metadata": _presentable_metadata(entity.metadata),
            "sources": entity.sources,
            "outgoing": outgoing,
            "incoming": incoming,
            "relationship_count": len(views),
        }

    def relationship_explorer_context(
        self,
        *,
        relationship_type: str | None = None,
        page: int = 1,
        limit: int = 24,
    ) -> dict:
        page = max(page, 1)
        limit = min(max(limit, 1), 100)
        relationship_counts = self.stats()["relationship_types"]
        relationships = self.list_relationships(
            relationship_type=relationship_type,
            limit=len(self.index.relationships),
        )
        total_results = len(relationships)
        total_pages = max(1, math.ceil(total_results / limit))
        page = min(page, total_pages)
        start = (page - 1) * limit
        rows = [
            {
                "relationship": relationship,
                "source": self.index.entities_by_id.get(relationship.source_id),
                "target": self.index.entities_by_id.get(relationship.target_id),
            }
            for relationship in relationships[start : start + limit]
        ]
        return {
            "selected_type": relationship_type or "",
            "relationship_counts": relationship_counts,
            "rows": rows,
            "total_relationships": self.relationships_loaded,
            "result_count": total_results,
            "displayed_count": len(rows),
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "start_index": start + 1 if total_results else 0,
            "end_index": min(start + limit, total_results),
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
        return ValidationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _validate_required_files(self) -> None:
        missing = [
            file_name
            for file_name in [
                "entities.json",
                "relationships.json",
                "validation_report.json",
            ]
            if not (self.data_dir / file_name).exists()
        ]
        if missing:
            raise FileNotFoundError(
                f"API dataset is incomplete in {self.data_dir}; missing: {', '.join(missing)}"
            )


def _selected_counts(counts: dict[str, int], keys: list[str]) -> dict[str, int]:
    return {key: counts[key] for key in keys if key in counts}


def _top_categories(entities: list[Entity], *, limit: int) -> dict[str, int]:
    counter: Counter[str] = Counter(
        category
        for entity in entities
        for category in entity.categories
    )
    return dict(counter.most_common(limit))


def _filter_entities(
    entities: list[Entity],
    *,
    entity_type: str | None,
    category: str | None,
) -> list[Entity]:
    filtered = entities
    if entity_type:
        filtered = [entity for entity in filtered if str(entity.entity_type) == entity_type]
    if category:
        filtered = [entity for entity in filtered if category in entity.categories]
    return sorted(filtered, key=lambda entity: (str(entity.entity_type), entity.name))


def _presentable_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(metadata.items())
        if value not in [None, "", [], {}]
    }
