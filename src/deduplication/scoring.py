from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from src.models.entity import Entity
from src.models.enums import EntityType
from src.normalization.names import normalize_name
from src.normalization.urls import canonical_domain, normalize_url

AUTO_MERGE_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.75


class DuplicateScore(BaseModel):
    total_score: float = Field(ge=0.0, le=1.0)
    url_score: float = Field(ge=0.0, le=1.0)
    name_score: float = Field(ge=0.0, le=1.0)
    type_score: float = Field(ge=0.0, le=1.0)
    metadata_score: float = Field(ge=0.0, le=1.0)
    decision: str
    reasons: list[str] = Field(default_factory=list)


def score_duplicate(
    a: Entity,
    b: Entity,
    auto_merge_threshold: float = AUTO_MERGE_THRESHOLD,
    review_threshold: float = REVIEW_THRESHOLD,
) -> DuplicateScore:
    if a.entity_type != b.entity_type:
        return DuplicateScore(
            total_score=0.0,
            url_score=0.0,
            name_score=0.0,
            type_score=0.0,
            metadata_score=0.0,
            decision="keep",
            reasons=["Entity types are incompatible"],
        )

    reasons = ["Entity types match"]
    url_score = _url_score(a, b, reasons)
    name_score = _name_score(a, b, reasons)
    metadata_score = _metadata_score(a, b, reasons)
    type_score = 1.0
    total_score = round(
        (0.45 * url_score)
        + (0.35 * name_score)
        + (0.10 * type_score)
        + (0.10 * metadata_score),
        3,
    )

    decision = _decision(
        total_score,
        name_score,
        url_score,
        auto_merge_threshold,
        review_threshold,
    )
    return DuplicateScore(
        total_score=total_score,
        url_score=round(url_score, 3),
        name_score=round(name_score, 3),
        type_score=type_score,
        metadata_score=round(metadata_score, 3),
        decision=decision,
        reasons=reasons,
    )


def _decision(
    total_score: float,
    name_score: float,
    url_score: float,
    auto_merge_threshold: float,
    review_threshold: float,
) -> str:
    if name_score < review_threshold and url_score < 1.0:
        return "keep"
    if total_score >= auto_merge_threshold:
        return "merge"
    if total_score >= review_threshold:
        return "review"
    return "keep"


def _url_score(a: Entity, b: Entity, reasons: list[str]) -> float:
    a_url = normalize_url(str(a.url)) if a.url else ""
    b_url = normalize_url(str(b.url)) if b.url else ""

    if not a_url and not b_url:
        reasons.append("Both URLs are missing; using neutral URL score")
        return 0.85
    if not a_url or not b_url:
        reasons.append("One URL is missing; using neutral URL score")
        return 0.5

    if a.entity_type in {EntityType.REPOSITORY, EntityType.MCP}:
        if a_url == b_url:
            reasons.append("Repository-like URLs match exactly")
            return 1.0
        reasons.append("Repository-like URLs differ")
        return 0.0

    if canonical_domain(a_url) == canonical_domain(b_url):
        reasons.append("Canonical domains match")
        return 1.0

    reasons.append("Canonical domains differ")
    return 0.0


def _name_score(a: Entity, b: Entity, reasons: list[str]) -> float:
    entity_type = str(a.entity_type)
    a_name = normalize_name(a.name, entity_type=entity_type)
    b_name = normalize_name(b.name, entity_type=entity_type)
    ratio_score = fuzz.ratio(a_name, b_name) / 100.0
    token_sort_score = fuzz.token_sort_ratio(a_name, b_name) / 100.0
    score = max(ratio_score, token_sort_score)

    if a_name == b_name:
        reasons.append("Normalized names match exactly")
    elif score >= 0.9:
        reasons.append("Normalized names are highly similar")
    elif score >= 0.75:
        reasons.append("Normalized names are moderately similar")
    else:
        reasons.append("Normalized names differ")

    return score


def _metadata_score(a: Entity, b: Entity, reasons: list[str]) -> float:
    comparisons = _metadata_comparisons(a, b)
    if not comparisons:
        reasons.append("No comparable metadata; using neutral metadata score")
        return 0.75

    score = sum(comparisons) / len(comparisons)
    if score == 1.0:
        reasons.append("Comparable metadata agrees")
    elif score >= 0.5:
        reasons.append("Comparable metadata partially agrees")
    else:
        reasons.append("Comparable metadata conflicts")
    return score


def _metadata_comparisons(a: Entity, b: Entity) -> list[float]:
    entity_type = EntityType(str(a.entity_type))
    metadata_a = a.metadata
    metadata_b = b.metadata

    if entity_type == EntityType.COMPANY:
        return _compare_fields(
            metadata_a,
            metadata_b,
            ["official_domain", "headquarters", "industry_sector", "founding_year"],
        )
    if entity_type == EntityType.MODEL:
        return _compare_fields(
            metadata_a,
            metadata_b,
            ["provider", "model_family", "license"],
        )
    if entity_type == EntityType.REPOSITORY:
        scores = _compare_fields(metadata_a, metadata_b, ["owner", "primary_language"])
        scores.extend(_compare_repository_paths(a, b))
        return scores
    if entity_type == EntityType.TOOL:
        scores = _compare_fields(metadata_a, metadata_b, ["provider", "official_domain"])
        scores.extend(_compare_category_overlap(a.categories, b.categories))
        return scores

    return _compare_fields(metadata_a, metadata_b, ["provider", "official_domain"])


def _compare_fields(
    metadata_a: dict[str, Any],
    metadata_b: dict[str, Any],
    fields: list[str],
) -> list[float]:
    scores: list[float] = []
    for field in fields:
        value_a = _canonical_metadata_value(metadata_a.get(field))
        value_b = _canonical_metadata_value(metadata_b.get(field))
        if value_a is None or value_b is None:
            continue
        scores.append(1.0 if value_a == value_b else 0.0)
    return scores


def _compare_repository_paths(a: Entity, b: Entity) -> list[float]:
    a_url = normalize_url(str(a.url)) if a.url else ""
    b_url = normalize_url(str(b.url)) if b.url else ""
    if not a_url or not b_url:
        return []
    return [1.0 if a_url == b_url else 0.0]


def _compare_category_overlap(a_categories: list[str], b_categories: list[str]) -> list[float]:
    if not a_categories or not b_categories:
        return []
    a_set = set(a_categories)
    b_set = set(b_categories)
    overlap = len(a_set & b_set)
    union = len(a_set | b_set)
    return [overlap / union if union else 0.0]


def _canonical_metadata_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        return "|".join(sorted(str(item).strip().casefold() for item in value))
    normalized = str(value).strip().casefold()
    return normalized or None
