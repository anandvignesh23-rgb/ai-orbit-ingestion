from __future__ import annotations

import json
import subprocess
import sys

from src.pipeline import IngestionPipeline
from src.schema import build_schema_bundle, export_schema_bundle, validate_dataset_contract


def test_build_schema_bundle_contains_public_export_models() -> None:
    bundle = build_schema_bundle()

    assert set(bundle) == {
        "entity",
        "relationship",
        "product_catalog",
        "relationship_view",
        "validation_report",
        "manifest",
    }
    assert bundle["entity"]["title"] == "Entity"
    assert bundle["relationship"]["title"] == "Relationship"
    assert "name" in bundle["entity"]["properties"]
    assert "relationship_type" in bundle["relationship"]["properties"]
    assert "search_text" in bundle["product_catalog"]["properties"]
    assert "canonical_relationship_type" in bundle["relationship_view"]["properties"]
    assert "schema_version" in bundle["manifest"]["properties"]


def test_export_schema_bundle_writes_schema_files(tmp_path) -> None:
    exported = export_schema_bundle(tmp_path)

    assert exported == {
        "entity": str(tmp_path / "entity.schema.json"),
        "relationship": str(tmp_path / "relationship.schema.json"),
        "product_catalog": str(tmp_path / "product_catalog.schema.json"),
        "relationship_view": str(tmp_path / "relationship_view.schema.json"),
        "validation_report": str(tmp_path / "validation_report.schema.json"),
        "manifest": str(tmp_path / "manifest.schema.json"),
    }
    for path in exported.values():
        schema = json.loads(open(path, encoding="utf-8").read())
        assert schema["type"] == "object"


def test_query_dataset_cli_exports_schema_bundle(tmp_path) -> None:
    output_dir = tmp_path / "schemas"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "export-schema",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["entity"] == str(output_dir / "entity.schema.json")
    assert payload["manifest"] == str(output_dir / "manifest.schema.json")
    assert payload["product_catalog"] == str(output_dir / "product_catalog.schema.json")
    assert payload["relationship_view"] == str(output_dir / "relationship_view.schema.json")
    assert (output_dir / "relationship.schema.json").exists()


def test_validate_dataset_contract_accepts_pipeline_export(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True

    result = validate_dataset_contract(tmp_path)

    assert result.success is True
    assert result.errors == []
    assert {artifact.artifact for artifact in result.artifacts} == {
        "entities",
        "relationships",
        "product_catalog",
        "relationship_views",
        "validation_report",
        "manifest",
    }
    assert next(artifact for artifact in result.artifacts if artifact.artifact == "entities").records == 283


def test_validate_dataset_contract_reports_invalid_artifact(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True
    (tmp_path / "entities.json").write_text(
        json.dumps([{"id": "", "entity_type": "tool", "name": ""}]),
        encoding="utf-8",
    )

    result = validate_dataset_contract(tmp_path)

    assert result.success is False
    assert any("entities[0]" in error for error in result.errors)


def test_query_dataset_cli_validates_contract(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "validate-contract",
            "--data-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["errors"] == []
