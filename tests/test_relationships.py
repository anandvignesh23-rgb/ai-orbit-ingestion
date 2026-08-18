from __future__ import annotations

from src.models import Entity, EntityType, RelationshipType, SourceReference
from src.relationships import RelationshipMapper
from src.utils.ids import generate_entity_id, generate_relationship_id


def make_entity(
    entity_type: EntityType,
    name: str,
    *,
    url: str | None = None,
    categories: list[str] | None = None,
    metadata: dict | None = None,
) -> Entity:
    return Entity(
        id=generate_entity_id(str(entity_type), url or name),
        entity_type=entity_type,
        name=name,
        url=url,
        categories=categories or [],
        sources=[
            SourceReference(
                name=f"{name} source",
                url=url or f"https://example.com/{name.lower().replace(' ', '-')}",
            )
        ],
        metadata=metadata or {},
    )


def by_edge(relationships):
    return {
        (relationship.source_id, relationship.relationship_type, relationship.target_id): relationship
        for relationship in relationships
    }


def test_relationship_mapper_creates_required_relationship_types() -> None:
    openai = make_entity(EntityType.COMPANY, "OpenAI", url="https://openai.com")
    chatgpt = make_entity(
        EntityType.TOOL,
        "ChatGPT",
        url="https://chatgpt.com",
        metadata={"provider": "OpenAI", "tasks": ["Question Answering"]},
    )
    task = make_entity(EntityType.TASK, "Question Answering")
    model = make_entity(
        EntityType.MODEL,
        "GPT-4o",
        metadata={"provider": "OpenAI"},
    )
    mcp = make_entity(
        EntityType.MCP,
        "ChatGPT MCP Server",
        metadata={"integrates_with": ["ChatGPT"]},
    )
    device = make_entity(
        EntityType.DEVICE,
        "OpenAI Device",
        metadata={"runs_models": ["GPT-4o"]},
    )

    relationships = RelationshipMapper().map_relationships(
        [openai, chatgpt, task, model, mcp, device]
    )
    edges = by_edge(relationships)

    assert (openai.id, "develops", chatgpt.id) in edges
    assert (openai.id, "develops", model.id) in edges
    assert (chatgpt.id, "solves", task.id) in edges
    assert (mcp.id, "integrates_with", chatgpt.id) in edges
    assert (device.id, "runs", model.id) in edges


def test_relationship_ids_are_deterministic_edge_keys() -> None:
    company = make_entity(EntityType.COMPANY, "Anthropic")
    tool = make_entity(EntityType.TOOL, "Claude", metadata={"provider": "Anthropic"})

    relationship = RelationshipMapper().map_relationships([company, tool])[0]

    assert relationship.id == generate_relationship_id(company.id, "develops", tool.id)


def test_relationship_mapper_deduplicates_identical_edges() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    tool = make_entity(
        EntityType.TOOL,
        "ChatGPT",
        metadata={"provider": "OpenAI", "company": "OpenAI", "developer": "OpenAI"},
    )

    relationships = RelationshipMapper().map_relationships([company, tool])

    assert len(relationships) == 1
    assert relationships[0].relationship_type == RelationshipType.DEVELOPS


def test_relationship_mapper_accumulates_evidence_for_repeated_edge_signals() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    tool = make_entity(
        EntityType.TOOL,
        "ChatGPT",
        metadata={"provider": "OpenAI", "company": "OpenAI", "developer": "OpenAI"},
    )

    relationship = RelationshipMapper().map_relationships([company, tool])[0]
    notes = {evidence.note for evidence in relationship.evidence}

    assert relationship.confidence == 0.99
    assert len(relationship.evidence) == 6
    assert "Provider metadata links OpenAI to ChatGPT" in notes
    assert "Company metadata links OpenAI to ChatGPT" in notes
    assert "Developer metadata links OpenAI to ChatGPT" in notes


def test_relationship_mapper_includes_multiple_provenance_records_as_evidence() -> None:
    company = make_entity(EntityType.COMPANY, "Anthropic")
    tool = make_entity(EntityType.TOOL, "Claude", metadata={"provider": "Anthropic"})
    tool.sources.append(
        SourceReference(
            name="Directory profile",
            url="https://example.com/directories/claude",
        )
    )

    relationship = RelationshipMapper().map_relationships([company, tool])[0]
    source_names = {evidence.source_name for evidence in relationship.evidence}

    assert source_names == {"Anthropic source", "Claude source", "Directory profile"}


def test_relationship_mapper_does_not_create_dangling_relationships() -> None:
    tool = make_entity(
        EntityType.TOOL,
        "Unknown Provider Tool",
        metadata={"provider": "Missing Company", "tasks": ["Missing Task"]},
    )

    relationships = RelationshipMapper().map_relationships([tool])

    assert relationships == []


def test_relationship_mapper_uses_normalized_names_for_matching() -> None:
    company = make_entity(EntityType.COMPANY, "Hugging Face")
    model = make_entity(EntityType.MODEL, "BERT", metadata={"provider": "HuggingFace"})

    relationships = RelationshipMapper().map_relationships([company, model])

    assert len(relationships) == 1
    assert relationships[0].source_id == company.id
    assert relationships[0].target_id == model.id


def test_relationship_mapper_adds_evidence_and_confidence() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI", url="https://openai.com")
    model = make_entity(EntityType.MODEL, "GPT-4o", metadata={"provider": "OpenAI"})

    relationship = RelationshipMapper().map_relationships([company, model])[0]

    assert relationship.confidence == 0.95
    assert relationship.evidence[0].source_name == "OpenAI source"
    assert "Provider metadata" in relationship.evidence[0].note


def test_relationship_mapper_avoids_self_relations() -> None:
    tool = make_entity(
        EntityType.TOOL,
        "ChatGPT",
        metadata={"tasks": ["ChatGPT"]},
    )

    relationships = RelationshipMapper().map_relationships([tool])

    assert relationships == []


def test_relationship_mapper_maps_explicit_entity_collection_membership() -> None:
    collection = make_entity(EntityType.COLLECTION, "AI Agents Collection")
    tool = make_entity(
        EntityType.TOOL,
        "CrewAI",
        metadata={"collections": ["AI Agents Collection"]},
    )

    relationships = RelationshipMapper().map_relationships([collection, tool])
    edges = by_edge(relationships)

    assert (tool.id, "part_of_collection", collection.id) in edges
    relationship = edges[(tool.id, "part_of_collection", collection.id)]
    assert relationship.relationship_type == RelationshipType.PART_OF_COLLECTION
    assert relationship.confidence == 0.88
    assert "Collections metadata links CrewAI to AI Agents Collection" in {
        evidence.note for evidence in relationship.evidence
    }


def test_relationship_mapper_maps_explicit_collection_member_lists() -> None:
    model = make_entity(EntityType.MODEL, "GPT-4o")
    collection = make_entity(
        EntityType.COLLECTION,
        "OpenAI Models",
        metadata={"members": ["GPT-4o", "Missing Model"]},
    )

    relationships = RelationshipMapper().map_relationships([model, collection])

    assert len(relationships) == 1
    assert relationships[0].source_id == model.id
    assert relationships[0].relationship_type == RelationshipType.PART_OF_COLLECTION
    assert relationships[0].target_id == collection.id


def test_relationship_mapper_maps_repository_owner_to_company() -> None:
    company = make_entity(EntityType.COMPANY, "Hugging Face")
    repository = make_entity(
        EntityType.REPOSITORY,
        "transformers",
        metadata={"owner": "huggingface"},
    )

    relationships = RelationshipMapper().map_relationships([company, repository])
    edges = by_edge(relationships)

    assert (company.id, "develops", repository.id) in edges
    assert edges[(company.id, "develops", repository.id)].confidence == 0.9


def test_relationship_mapper_maps_repository_topics_to_tasks() -> None:
    task = make_entity(
        EntityType.TASK,
        "Retrieval Augmented Generation",
        metadata={"curated": True},
    )
    task.categories = ["rag"]
    repository = make_entity(
        EntityType.REPOSITORY,
        "llama_index",
        categories=["developer-tools", "open-source", "rag"],
        metadata={"topics": ["rag"]},
    )

    relationships = RelationshipMapper().map_relationships([task, repository])
    edges = by_edge(relationships)

    assert (repository.id, "solves", task.id) in edges
    assert edges[(repository.id, "solves", task.id)].confidence == 0.82


def test_relationship_mapper_maps_category_collection_membership() -> None:
    collection = make_entity(
        EntityType.COLLECTION,
        "RAG Systems Collection",
    )
    collection.categories = ["developer-tools", "open-source", "rag"]
    repository = make_entity(
        EntityType.REPOSITORY,
        "langchain",
        categories=["agents", "developer-tools", "open-source", "rag"],
    )

    relationships = RelationshipMapper().map_relationships([collection, repository])
    edges = by_edge(relationships)

    assert (repository.id, "part_of_collection", collection.id) in edges
    assert edges[(repository.id, "part_of_collection", collection.id)].confidence == 0.8


def test_relationship_mapper_returns_relationships_with_valid_references() -> None:
    company = make_entity(EntityType.COMPANY, "OpenAI")
    tool = make_entity(EntityType.TOOL, "ChatGPT", metadata={"provider": "OpenAI"})
    relationships = RelationshipMapper().map_relationships([company, tool])
    entity_ids = {company.id, tool.id}

    assert relationships
    assert all(relationship.source_id in entity_ids for relationship in relationships)
    assert all(relationship.target_id in entity_ids for relationship in relationships)
