from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from src.pipeline import IngestionPipeline
from src.quality import QualityGateConfig
from src.release import build_release_bundle, verify_release_archive, verify_release_bundle


def test_build_release_bundle_packages_export_artifacts(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True

    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="test-release",
        quality_config=QualityGateConfig(
            min_entities=283,
            min_relationships=171,
            max_possible_duplicates=30,
        ),
    )
    bundle_dir = Path(result.bundle_dir)

    assert result.success is True
    assert bundle_dir.name == "test-release"
    assert (bundle_dir / "entities.json").exists()
    assert (bundle_dir / "relationships.json").exists()
    assert (bundle_dir / "product_catalog.json").exists()
    assert (bundle_dir / "relationship_views.json").exists()
    assert (bundle_dir / "schema" / "entity.schema.json").exists()
    assert (bundle_dir / "graph_csv" / "nodes.csv").exists()
    assert (bundle_dir / "graph_csv" / "edges.csv").exists()
    assert (bundle_dir / "quality_gate.json").exists()
    assert (bundle_dir / "RELEASE_NOTES.md").exists()
    assert (bundle_dir / "checksums.json").exists()
    assert (bundle_dir / "release_manifest.json").exists()
    release_notes = (bundle_dir / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    release_manifest = json.loads((bundle_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert "release_manifest.json" in result.files
    assert "RELEASE_NOTES.md" in result.files
    assert "checksums.json" in result.files
    assert "schema/manifest.schema.json" in result.files
    assert "product_catalog.json" in result.files
    assert "relationship_views.json" in result.files
    assert "# AI Orbit Release Bundle: test-release" in release_notes
    assert "Quality Checks" in release_notes
    assert "entities.json" in release_manifest["checksums"]
    assert "product_catalog.json" in release_manifest["checksums"]
    assert "relationship_views.json" in release_manifest["checksums"]
    assert "RELEASE_NOTES.md" in release_manifest["checksums"]
    assert "checksums.json" not in release_manifest["checksums"]


def test_verify_release_bundle_accepts_unchanged_bundle(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True
    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="verified-release",
        quality_config=QualityGateConfig(min_entities=283),
    )

    verification = verify_release_bundle(result.bundle_dir)

    assert verification.success is True
    assert verification.checked_files > 0
    assert verification.missing_files == []
    assert verification.changed_files == []


def test_verify_release_bundle_detects_modified_file(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True
    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="tampered-release",
        quality_config=QualityGateConfig(min_entities=283),
    )
    bundle_dir = Path(result.bundle_dir)
    (bundle_dir / "entities.json").write_text("[]\n", encoding="utf-8")

    verification = verify_release_bundle(bundle_dir)

    assert verification.success is False
    assert verification.changed_files == ["entities.json"]


def test_release_bundle_records_failed_quality_gate(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True

    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="failed-release",
        quality_config=QualityGateConfig(min_entities=999),
    )

    assert result.success is False
    quality_payload = json.loads((Path(result.bundle_dir) / "quality_gate.json").read_text(encoding="utf-8"))
    assert quality_payload["success"] is False


def test_build_release_bundle_can_create_zip_archive(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True

    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="archived-release",
        quality_config=QualityGateConfig(min_entities=283),
        create_archive=True,
    )

    assert result.archive_path == str(tmp_path / "releases" / "archived-release.zip")
    assert result.archive_sha256 is not None
    assert len(result.archive_sha256) == 64
    with zipfile.ZipFile(result.archive_path) as archive:
        names = set(archive.namelist())
    assert "archived-release/entities.json" in names
    assert "archived-release/RELEASE_NOTES.md" in names
    assert "archived-release/release_manifest.json" in names
    assert "archived-release/schema/entity.schema.json" in names


def test_verify_release_archive_accepts_zipped_bundle(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True

    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="archive-verified-release",
        quality_config=QualityGateConfig(min_entities=283),
        create_archive=True,
    )

    verification = verify_release_archive(result.archive_path)

    assert verification.success is True
    assert verification.bundle_dir == result.archive_path
    assert verification.checked_files > 0
    assert verification.missing_files == []
    assert verification.changed_files == []


def test_release_bundle_cli_packages_dataset(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "release-bundle",
            "--data-dir",
            str(data_dir),
            "--output-dir",
            str(tmp_path / "releases"),
            "--bundle-name",
            "cli-release",
            "--min-entities",
            "283",
            "--min-relationships",
            "171",
            "--max-possible-duplicates",
            "30",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    bundle_dir = Path(payload["bundle_dir"])
    assert payload["success"] is True
    assert bundle_dir.name == "cli-release"
    assert (bundle_dir / "release_manifest.json").exists()


def test_release_bundle_cli_can_create_zip_archive(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "release-bundle",
            "--data-dir",
            str(data_dir),
            "--output-dir",
            str(tmp_path / "releases"),
            "--bundle-name",
            "cli-archive-release",
            "--min-entities",
            "283",
            "--zip",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["archive_path"] == str(tmp_path / "releases" / "cli-archive-release.zip")
    assert len(payload["archive_sha256"]) == 64
    assert Path(payload["archive_path"]).exists()


def test_verify_release_bundle_cli_reports_success(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True
    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="cli-verified-release",
        quality_config=QualityGateConfig(min_entities=283),
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "verify-release-bundle",
            "--bundle-dir",
            result.bundle_dir,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["missing_files"] == []
    assert payload["changed_files"] == []


def test_verify_release_archive_cli_reports_success(tmp_path) -> None:
    data_dir = tmp_path / "data"
    pipeline = IngestionPipeline(data_dir=data_dir)
    assert pipeline.run() is True
    result = build_release_bundle(
        data_dir,
        tmp_path / "releases",
        bundle_name="cli-archive-verified-release",
        quality_config=QualityGateConfig(min_entities=283),
        create_archive=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "verify-release-archive",
            "--archive-path",
            result.archive_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["bundle_dir"] == result.archive_path
    assert payload["missing_files"] == []
    assert payload["changed_files"] == []
