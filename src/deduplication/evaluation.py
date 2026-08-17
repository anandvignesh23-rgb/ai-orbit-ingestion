from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from src.deduplication.scoring import DuplicateScore, score_duplicate
from src.models import Entity, EntityType, SourceReference
from src.utils.ids import generate_entity_id

DuplicateLabel = Literal["duplicate", "distinct"]


class LabeledPairResult(BaseModel):
    label: DuplicateLabel
    predicted_duplicate: bool
    score: DuplicateScore
    left_name: str
    right_name: str


class DeduplicationEvaluationReport(BaseModel):
    total_pairs: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    accuracy: float
    results: list[LabeledPairResult]


def evaluate_labeled_pairs(
    path: str | Path = "config/deduplication_pairs.json",
) -> DeduplicationEvaluationReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    results: list[LabeledPairResult] = []

    for pair in payload:
        left = _entity_from_payload(pair["left"])
        right = _entity_from_payload(pair["right"])
        score = score_duplicate(left, right)
        predicted_duplicate = score.decision == "merge"
        results.append(
            LabeledPairResult(
                label=pair["label"],
                predicted_duplicate=predicted_duplicate,
                score=score,
                left_name=left.name,
                right_name=right.name,
            )
        )

    true_positives = sum(
        result.label == "duplicate" and result.predicted_duplicate for result in results
    )
    true_negatives = sum(
        result.label == "distinct" and not result.predicted_duplicate for result in results
    )
    false_positives = sum(
        result.label == "distinct" and result.predicted_duplicate for result in results
    )
    false_negatives = sum(
        result.label == "duplicate" and not result.predicted_duplicate for result in results
    )
    precision = _safe_divide(true_positives, true_positives + false_positives)
    recall = _safe_divide(true_positives, true_positives + false_negatives)
    accuracy = _safe_divide(true_positives + true_negatives, len(results))

    return DeduplicationEvaluationReport(
        total_pairs=len(results),
        true_positives=true_positives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=round(precision, 3),
        recall=round(recall, 3),
        accuracy=round(accuracy, 3),
        results=results,
    )


def _entity_from_payload(payload: dict[str, Any]) -> Entity:
    entity_type = EntityType(payload["entity_type"])
    name = payload["name"]
    url = payload.get("url")
    return Entity(
        id=generate_entity_id(str(entity_type), url or name),
        entity_type=entity_type,
        name=name,
        url=url,
        categories=payload.get("categories", []),
        sources=[
            SourceReference(
                name="Labeled duplicate fixture",
                url=url or "https://example.com/labeled-duplicate-fixture",
            )
        ],
        metadata=payload.get("metadata", {}),
    )


def _safe_divide(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
