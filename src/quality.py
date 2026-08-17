from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.query import load_dataset
from src.schema import DatasetManifest, validate_dataset_contract
from src.validation import ValidationReport


class QualityGateConfig(BaseModel):
    max_critical_errors: int = Field(default=0, ge=0)
    min_entities: int | None = Field(default=None, ge=0)
    min_relationships: int | None = Field(default=None, ge=0)
    max_possible_duplicates: int | None = Field(default=None, ge=0)
    max_orphans: int | None = Field(default=None, ge=0)
    max_orphan_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    allow_source_failures: bool = False


class QualityCheck(BaseModel):
    name: str
    passed: bool
    message: str


class QualityGateResult(BaseModel):
    data_dir: str
    success: bool
    checks: list[QualityCheck]


def run_quality_gate(
    data_dir: str | Path,
    config: QualityGateConfig | None = None,
) -> QualityGateResult:
    root = Path(data_dir)
    config = config or QualityGateConfig()
    checks: list[QualityCheck] = []

    contract = validate_dataset_contract(root)
    checks.append(
        QualityCheck(
            name="contract",
            passed=contract.success,
            message="exported artifacts match contract" if contract.success else "; ".join(contract.errors),
        )
    )

    report = _load_validation_report(root)
    manifest = _load_manifest(root)
    index = load_dataset(root)
    analytics = index.analytics(limit=0)

    checks.append(
        _threshold_check(
            "critical_errors",
            report.summary.critical_errors <= config.max_critical_errors,
            f"{report.summary.critical_errors} <= {config.max_critical_errors}",
        )
    )
    if config.min_entities is not None:
        checks.append(
            _threshold_check(
                "min_entities",
                report.summary.canonical_entities >= config.min_entities,
                f"{report.summary.canonical_entities} >= {config.min_entities}",
            )
        )
    if config.min_relationships is not None:
        checks.append(
            _threshold_check(
                "min_relationships",
                report.summary.relationships >= config.min_relationships,
                f"{report.summary.relationships} >= {config.min_relationships}",
            )
        )
    if config.max_possible_duplicates is not None:
        checks.append(
            _threshold_check(
                "possible_duplicates",
                report.summary.possible_duplicates <= config.max_possible_duplicates,
                f"{report.summary.possible_duplicates} <= {config.max_possible_duplicates}",
            )
        )
    if config.max_orphans is not None:
        checks.append(
            _threshold_check(
                "orphans",
                analytics.orphan_count <= config.max_orphans,
                f"{analytics.orphan_count} <= {config.max_orphans}",
            )
        )
    if config.max_orphan_ratio is not None:
        orphan_ratio = 0.0
        if analytics.entity_count:
            orphan_ratio = analytics.orphan_count / analytics.entity_count
        checks.append(
            _threshold_check(
                "orphan_ratio",
                orphan_ratio <= config.max_orphan_ratio,
                f"{orphan_ratio:.3f} <= {config.max_orphan_ratio:.3f}",
            )
        )

    failed_sources = [
        source.source_name
        for source in manifest.source_runs
        if source.status != "ok"
    ]
    if not config.allow_source_failures:
        checks.append(
            QualityCheck(
                name="source_failures",
                passed=not failed_sources,
                message="no source failures" if not failed_sources else f"failed sources: {', '.join(failed_sources)}",
            )
        )

    return QualityGateResult(
        data_dir=str(root),
        success=all(check.passed for check in checks),
        checks=checks,
    )


def _load_validation_report(root: Path) -> ValidationReport:
    return ValidationReport.model_validate(
        json.loads((root / "validation_report.json").read_text(encoding="utf-8"))
    )


def _load_manifest(root: Path) -> DatasetManifest:
    return DatasetManifest.model_validate(
        json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    )


def _threshold_check(name: str, passed: bool, message: str) -> QualityCheck:
    return QualityCheck(name=name, passed=passed, message=message)
