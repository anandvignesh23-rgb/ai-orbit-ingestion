from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RawRecord(BaseModel):
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    record_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class SourceError(Exception):
    """Raised when a source cannot complete discovery or extraction."""


class BaseSource(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def discover(self) -> list[RawRecord]:
        raise NotImplementedError

    @abstractmethod
    def extract(self, candidate: RawRecord) -> RawRecord:
        raise NotImplementedError
