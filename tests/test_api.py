from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.pipeline import IngestionPipeline


def make_client(tmp_path) -> TestClient:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True
    return TestClient(create_app(data_dir=tmp_path))


def test_api_health_and_stats_load_generated_dataset_without_running_ingestion(tmp_path) -> None:
    client = make_client(tmp_path)

    info = client.get("/info")
    health = client.get("/health")
    stats = client.get("/stats")

    assert info.status_code == 200
    assert info.json() == {
        "name": "AI Orbit Data Ingestion Pipeline",
        "status": "online",
        "description": "API serving normalized AI ecosystem entities and relationships.",
        "url": "http://testserver",
        "docs": "http://testserver/docs",
        "health": "http://testserver/health",
        "stats": "http://testserver/stats",
        "search": "http://testserver/search?q=agent",
    }
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "entities_loaded": 283,
        "relationships_loaded": 171,
    }
    assert stats.status_code == 200
    assert stats.json()["entities"] == 283
    assert stats.json()["relationships"] == 171
    assert stats.json()["entity_types"]["tool"] == 45
    assert stats.json()["validation_errors"] == 0
    assert stats.json()["average_relationships_per_entity"] > 0


def test_root_serves_presentable_landing_page(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI Orbit Data Ingestion Pipeline" in response.text
    assert '<a class="button primary" href="/docs">Explore API Docs</a>' in response.text
    assert "Live Dataset Metrics" in response.text
    assert ">283</strong><span>Total Entities</span>" in response.text
    assert ">171</strong><span>Total Relationships</span>" in response.text
    assert "Pipeline" in response.text
    assert "Data Sources" in response.text
    assert "Engineering Highlights" in response.text


def test_api_lists_and_fetches_entities(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.get("/entities", params={"type": "tool", "limit": 5, "offset": 0})
    entities = response.json()
    entity_id = entities[0]["id"]
    entity = client.get(f"/entities/{entity_id}")

    assert response.status_code == 200
    assert len(entities) == 5
    assert all(item["entity_type"] == "tool" for item in entities)
    assert entity.status_code == 200
    assert entity.json()["id"] == entity_id
    assert client.get("/entities/not-found").status_code == 404
    assert client.get("/entities", params={"limit": 101}).status_code == 422


def test_api_search_uses_dataset_search_helpers(tmp_path) -> None:
    client = make_client(tmp_path)

    response = client.get("/search", params={"q": "chatgpt", "type": "tool"})
    category_response = client.get("/search", params={"q": "developer tools", "limit": 5})

    assert response.status_code == 200
    results = response.json()
    assert results
    assert results[0]["name"] == "ChatGPT"
    assert results[0]["score"] > 0
    assert category_response.status_code == 200
    assert category_response.json()


def test_api_relationship_endpoints_expose_canonical_and_entity_views(tmp_path) -> None:
    client = make_client(tmp_path)

    relationships = client.get("/relationships", params={"relationship_type": "develops", "limit": 1}).json()
    relationship = relationships[0]
    source_views = client.get(f"/entities/{relationship['source_id']}/relationships").json()
    target_views = client.get(
        f"/entities/{relationship['target_id']}/relationships",
        params={"relationship_type": "developed_by"},
    ).json()

    assert len(relationships) == 1
    assert relationship["relationship_type"] == "develops"
    assert source_views["entity_id"] == relationship["source_id"]
    assert any(view["direction"] == "outgoing" for view in source_views["outgoing"])
    assert any(
        view["direction"] == "incoming"
        and view["effective_relationship_type"] == "developed_by"
        for view in target_views["incoming"]
    )
    assert client.get("/entities/not-found/relationships").status_code == 404
    assert client.get("/relationships", params={"limit": 101}).status_code == 422


def test_api_startup_fails_when_required_dataset_files_are_missing(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="validation_report.json"):
        create_app(data_dir=tmp_path)
