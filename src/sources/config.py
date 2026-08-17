from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.sources.base import BaseSource
from src.sources.curated import CuratedSource
from src.sources.github import GitHubSource
from src.sources.huggingface import HuggingFaceSource
from src.sources.rss import RSSSource
from src.sources.youtube import YouTubeSource


def load_source_config(config_path: str | Path = "config/sources.yaml") -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("source config must be a mapping")
    return data


def build_sources_from_config(
    config_path: str | Path = "config/sources.yaml",
) -> list[BaseSource]:
    config = load_source_config(config_path)
    sources: list[BaseSource] = []

    github = config.get("github", {})
    if _enabled(github):
        sources.append(
            GitHubSource(
                queries=github.get("queries") or None,
                per_page=int(github.get("per_page", 10)),
                max_pages=int(github.get("max_pages", 1)),
                timeout=float(github.get("timeout", 10.0)),
            )
        )

    huggingface = config.get("huggingface", {})
    if _enabled(huggingface):
        sources.append(
            HuggingFaceSource(
                tasks=huggingface.get("tasks") or huggingface.get("queries") or None,
                limit=int(huggingface.get("limit", 10)),
                timeout=float(huggingface.get("timeout", 10.0)),
            )
        )

    rss = config.get("rss", {})
    if _enabled(rss):
        sources.append(
            RSSSource(
                feeds=rss.get("feeds") or [],
                timeout=float(rss.get("timeout", 10.0)),
            )
        )

    youtube = config.get("youtube", {})
    if _enabled(youtube):
        sources.append(
            YouTubeSource(
                queries=youtube.get("queries") or None,
                max_results=int(youtube.get("max_results", 5)),
                timeout=float(youtube.get("timeout", 10.0)),
            )
        )

    curated = config.get("curated", {})
    if _enabled(curated):
        sources.append(CuratedSource(seed_dir=curated.get("seed_dir", "config/seeds")))

    return sources


def _enabled(section: Any) -> bool:
    return isinstance(section, dict) and bool(section.get("enabled", False))
