from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request

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


def create_app(data_dir: str | Path = "data") -> FastAPI:
    dataset_service = DatasetService(data_dir=data_dir)
    app = FastAPI(
        title="AI Orbit Data API",
        description="Public demonstration API for the AI Orbit ingestion pipeline.",
        version="1.0.0",
    )
    app.state.dataset_service = dataset_service

    @app.get("/", response_model=RootResponse)
    def root(request: Request) -> RootResponse:
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


app = create_app()
