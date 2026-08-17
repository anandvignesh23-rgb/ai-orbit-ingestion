from __future__ import annotations

import csv
import json
import subprocess
import sys

from src.models import Entity, EntityType, Relationship, RelationshipType, SourceReference
from src.query import diff_datasets, inverse_relationship_type, load_dataset
from src.utils.ids import generate_entity_id, generate_relationship_id


def make_entity(entity_type: EntityType, name: str, *, metadata: dict | None = None) -> Entity:
    return Entity(
        id=generate_entity_id(str(entity_type), name),
        entity_type=entity_type,
        name=name,
        categories=["developer-tools"] if name == "ChatGPT" else [],
        sources=[
            SourceReference(
                name=f"{name} source",
                url=f"https://example.com/{name.lower().replace(' ', '-')}",
            )
        ],
        metadata=metadata or {},
    )


def write_dataset(tmp_path) -> tuple[Entity, Entity, Entity, Entity]:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    tool = make_entity(
        EntityType.TOOL,
        "ChatGPT",
        metadata={"provider": "OpenAI"},
    )
    task = make_entity(EntityType.TASK, "Question Answering")
    orphan = make_entity(EntityType.MODEL, "Unlinked Model")
    relationships = [
        Relationship(
            id=generate_relationship_id(company.id, "develops", tool.id),
            source_id=company.id,
            relationship_type=RelationshipType.DEVELOPS,
            target_id=tool.id,
            confidence=0.95,
        ),
        Relationship(
            id=generate_relationship_id(tool.id, "solves", task.id),
            source_id=tool.id,
            relationship_type=RelationshipType.SOLVES,
            target_id=task.id,
            confidence=0.92,
        ),
    ]
    manifest = {
        "run_mode": "test",
        "success": True,
        "summary": {
            "raw_records": 3,
            "canonical_entities": 3,
            "relationships": 2,
            "duplicates_merged": 0,
            "possible_duplicates": 0,
            "critical_errors": 0,
        },
    }

    (tmp_path / "entities.json").write_text(
        json.dumps(
            [
                company.model_dump(mode="json"),
                tool.model_dump(mode="json"),
                task.model_dump(mode="json"),
                orphan.model_dump(mode="json"),
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "relationships.json").write_text(
        json.dumps([relationship.model_dump(mode="json") for relationship in relationships]),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return company, tool, task, orphan


def test_dataset_index_summarizes_manifest_counts(tmp_path) -> None:
    write_dataset(tmp_path)

    summary = load_dataset(tmp_path).summary()

    assert summary["run_mode"] == "test"
    assert summary["success"] is True
    assert summary["canonical_entities"] == 3
    assert summary["relationships"] == 2


def test_dataset_index_searches_entities_with_filters(tmp_path) -> None:
    _, tool, _, _ = write_dataset(tmp_path)

    matches = load_dataset(tmp_path).search_entities(
        "chat",
        entity_type="tool",
        category="developer-tools",
    )

    assert len(matches) == 1
    assert matches[0].entity.id == tool.id
    assert matches[0].score > 0


def test_dataset_index_search_handles_product_search_cases(tmp_path) -> None:
    _, tool, _, _ = write_dataset(tmp_path)
    index = load_dataset(tmp_path)

    exact = index.search_entities("ChatGPT")
    case_insensitive = index.search_entities("cHaTgPt")
    partial = index.search_entities("chat")
    category = index.search_entities("developer tools")
    no_results = index.search_entities("not-a-real-ai-orbit-record")

    assert exact[0].entity.id == tool.id
    assert exact[0].score == 1.0
    assert case_insensitive[0].entity.id == tool.id
    assert partial[0].entity.id == tool.id
    assert category[0].entity.id == tool.id
    assert no_results == []


def test_dataset_index_returns_neighborhood(tmp_path) -> None:
    company, tool, task, _ = write_dataset(tmp_path)

    neighborhood = load_dataset(tmp_path).neighborhood("ChatGPT")

    assert neighborhood is not None
    assert neighborhood.entity.id == tool.id
    assert [relationship.source_id for relationship in neighborhood.incoming] == [company.id]
    assert [relationship.target_id for relationship in neighborhood.outgoing] == [task.id]
    assert {entity.id for entity in neighborhood.related_entities} == {company.id, task.id}


def test_dataset_index_relationship_lookup_helpers(tmp_path) -> None:
    company, tool, task, _ = write_dataset(tmp_path)
    index = load_dataset(tmp_path)

    assert index.get_relationships_for_entity(tool.id)
    assert index.get_incoming_relationships(tool.id)[0].source_id == company.id
    assert index.get_outgoing_relationships(tool.id)[0].target_id == task.id
    assert {entity.id for entity in index.get_related_entities(tool.id)} == {company.id, task.id}
    assert index.filter_by_type("tool") == [tool]
    assert index.filter_by_category("developer-tools") == [tool]


def test_dataset_index_relationship_views_include_inverse_types(tmp_path) -> None:
    company, tool, task, _ = write_dataset(tmp_path)
    index = load_dataset(tmp_path)

    tool_views = index.get_relationship_views_for_entity(tool.id)
    company_views = index.get_relationship_views_for_entity(company.id)
    developed_by = index.get_relationship_views_for_entity(tool.id, relationship_type="developed_by")
    solves = index.get_relationship_views_for_entity(tool.id, relationship_type="solves")

    assert inverse_relationship_type("develops") == "developed_by"
    assert {view.effective_relationship_type for view in tool_views} == {"developed_by", "solves"}
    assert company_views[0].effective_relationship_type == "develops"
    assert developed_by[0].direction == "incoming"
    assert developed_by[0].related_entity.id == company.id
    assert solves[0].direction == "outgoing"
    assert solves[0].related_entity.id == task.id


def test_inverse_relationship_type_supports_collection_membership() -> None:
    assert inverse_relationship_type("part_of_collection") == "contains"


def test_dataset_index_computes_graph_analytics(tmp_path) -> None:
    _, tool, _, orphan = write_dataset(tmp_path)

    analytics = load_dataset(tmp_path).analytics(limit=2)

    assert analytics.entity_count == 4
    assert analytics.relationship_count == 2
    assert analytics.relationship_type_counts == {"develops": 1, "solves": 1}
    assert analytics.entity_type_counts == {
        "company": 1,
        "model": 1,
        "task": 1,
        "tool": 1,
    }
    assert analytics.orphan_count == 1
    assert analytics.orphans[0].id == orphan.id
    assert analytics.top_connected[0].id == tool.id
    assert analytics.top_connected[0].total == 2


def test_dataset_index_exports_graph_csv(tmp_path) -> None:
    company, tool, _, _ = write_dataset(tmp_path)
    output_dir = tmp_path / "csv"

    exported = load_dataset(tmp_path).export_csv(output_dir)

    with open(exported["nodes"], encoding="utf-8", newline="") as file:
        nodes = list(csv.DictReader(file))
    with open(exported["edges"], encoding="utf-8", newline="") as file:
        edges = list(csv.DictReader(file))

    assert exported == {
        "nodes": str(output_dir / "nodes.csv"),
        "edges": str(output_dir / "edges.csv"),
    }
    assert len(nodes) == 4
    assert len(edges) == 2
    assert nodes[0]["id"] == company.id
    assert nodes[1]["label"] == "ChatGPT"
    assert nodes[1]["categories"] == "developer-tools"
    assert edges[0]["source_label"] == "OpenAI"
    assert edges[0]["target_label"] == "ChatGPT"
    assert edges[0]["relationship_type"] == "develops"


def test_diff_datasets_reports_added_removed_and_changed_records(tmp_path) -> None:
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    company, tool, task, orphan = write_dataset(before_dir)

    added = make_entity(EntityType.TOOL, "New Tool")
    changed_tool = tool.model_copy(
        update={"description": "Updated product description."}
    )
    added_relationship = Relationship(
        id=generate_relationship_id(company.id, "develops", added.id),
        source_id=company.id,
        relationship_type=RelationshipType.DEVELOPS,
        target_id=added.id,
        confidence=0.95,
    )
    after_entities = [company, changed_tool, task, added]
    after_relationships = [
        Relationship(
            id=generate_relationship_id(company.id, "develops", tool.id),
            source_id=company.id,
            relationship_type=RelationshipType.DEVELOPS,
            target_id=tool.id,
            confidence=0.95,
        ),
        added_relationship,
    ]
    (after_dir / "entities.json").write_text(
        json.dumps([entity.model_dump(mode="json") for entity in after_entities]),
        encoding="utf-8",
    )
    (after_dir / "relationships.json").write_text(
        json.dumps([relationship.model_dump(mode="json") for relationship in after_relationships]),
        encoding="utf-8",
    )

    diff = diff_datasets(before_dir, after_dir)

    assert [entity.id for entity in diff.added_entities] == [added.id]
    assert [entity.id for entity in diff.removed_entities] == [orphan.id]
    assert diff.changed_entities[0].id == tool.id
    assert diff.changed_entities[0].changed_fields == ["description"]
    assert [relationship.id for relationship in diff.added_relationships] == [added_relationship.id]
    assert len(diff.removed_relationships) == 1
    assert diff.removed_relationships[0].relationship_type == "solves"


def test_query_dataset_cli_search_outputs_json(tmp_path) -> None:
    _, tool, _, _ = write_dataset(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "--data-dir",
            str(tmp_path),
            "search",
            "chatgpt",
            "--type",
            "tool",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload[0]["id"] == tool.id
    assert payload[0]["name"] == "ChatGPT"


def test_query_dataset_cli_analytics_outputs_json(tmp_path) -> None:
    write_dataset(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "--data-dir",
            str(tmp_path),
            "analytics",
            "--limit",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["relationship_type_counts"] == {"develops": 1, "solves": 1}
    assert payload["orphan_count"] == 1
    assert len(payload["top_connected"]) == 1


def test_query_dataset_cli_exports_csv(tmp_path) -> None:
    write_dataset(tmp_path)
    output_dir = tmp_path / "graph-csv"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "--data-dir",
            str(tmp_path),
            "export-csv",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload == {
        "nodes": str(output_dir / "nodes.csv"),
        "edges": str(output_dir / "edges.csv"),
    }
    assert (output_dir / "nodes.csv").exists()
    assert (output_dir / "edges.csv").exists()


def test_query_dataset_cli_diffs_datasets(tmp_path) -> None:
    before_dir = tmp_path / "before-cli"
    after_dir = tmp_path / "after-cli"
    before_dir.mkdir()
    after_dir.mkdir()
    write_dataset(before_dir)
    company, tool, task, _ = write_dataset(after_dir)
    added = make_entity(EntityType.TOOL, "Extra Tool")
    relationships = [
        Relationship(
            id=generate_relationship_id(company.id, "develops", tool.id),
            source_id=company.id,
            relationship_type=RelationshipType.DEVELOPS,
            target_id=tool.id,
            confidence=0.95,
        ),
        Relationship(
            id=generate_relationship_id(tool.id, "solves", task.id),
            source_id=tool.id,
            relationship_type=RelationshipType.SOLVES,
            target_id=task.id,
            confidence=0.92,
        ),
    ]
    entities = [company, tool, task, added]
    (after_dir / "entities.json").write_text(
        json.dumps([entity.model_dump(mode="json") for entity in entities]),
        encoding="utf-8",
    )
    (after_dir / "relationships.json").write_text(
        json.dumps([relationship.model_dump(mode="json") for relationship in relationships]),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/query_dataset.py",
            "diff",
            "--before",
            str(before_dir),
            "--after",
            str(after_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["added_entities"][0]["name"] == "Extra Tool"
    assert payload["removed_entities"][0]["name"] == "Unlinked Model"
