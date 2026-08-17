from __future__ import annotations

import json
from pathlib import Path

from src.sources.curated import CuratedSource


def write_seed(seed_dir: Path, filename: str, records: list | str) -> Path:
    path = seed_dir / filename
    if isinstance(records, str):
        path.write_text(records, encoding="utf-8")
    else:
        path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_curated_discover_loads_seed_records_and_infers_type(tmp_path: Path) -> None:
    write_seed(
        tmp_path,
        "companies.json",
        [
            {
                "name": "OpenAI",
                "description": "AI research and product company.",
                "url": "https://openai.com",
                "categories": ["research"],
                "metadata": {"official_domain": "openai.com"},
                "sources": [{"name": "Official site", "url": "https://openai.com"}],
            }
        ],
    )

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert len(records) == 1
    record = records[0]
    assert record.source_name == "curated"
    assert record.record_type == "company"
    assert record.source_url == "https://openai.com"
    assert record.payload["name"] == "OpenAI"
    assert record.payload["entity_type"] == "company"
    assert record.payload["seed_file"] == "companies.json"
    assert record.payload["sources"] == [
        {
            "name": "Official site",
            "url": "https://openai.com",
            "source_type": "official_site",
            "is_official": True,
        }
    ]


def test_curated_discover_uses_explicit_type_for_general_seed_files(tmp_path: Path) -> None:
    write_seed(
        tmp_path,
        "personal_assistants.json",
        [
            {
                "name": "Pi",
                "entity_type": "personal",
                "url": "https://pi.ai",
            }
        ],
    )

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert len(records) == 1
    assert records[0].record_type == "personal"
    assert records[0].payload["sources"] == [
        {
            "name": "Official source",
            "url": "https://pi.ai",
            "source_type": "official_site",
            "is_official": True,
        }
    ]


def test_curated_discover_supports_creative_and_mcp_seed_records(tmp_path: Path) -> None:
    write_seed(
        tmp_path,
        "tools.json",
        [
            {
                "name": "Runway",
                "type": "creative",
                "url": "https://runwayml.com",
            },
            {
                "name": "GitHub MCP Server",
                "entity_type": "mcp",
                "url": "https://github.com/github/github-mcp-server",
            },
        ],
    )

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert [record.record_type for record in records] == ["creative", "mcp"]


def test_curated_discover_skips_malformed_missing_name_type_and_provenance(
    tmp_path: Path,
) -> None:
    write_seed(
        tmp_path,
        "unknown.json",
        [
            {"name": "No type", "url": "https://example.com/no-type"},
            {"entity_type": "tool", "url": "https://example.com/no-name"},
            {"name": "No provenance", "entity_type": "tool"},
            "not-a-dict",
            {"name": "Valid", "entity_type": "tool", "url": "https://example.com/valid"},
        ],
    )

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert len(records) == 1
    assert records[0].payload["name"] == "Valid"


def test_curated_discover_empty_project_seed_files_are_valid(tmp_path: Path) -> None:
    write_seed(tmp_path, "companies.json", [])

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert records == []


def test_curated_discover_bad_json_fails_gracefully(tmp_path: Path) -> None:
    write_seed(tmp_path, "companies.json", "{not-json")

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert records == []


def test_curated_discover_non_list_seed_fails_gracefully(tmp_path: Path) -> None:
    (tmp_path / "companies.json").write_text(
        json.dumps({"name": "OpenAI"}),
        encoding="utf-8",
    )

    records = CuratedSource(seed_dir=tmp_path).discover()

    assert records == []


def test_curated_extract_returns_candidate_without_global_processing(tmp_path: Path) -> None:
    write_seed(
        tmp_path,
        "tasks.json",
        [{"name": "Summarization", "url": "https://example.com/tasks/summarization"}],
    )
    source = CuratedSource(seed_dir=tmp_path)
    record = source.discover()[0]

    assert source.extract(record) is record


def test_project_curated_seed_files_are_populated_and_provenanced() -> None:
    records = CuratedSource(seed_dir="config/seeds").discover()

    assert len(records) >= 20
    assert {record.record_type for record in records} >= {
        "collection",
        "company",
        "device",
        "robot",
        "task",
        "tool",
    }
    for record in records:
        assert record.payload["sources"]
        assert record.source_url
