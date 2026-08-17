from __future__ import annotations

from pathlib import Path

import pytest

from src.sources import (
    CuratedSource,
    GitHubSource,
    HuggingFaceSource,
    RSSSource,
    YouTubeSource,
    build_sources_from_config,
    load_source_config,
)


def test_load_source_config_returns_mapping(tmp_path: Path) -> None:
    config = tmp_path / "sources.yaml"
    config.write_text("github:\n  enabled: true\n", encoding="utf-8")

    assert load_source_config(config) == {"github": {"enabled": True}}


def test_load_source_config_rejects_non_mapping(tmp_path: Path) -> None:
    config = tmp_path / "sources.yaml"
    config.write_text("- nope\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_source_config(config)


def test_build_sources_from_config_instantiates_enabled_sources(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    config = tmp_path / "sources.yaml"
    config.write_text(
        f"""
github:
  enabled: true
  queries: ["topic:llm"]
  per_page: 2
  max_pages: 3
huggingface:
  enabled: true
  tasks: ["text-generation"]
  limit: 4
rss:
  enabled: true
  feeds:
    - name: Example
      url: https://example.com/feed.xml
youtube:
  enabled: true
  queries: ["AI agents"]
  max_results: 2
curated:
  enabled: true
  seed_dir: {seed_dir}
""",
        encoding="utf-8",
    )

    sources = build_sources_from_config(config)

    assert [type(source) for source in sources] == [
        GitHubSource,
        HuggingFaceSource,
        RSSSource,
        YouTubeSource,
        CuratedSource,
    ]
    assert sources[0].queries == ["topic:llm"]
    assert sources[0].per_page == 2
    assert sources[0].max_pages == 3
    assert sources[1].tasks == ["text-generation"]
    assert sources[1].limit == 4
    assert sources[2].feeds[0].name == "Example"
    assert sources[3].queries == ["AI agents"]
    assert sources[3].max_results == 2
    assert sources[4].seed_dir == seed_dir


def test_build_sources_from_config_skips_disabled_sources(tmp_path: Path) -> None:
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
github:
  enabled: false
curated:
  enabled: true
  seed_dir: config/seeds
""",
        encoding="utf-8",
    )

    sources = build_sources_from_config(config)

    assert len(sources) == 1
    assert isinstance(sources[0], CuratedSource)
