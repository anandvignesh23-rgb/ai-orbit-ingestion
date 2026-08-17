from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.models.enums import EntityType
from src.sources.base import BaseSource, RawRecord, SourceError

LOGGER = logging.getLogger("source.curated")

SEED_TYPE_BY_FILE = {
    "collections.json": EntityType.COLLECTION,
    "companies.json": EntityType.COMPANY,
    "creative.json": EntityType.CREATIVE,
    "devices.json": EntityType.DEVICE,
    "mcp.json": EntityType.MCP,
    "personal.json": EntityType.PERSONAL,
    "robots.json": EntityType.ROBOT,
    "tasks.json": EntityType.TASK,
    "tools.json": EntityType.TOOL,
}


class CuratedSource(BaseSource):
    def __init__(self, seed_dir: str | Path = "config/seeds") -> None:
        self.seed_dir = Path(seed_dir)

    @property
    def source_name(self) -> str:
        return "curated"

    def discover(self) -> list[RawRecord]:
        records: list[RawRecord] = []
        try:
            for path in sorted(self.seed_dir.glob("*.json")):
                inferred_type = SEED_TYPE_BY_FILE.get(path.name)
                raw_items = self._load_seed_file(path)
                for index, item in enumerate(raw_items):
                    record = self._record_from_item(
                        item,
                        path=path,
                        index=index,
                        inferred_type=inferred_type,
                    )
                    if record is not None:
                        records.append(record)
        except SourceError:
            LOGGER.exception("curated_discovery_failed")
            return []

        LOGGER.info("discovered=%s", len(records))
        return records

    def extract(self, candidate: RawRecord) -> RawRecord:
        return candidate

    def _load_seed_file(self, path: Path) -> list[Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SourceError(f"curated_seed_unreadable path={path}") from exc
        except json.JSONDecodeError as exc:
            raise SourceError(f"curated_seed_malformed_json path={path}") from exc
        if not isinstance(data, list):
            raise SourceError(f"curated_seed_expected_list path={path}")
        return data

    def _record_from_item(
        self,
        item: Any,
        *,
        path: Path,
        index: int,
        inferred_type: EntityType | None,
    ) -> RawRecord | None:
        if not isinstance(item, dict):
            LOGGER.warning("malformed_curated_record path=%s index=%s", path, index)
            return None

        name = _clean_required_text(item.get("name"))
        if not name:
            LOGGER.warning("curated_record_missing_name path=%s index=%s", path, index)
            return None

        entity_type = _entity_type_from_item(item, inferred_type)
        if entity_type is None:
            LOGGER.warning("curated_record_missing_type path=%s index=%s", path, index)
            return None

        url = _clean_optional_text(item.get("url") or item.get("official_url"))
        sources = _sources_from_item(item, fallback_url=url)
        if not sources:
            LOGGER.warning("curated_record_missing_provenance path=%s index=%s", path, index)
            return None

        payload = dict(item)
        payload["name"] = name
        payload["entity_type"] = str(entity_type)
        payload["url"] = url
        payload["sources"] = sources
        payload["seed_file"] = path.name

        return RawRecord(
            source_name=self.source_name,
            source_url=url or sources[0].get("url"),
            record_type=str(entity_type),
            payload=payload,
        )


def _entity_type_from_item(
    item: dict[str, Any],
    inferred_type: EntityType | None,
) -> EntityType | None:
    raw_type = item.get("entity_type") or item.get("type")
    if raw_type:
        try:
            return EntityType(str(raw_type).strip().lower())
        except ValueError:
            return None
    return inferred_type


def _sources_from_item(
    item: dict[str, Any],
    *,
    fallback_url: str | None,
) -> list[dict[str, Any]]:
    raw_sources = item.get("sources")
    sources: list[dict[str, Any]] = []
    if isinstance(raw_sources, list):
        for source in raw_sources:
            if not isinstance(source, dict):
                continue
            name = _clean_required_text(source.get("name"))
            url = _clean_required_text(source.get("url"))
            if name and url:
                sources.append(
                    {
                        "name": name,
                        "url": url,
                        "source_type": source.get("source_type") or _source_type_from_name(name),
                        "is_official": bool(source.get("is_official")) or "official" in name.casefold(),
                    }
                )

    if not sources and fallback_url:
        sources.append(
            {
                "name": "Official source",
                "url": fallback_url,
                "source_type": "official_site",
                "is_official": True,
            }
        )
    return sources


def _clean_required_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_optional_text(value: Any) -> str | None:
    return _clean_required_text(value)


def _source_type_from_name(name: str) -> str:
    lowered = name.casefold()
    if "official" in lowered:
        return "official_site"
    if "github" in lowered:
        return "github"
    if "hugging" in lowered:
        return "huggingface"
    return "curated"
