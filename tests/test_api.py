from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import create_app
from src.pipeline import IngestionPipeline


def make_client(tmp_path) -> TestClient:
    pipeline = IngestionPipeline(data_dir=tmp_path)
    assert pipeline.run() is True
    return TestClient(create_app(data_dir=tmp_path))


def test_api_health_and_stats_load_generated_dataset_without_running_ingestion(tmp_path) -> None:
    client = make_client(tmp_path)

    health = client.get("/health")
    stats = client.get("/stats")

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


def test_api_lists_and_fetches_entities(tmp_path) -> None:
    client = make_client(tmp_path)

    entities = client.get("/entities", params={"type": "tool", "limit": 5}).json()
    entity_id = entities[0]["id"]
    entity = client.get(f"/entities/{entity_id}")

    assert len(entities) == 5
    assert all(item["entity_type"] == "tool" for item in entities)
    assert entity.status_code == 200
    assert entity.json()["id"] == entity_id
    assert client.get("/entities/not-found").status_code == 404


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

    relationships = client.get("/relationships", params={"type": "develops", "limit": 1}).json()
    relationship = relationships[0]
    source_views = client.get(f"/entities/{relationship['source_id']}/relationships").json()
    target_views = client.get(
        f"/entities/{relationship['target_id']}/relationships",
        params={"type": "developed_by"},
    ).json()

    assert len(relationships) == 1
    assert relationship["relationship_type"] == "develops"
    assert any(view["direction"] == "outgoing" for view in source_views)
    assert any(
        view["direction"] == "incoming"
        and view["effective_relationship_type"] == "developed_by"
        for view in target_views
    )
    assert client.get("/entities/not-found/relationships").status_code == 404
