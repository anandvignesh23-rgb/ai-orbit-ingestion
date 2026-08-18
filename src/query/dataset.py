from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from rapidfuzz import fuzz

from src.models import Entity, Relationship
from src.normalization.names import normalize_name


INVERSE_RELATIONSHIP_TYPES = {
    "develops": "developed_by",
    "solves": "solved_by",
    "integrates_with": "integrated_by",
    "runs": "runs_on",
    "part_of_collection": "contains",
}


class EntityMatch(BaseModel):
    entity: Entity
    score: float


class Neighborhood(BaseModel):
    entity: Entity
    incoming: list[Relationship]
    outgoing: list[Relationship]
    related_entities: list[Entity]


class RelationshipView(BaseModel):
    relationship: Relationship
    effective_relationship_type: str
    direction: str
    related_entity: Entity | None = None


class EntityDegree(BaseModel):
    id: str
    name: str
    entity_type: str
    incoming: int
    outgoing: int
    total: int


class GraphAnalytics(BaseModel):
    entity_count: int
    relationship_count: int
    relationship_type_counts: dict[str, int]
    entity_type_counts: dict[str, int]
    orphan_count: int
    orphans: list[EntityDegree]
    top_connected: list[EntityDegree]


class ChangedEntity(BaseModel):
    id: str
    before_name: str
    after_name: str
    changed_fields: list[str]


class DatasetDiff(BaseModel):
    before_summary: dict[str, Any]
    after_summary: dict[str, Any]
    added_entities: list[Entity]
    removed_entities: list[Entity]
    changed_entities: list[ChangedEntity]
    added_relationships: list[Relationship]
    removed_relationships: list[Relationship]


class DatasetIndex:
    def __init__(
        self,
        *,
        entities: list[Entity],
        relationships: list[Relationship],
        manifest: dict[str, Any] | None = None,
    ) -> None:
        self.entities = entities
        self.relationships = relationships
        self.manifest = manifest or {}
        self.entities_by_id = {entity.id: entity for entity in entities}
        self.relationships_by_entity_id: dict[str, list[Relationship]] = {}
        for relationship in relationships:
            self.relationships_by_entity_id.setdefault(relationship.source_id, []).append(relationship)
            self.relationships_by_entity_id.setdefault(relationship.target_id, []).append(relationship)

    def summary(self) -> dict[str, Any]:
        if self.manifest.get("summary"):
            return {
                "run_mode": self.manifest.get("run_mode"),
                "success": self.manifest.get("success"),
                **self.manifest["summary"],
            }
        return {
            "run_mode": None,
            "success": None,
            "canonical_entities": len(self.entities),
            "relationships": len(self.relationships),
        }

    def search_entities(
        self,
        query: str,
        *,
        entity_type: str | None = None,
        category: str | None = None,
        source_name: str | None = None,
        limit: int = 10,
    ) -> list[EntityMatch]:
        normalized_query = normalize_name(query)
        matches: list[EntityMatch] = []

        for entity in self.entities:
            if entity_type and str(entity.entity_type) != entity_type:
                continue
            if category and category not in entity.categories:
                continue
            if source_name and not any(source_name.lower() in source.name.lower() for source in entity.sources):
                continue

            score = _match_score(entity, normalized_query)
            if score <= 0:
                continue
            matches.append(EntityMatch(entity=entity, score=score))

        return sorted(
            matches,
            key=lambda match: (-match.score, str(match.entity.entity_type), match.entity.name),
        )[:limit]

    def find_entity(self, identifier: str) -> Entity | None:
        if identifier in self.entities_by_id:
            return self.entities_by_id[identifier]
        matches = self.search_entities(identifier, limit=1)
        if not matches:
            return None
        return matches[0].entity

    def neighborhood(self, identifier: str) -> Neighborhood | None:
        entity = self.find_entity(identifier)
        if entity is None:
            return None

        incoming: list[Relationship] = []
        outgoing: list[Relationship] = []
        related_ids: set[str] = set()

        for relationship in self.relationships_by_entity_id.get(entity.id, []):
            if relationship.source_id == entity.id:
                outgoing.append(relationship)
                related_ids.add(relationship.target_id)
            if relationship.target_id == entity.id:
                incoming.append(relationship)
                related_ids.add(relationship.source_id)

        related_entities = [
            self.entities_by_id[entity_id]
            for entity_id in sorted(related_ids)
            if entity_id in self.entities_by_id
        ]
        return Neighborhood(
            entity=entity,
            incoming=sorted(incoming, key=lambda relationship: relationship.id),
            outgoing=sorted(outgoing, key=lambda relationship: relationship.id),
            related_entities=related_entities,
        )

    def get_relationships_for_entity(self, entity_id: str) -> list[Relationship]:
        return sorted(
            self.relationships_by_entity_id.get(entity_id, []),
            key=lambda relationship: relationship.id,
        )

    def get_outgoing_relationships(self, entity_id: str) -> list[Relationship]:
        return sorted(
            [relationship for relationship in self.relationships if relationship.source_id == entity_id],
            key=lambda relationship: relationship.id,
        )

    def get_incoming_relationships(self, entity_id: str) -> list[Relationship]:
        return sorted(
            [relationship for relationship in self.relationships if relationship.target_id == entity_id],
            key=lambda relationship: relationship.id,
        )

    def get_related_entities(
        self,
        entity_id: str,
        *,
        relationship_type: str | None = None,
    ) -> list[Entity]:
        related_ids: set[str] = set()
        for relationship in self.get_relationships_for_entity(entity_id):
            if relationship_type and str(relationship.relationship_type) != relationship_type:
                continue
            if relationship.source_id == entity_id:
                related_ids.add(relationship.target_id)
            elif relationship.target_id == entity_id:
                related_ids.add(relationship.source_id)
        return [
            self.entities_by_id[related_id]
            for related_id in sorted(related_ids)
            if related_id in self.entities_by_id
        ]

    def get_relationship_views_for_entity(
        self,
        entity_id: str,
        *,
        relationship_type: str | None = None,
    ) -> list[RelationshipView]:
        views: list[RelationshipView] = []
        for relationship in self.get_relationships_for_entity(entity_id):
            if relationship.source_id == entity_id:
                effective_type = str(relationship.relationship_type)
                related_id = relationship.target_id
                direction = "outgoing"
            else:
                effective_type = inverse_relationship_type(str(relationship.relationship_type))
                related_id = relationship.source_id
                direction = "incoming"
            if relationship_type and effective_type != relationship_type:
                continue
            views.append(
                RelationshipView(
                    relationship=relationship,
                    effective_relationship_type=effective_type,
                    direction=direction,
                    related_entity=self.entities_by_id.get(related_id),
                )
            )
        return sorted(
            views,
            key=lambda view: (
                view.effective_relationship_type,
                view.related_entity.name if view.related_entity else "",
                view.relationship.id,
            ),
        )

    def filter_by_type(self, entity_type: str) -> list[Entity]:
        return [entity for entity in self.entities if str(entity.entity_type) == entity_type]

    def filter_by_category(self, category: str) -> list[Entity]:
        return [entity for entity in self.entities if category in entity.categories]

    def analytics(self, *, limit: int = 10) -> GraphAnalytics:
        incoming_counts = Counter(relationship.target_id for relationship in self.relationships)
        outgoing_counts = Counter(relationship.source_id for relationship in self.relationships)
        degrees = [
            EntityDegree(
                id=entity.id,
                name=entity.name,
                entity_type=str(entity.entity_type),
                incoming=incoming_counts[entity.id],
                outgoing=outgoing_counts[entity.id],
                total=incoming_counts[entity.id] + outgoing_counts[entity.id],
            )
            for entity in self.entities
        ]
        sorted_degrees = sorted(
            degrees,
            key=lambda degree: (-degree.total, -degree.incoming, degree.entity_type, degree.name),
        )
        orphans = sorted(
            [degree for degree in degrees if degree.total == 0],
            key=lambda degree: (degree.entity_type, degree.name),
        )

        return GraphAnalytics(
            entity_count=len(self.entities),
            relationship_count=len(self.relationships),
            relationship_type_counts=dict(
                sorted(Counter(str(relationship.relationship_type) for relationship in self.relationships).items())
            ),
            entity_type_counts=dict(
                sorted(Counter(str(entity.entity_type) for entity in self.entities).items())
            ),
            orphan_count=len(orphans),
            orphans=orphans[:limit],
            top_connected=sorted_degrees[:limit],
        )

    def export_csv(self, output_dir: str | Path) -> dict[str, str]:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        nodes_path = root / "nodes.csv"
        edges_path = root / "edges.csv"

        with nodes_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "id",
                    "label",
                    "entity_type",
                    "url",
                    "categories",
                    "source_count",
                ],
            )
            writer.writeheader()
            for entity in self.entities:
                writer.writerow(
                    {
                        "id": entity.id,
                        "label": entity.name,
                        "entity_type": str(entity.entity_type),
                        "url": str(entity.url) if entity.url else "",
                        "categories": "|".join(entity.categories),
                        "source_count": len(entity.sources),
                    }
                )

        with edges_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "id",
                    "source_id",
                    "source_label",
                    "relationship_type",
                    "target_id",
                    "target_label",
                    "confidence",
                    "evidence_count",
                ],
            )
            writer.writeheader()
            for relationship in self.relationships:
                source = self.entities_by_id.get(relationship.source_id)
                target = self.entities_by_id.get(relationship.target_id)
                writer.writerow(
                    {
                        "id": relationship.id,
                        "source_id": relationship.source_id,
                        "source_label": source.name if source else "",
                        "relationship_type": str(relationship.relationship_type),
                        "target_id": relationship.target_id,
                        "target_label": target.name if target else "",
                        "confidence": relationship.confidence,
                        "evidence_count": len(relationship.evidence),
                    }
                )

        return {"nodes": str(nodes_path), "edges": str(edges_path)}


def load_dataset(data_dir: str | Path = "data") -> DatasetIndex:
    root = Path(data_dir)
    entities_path = root / "entities.json"
    relationships_path = root / "relationships.json"
    manifest_path = root / "manifest.json"

    if not entities_path.exists():
        raise FileNotFoundError(f"missing entities file: {entities_path}")
    if not relationships_path.exists():
        raise FileNotFoundError(f"missing relationships file: {relationships_path}")

    entities = [
        Entity.model_validate(item)
        for item in json.loads(entities_path.read_text(encoding="utf-8"))
    ]
    relationships = [
        Relationship.model_validate(item)
        for item in json.loads(relationships_path.read_text(encoding="utf-8"))
    ]
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else None
    )
    return DatasetIndex(entities=entities, relationships=relationships, manifest=manifest)


def inverse_relationship_type(relationship_type: str) -> str:
    return INVERSE_RELATIONSHIP_TYPES.get(relationship_type, f"incoming_{relationship_type}")


def diff_datasets(before_dir: str | Path, after_dir: str | Path) -> DatasetDiff:
    before = load_dataset(before_dir)
    after = load_dataset(after_dir)
    before_entity_ids = set(before.entities_by_id)
    after_entity_ids = set(after.entities_by_id)
    before_relationships = {relationship.id: relationship for relationship in before.relationships}
    after_relationships = {relationship.id: relationship for relationship in after.relationships}

    added_entity_ids = after_entity_ids - before_entity_ids
    removed_entity_ids = before_entity_ids - after_entity_ids
    shared_entity_ids = before_entity_ids & after_entity_ids

    changed_entities = [
        change
        for entity_id in sorted(shared_entity_ids)
        if (change := _changed_entity(before.entities_by_id[entity_id], after.entities_by_id[entity_id]))
        is not None
    ]

    return DatasetDiff(
        before_summary=before.summary(),
        after_summary=after.summary(),
        added_entities=sorted(
            [after.entities_by_id[entity_id] for entity_id in added_entity_ids],
            key=lambda entity: (str(entity.entity_type), entity.name),
        ),
        removed_entities=sorted(
            [before.entities_by_id[entity_id] for entity_id in removed_entity_ids],
            key=lambda entity: (str(entity.entity_type), entity.name),
        ),
        changed_entities=changed_entities,
        added_relationships=sorted(
            [
                after_relationships[relationship_id]
                for relationship_id in set(after_relationships) - set(before_relationships)
            ],
            key=lambda relationship: relationship.id,
        ),
        removed_relationships=sorted(
            [
                before_relationships[relationship_id]
                for relationship_id in set(before_relationships) - set(after_relationships)
            ],
            key=lambda relationship: relationship.id,
        ),
    )


def _match_score(entity: Entity, normalized_query: str) -> float:
    if not normalized_query:
        return 0.0

    normalized_name = normalize_name(entity.name, entity_type=str(entity.entity_type))
    normalized_categories = {
        normalize_name(category)
        for category in entity.categories
        if category
    }
    provider_values = [
        str(entity.metadata.get(field, ""))
        for field in ["provider", "company", "developer", "owner", "publisher"]
        if entity.metadata.get(field)
    ]
    normalized_provider_text = normalize_name(" ".join(provider_values))
    normalized_source_text = normalize_name(" ".join(source.name for source in entity.sources))
    normalized_metadata_text = normalize_name(" ".join(_metadata_search_values(entity.metadata)))
    normalized_description = normalize_name(entity.description or "")
    fuzzy_name_score = fuzz.partial_ratio(normalized_query, normalized_name) / 100

    scores = [
        1.0 if normalized_query == normalized_name else 0.0,
        0.92 if normalized_name.startswith(normalized_query) else 0.0,
        0.84 if normalized_query in normalized_name else 0.0,
        0.78 if normalized_query in normalized_categories else 0.0,
        0.74 if normalized_provider_text and normalized_query == normalized_provider_text else 0.0,
        0.68 if normalized_provider_text and normalized_query in normalized_provider_text else 0.0,
        min(0.66, fuzzy_name_score)
        if normalized_name and fuzzy_name_score >= 0.75
        else 0.0,
        0.58 if normalized_query in normalized_source_text else 0.0,
        0.52 if normalized_query in normalized_description else 0.0,
        0.48 if normalized_query in normalized_metadata_text else 0.0,
    ]
    return max(scores)


def _metadata_search_values(metadata: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in metadata.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif isinstance(value, dict):
            values.extend(_metadata_search_values(value))
        elif value is not None:
            values.append(str(value))
    return values


def _changed_entity(before: Entity, after: Entity) -> ChangedEntity | None:
    changed_fields: list[str] = []
    for field in ["name", "description", "url", "categories", "sources", "metadata"]:
        if getattr(before, field) != getattr(after, field):
            changed_fields.append(field)
    if not changed_fields:
        return None
    return ChangedEntity(
        id=after.id,
        before_name=before.name,
        after_name=after.name,
        changed_fields=changed_fields,
    )
