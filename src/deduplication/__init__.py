from src.deduplication.merger import merge_entities
from src.deduplication.evaluation import (
    DeduplicationEvaluationReport,
    LabeledPairResult,
    evaluate_labeled_pairs,
)
from src.deduplication.resolver import DeduplicationResult, EntityResolver
from src.deduplication.scoring import (
    AUTO_MERGE_THRESHOLD,
    REVIEW_THRESHOLD,
    DuplicateScore,
    score_duplicate,
)

__all__ = [
    "AUTO_MERGE_THRESHOLD",
    "DeduplicationEvaluationReport",
    "DeduplicationResult",
    "DuplicateScore",
    "EntityResolver",
    "LabeledPairResult",
    "REVIEW_THRESHOLD",
    "evaluate_labeled_pairs",
    "merge_entities",
    "score_duplicate",
]
