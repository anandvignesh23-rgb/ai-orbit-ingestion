from __future__ import annotations

from typing import Any

from src.config import source_priority_config
from src.models.entity import Entity, SourceReference
from src.normalization.names import normalize_name


def merge_entities(primary: Entity, duplicate: Entity) -> Entity:
    if primary.entity_type != duplicate.entity_type:
        raise ValueError("cannot merge entities with different types")

    sources = _merge_sources(primary.sources, duplicate.sources)
    metadata = _merge_metadata(primary, duplicate)
    pipeline_metadata = _merge_pipeline_metadata(primary, duplicate, len(sources), metadata)

    return Entity(
        id=primary.id,
        entity_type=primary.entity_type,
        name=_best_name(primary.name, duplicate.name),
        description=_best_description(primary.description, duplicate.description),
        url=primary.url or duplicate.url,
        categories=sorted(set(primary.categories) | set(duplicate.categories)),
        sources=sources,
        metadata=metadata,
        display=primary.display or duplicate.display,
        pipeline_metadata=pipeline_metadata,
    )


def _best_name(primary_name: str, duplicate_name: str) -> str:
    if normalize_name(primary_name) == normalize_name(duplicate_name):
        return primary_name if len(primary_name) <= len(duplicate_name) else duplicate_name
    if len(duplicate_name.strip()) > len(primary_name.strip()) and not _has_suffix_noise(
        duplicate_name
    ):
        return duplicate_name
    return primary_name


def _has_suffix_noise(name: str) -> bool:
    lowered = name.casefold()
    return any(suffix in lowered for suffix in [" inc", " llc", " ltd", " corp"])


def _best_description(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return b if len(b) > len(a) else a


def _merge_sources(
    primary_sources: list[SourceReference],
    duplicate_sources: list[SourceReference],
) -> list[SourceReference]:
    by_key: dict[tuple[str, str], SourceReference] = {}
    for source in [*primary_sources, *duplicate_sources]:
        key = (source.name.casefold(), str(source.url).rstrip("/"))
        by_key[key] = source
    return list(by_key.values())


def _merge_metadata(primary: Entity, duplicate: Entity) -> dict[str, Any]:
    merged = dict(primary.metadata)
    conflicts = list(primary.metadata.get("conflicts", []))
    primary_priority = _entity_source_priority(primary)
    duplicate_priority = _entity_source_priority(duplicate)

    for key, duplicate_value in duplicate.metadata.items():
        if key == "conflicts":
            conflicts.extend(duplicate_value if isinstance(duplicate_value, list) else [])
            continue
        if key not in merged or merged[key] in (None, "", []):
            merged[key] = duplicate_value
            continue
        if duplicate_value in (None, "", []) or merged[key] == duplicate_value:
            continue
        if isinstance(merged[key], list) and isinstance(duplicate_value, list):
            merged[key] = sorted(set(merged[key]) | set(duplicate_value))
            continue
        chosen = "primary"
        if duplicate_priority > primary_priority:
            merged[key] = duplicate_value
            chosen = "duplicate"
        conflicts.append(
            {
                "field": key,
                "primary": primary.metadata.get(key),
                "duplicate": duplicate_value,
                "chosen": chosen,
            }
        )

    if conflicts:
        merged["conflicts"] = conflicts
    return merged


def _merge_pipeline_metadata(
    primary: Entity,
    duplicate: Entity,
    source_count: int,
    metadata: dict[str, Any],
):
    pipeline_metadata = primary.pipeline_metadata or duplicate.pipeline_metadata
    if pipeline_metadata is None:
        return None
    merged = pipeline_metadata.model_copy(deep=True)
    duplicate_meta = duplicate.pipeline_metadata
    timestamps = [
        value
        for value in [
            getattr(primary.pipeline_metadata, "first_seen_at", None),
            getattr(duplicate_meta, "first_seen_at", None),
        ]
        if value is not None
    ]
    if timestamps:
        merged.first_seen_at = min(timestamps)
    last_seen = [
        value
        for value in [
            getattr(primary.pipeline_metadata, "last_seen_at", None),
            getattr(duplicate_meta, "last_seen_at", None),
        ]
        if value is not None
    ]
    if last_seen:
        merged.last_seen_at = max(last_seen)
    merged.source_count = source_count
    merged.conflicts = [str(item) for item in metadata.get("conflicts", [])]
    return merged


def _entity_source_priority(entity: Entity) -> int:
    priorities = source_priority_config()
    if not entity.sources:
        return priorities.get("unknown", 50)
    return max(_source_priority(source, priorities) for source in entity.sources)


def _source_priority(source: SourceReference, priorities: dict[str, int]) -> int:
    if source.is_official:
        return priorities.get("official_site", 100)
    if source.source_type and source.source_type in priorities:
        return priorities[source.source_type]
    return priorities.get("unknown", 50)
