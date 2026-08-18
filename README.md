# AI Orbit Data Ingestion Pipeline

AI Orbit is the user-facing AI ecosystem discovery platform. This ingestion
pipeline operates as the internal data layer that discovers, cleans, normalizes,
deduplicates, classifies, validates, and connects ecosystem entities before they
are consumed by the AI Orbit product.

```text
Discovery
-> Extraction
-> Cleaning
-> Normalization
-> Deduplication
-> Classification
-> Relationship Mapping
-> Validation
-> Export
```

## Architecture

The pipeline is not a standalone end-user product. It feeds the AI Orbit
product/API and discovery UI:

```text
External AI Ecosystem Sources
GitHub / Hugging Face / RSS / YouTube / Official Sites / Curated Sources
                                ↓
                    AI Orbit Ingestion Pipeline
                                ↓
                     Canonical Knowledge Layer
                                ↓
                 Entities + Relationships Dataset
                                ↓
                      AI Orbit Product/API
                                ↓
                  Search / Browse / Discovery UI
```

The codebase is organized by pipeline stage:

- `src/models/`: Pydantic entity and relationship schemas
- `src/sources/`: GitHub, Hugging Face, RSS, YouTube, and curated source adapters
- `src/cleaning/`: deterministic text sanitization
- `src/normalization/`: name, URL, and raw-record-to-entity normalization
- `src/deduplication/`: scoring, resolving, and merging
- `src/classification/`: deterministic category rules
- `src/relationships/`: rule-based relationship mapping
- `src/validation/`: dataset and relationship validation reports
- `src/api/`: optional FastAPI demo service over generated JSON exports
- `src/utils/`: stable IDs, logging, and resilience helpers
- `src/pipeline.py`: end-to-end deterministic export pipeline
- `scripts/build_representative_dataset.py`: reusable representative dataset builder

## API-First Sources

The source layer uses structured APIs and feeds rather than a crawler.

- `GitHubSource`: official GitHub REST repository search
- `HuggingFaceSource`: public Hugging Face models API
- `RSSSource`: configured RSS feeds parsed with `feedparser`
- `YouTubeSource`: optional YouTube Data API search when `YOUTUBE_API_KEY` exists
- `CuratedSource`: official-source JSON seed files from `config/seeds/`

Each adapter returns `RawRecord` objects and leaves global cleaning,
normalization, deduplication, and classification to shared stages.

`RawRecordNormalizer` converts those records into canonical `Entity` objects for
repositories, models, news, videos, and curated entities while preserving
provenance and source-specific metadata.

Configured sources can be loaded from `config/sources.yaml` with
`build_sources_from_config()`. `IngestionPipeline.discover_configured_entities()`
uses that config path, isolates source failures, and normalizes returned raw
records into entities. The default `run.py` path remains deterministic, while
`run.py --mode configured` uses the enabled configured sources.

The checked-in curated seeds provide a small official-source baseline across
companies, tools, tasks, devices, robots, collections, creative tools, and MCP
servers. This makes configured mode useful even without API keys.

## Entity Schema

Entities use Pydantic:

```python
class Entity(BaseModel):
    id: str
    entity_type: EntityType
    name: str
    description: str | None = None
    url: HttpUrl | None = None
    categories: list[str] = []
    sources: list[SourceReference] = []
    metadata: dict[str, Any] = {}
    display: DisplayMetadata | None = None
    pipeline_metadata: PipelineMetadata | None = None
```

Supported entity types:

```text
tool, task, company, news, video, robot, device, model, repository,
mcp, collection, personal, creative
```

Canonical data distinguishes product-facing fields from internal pipeline data.
Product-facing fields include ID, type, name, description, URL, categories,
provider/display metadata, source provenance, and relationships. Internal
observability fields belong in `pipeline_metadata`, including discovery times,
source count, duplicate/review status, and conflict notes. Specialized source
facts remain in `metadata`.

## Stable IDs

Entity and relationship IDs are deterministic UUIDv5 values using a fixed
application namespace.

- Entity logical key: `entity:{entity_type}:{canonical_key}`
- Relationship logical key: `relationship:{source_id}|{relationship_type}|{target_id}`

No final entity or relationship ID uses random UUIDs.

## Cleaning And Normalization

Text cleaning is deterministic:

- HTML tags removed with BeautifulSoup
- HTML entities decoded
- Unicode normalized with NFKC
- Whitespace collapsed and trimmed
- `None` safely converts to an empty string

Name normalization lowercases, removes punctuation, collapses whitespace, and
removes common company suffixes for company comparisons. Product qualifiers are
preserved, so `Claude` and `Claude Desktop` remain distinct.

URL normalization lowercases hostnames, removes `www.`, normalizes scheme to
HTTPS, removes fragments, trims trailing slashes, and removes tracking query
params such as `utm_source`, `fbclid`, and `gclid`.

## Entity Resolution

Deduplication uses explainable multi-signal scoring, not a single fuzzy string
threshold.

```text
DuplicateScore =
0.45 * URLMatch
+ 0.35 * NameSimilarity
+ 0.10 * TypeCompatibility
+ 0.10 * MetadataSimilarity
```

All component scores are in `[0, 1]`. Entity types must be compatible before
scoring. URLs/domains carry the most weight, repository-like URLs compare full
paths, normalized names are scored with RapidFuzz, and missing metadata uses a
neutral score rather than becoming automatic disagreement.

Default thresholds:

```text
score >= 0.90       merge
0.75 <= score < .90 review
score < 0.75        keep separate
```

Merging preserves the canonical ID, best name, richest description, unique
provenance, categories, list metadata, and conflict markers for irreconcilable
metadata disagreements. Scalar metadata conflicts prefer higher-priority source
types from `config/source_priority.yaml`, while preserving both source
references and recording the conflict.

The scorer can be checked against labeled calibration pairs:

```bash
python scripts/evaluate_deduplication.py
```

The current fixture in `config/deduplication_pairs.json` covers 25 duplicate
and distinct pairs across companies, tools, repositories, models, devices,
robots, collections, and news records.

## Classification

`EntityClassifier` is deterministic and does not require an LLM. It uses:

- existing category aliases from `config/categories.yaml`
- entity type defaults
- metadata fields and tags
- keyword rules
- provider/domain signals

Canonical categories include:

```text
agents, rag, code-generation, image-generation, video-generation, speech,
computer-vision, developer-tools, productivity, research, education, robotics,
hardware, multimodal, open-source, search, data-analysis, automation
```

## Relationship Model

Relationships use deterministic IDs and evidence:

```python
class Relationship(BaseModel):
    id: str
    source_id: str
    relationship_type: RelationshipType
    target_id: str
    confidence: float
    evidence: list[Evidence] = []
```

Supported relationship types:

```text
develops, solves, integrates_with, runs, part_of_collection
```

`RelationshipMapper` creates only edges where both endpoints exist:

- `Company -> develops -> Tool`
- `Company -> develops -> Model`
- `Tool -> solves -> Task`
- `MCP -> integrates_with -> Tool`
- `Device -> runs -> Model`

`part_of_collection` is optional and conservative: it is generated only from
explicit metadata such as `collection`, `collections`, `member_of`, `items`,
`members`, or `includes`. The mapper does not infer collection membership from
category overlap or fuzzy similarity.

Duplicate edges and self-relations are avoided. When multiple metadata fields or
source records support the same edge, the mapper keeps one deterministic
relationship, appends unique evidence entries from both endpoints, and slightly
raises confidence for each additional independent signal.

`relationships.json` stores only canonical directed edges. Product/API lookup
helpers expose inverse views such as `developed_by`, `solved_by`,
`integrated_by`, `runs_on`, and `contains` without duplicating canonical records. The
derived `product_catalog.json` includes these relationship summaries for UI
rendering, and `relationship_views.json` materializes both outgoing and
incoming product-facing views for clients that prefer a flat edge feed. Inverse
view rows are marked with `derived: true` and retain the original canonical
relationship type.

## Validation

`DatasetValidator` produces a JSON-serializable `ValidationReport` with summary
counts, entity counts, source counts, errors, warnings, duplicate candidates,
and relationship errors.

Validation checks dataset size, duplicate IDs, duplicate canonical URLs,
required provenance, normalized categories, relationship references, duplicate
edges, self-relations, invalid relationship types, and specialized metadata
warnings.

Validation also reports product-oriented quality metrics: entities by category,
relationships by type, average relationship density, entities without
relationships, recently added count, completeness score, and coverage warnings
from `config/product.yaml`. Schema validity remains separate from product
quality warnings.

## Resilience

Network sources use explicit timeouts, retry transient transport failures with
exponential backoff, and fail gracefully at source level. Shared helpers isolate
source failures during discovery and redact secret query parameters before URLs
appear in errors.

Secrets are never hardcoded. Use `.env` for optional keys.

## Output Files

Generated dataset files:

```text
data/entities.json
data/relationships.json
data/product_catalog.json
data/relationship_views.json
data/validation_report.json
data/manifest.json
```

`manifest.json` is a compact run index containing schema version, generation
time, run mode, validation success, summary counts, source counts, source run
statuses, and the files emitted by the run.

`entities.json` and `relationships.json` remain the canonical source of truth.
`product_catalog.json` is a derived AI Orbit product-facing adapter optimized
for search, browsing, provider display, related entity IDs, recently-added
flags, and completeness scoring. `relationship_views.json` is a derived
product-facing edge view that includes canonical outgoing rows plus generated
inverse rows, leaving `relationships.json` compact and canonical.

Configured discovery also preserves source-level debugging artifacts:

```text
data/raw/source_records.json
data/raw/source_results.json
```

Regenerate them with:

```bash
python scripts/build_representative_dataset.py
```

Current generated dataset:

```text
entities:       283
relationships:  610
errors:           0
warnings:         0
```

Entity distribution:

```text
task:        25
company:     25
tool:        45
model:       35
repository:  35
device:      12
robot:       12
personal:    12
creative:    15
collection:  12
mcp:         20
news:        20
video:       15
```

Query an exported dataset:

```bash
python scripts/query_dataset.py --data-dir data summary
python scripts/query_dataset.py --data-dir data analytics --limit 10
python scripts/query_dataset.py --data-dir data export-csv --output-dir data/graph_csv
python scripts/query_dataset.py export-schema --output-dir data/schema
python scripts/query_dataset.py validate-contract --data-dir data
python scripts/query_dataset.py quality-gate --data-dir data --min-entities 283 --min-relationships 610 --max-possible-duplicates 30
python scripts/query_dataset.py release-bundle --data-dir data --output-dir releases --min-entities 283 --min-relationships 610 --max-possible-duplicates 30 --zip
python scripts/query_dataset.py verify-release-bundle --bundle-dir releases/ai-orbit-release-YYYYMMDDTHHMMSSZ
python scripts/query_dataset.py verify-release-archive --archive-path releases/ai-orbit-release-YYYYMMDDTHHMMSSZ.zip
python scripts/query_dataset.py --data-dir data search chatgpt --type tool
python scripts/query_dataset.py --data-dir data entity ChatGPT
python scripts/query_dataset.py --data-dir data neighbors ChatGPT
python scripts/query_dataset.py diff --before data_old --after data
```

Release bundles include JSON exports, schemas, graph CSVs, checksums, quality
gate output, `release_manifest.json`, and human-readable `RELEASE_NOTES.md`.

## How AI Orbit Uses This Data

The ingestion pipeline is not the direct end-user interface. It creates the
structured knowledge layer consumed by the AI Orbit search and discovery
product:

```text
Source systems
-> ingestion pipeline
-> canonical entities/relationships
-> AI Orbit application
```

## Consuming the Dataset

Another service can load `entities.json` and `relationships.json` to support
browse by type, browse by category, lightweight search, related-entity lookup,
and company/tool/model navigation. Product-specific adapters such as
`product_catalog.json` and `relationship_views.json` are derived from the same
canonical files and should not be edited as independent source data.

An optional FastAPI demo layer serves the pre-generated dataset without running
ingestion on each request:

```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Available demo endpoints:

```text
GET /database
GET /health
GET /stats
GET /entities
GET /entities/{entity_id}
GET /relationships
GET /entities/{entity_id}/relationships
GET /search?q=...
```

## Live Deployment

Live Demo:
https://ai-orbit-ingestion.vercel.app

Searchable Database:
https://ai-orbit-ingestion.vercel.app/database

API Documentation:
https://ai-orbit-ingestion.vercel.app/docs

Dataset Statistics:
https://ai-orbit-ingestion.vercel.app/stats

Health:
https://ai-orbit-ingestion.vercel.app/health

Deployment architecture:

```text
External APIs
-> offline ingestion
-> canonical JSON
-> FastAPI
-> public API
```

The deployed service reads committed canonical JSON artifacts from `data/`.
Public API requests do not execute the ingestion pipeline and do not call
GitHub, Hugging Face, YouTube, or RSS sources.

Local API command:

```bash
uvicorn src.api.app:app --reload
```

Production command for Python web hosts:

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port $PORT
```

## Setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional environment variables:

```env
GITHUB_TOKEN=
YOUTUBE_API_KEY=
LOG_LEVEL=INFO
```

`GITHUB_TOKEN` raises GitHub rate limits. `YOUTUBE_API_KEY` enables YouTube
Data API discovery; without it, YouTube is skipped successfully.

## Running

Run the end-to-end deterministic pipeline:

```bash
python run.py
```

Run configured source discovery:

```bash
python run.py --mode configured --config config/sources.yaml --data-dir data/configured
```

Or rebuild the representative dataset directly:

```bash
python scripts/build_representative_dataset.py
```

Run tests:

```bash
pytest
```

The test suite is deterministic and mocks external API behavior. Live API smoke
tests are intentionally separate from unit tests.

## Known Limitations

- The representative dataset is deterministic and curated rather than a live
  scrape of hundreds of current records.
- Some possible duplicate candidates remain in the validation report for human
  review because conservative scoring is preferred over unsafe auto-merges.
- YouTube live discovery requires a valid API key and quota.
- The default `run.py` mode uses the deterministic representative builder;
  live/configured discovery is opt-in with `--mode configured`.

## Future Improvements

- Expand the duplicate calibration set with production review outcomes
- Add richer relationship evidence from multiple provenance records
- Add CI with offline mocked tests and optional live smoke checks
