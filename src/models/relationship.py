from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from src.models.enums import RelationshipType


class Evidence(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_name: str = Field(min_length=1)
    source_url: HttpUrl
    note: str | None = None


class Relationship(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    relationship_type: RelationshipType
    target_id: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)

    @field_validator("target_id")
    @classmethod
    def relationship_cannot_target_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("target_id must not be blank")
        return value
