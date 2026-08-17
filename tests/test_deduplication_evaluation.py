from __future__ import annotations

import json
import subprocess
import sys

from src.deduplication import evaluate_labeled_pairs


def test_deduplication_evaluation_matches_labeled_fixture() -> None:
    report = evaluate_labeled_pairs()

    assert report.total_pairs == 25
    assert report.true_positives == 12
    assert report.true_negatives == 13
    assert report.false_positives == 0
    assert report.false_negatives == 0
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.accuracy == 1.0
    assert all(result.score.reasons for result in report.results)


def test_deduplication_evaluation_cli_returns_nonzero_only_on_errors() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/evaluate_deduplication.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["total_pairs"] == 25
    assert payload["false_positives"] == 0
    assert payload["false_negatives"] == 0
    assert payload["accuracy"] == 1.0
