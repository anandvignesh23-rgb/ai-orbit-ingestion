from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from src.api.schemas import (
    EntityRelationshipsResponse,
    EntitySearchResult,
    HealthResponse,
    RelationshipViewResponse,
    RootResponse,
    StatsResponse,
    relationship_view_response,
    search_result_from_match,
)
from src.api.services import DatasetService
from src.models import Entity, Relationship


TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
GITHUB_URL = "https://github.com/anandvignesh23-rgb/ai-orbit-ingestion"


def create_app(data_dir: str | Path = "data") -> FastAPI:
    dataset_service = DatasetService(data_dir=data_dir)
    app = FastAPI(
        title="AI Orbit Data API",
        description="Public demonstration API for the AI Orbit ingestion pipeline.",
        version="1.0.0",
    )
    app.state.dataset_service = dataset_service

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> HTMLResponse:
        base_url = str(request.base_url).rstrip("/")
        html = _render_landing_page(
            dataset_service.landing_page_context(),
            base_url=base_url,
        )
        return HTMLResponse(content=html)

    @app.get("/info", response_model=RootResponse)
    def info(request: Request) -> RootResponse:
        base_url = str(request.base_url).rstrip("/")
        return RootResponse(
            name="AI Orbit Data Ingestion Pipeline",
            status="online",
            description="API serving normalized AI ecosystem entities and relationships.",
            url=base_url,
            docs=f"{base_url}/docs",
            health=f"{base_url}/health",
            stats=f"{base_url}/stats",
            search=f"{base_url}/search?q=agent",
        )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            entities_loaded=dataset_service.entities_loaded,
            relationships_loaded=dataset_service.relationships_loaded,
        )

    @app.get("/stats", response_model=StatsResponse)
    def stats() -> StatsResponse:
        return StatsResponse.model_validate(dataset_service.stats())

    @app.get("/entities", response_model=list[Entity])
    def entities(
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> list[Entity]:
        return dataset_service.list_entities(
            entity_type=type,
            category=category,
            offset=offset,
            limit=limit,
        )

    @app.get("/entities/{entity_id}", response_model=Entity)
    def entity(entity_id: str) -> Entity:
        found = dataset_service.get_entity(entity_id)
        if found is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return found

    @app.get("/relationships", response_model=list[Relationship])
    def relationships(
        relationship_type: str | None = Query(default=None),
        source_id: str | None = Query(default=None),
        target_id: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=100),
    ) -> list[Relationship]:
        return dataset_service.list_relationships(
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            offset=offset,
            limit=limit,
        )

    @app.get("/entities/{entity_id}/relationships", response_model=EntityRelationshipsResponse)
    def entity_relationships(
        entity_id: str,
        relationship_type: str | None = Query(default=None),
    ) -> EntityRelationshipsResponse:
        views = dataset_service.relationship_views_for_entity(
            entity_id,
            relationship_type=relationship_type,
        )
        if views is None:
            raise HTTPException(status_code=404, detail="entity not found")
        responses = [relationship_view_response(view) for view in views]
        return EntityRelationshipsResponse(
            entity_id=entity_id,
            outgoing=[view for view in responses if view.direction == "outgoing"],
            incoming=[view for view in responses if view.direction == "incoming"],
        )

    @app.get("/search", response_model=list[EntitySearchResult])
    def search(
        q: str = Query(min_length=1),
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=100),
    ) -> list[EntitySearchResult]:
        matches = dataset_service.index.search_entities(
            q,
            entity_type=type,
            category=category,
            limit=limit,
        )
        return [search_result_from_match(match) for match in matches]

    return app


def _render_landing_page(context: dict, *, base_url: str) -> str:
    metrics = context["metrics"]
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "BASE_URL": base_url,
        "GITHUB_URL": GITHUB_URL,
        "TOTAL_ENTITIES": str(metrics.get("entities", "N/A")),
        "TOTAL_RELATIONSHIPS": str(metrics.get("relationships", "N/A")),
        "DUPLICATES_MERGED": str(metrics.get("duplicates_merged", "N/A")),
        "VALIDATION_ERRORS": str(metrics.get("validation_errors", "N/A")),
        "ENTITY_TYPE_ROWS": _count_rows(context.get("entity_types", {})),
        "RELATIONSHIP_TYPE_ROWS": _count_rows(context.get("relationship_types", {})),
        "SOURCE_BADGES": _source_badges(context.get("sources", [])),
        "CATEGORY_BADGES": _category_badges(context.get("top_categories", {})),
    }
    html = template
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def _count_rows(counts: dict[str, int]) -> str:
    return "\n".join(
        f'<div class="count-row"><span>{escape(label.replace("_", " ").title())}</span><strong>{count}</strong></div>'
        for label, count in counts.items()
    )


def _source_badges(sources: list[str]) -> str:
    if not sources:
        return '<span class="badge muted">N/A</span>'
    return "\n".join(
        f'<span class="badge">{escape(source)}</span>'
        for source in sources[:6]
    )


def _category_badges(categories: dict[str, int]) -> str:
    if not categories:
        return '<span class="badge muted">N/A</span>'
    return "\n".join(
        f'<span class="badge">{escape(category)} <small>{count}</small></span>'
        for category, count in categories.items()
    )


app = create_app()
