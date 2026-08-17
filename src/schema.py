from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from src.models import Entity, Relationship
from src.product_export import ProductCatalogRecord
from src.relationship_views import ProductRelationshipView
from src.validation import ValidationReport, ValidationSummary


class SourceRunManifest(BaseModel):
    source_name: str
    status: str
    records: int = Field(ge=0)
    error: str | None = None


class DatasetManifest(BaseModel):
    schema_version: str
    generated_at: str
    run_mode: Literal["deterministic", "configured"]
    success: bool
    summary: ValidationSummary
    entity_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
    source_runs: list[SourceRunManifest] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class ArtifactValidation(BaseModel):
    artifact: str
    valid: bool
    records: int = 0
    errors: list[str] = Field(default_factory=list)


class ContractValidationResult(BaseModel):
    data_dir: str
    success: bool
    artifacts: list[ArtifactValidation]
    errors: list[str] = Field(default_factory=list)


def build_schema_bundle() -> dict[str, dict]:
    return {
        "entity": Entity.model_json_schema(),
        "relationship": Relationship.model_json_schema(),
        "product_catalog": ProductCatalogRecord.model_json_schema(),
        "relationship_view": ProductRelationshipView.model_json_schema(),
        "validation_report": ValidationReport.model_json_schema(),
        "manifest": DatasetManifest.model_json_schema(),
    }


def export_schema_bundle(output_dir: str | Path) -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    exported: dict[str, str] = {}
    for name, schema in build_schema_bundle().items():
        path = root / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        exported[name] = str(path)
    return exported


def validate_dataset_contract(data_dir: str | Path) -> ContractValidationResult:
    root = Path(data_dir)
    artifacts = [
        _validate_list_artifact(root / "entities.json", "entities", Entity),
        _validate_list_artifact(root / "relationships.json", "relationships", Relationship),
        _validate_list_artifact(root / "product_catalog.json", "product_catalog", ProductCatalogRecord),
        _validate_list_artifact(root / "relationship_views.json", "relationship_views", ProductRelationshipView),
        _validate_object_artifact(root / "validation_report.json", "validation_report", ValidationReport),
        _validate_object_artifact(root / "manifest.json", "manifest", DatasetManifest),
    ]
    errors = [error for artifact in artifacts for error in artifact.errors]
    errors.extend(_validate_manifest_file_references(root))
    return ContractValidationResult(
        data_dir=str(root),
        success=not errors,
        artifacts=artifacts,
        errors=errors,
    )


def _validate_list_artifact(path: Path, artifact: str, model: type[BaseModel]) -> ArtifactValidation:
    payload, errors = _read_json(path, artifact)
    if errors:
        return ArtifactValidation(artifact=artifact, valid=False, errors=errors)
    if not isinstance(payload, list):
        return ArtifactValidation(
            artifact=artifact,
            valid=False,
            errors=[f"{artifact} must be a JSON array"],
        )

    validation_errors: list[str] = []
    for index, item in enumerate(payload):
        try:
            model.model_validate(item)
        except ValidationError as exc:
            validation_errors.append(f"{artifact}[{index}]: {exc.errors()[0]['msg']}")
    return ArtifactValidation(
        artifact=artifact,
        valid=not validation_errors,
        records=len(payload),
        errors=validation_errors,
    )


def _validate_object_artifact(path: Path, artifact: str, model: type[BaseModel]) -> ArtifactValidation:
    payload, errors = _read_json(path, artifact)
    if errors:
        return ArtifactValidation(artifact=artifact, valid=False, errors=errors)
    if not isinstance(payload, dict):
        return ArtifactValidation(
            artifact=artifact,
            valid=False,
            errors=[f"{artifact} must be a JSON object"],
        )

    try:
        model.model_validate(payload)
    except ValidationError as exc:
        return ArtifactValidation(
            artifact=artifact,
            valid=False,
            errors=[f"{artifact}: {error['msg']}" for error in exc.errors()],
        )
    return ArtifactValidation(artifact=artifact, valid=True, records=1)


def _read_json(path: Path, artifact: str) -> tuple[Any, list[str]]:
    if not path.exists():
        return None, [f"{artifact} file is missing: {path}"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [f"{artifact} is not valid JSON: {exc.msg}"]


def _validate_manifest_file_references(root: Path) -> list[str]:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = DatasetManifest.model_validate(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, ValidationError):
        return []
    return [
        f"manifest references missing file: {file_name}"
        for file_name in manifest.files
        if not (root / file_name).exists()
    ]
