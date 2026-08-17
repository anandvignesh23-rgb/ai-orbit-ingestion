from __future__ import annotations

from src.models import Relationship, RelationshipType
from src.relationship_views import build_relationship_views
from src.utils.ids import generate_relationship_id


def test_relationship_views_materialize_inverse_edges_without_mutating_canonical_relationship() -> None:
    relationship = Relationship(
        id=generate_relationship_id("company-openai", "develops", "tool-chatgpt"),
        source_id="company-openai",
        relationship_type=RelationshipType.DEVELOPS,
        target_id="tool-chatgpt",
        confidence=0.95,
    )

    views = build_relationship_views([relationship])

    assert views == [
        {
            "view_id": f"{relationship.id}:outgoing",
            "relationship_id": relationship.id,
            "source_id": "company-openai",
            "target_id": "tool-chatgpt",
            "relationship_type": "develops",
            "canonical_relationship_type": "develops",
            "direction": "outgoing",
            "confidence": 0.95,
            "derived": False,
        },
        {
            "view_id": f"{relationship.id}:incoming",
            "relationship_id": relationship.id,
            "source_id": "tool-chatgpt",
            "target_id": "company-openai",
            "relationship_type": "developed_by",
            "canonical_relationship_type": "develops",
            "direction": "incoming",
            "confidence": 0.95,
            "derived": True,
        },
    ]
    assert relationship.source_id == "company-openai"
    assert relationship.target_id == "tool-chatgpt"


def test_relationship_views_can_skip_inverse_generation() -> None:
    relationship = Relationship(
        id="relationship-1",
        source_id="company-1",
        relationship_type=RelationshipType.INTEGRATES_WITH,
        target_id="tool-1",
        confidence=0.8,
    )

    views = build_relationship_views([relationship], include_inverse=False)

    assert len(views) == 1
    assert views[0]["relationship_type"] == "integrates_with"
    assert views[0]["derived"] is False


def test_relationship_views_use_collection_inverse_type() -> None:
    relationship = Relationship(
        id="relationship-collection-1",
        source_id="tool-1",
        relationship_type=RelationshipType.PART_OF_COLLECTION,
        target_id="collection-1",
        confidence=0.88,
    )

    views = build_relationship_views([relationship])

    assert views[0]["relationship_type"] == "contains"
    assert views[0]["source_id"] == "collection-1"
    assert views[0]["target_id"] == "tool-1"
    assert views[0]["derived"] is True
    assert views[1]["relationship_type"] == "part_of_collection"
    assert views[1]["derived"] is False
