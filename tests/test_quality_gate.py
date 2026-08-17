from __future__ import annotations

import json
import subprocess
import sys

from src.pipeline import IngestionPipeline
from src.quality import QualityGateConfig, run_quality_gate


def test_quality_gate_passes_pipeline_export_with_thresholds(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True

    result = run_quality_gate(
        tmp_path,
        QualityGateConfig(
            min_entities=283,
            min_relationships=171,
            max_critical_errors=0,
            max_possible_duplicates=30,
            max_orphan_ratio=0.5,
        ),
    )

    assert result.success is True
    assert all(check.passed for check in result.checks)


def test_quality_gate_fails_when_threshold_is_missed(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True

    result = run_quality_gate(tmp_path, QualityGateConfig(min_entities=999))

    assert result.success is False
    failed = [check for check in result.checks if not check.passed]
    assert failed[0].name == "min_entities"
    assert failed[0].message == "283 >= 999"


def test_quality_gate_cli_exits_zero_on_success(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "quality-gate",
            "--data-dir",
            str(tmp_path),
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
    assert payload["success"] is True


def test_quality_gate_cli_exits_nonzero_on_failure(tmp_path) -> None:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "quality-gate",
            "--data-dir",
            str(tmp_path),
            "--max-orphans",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["success"] is False
    assert any(check["name"] == "orphans" for check in payload["checks"])
