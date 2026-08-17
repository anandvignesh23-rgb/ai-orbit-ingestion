from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query

from src.api.schemas import (
    EntitySearchResult,
    HealthResponse,
    RelationshipViewResponse,
    StatsResponse,
    relationship_view_response,
    search_result_from_match,
)
from src.api.services import DatasetService
from src.models import Entity, Relationship


def create_app(data_dir: str | Path = "data") -> FastAPI:
    @lru_cache(maxsize=1)
    def get_service() -> DatasetService:
        return DatasetService(data_dir=data_dir)

    app = FastAPI(
        title="AI Orbit Dataset API",
        description="Thin demo API over pre-generated AI Orbit canonical dataset files.",
        version="1.0.0",
    )

    @app.get("/health", response_model=HealthResponse)
    def health(service: DatasetService = Depends(get_service)) -> HealthResponse:
        return HealthResponse(
            status="ok",
            entities_loaded=service.entities_loaded,
            relationships_loaded=service.relationships_loaded,
        )

    @app.get("/stats", response_model=StatsResponse)
    def stats(service: DatasetService = Depends(get_service)) -> StatsResponse:
        return StatsResponse.model_validate(service.stats())

    @app.get("/entities", response_model=list[Entity])
    def entities(
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=500),
        service: DatasetService = Depends(get_service),
    ) -> list[Entity]:
        return service.list_entities(
            entity_type=type,
            category=category,
            offset=offset,
            limit=limit,
        )

    @app.get("/entities/{entity_id}", response_model=Entity)
    def entity(entity_id: str, service: DatasetService = Depends(get_service)) -> Entity:
        found = service.get_entity(entity_id)
        if found is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return found

    @app.get("/relationships", response_model=list[Relationship])
    def relationships(
        type: str | None = Query(default=None),
        source_id: str | None = Query(default=None),
        target_id: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        service: DatasetService = Depends(get_service),
    ) -> list[Relationship]:
        return service.list_relationships(
            relationship_type=type,
            source_id=source_id,
            target_id=target_id,
            offset=offset,
            limit=limit,
        )

    @app.get("/entities/{entity_id}/relationships", response_model=list[RelationshipViewResponse])
    def entity_relationships(
        entity_id: str,
        type: str | None = Query(default=None),
        service: DatasetService = Depends(get_service),
    ) -> list[RelationshipViewResponse]:
        views = service.relationship_views_for_entity(entity_id, relationship_type=type)
        if views is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return [relationship_view_response(view) for view in views]

    @app.get("/search", response_model=list[EntitySearchResult])
    def search(
        q: str = Query(min_length=1),
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=100),
        service: DatasetService = Depends(get_service),
    ) -> list[EntitySearchResult]:
        matches = service.index.search_entities(
            q,
            entity_type=type,
            category=category,
            limit=limit,
        )
        return [search_result_from_match(match) for match in matches]

    return app


app = create_app()
