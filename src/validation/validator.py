from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from src.config import product_config
from src.deduplication.scoring import DuplicateScore, score_duplicate
from src.models.entity import Entity
from src.models.enums import EntityType, RelationshipType
from src.models.relationship import Relationship
from src.normalization.urls import normalize_url
from src.validation.report import ProductQualityMetrics, RelationshipMetrics, ValidationReport, ValidationSummary


class DatasetValidator:
    def __init__(
        self,
        *,
        relaxed: bool = True,
        min_entities: int = 250,
        max_entities: int = 300,
    ) -> None:
        self.relaxed = relaxed
        self.min_entities = min_entities
        self.max_entities = max_entities

    def validate(
        self,
        entities: list[Entity],
        relationships: list[Relationship | Any],
        *,
        raw_records: int = 0,
        duplicates_merged: int = 0,
        possible_duplicates: list[DuplicateScore] | None = None,
    ) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        relationship_errors: list[str] = []
        duplicate_candidates = [
            candidate.model_dump() for candidate in possible_duplicates or []
        ]

        self._validate_dataset_size(entities, errors, warnings)
        self._validate_entities(entities, errors, warnings)
        self._validate_duplicate_ids(entities, errors)
        self._validate_duplicate_urls(entities, warnings)
        duplicate_candidates.extend(self._find_high_confidence_duplicates(entities))
        self._validate_relationships(relationships, {entity.id for entity in entities}, relationship_errors)
        self._validate_product_quality(entities, relationships, warnings)
        self._validate_coverage(entities, warnings)

        entity_counts = dict(Counter(str(entity.entity_type) for entity in entities))
        category_counts = _category_counts(entities)
        source_counts = _source_counts(entities)
        relationship_counts = dict(Counter(str(relationship.relationship_type) for relationship in relationships))
        relationship_metrics = _relationship_metrics(entities, relationships)
        product_quality_metrics = _product_quality_metrics(entities, relationships)
        summary = ValidationSummary(
            raw_records=raw_records,
            canonical_entities=len(entities),
            relationships=len(relationships),
            duplicates_merged=duplicates_merged,
            possible_duplicates=len(duplicate_candidates),
            critical_errors=len(errors) + len(relationship_errors),
        )
        return ValidationReport(
            summary=summary,
            entity_counts=entity_counts,
            category_counts=category_counts,
            source_counts=source_counts,
            relationship_counts=relationship_counts,
            relationship_metrics=relationship_metrics,
            product_quality_metrics=product_quality_metrics,
            errors=errors,
            warnings=warnings,
            duplicate_candidates=duplicate_candidates,
            relationship_errors=relationship_errors,
        )

    def _validate_dataset_size(
        self,
        entities: list[Entity],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        count = len(entities)
        if self.min_entities <= count <= self.max_entities:
            return
        message = (
            f"entity count {count} is outside expected range "
            f"{self.min_entities}-{self.max_entities}"
        )
        if self.relaxed:
            warnings.append(message)
        else:
            errors.append(message)

    def _validate_entities(
        self,
        entities: list[Entity],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        for entity in entities:
            try:
                EntityType(str(entity.entity_type))
            except ValueError:
                errors.append(f"invalid entity type for entity {entity.id}")
            if not entity.name.strip():
                errors.append(f"entity {entity.id} has blank name")
            if entity.url and not normalize_url(str(entity.url)):
                errors.append(f"entity {entity.id} has invalid URL")
            if not entity.sources:
                errors.append(f"entity {entity.id} has no provenance sources")
            for category in entity.categories:
                if category != category.lower() or " " in category:
                    errors.append(f"entity {entity.id} has non-normalized category {category}")
            self._validate_specialized_metadata(entity, warnings)

    def _validate_specialized_metadata(self, entity: Entity, warnings: list[str]) -> None:
        entity_type = EntityType(str(entity.entity_type))
        if entity_type == EntityType.REPOSITORY:
            for field in ["owner", "primary_language"]:
                if not entity.metadata.get(field):
                    warnings.append(f"repository {entity.id} is missing metadata field {field}")
        elif entity_type == EntityType.MODEL:
            for field in ["provider", "pipeline_task"]:
                if not entity.metadata.get(field):
                    warnings.append(f"model {entity.id} is missing metadata field {field}")
        elif entity_type == EntityType.COMPANY and not (
            entity.metadata.get("official_domain") or entity.url
        ):
            warnings.append(f"company {entity.id} is missing official domain metadata")

    def _validate_product_quality(
        self,
        entities: list[Entity],
        relationships: list[Relationship | Any],
        warnings: list[str],
    ) -> None:
        connected_ids = {
            entity_id
            for relationship in relationships
            for entity_id in [str(getattr(relationship, "source_id", "")), str(getattr(relationship, "target_id", ""))]
            if entity_id
        }
        for entity in entities:
            entity_type = EntityType(str(entity.entity_type))
            if not entity.description:
                warnings.append(f"entity {entity.id} may display poorly: missing description")
            elif len(entity.description) < 20:
                warnings.append(f"entity {entity.id} may display poorly: description too short")
            if not entity.url:
                warnings.append(f"entity {entity.id} may display poorly: missing URL")
            if not entity.categories:
                warnings.append(f"entity {entity.id} may display poorly: missing categories")
            if entity_type in {EntityType.TOOL, EntityType.MODEL} and not entity.metadata.get("provider"):
                warnings.append(f"{entity_type} {entity.id} may display poorly: missing provider")
            if entity.id not in connected_ids:
                warnings.append(f"entity {entity.id} has no relationships")

    def _validate_coverage(self, entities: list[Entity], warnings: list[str]) -> None:
        coverage = product_config().get("coverage", {})
        if not isinstance(coverage, dict):
            return
        counts = Counter(str(entity.entity_type) for entity in entities)
        for entity_type, minimum in coverage.items():
            try:
                minimum_count = int(minimum)
            except (TypeError, ValueError):
                continue
            actual = counts.get(str(entity_type), 0)
            if actual < minimum_count:
                warnings.append(
                    f"coverage warning: {entity_type} has {actual} records, expected at least {minimum_count}"
                )

    def _validate_duplicate_ids(self, entities: list[Entity], errors: list[str]) -> None:
        counts = Counter(entity.id for entity in entities)
        for entity_id, count in counts.items():
            if count > 1:
                errors.append(f"duplicate entity id {entity_id}")

    def _validate_duplicate_urls(self, entities: list[Entity], warnings: list[str]) -> None:
        by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
        for entity in entities:
            if not entity.url:
                continue
            by_key[(str(entity.entity_type), normalize_url(str(entity.url)))].append(entity.id)
        for (entity_type, url), ids in by_key.items():
            if url and len(ids) > 1:
                warnings.append(f"duplicate canonical URL for {entity_type}: {url}")

    def _find_high_confidence_duplicates(self, entities: list[Entity]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for index, entity in enumerate(entities):
            for other in entities[index + 1 :]:
                score = score_duplicate(entity, other)
                if score.decision in {"merge", "review"}:
                    payload = score.model_dump()
                    payload["entity_ids"] = [entity.id, other.id]
                    candidates.append(payload)
        return candidates

    def _validate_relationships(
        self,
        relationships: list[Relationship | Any],
        entity_ids: set[str],
        relationship_errors: list[str],
    ) -> None:
        seen_edges: set[tuple[str, str, str]] = set()
        for relationship in relationships:
            source_id = str(getattr(relationship, "source_id", ""))
            target_id = str(getattr(relationship, "target_id", ""))
            relationship_type = str(getattr(relationship, "relationship_type", ""))
            relationship_id = str(getattr(relationship, "id", ""))

            if source_id not in entity_ids:
                relationship_errors.append(f"relationship {relationship_id} has missing source {source_id}")
            if target_id not in entity_ids:
                relationship_errors.append(f"relationship {relationship_id} has missing target {target_id}")
            try:
                RelationshipType(relationship_type)
            except ValueError:
                relationship_errors.append(
                    f"relationship {relationship_id} has invalid type {relationship_type}"
                )
            if source_id and source_id == target_id:
                relationship_errors.append(f"relationship {relationship_id} is a self-relation")

            edge = (source_id, relationship_type, target_id)
            if edge in seen_edges:
                relationship_errors.append(
                    f"duplicate relationship edge {source_id}|{relationship_type}|{target_id}"
                )
            seen_edges.add(edge)


def _source_counts(entities: list[Entity]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entity in entities:
        for source in entity.sources:
            counts[source.name] += 1
    return dict(counts)


def _category_counts(entities: list[Entity]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entity in entities:
        counts.update(entity.categories)
    return dict(counts)


def _relationship_metrics(
    entities: list[Entity],
    relationships: list[Relationship | Any],
) -> RelationshipMetrics:
    connected_ids = {
        entity_id
        for relationship in relationships
        for entity_id in [str(getattr(relationship, "source_id", "")), str(getattr(relationship, "target_id", ""))]
        if entity_id
    }
    total = len(relationships)
    entity_count = len(entities)
    return RelationshipMetrics(
        total_relationships=total,
        average_relationships_per_entity=round(total / entity_count, 3) if entity_count else 0.0,
        entities_without_relationships=sum(1 for entity in entities if entity.id not in connected_ids),
    )


def _product_quality_metrics(
    entities: list[Entity],
    relationships: list[Relationship | Any],
) -> ProductQualityMetrics:
    connected_ids = {
        entity_id
        for relationship in relationships
        for entity_id in [str(getattr(relationship, "source_id", "")), str(getattr(relationship, "target_id", ""))]
        if entity_id
    }
    scores = [_completeness_score(entity, entity.id in connected_ids) for entity in entities]
    return ProductQualityMetrics(
        recently_added_entities=sum(
            1 for entity in entities if entity.display and entity.display.recently_added
        ),
        average_completeness_score=round(sum(scores) / len(scores), 3) if scores else 0.0,
    )


def _completeness_score(entity: Entity, has_relationships: bool) -> float:
    provider = entity.metadata.get("provider") or entity.metadata.get("company") or entity.metadata.get("developer")
    checks = [
        True,
        bool(entity.description),
        bool(entity.url),
        bool(entity.categories),
        bool(provider),
        bool(entity.sources),
        bool(entity.display and (entity.display.logo_url or entity.display.image_url or entity.display.short_description)),
        has_relationships,
    ]
    return sum(1 for check in checks if check) / len(checks)
