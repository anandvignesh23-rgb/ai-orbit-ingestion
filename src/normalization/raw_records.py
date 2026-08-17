from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.cleaning import clean_description
from src.config import product_config
from src.models import DisplayMetadata, Entity, EntityType, PipelineMetadata, SourceReference
from src.normalization.urls import normalize_url
from src.sources.base import RawRecord
from src.utils.ids import generate_entity_id


class RawRecordNormalizer:
    def normalize(self, record: RawRecord) -> Entity:
        record_type = EntityType(record.record_type)
        payload = record.payload

        if record_type == EntityType.REPOSITORY:
            return self._repository(record, payload)
        if record_type == EntityType.MODEL:
            return self._model(record, payload)
        if record_type == EntityType.NEWS:
            return self._news(record, payload)
        if record_type == EntityType.VIDEO:
            return self._video(record, payload)
        return self._generic(record, payload, record_type)

    def normalize_many(self, records: list[RawRecord]) -> list[Entity]:
        return [self.normalize(record) for record in records]

    def _repository(self, record: RawRecord, payload: dict[str, Any]) -> Entity:
        url = _first_text(payload.get("html_url"), record.source_url)
        name = _required_text(payload.get("name") or payload.get("full_name"))
        return self._entity(
            record,
            entity_type=EntityType.REPOSITORY,
            name=name,
            url=url,
            description=payload.get("description"),
            metadata={
                "owner": payload.get("owner"),
                "stars": payload.get("stars"),
                "primary_language": payload.get("primary_language"),
                "last_updated": payload.get("last_updated"),
                "topics": payload.get("topics") or [],
                "full_name": payload.get("full_name"),
            },
        )

    def _model(self, record: RawRecord, payload: dict[str, Any]) -> Entity:
        model_url = _first_text(payload.get("model_url"), record.source_url)
        name = _required_text(payload.get("name") or payload.get("model_id"))
        return self._entity(
            record,
            entity_type=EntityType.MODEL,
            name=name,
            url=model_url,
            description=payload.get("description"),
            metadata={
                "provider": payload.get("provider"),
                "license": payload.get("license"),
                "modalities": _modalities_from_pipeline_task(payload.get("pipeline_task")),
                "pipeline_task": payload.get("pipeline_task"),
                "downloads": payload.get("downloads"),
                "last_updated": payload.get("last_modified"),
                "tags": payload.get("tags") or [],
                "model_id": payload.get("model_id"),
            },
        )

    def _news(self, record: RawRecord, payload: dict[str, Any]) -> Entity:
        article_url = _first_text(payload.get("article_url"), record.source_url)
        return self._entity(
            record,
            entity_type=EntityType.NEWS,
            name=_required_text(payload.get("title")),
            url=article_url,
            description=payload.get("description"),
            metadata={
                "publisher": payload.get("publisher"),
                "published_at": payload.get("published_at"),
                "feed_name": payload.get("feed_name"),
                "feed_url": payload.get("feed_url"),
            },
        )

    def _video(self, record: RawRecord, payload: dict[str, Any]) -> Entity:
        video_url = _first_text(payload.get("video_url"), record.source_url)
        return self._entity(
            record,
            entity_type=EntityType.VIDEO,
            name=_required_text(payload.get("title")),
            url=video_url,
            description=payload.get("description"),
            metadata={
                "channel": payload.get("channel"),
                "channel_id": payload.get("channel_id"),
                "published_at": payload.get("published_at"),
                "video_id": payload.get("video_id"),
                "query": payload.get("query"),
            },
        )

    def _generic(
        self,
        record: RawRecord,
        payload: dict[str, Any],
        record_type: EntityType,
    ) -> Entity:
        url = _first_text(payload.get("url"), record.source_url)
        categories = [
            str(category).strip().lower()
            for category in payload.get("categories", [])
            if str(category).strip()
        ]
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return self._entity(
            record,
            entity_type=record_type,
            name=_required_text(payload.get("name")),
            url=url,
            description=payload.get("description"),
            categories=categories,
            metadata={**metadata, "seed_file": payload.get("seed_file")},
            sources_payload=payload.get("sources"),
        )

    def _entity(
        self,
        record: RawRecord,
        *,
        entity_type: EntityType,
        name: str,
        url: str | None,
        description: Any = None,
        categories: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        sources_payload: Any = None,
    ) -> Entity:
        normalized_url = normalize_url(url)
        canonical_key = normalized_url or f"{record.source_name}:{record.record_type}:{name}"
        now = datetime.now(UTC)
        cleaned_description = clean_description(description)
        clean_metadata = {key: value for key, value in (metadata or {}).items() if value is not None}
        sources = _sources(record, normalized_url, sources_payload, retrieved_at=now)
        return Entity(
            id=generate_entity_id(str(entity_type), canonical_key),
            entity_type=entity_type,
            name=name,
            description=cleaned_description,
            url=normalized_url or None,
            categories=categories or [],
            sources=sources,
            metadata=clean_metadata,
            display=_display_metadata(cleaned_description, clean_metadata, now),
            pipeline_metadata=PipelineMetadata(
                discovered_at=now,
                normalized_at=now,
                first_seen_at=now,
                last_seen_at=now,
                source_count=len(sources),
            ),
        )


def _sources(
    record: RawRecord,
    normalized_url: str,
    sources_payload: Any = None,
    *,
    retrieved_at: datetime | None = None,
) -> list[SourceReference]:
    sources: list[SourceReference] = []
    if isinstance(sources_payload, list):
        for source in sources_payload:
            if not isinstance(source, dict):
                continue
            name = _first_text(source.get("name"))
            url = normalize_url(source.get("url"))
            if name and url:
                sources.append(
                    SourceReference(
                        name=name,
                        url=url,
                        source_type=_source_type(source.get("source_type"), name, record.source_name),
                        retrieved_at=retrieved_at,
                        is_official=bool(source.get("is_official")) or _looks_official(name),
                    )
                )
    if sources:
        return sources

    source_url = normalized_url or normalize_url(record.source_url)
    if source_url:
        return [
            SourceReference(
                name=record.source_name,
                url=source_url,
                source_type=_source_type(None, record.source_name, record.source_name),
                retrieved_at=retrieved_at,
                is_official=_looks_official(record.source_name),
            )
        ]
    return []


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _required_text(value: Any) -> str:
    text = _first_text(value)
    if text is None:
        raise ValueError("raw record is missing required text field")
    return text


def _modalities_from_pipeline_task(task: Any) -> list[str]:
    normalized = str(task or "").lower()
    if "image" in normalized or "video" in normalized:
        return ["multimodal"]
    if "speech" in normalized or "audio" in normalized:
        return ["audio"]
    return ["text"]


def _display_metadata(
    description: str | None,
    metadata: dict[str, Any],
    discovered_at: datetime,
) -> DisplayMetadata:
    provider = _first_text(
        metadata.get("provider"),
        metadata.get("company"),
        metadata.get("developer"),
        metadata.get("publisher"),
    )
    return DisplayMetadata(
        short_description=_short_description(description),
        provider_name=provider,
        recently_added=_is_recently_added(discovered_at),
    )


def _short_description(description: str | None) -> str | None:
    if not description:
        return None
    return description if len(description) <= 160 else description[:157].rstrip() + "..."


def _is_recently_added(discovered_at: datetime) -> bool:
    days = int(product_config().get("freshness", {}).get("recently_added_days", 0) or 0)
    return days > 0 and (datetime.now(UTC) - discovered_at).days <= days


def _source_type(raw_value: Any, source_name: str, source_provider: str) -> str:
    if raw_value:
        return str(raw_value).strip().lower()
    lowered = f"{source_name} {source_provider}".casefold()
    if "github" in lowered:
        return "github"
    if "hugging" in lowered:
        return "huggingface"
    if "rss" in lowered or "feed" in lowered:
        return "rss"
    if "youtube" in lowered:
        return "youtube"
    if "official" in lowered:
        return "official_site"
    if "curated" in lowered:
        return "curated"
    return "unknown"


def _looks_official(source_name: str) -> bool:
    return "official" in source_name.casefold()
