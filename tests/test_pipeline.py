from __future__ import annotations

import json
import subprocess
import sys

from src.pipeline import IngestionPipeline


def test_pipeline_run_exports_valid_dataset(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)

    success = pipeline.run()

    assert success is True
    assert (tmp_path / "entities.json").exists()
    assert (tmp_path / "relationships.json").exists()
    assert (tmp_path / "product_catalog.json").exists()
    assert (tmp_path / "relationship_views.json").exists()
    assert (tmp_path / "validation_report.json").exists()
    assert (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "raw" / "source_records.json").exists()

    entities = json.loads((tmp_path / "entities.json").read_text(encoding="utf-8"))
    relationships = json.loads(
        (tmp_path / "relationships.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (tmp_path / "validation_report.json").read_text(encoding="utf-8")
    )
    product_catalog = json.loads((tmp_path / "product_catalog.json").read_text(encoding="utf-8"))
    relationship_views = json.loads((tmp_path / "relationship_views.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert len(entities) == 283
    assert len(relationships) == 610
    assert len(product_catalog) == 283
    assert len(relationship_views) == 1220
    assert {"provider", "related_entity_ids", "search_text", "completeness_score"} <= set(product_catalog[0])
    assert {"view_id", "canonical_relationship_type", "direction", "derived"} <= set(relationship_views[0])
    assert report["summary"]["critical_errors"] == 0
    assert report["relationship_metrics"]["total_relationships"] == 610
    assert report["relationship_metrics"]["average_relationships_per_entity"] > 0
    assert report["product_quality_metrics"]["average_completeness_score"] > 0
    assert manifest["schema_version"] == "1.0"
    assert manifest["run_mode"] == "deterministic"
    assert manifest["success"] is True
    assert manifest["summary"]["canonical_entities"] == 283
    assert manifest["summary"]["relationships"] == 610
    assert "entities.json" in manifest["files"]
    assert "product_catalog.json" in manifest["files"]
    assert "relationship_views.json" in manifest["files"]
    assert "raw/source_records.json" not in manifest["files"]


def test_pipeline_stage_methods_are_separable(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)

    raw_records = pipeline.discover()
    extracted = pipeline.extract()
    cleaned = pipeline.clean()
    normalized = pipeline.normalize()
    deduplicated = pipeline.deduplicate()
    classified = pipeline.classify()
    relationships = pipeline.map_relationships()
    success = pipeline.validate()
    pipeline.export()

    assert raw_records
    assert extracted == raw_records
    assert cleaned == raw_records
    assert normalized == raw_records
    assert deduplicated == raw_records
    assert classified == raw_records
    assert relationships
    assert success is True


def test_pipeline_run_configured_exports_relaxed_dataset(tmp_path) -> None:
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
        f"curated:\n  enabled: true\n  seed_dir: {seed_dir}\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "configured-output"
    pipeline = IngestionPipeline(data_dir=data_dir)

    success = pipeline.run_configured(config_path=config)

    assert success is True
    report = json.loads((data_dir / "validation_report.json").read_text(encoding="utf-8"))
    raw_records = json.loads(
        (data_dir / "raw" / "source_records.json").read_text(encoding="utf-8")
    )
    source_results = json.loads(
        (data_dir / "raw" / "source_results.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    assert report["summary"]["canonical_entities"] == 1
    assert report["summary"]["critical_errors"] == 0
    assert report["warnings"]
    assert raw_records[0]["source_name"] == "curated"
    assert source_results == [
        {"source_name": "curated", "status": "ok", "records": 1, "error": None}
    ]
    assert manifest["run_mode"] == "configured"
    assert manifest["source_runs"] == source_results
    assert "raw/source_records.json" in manifest["files"]
    assert "raw/source_results.json" in manifest["files"]


def test_run_py_supports_configured_mode(tmp_path) -> None:
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    (seed_dir / "tasks.json").write_text(
        json.dumps([{"name": "Summarization", "url": "https://example.com/task"}]),
        encoding="utf-8",
    )
    config = tmp_path / "sources.yaml"
    config.write_text(
        f"curated:\n  enabled: true\n  seed_dir: {seed_dir}\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "cli-output"

    result = subprocess.run(
        [
            sys.executable,
            "run.py",
            "--mode",
            "configured",
            "--config",
            str(config),
            "--data-dir",
            str(data_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Configured pipeline completed successfully." in result.stdout
    assert (data_dir / "entities.json").exists()
    assert (data_dir / "product_catalog.json").exists()
    assert (data_dir / "relationship_views.json").exists()
    assert (data_dir / "manifest.json").exists()
    assert (data_dir / "raw" / "source_records.json").exists()
