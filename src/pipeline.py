from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.build_representative_dataset import build_entities
from src.classification import EntityClassifier
from src.deduplication import EntityResolver
from src.models.entity import Entity
from src.models.relationship import Relationship
from src.normalization import RawRecordNormalizer
from src.product_export import build_product_catalog
from src.relationship_views import build_relationship_views
from src.relationships import RelationshipMapper
from src.sources.base import RawRecord
from src.sources.config import build_sources_from_config
from src.utils.logging import configure_logging
from src.utils.resilience import SourceRunResult, discover_sources
from src.validation import DatasetValidator, ValidationReport


class IngestionPipeline:
    """Deterministic representative dataset pipeline."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.raw_records: list[Entity] = []
        self.source_records: list[RawRecord] = []
        self.source_results: list[SourceRunResult] = []
        self.entities: list[Entity] = []
        self.relationships: list[Relationship] = []
        self.validation_report: ValidationReport | None = None
        self.duplicates_merged = 0
        self.possible_duplicates = []
        self.run_mode = "deterministic"

    def discover(self) -> list[Entity]:
        self.raw_records = build_entities()
        return self.raw_records

    def discover_configured_records(
        self,
        config_path: str | Path = "config/sources.yaml",
    ) -> list[RawRecord]:
        sources = build_sources_from_config(config_path)
        self.source_results = discover_sources(sources)
        self.source_records = [
            record
            for result in self.source_results
            for record in result.records
        ]
        return self.source_records

    def discover_configured_entities(self, config_path: str | Path = "config/sources.yaml") -> list[Entity]:
        raw_records = self.discover_configured_records(config_path)
        normalizer = RawRecordNormalizer()
        return normalizer.normalize_many(raw_records)

    def extract(self) -> list[Entity]:
        return self.raw_records

    def clean(self) -> list[Entity]:
        return self.raw_records

    def normalize(self) -> list[Entity]:
        self.entities = self.raw_records
        return self.entities

    def deduplicate(self) -> list[Entity]:
        return self.entities

    def classify(self) -> list[Entity]:
        return self.entities

    def map_relationships(self) -> list[Relationship]:
        self.relationships = RelationshipMapper().map_relationships(self.entities)
        return self.relationships

    def validate(self) -> bool:
        self.validation_report = DatasetValidator(relaxed=False).validate(
            self.entities,
            self.relationships,
            raw_records=len(self.raw_records),
            duplicates_merged=self.duplicates_merged,
            possible_duplicates=self.possible_duplicates,
        )
        return self.validation_report.success

    def validate_relaxed(self) -> bool:
        self.validation_report = DatasetValidator(relaxed=True).validate(
            self.entities,
            self.relationships,
            raw_records=len(self.raw_records),
            duplicates_merged=self.duplicates_merged,
            possible_duplicates=self.possible_duplicates,
        )
        return self.validation_report.success

    def export(self) -> None:
        if self.validation_report is None:
            raise RuntimeError("validate must run before export")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "entities.json").write_text(
            json.dumps([entity.model_dump(mode="json") for entity in self.entities], indent=2)
            + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "relationships.json").write_text(
            json.dumps(
                [
                    relationship.model_dump(mode="json")
                    for relationship in self.relationships
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "validation_report.json").write_text(
            json.dumps(self.validation_report.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "product_catalog.json").write_text(
            json.dumps(build_product_catalog(self.entities, self.relationships), indent=2) + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "relationship_views.json").write_text(
            json.dumps(build_relationship_views(self.relationships), indent=2) + "\n",
            encoding="utf-8",
        )
        self.export_raw_records()
        self.export_manifest()

    def export_raw_records(self) -> None:
        if not self.source_records and not self.source_results:
            return
        raw_dir = self.data_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "source_records.json").write_text(
            json.dumps(
                [record.model_dump(mode="json") for record in self.source_records],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (raw_dir / "source_results.json").write_text(
            json.dumps(
                [
                    {
                        "source_name": result.source_name,
                        "status": result.status,
                        "records": len(result.records),
                        "error": result.error,
                    }
                    for result in self.source_results
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def export_manifest(self) -> None:
        if self.validation_report is None:
            raise RuntimeError("validate must run before export")
        (self.data_dir / "manifest.json").write_text(
            json.dumps(self._build_manifest(), indent=2) + "\n",
            encoding="utf-8",
        )

    def _build_manifest(self) -> dict[str, Any]:
        assert self.validation_report is not None
        files = [
            "entities.json",
            "relationships.json",
            "product_catalog.json",
            "relationship_views.json",
            "validation_report.json",
            "manifest.json",
        ]
        if self.source_records or self.source_results:
            files.extend(["raw/source_records.json", "raw/source_results.json"])

        return {
            "schema_version": "1.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "run_mode": self.run_mode,
            "success": self.validation_report.success,
            "summary": self.validation_report.summary.model_dump(mode="json"),
            "entity_counts": self.validation_report.entity_counts,
            "source_counts": self.validation_report.source_counts,
            "source_runs": [
                {
                    "source_name": result.source_name,
                    "status": result.status,
                    "records": len(result.records),
                    "error": result.error,
                }
                for result in self.source_results
            ],
            "files": files,
        }

    def run(self) -> bool:
        self.run_mode = "deterministic"
        configure_logging()
        print("AI Orbit Data Ingestion Pipeline")
        print("[1/8] Discovery")
        self.discover()
        print(f"{len(self.raw_records)} raw records")
        print("[2/8] Extraction")
        self.extract()
        print("[3/8] Cleaning")
        self.clean()
        print("[4/8] Normalization")
        self.normalize()
        print("[5/8] Entity Resolution")
        self.deduplicate()
        print(f"{len(self.entities)} canonical entities")
        print("[6/8] Classification")
        self.classify()
        print("[7/8] Relationship Mapping")
        self.map_relationships()
        print(f"{len(self.relationships)} relationships created")
        print("[8/8] Validation")
        success = self.validate()
        assert self.validation_report is not None
        print(f"Critical errors: {self.validation_report.summary.critical_errors}")
        if success:
            self.export()
            print("Pipeline completed successfully.")
        else:
            print("Pipeline completed with validation errors.")
        return success

    def run_configured(self, config_path: str | Path = "config/sources.yaml") -> bool:
        self.run_mode = "configured"
        configure_logging()
        print("AI Orbit Data Ingestion Pipeline")
        print("[1/8] Discovery")
        self.raw_records = self.discover_configured_entities(config_path)
        print(f"{len(self.raw_records)} raw records")
        print("[2/8] Extraction")
        self.extract()
        print("[3/8] Cleaning")
        self.clean()
        print("[4/8] Normalization")
        self.normalize()
        print("[5/8] Entity Resolution")
        deduped = EntityResolver().resolve(self.entities)
        self.entities = deduped.entities
        self.duplicates_merged = deduped.merged_count
        self.possible_duplicates = deduped.possible_duplicates
        print(f"{self.duplicates_merged} duplicates merged")
        print(f"{len(self.entities)} canonical entities")
        print("[6/8] Classification")
        self.entities = EntityClassifier().classify_many(self.entities)
        print("[7/8] Relationship Mapping")
        self.map_relationships()
        print(f"{len(self.relationships)} relationships created")
        print("[8/8] Validation")
        success = self.validate_relaxed()
        assert self.validation_report is not None
        print(f"Critical errors: {self.validation_report.summary.critical_errors}")
        if success:
            self.export()
            print("Configured pipeline completed successfully.")
        else:
            print("Configured pipeline completed with validation errors.")
        return success
