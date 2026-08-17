from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, Field

from src.query import load_dataset
from src.quality import QualityGateConfig, QualityGateResult, run_quality_gate
from src.schema import export_schema_bundle


class ReleaseBundleResult(BaseModel):
    bundle_dir: str
    success: bool
    files: list[str] = Field(default_factory=list)
    quality_gate: QualityGateResult
    archive_path: str | None = None
    archive_sha256: str | None = None


class BundleVerificationResult(BaseModel):
    bundle_dir: str
    success: bool
    checked_files: int
    missing_files: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)


def build_release_bundle(
    data_dir: str | Path,
    output_dir: str | Path,
    *,
    quality_config: QualityGateConfig | None = None,
    bundle_name: str | None = None,
    create_archive: bool = False,
) -> ReleaseBundleResult:
    source_root = Path(data_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    name = bundle_name or f"ai-orbit-release-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    bundle_root = output_root / name
    bundle_root.mkdir(parents=True, exist_ok=True)

    files: list[str] = []
    files.extend(_copy_core_artifacts(source_root, bundle_root))
    schema_files = export_schema_bundle(bundle_root / "schema")
    files.extend(_relative_paths(bundle_root, schema_files.values()))
    csv_files = load_dataset(source_root).export_csv(bundle_root / "graph_csv")
    files.extend(_relative_paths(bundle_root, csv_files.values()))
    quality_gate = run_quality_gate(source_root, quality_config)
    quality_path = bundle_root / "quality_gate.json"
    quality_path.write_text(
        json.dumps(quality_gate.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    files.append(quality_path.relative_to(bundle_root).as_posix())
    notes_path = bundle_root / "RELEASE_NOTES.md"
    notes_path.write_text(
        _build_release_notes(
            bundle_name=name,
            source_data_dir=source_root,
            quality_gate=quality_gate,
            files=sorted(files),
        ),
        encoding="utf-8",
    )
    files.append(notes_path.relative_to(bundle_root).as_posix())
    checksums = _build_checksums(bundle_root, files)
    checksums_path = bundle_root / "checksums.json"
    checksums_path.write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    files.append(checksums_path.relative_to(bundle_root).as_posix())

    release_manifest = {
        "bundle_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "source_data_dir": str(source_root),
        "success": quality_gate.success,
        "files": sorted(files),
        "checksums": checksums,
    }
    manifest_path = bundle_root / "release_manifest.json"
    manifest_path.write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")
    files.append(manifest_path.relative_to(bundle_root).as_posix())
    archive_path: Path | None = None
    archive_hash: str | None = None
    if create_archive:
        archive_path = _create_zip_archive(bundle_root)
        archive_hash = _sha256_file(archive_path)

    return ReleaseBundleResult(
        bundle_dir=str(bundle_root),
        success=quality_gate.success,
        files=sorted(files),
        quality_gate=quality_gate,
        archive_path=str(archive_path) if archive_path else None,
        archive_sha256=archive_hash,
    )


def verify_release_bundle(bundle_dir: str | Path) -> BundleVerificationResult:
    root = Path(bundle_dir)
    manifest_path = root / "release_manifest.json"
    if not manifest_path.exists():
        return BundleVerificationResult(
            bundle_dir=str(root),
            success=False,
            checked_files=0,
            missing_files=["release_manifest.json"],
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksums = manifest.get("checksums", {})
    missing_files: list[str] = []
    changed_files: list[str] = []
    for file_name, expected_hash in sorted(checksums.items()):
        path = root / file_name
        if not path.exists():
            missing_files.append(file_name)
            continue
        if _sha256_file(path) != expected_hash:
            changed_files.append(file_name)

    return BundleVerificationResult(
        bundle_dir=str(root),
        success=not missing_files and not changed_files,
        checked_files=len(checksums),
        missing_files=missing_files,
        changed_files=changed_files,
    )


def verify_release_archive(archive_path: str | Path) -> BundleVerificationResult:
    archive = Path(archive_path)
    if not archive.exists():
        return BundleVerificationResult(
            bundle_dir=str(archive),
            success=False,
            checked_files=0,
            missing_files=[str(archive)],
        )
    if not zipfile.is_zipfile(archive):
        return BundleVerificationResult(
            bundle_dir=str(archive),
            success=False,
            checked_files=0,
            changed_files=[str(archive)],
        )

    with tempfile.TemporaryDirectory(prefix="ai-orbit-release-") as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(temp_root)
        bundle_root = _find_extracted_bundle_root(temp_root)
        if bundle_root is None:
            return BundleVerificationResult(
                bundle_dir=str(archive),
                success=False,
                checked_files=0,
                missing_files=["release_manifest.json"],
            )
        result = verify_release_bundle(bundle_root)
        return BundleVerificationResult(
            bundle_dir=str(archive),
            success=result.success,
            checked_files=result.checked_files,
            missing_files=result.missing_files,
            changed_files=result.changed_files,
        )


def _copy_core_artifacts(source_root: Path, bundle_root: Path) -> list[str]:
    files: list[str] = []
    for file_name in [
        "entities.json",
        "relationships.json",
        "product_catalog.json",
        "relationship_views.json",
        "validation_report.json",
        "manifest.json",
    ]:
        source = source_root / file_name
        if source.exists():
            destination = bundle_root / file_name
            shutil.copy2(source, destination)
            files.append(destination.relative_to(bundle_root).as_posix())

    raw_source = source_root / "raw"
    if raw_source.exists():
        raw_destination = bundle_root / "raw"
        if raw_destination.exists():
            shutil.rmtree(raw_destination)
        shutil.copytree(raw_source, raw_destination)
        files.extend(
            file.relative_to(bundle_root).as_posix()
            for file in sorted(raw_destination.rglob("*"))
            if file.is_file()
        )
    return files


def _relative_paths(root: Path, paths: Iterable[str]) -> list[str]:
    return [Path(path).relative_to(root).as_posix() for path in paths]


def _build_checksums(root: Path, files: Iterable[str]) -> dict[str, str]:
    return {file_name: _sha256_file(root / file_name) for file_name in sorted(files)}


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_zip_archive(bundle_root: Path) -> Path:
    archive_path = bundle_root.with_suffix(".zip")
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_root.parent))
    return archive_path


def _find_extracted_bundle_root(root: Path) -> Path | None:
    manifests = sorted(root.rglob("release_manifest.json"))
    if not manifests:
        return None
    return manifests[0].parent


def _build_release_notes(
    *,
    bundle_name: str,
    source_data_dir: Path,
    quality_gate: QualityGateResult,
    files: list[str],
) -> str:
    checks = "\n".join(
        f"- [{'x' if check.passed else ' '}] {check.name}: {check.message}"
        for check in quality_gate.checks
    )
    file_list = "\n".join(f"- `{file_name}`" for file_name in files)
    status = "passed" if quality_gate.success else "failed"
    return (
        f"# AI Orbit Release Bundle: {bundle_name}\n\n"
        f"- Source data directory: `{source_data_dir}`\n"
        f"- Quality gate: {status}\n\n"
        "## Quality Checks\n\n"
        f"{checks}\n\n"
        "## Included Artifacts\n\n"
        f"{file_list}\n\n"
        "## Verification\n\n"
        "Use `verify-release-bundle` for directory bundles or "
        "`verify-release-archive` for zip archives.\n"
    )
