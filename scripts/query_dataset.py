from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.query import diff_datasets, load_dataset
from src.quality import QualityGateConfig, run_quality_gate
from src.release import build_release_bundle, verify_release_archive, verify_release_bundle
from src.schema import export_schema_bundle, validate_dataset_contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Query an exported AI Orbit dataset")
    parser.add_argument("--data-dir", default="data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Print dataset summary counts")

    analytics_parser = subparsers.add_parser("analytics", help="Print graph analytics")
    analytics_parser.add_argument("--limit", type=int, default=10)

    csv_parser = subparsers.add_parser("export-csv", help="Export graph nodes and edges as CSV")
    csv_parser.add_argument("--output-dir", required=True)

    diff_parser = subparsers.add_parser("diff", help="Diff two exported datasets")
    diff_parser.add_argument("--before", required=True)
    diff_parser.add_argument("--after", required=True)

    schema_parser = subparsers.add_parser("export-schema", help="Export JSON schemas")
    schema_parser.add_argument("--output-dir", required=True)

    contract_parser = subparsers.add_parser("validate-contract", help="Validate exported JSON artifacts")
    contract_parser.add_argument("--data-dir", default="data")

    quality_parser = subparsers.add_parser("quality-gate", help="Run dataset quality gates")
    quality_parser.add_argument("--data-dir", default="data")
    quality_parser.add_argument("--max-critical-errors", type=int, default=0)
    quality_parser.add_argument("--min-entities", type=int)
    quality_parser.add_argument("--min-relationships", type=int)
    quality_parser.add_argument("--max-possible-duplicates", type=int)
    quality_parser.add_argument("--max-orphans", type=int)
    quality_parser.add_argument("--max-orphan-ratio", type=float)
    quality_parser.add_argument("--allow-source-failures", action="store_true")

    release_parser = subparsers.add_parser("release-bundle", help="Build a portable release bundle")
    release_parser.add_argument("--data-dir", default="data")
    release_parser.add_argument("--output-dir", required=True)
    release_parser.add_argument("--bundle-name")
    release_parser.add_argument("--max-critical-errors", type=int, default=0)
    release_parser.add_argument("--min-entities", type=int)
    release_parser.add_argument("--min-relationships", type=int)
    release_parser.add_argument("--max-possible-duplicates", type=int)
    release_parser.add_argument("--max-orphans", type=int)
    release_parser.add_argument("--max-orphan-ratio", type=float)
    release_parser.add_argument("--allow-source-failures", action="store_true")
    release_parser.add_argument("--zip", action="store_true", help="Also create a zip archive beside the bundle")

    verify_release_parser = subparsers.add_parser("verify-release-bundle", help="Verify release bundle checksums")
    verify_release_parser.add_argument("--bundle-dir", required=True)

    verify_archive_parser = subparsers.add_parser("verify-release-archive", help="Verify a zipped release archive")
    verify_archive_parser.add_argument("--archive-path", required=True)

    search_parser = subparsers.add_parser("search", help="Search entities")
    search_parser.add_argument("query")
    search_parser.add_argument("--type")
    search_parser.add_argument("--category")
    search_parser.add_argument("--source")
    search_parser.add_argument("--limit", type=int, default=10)

    entity_parser = subparsers.add_parser("entity", help="Print one entity as JSON")
    entity_parser.add_argument("identifier")

    neighbors_parser = subparsers.add_parser("neighbors", help="Print an entity neighborhood")
    neighbors_parser.add_argument("identifier")

    args = parser.parse_args()

    if args.command == "diff":
        print(json.dumps(diff_datasets(args.before, args.after).model_dump(mode="json"), indent=2))
        return
    if args.command == "export-schema":
        print(json.dumps(export_schema_bundle(args.output_dir), indent=2))
        return
    if args.command == "validate-contract":
        result = validate_dataset_contract(args.data_dir)
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise SystemExit(0 if result.success else 1)
    if args.command == "quality-gate":
        result = run_quality_gate(
            args.data_dir,
            QualityGateConfig(
                max_critical_errors=args.max_critical_errors,
                min_entities=args.min_entities,
                min_relationships=args.min_relationships,
                max_possible_duplicates=args.max_possible_duplicates,
                max_orphans=args.max_orphans,
                max_orphan_ratio=args.max_orphan_ratio,
                allow_source_failures=args.allow_source_failures,
            ),
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise SystemExit(0 if result.success else 1)
    if args.command == "release-bundle":
        result = build_release_bundle(
            args.data_dir,
            args.output_dir,
            bundle_name=args.bundle_name,
            create_archive=args.zip,
            quality_config=QualityGateConfig(
                max_critical_errors=args.max_critical_errors,
                min_entities=args.min_entities,
                min_relationships=args.min_relationships,
                max_possible_duplicates=args.max_possible_duplicates,
                max_orphans=args.max_orphans,
                max_orphan_ratio=args.max_orphan_ratio,
                allow_source_failures=args.allow_source_failures,
            ),
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise SystemExit(0 if result.success else 1)
    if args.command == "verify-release-bundle":
        result = verify_release_bundle(args.bundle_dir)
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise SystemExit(0 if result.success else 1)
    if args.command == "verify-release-archive":
        result = verify_release_archive(args.archive_path)
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise SystemExit(0 if result.success else 1)

    index = load_dataset(args.data_dir)

    if args.command == "summary":
        print(json.dumps(index.summary(), indent=2))
    elif args.command == "analytics":
        print(json.dumps(index.analytics(limit=args.limit).model_dump(mode="json"), indent=2))
    elif args.command == "export-csv":
        print(json.dumps(index.export_csv(args.output_dir), indent=2))
    elif args.command == "search":
        matches = index.search_entities(
            args.query,
            entity_type=args.type,
            category=args.category,
            source_name=args.source,
            limit=args.limit,
        )
        print(
            json.dumps(
                [
                    {
                        "id": match.entity.id,
                        "entity_type": str(match.entity.entity_type),
                        "name": match.entity.name,
                        "url": str(match.entity.url) if match.entity.url else None,
                        "categories": match.entity.categories,
                        "score": match.score,
                    }
                    for match in matches
                ],
                indent=2,
            )
        )
    elif args.command == "entity":
        entity = index.find_entity(args.identifier)
        if entity is None:
            raise SystemExit(f"entity not found: {args.identifier}")
        print(json.dumps(entity.model_dump(mode="json"), indent=2))
    elif args.command == "neighbors":
        neighborhood = index.neighborhood(args.identifier)
        if neighborhood is None:
            raise SystemExit(f"entity not found: {args.identifier}")
        print(json.dumps(neighborhood.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
