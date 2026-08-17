from __future__ import annotations

import json
from pathlib import Path

from src.pipeline import IngestionPipeline


def test_pipeline_discovers_configured_curated_entities(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    (seed_dir / "companies.json").write_text(
        json.dumps(
            [
                {
                    "name": "OpenAI",
                    "url": "https://openai.com",
                    "metadata": {"official_domain": "openai.com"},
                    "sources": [{"name": "Official site", "url": "https://openai.com"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    config = tmp_path / "sources.yaml"
    config.write_text(
        f"""
curated:
  enabled: true
  seed_dir: {seed_dir}
""",
        encoding="utf-8",
    )

    entities = IngestionPipeline(data_dir=tmp_path / "data").discover_configured_entities(config)

    assert len(entities) == 1
    assert entities[0].name == "OpenAI"
    assert entities[0].entity_type == "company"
    assert entities[0].metadata["official_domain"] == "openai.com"
