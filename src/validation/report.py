from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ValidationSummary(BaseModel):
    raw_records: int = 0
    canonical_entities: int = 0
    relationships: int = 0
    duplicates_merged: int = 0
    possible_duplicates: int = 0
    critical_errors: int = 0


class RelationshipMetrics(BaseModel):
    total_relationships: int = 0
    average_relationships_per_entity: float = 0.0
    entities_without_relationships: int = 0


class ProductQualityMetrics(BaseModel):
    recently_added_entities: int = 0
    average_completeness_score: float = 0.0


class ValidationReport(BaseModel):
    summary: ValidationSummary
    entity_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
    relationship_counts: dict[str, int] = Field(default_factory=dict)
    relationship_metrics: RelationshipMetrics = Field(default_factory=RelationshipMetrics)
    product_quality_metrics: ProductQualityMetrics = Field(default_factory=ProductQualityMetrics)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duplicate_candidates: list[dict[str, Any]] = Field(default_factory=list)
    relationship_errors: list[str] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors and not self.relationship_errors
