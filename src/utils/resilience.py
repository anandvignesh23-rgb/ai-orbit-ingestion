from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from src.sources.base import BaseSource, RawRecord

LOGGER = logging.getLogger("pipeline.resilience")


@dataclass(frozen=True)
class SourceRunResult:
    source_name: str
    records: list[RawRecord]
    status: str
    error: str | None = None


def discover_sources(sources: Iterable[BaseSource]) -> list[SourceRunResult]:
    results: list[SourceRunResult] = []
    for source in sources:
        try:
            records = source.discover()
        except Exception as exc:
            LOGGER.exception("source_failed source=%s", source.source_name)
            results.append(
                SourceRunResult(
                    source_name=source.source_name,
                    records=[],
                    status="failed",
                    error=type(exc).__name__,
                )
            )
            continue

        results.append(
            SourceRunResult(
                source_name=source.source_name,
                records=records,
                status="ok",
            )
        )
        LOGGER.info("source_complete source=%s records=%s", source.source_name, len(records))
    return results
