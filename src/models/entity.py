from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from src.models.enums import EntityType


class SourceReference(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    url: HttpUrl
    source_type: str | None = None
    retrieved_at: datetime | None = None
    is_official: bool = False


class DisplayMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    logo_url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    short_description: str | None = None
    provider_name: str | None = None
    recently_added: bool = False


class PipelineMetadata(BaseModel):
    discovered_at: datetime | None = None
    normalized_at: datetime | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    source_count: int = Field(default=1, ge=0)
    duplicate_status: str | None = None
    duplicate_score: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_review: bool = False
    conflicts: list[str] = Field(default_factory=list)


class Entity(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    id: str = Field(min_length=1)
    entity_type: EntityType
    name: str = Field(min_length=1)
    description: str | None = None
    url: HttpUrl | None = None
    categories: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    display: DisplayMetadata | None = None
    pipeline_metadata: PipelineMetadata | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value

    @field_validator("categories")
    @classmethod
    def categories_must_be_normalized(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            category = value.strip()
            if not category:
                continue
            if category != category.lower():
                raise ValueError("categories must be lowercase canonical values")
            normalized.append(category)
        return normalized
