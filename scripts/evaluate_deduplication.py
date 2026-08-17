from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.deduplication import evaluate_labeled_pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate duplicate scoring labels")
    parser.add_argument("--pairs", default="config/deduplication_pairs.json")
    args = parser.parse_args()

    report = evaluate_labeled_pairs(args.pairs)
    print(json.dumps(report.model_dump(mode="json", exclude={"results"}), indent=2))
    raise SystemExit(0 if report.false_positives == 0 and report.false_negatives == 0 else 1)


if __name__ == "__main__":
    main()
