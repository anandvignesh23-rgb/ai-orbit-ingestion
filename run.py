import argparse

from src.pipeline import IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Orbit data ingestion pipeline")
    parser.add_argument(
        "--mode",
        choices=["deterministic", "configured"],
        default="deterministic",
        help="deterministic builds the representative dataset; configured uses config/sources.yaml",
    )
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    pipeline = IngestionPipeline(data_dir=args.data_dir)
    if args.mode == "configured":
        success = pipeline.run_configured(config_path=args.config)
    else:
        success = pipeline.run()
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
