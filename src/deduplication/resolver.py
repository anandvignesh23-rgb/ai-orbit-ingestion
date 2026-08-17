from __future__ import annotations

from pydantic import BaseModel, Field

from src.deduplication.merger import merge_entities
from src.deduplication.scoring import (
    AUTO_MERGE_THRESHOLD,
    REVIEW_THRESHOLD,
    DuplicateScore,
    score_duplicate,
)
from src.models.entity import Entity


class DeduplicationResult(BaseModel):
    entities: list[Entity]
    merged_count: int = 0
    possible_duplicates: list[DuplicateScore] = Field(default_factory=list)


class EntityResolver:
    def __init__(
        self,
        auto_merge_threshold: float = AUTO_MERGE_THRESHOLD,
        review_threshold: float = REVIEW_THRESHOLD,
    ) -> None:
        self.auto_merge_threshold = auto_merge_threshold
        self.review_threshold = review_threshold

    def resolve(self, entities: list[Entity]) -> DeduplicationResult:
        canonical: list[Entity] = []
        merged_count = 0
        possible_duplicates: list[DuplicateScore] = []

        for entity in entities:
            merged = False
            for index, existing in enumerate(canonical):
                score = score_duplicate(
                    existing,
                    entity,
                    auto_merge_threshold=self.auto_merge_threshold,
                    review_threshold=self.review_threshold,
                )
                if score.decision == "merge":
                    canonical[index] = merge_entities(existing, entity)
                    merged_count += 1
                    merged = True
                    break
                if score.decision == "review":
                    possible_duplicates.append(score)
            if not merged:
                canonical.append(entity)

        return DeduplicationResult(
            entities=canonical,
            merged_count=merged_count,
            possible_duplicates=possible_duplicates,
        )
