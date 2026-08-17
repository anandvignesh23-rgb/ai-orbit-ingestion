from __future__ import annotations

import pytest

from src.deduplication import EntityResolver, merge_entities, score_duplicate
from src.models import Entity, EntityType, SourceReference
from src.utils.ids import generate_entity_id


def make_entity(
    entity_type: EntityType,
    name: str,
    *,
    url: str | None = None,
    categories: list[str] | None = None,
    metadata: dict | None = None,
    description: str | None = None,
    source_name: str = "Fixture",
) -> Entity:
    canonical_key = url or name
    return Entity(
        id=generate_entity_id(str(entity_type), canonical_key),
        entity_type=entity_type,
        name=name,
        description=description,
        url=url,
        categories=categories or [],
        sources=[
            SourceReference(
                name=source_name,
                url=url or "https://example.com/source",
            )
        ],
        metadata=metadata or {},
    )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (
            make_entity(EntityType.COMPANY, "OpenAI"),
            make_entity(EntityType.COMPANY, "Open AI"),
        ),
        (
            make_entity(EntityType.COMPANY, "OpenAI"),
            make_entity(EntityType.COMPANY, "OpenAI Inc."),
        ),
        (
            make_entity(EntityType.COMPANY, "Hugging Face"),
            make_entity(EntityType.COMPANY, "HuggingFace"),
        ),
        (
            make_entity(EntityType.COMPANY, "Anthropic", url="https://anthropic.com"),
            make_entity(EntityType.COMPANY, "Anthropic PBC", url="https://www.anthropic.com/"),
        ),
        (
            make_entity(EntityType.TOOL, "ChatGPT", url="https://chatgpt.com"),
            make_entity(EntityType.TOOL, "Chat GPT", url="https://www.chatgpt.com/"),
        ),
        (
            make_entity(
                EntityType.TOOL,
                "Cursor",
                metadata={"provider": "Anysphere"},
                categories=["developer-tools"],
            ),
            make_entity(
                EntityType.TOOL,
                "Cursor",
                metadata={"provider": "Anysphere"},
                categories=["developer-tools", "code-generation"],
            ),
        ),
        (
            make_entity(
                EntityType.MODEL,
                "Llama 3",
                metadata={"provider": "Meta", "license": "llama-license"},
            ),
            make_entity(
                EntityType.MODEL,
                "Llama-3",
                metadata={"provider": "Meta", "license": "llama-license"},
            ),
        ),
        (
            make_entity(
                EntityType.REPOSITORY,
                "langchain",
                url="https://github.com/langchain-ai/langchain",
                metadata={"owner": "langchain-ai", "primary_language": "Python"},
            ),
            make_entity(
                EntityType.REPOSITORY,
                "LangChain",
                url="http://www.github.com/langchain-ai/langchain/",
                metadata={"owner": "langchain-ai", "primary_language": "Python"},
            ),
        ),
        (
            make_entity(EntityType.DEVICE, "NVIDIA Jetson Orin", url="https://nvidia.com/jetson"),
            make_entity(EntityType.DEVICE, "Nvidia Jetson Orin", url="https://www.nvidia.com/jetson/"),
        ),
        (
            make_entity(EntityType.ROBOT, "Figure 02", url="https://figure.ai"),
            make_entity(EntityType.ROBOT, "Figure-02", url="https://www.figure.ai/"),
        ),
        (
            make_entity(EntityType.MCP, "GitHub MCP Server", url="https://github.com/github/github-mcp-server"),
            make_entity(EntityType.MCP, "Github MCP Server", url="https://www.github.com/github/github-mcp-server/"),
        ),
        (
            make_entity(EntityType.CREATIVE, "Runway Gen-3", url="https://runwayml.com"),
            make_entity(EntityType.CREATIVE, "Runway Gen 3", url="https://www.runwayml.com/"),
        ),
    ],
)
def test_labeled_positive_pairs_merge(left: Entity, right: Entity) -> None:
    score = score_duplicate(left, right)

    assert score.decision == "merge"
    assert score.total_score >= 0.90
    assert score.reasons


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (
            make_entity(EntityType.TOOL, "Claude"),
            make_entity(EntityType.TOOL, "Claude Desktop"),
        ),
        (
            make_entity(EntityType.COMPANY, "LangChain"),
            make_entity(EntityType.REPOSITORY, "LangChain"),
        ),
        (
            make_entity(EntityType.COMPANY, "Meta"),
            make_entity(EntityType.COMPANY, "Meta AI"),
        ),
        (
            make_entity(EntityType.COMPANY, "OpenAI"),
            make_entity(EntityType.COMPANY, "Anthropic"),
        ),
        (
            make_entity(
                EntityType.REPOSITORY,
                "langchain",
                url="https://github.com/langchain-ai/langchain",
            ),
            make_entity(
                EntityType.REPOSITORY,
                "openai-python",
                url="https://github.com/openai/openai-python",
            ),
        ),
        (
            make_entity(EntityType.TOOL, "Claude", metadata={"provider": "Anthropic"}),
            make_entity(EntityType.TOOL, "Claude Code", metadata={"provider": "Anthropic"}),
        ),
        (
            make_entity(EntityType.MODEL, "GPT-4o", metadata={"provider": "OpenAI"}),
            make_entity(EntityType.MODEL, "GPT-4.1", metadata={"provider": "OpenAI"}),
        ),
        (
            make_entity(EntityType.COMPANY, "Mistral AI", metadata={"official_domain": "mistral.ai"}),
            make_entity(EntityType.COMPANY, "Meta AI", metadata={"official_domain": "ai.meta.com"}),
        ),
        (
            make_entity(EntityType.TOOL, "Gemini", url="https://gemini.google.com"),
            make_entity(EntityType.TOOL, "Gemini CLI", url="https://github.com/google-gemini/gemini-cli"),
        ),
        (
            make_entity(EntityType.DEVICE, "Rabbit R1", url="https://rabbit.tech"),
            make_entity(EntityType.DEVICE, "Humane AI Pin", url="https://hu.ma.ne"),
        ),
        (
            make_entity(EntityType.COLLECTION, "AI Agents"),
            make_entity(EntityType.COLLECTION, "AI Hardware"),
        ),
        (
            make_entity(EntityType.PERSONAL, "Pi"),
            make_entity(EntityType.PERSONAL, "Perplexity"),
        ),
        (
            make_entity(EntityType.NEWS, "OpenAI releases model"),
            make_entity(EntityType.NEWS, "Anthropic releases model"),
        ),
    ],
)
def test_labeled_negative_pairs_do_not_merge(left: Entity, right: Entity) -> None:
    score = score_duplicate(left, right)

    assert score.decision != "merge"


def test_partial_similarity_does_not_force_merge() -> None:
    score = score_duplicate(
        make_entity(EntityType.TOOL, "Claude"),
        make_entity(EntityType.TOOL, "Claude Desktop"),
    )

    assert score.name_score < 0.75
    assert score.decision == "keep"


def test_review_threshold_zone_is_configurable() -> None:
    score = score_duplicate(
        make_entity(EntityType.COMPANY, "Meta"),
        make_entity(EntityType.COMPANY, "Meta AI"),
        review_threshold=0.70,
    )

    assert score.decision == "review"


def test_repository_url_scoring_uses_full_path_not_domain_only() -> None:
    score = score_duplicate(
        make_entity(
            EntityType.REPOSITORY,
            "LangChain",
            url="https://github.com/langchain-ai/langchain",
        ),
        make_entity(
            EntityType.REPOSITORY,
            "LangChain",
            url="https://github.com/openai/openai-python",
        ),
    )

    assert score.url_score == 0.0
    assert score.decision != "merge"


def test_merge_entities_preserves_provenance_categories_and_best_description() -> None:
    primary = make_entity(
        EntityType.TOOL,
        "ChatGPT",
        url="https://chatgpt.com",
        categories=["productivity"],
        metadata={"provider": "OpenAI", "supported_modalities": ["text"]},
        description="AI assistant.",
        source_name="Official",
    )
    duplicate = make_entity(
        EntityType.TOOL,
        "Chat GPT",
        url="https://chatgpt.com/",
        categories=["productivity", "developer-tools"],
        metadata={"provider": "OpenAI", "supported_modalities": ["text", "voice"]},
        description="AI assistant for writing, coding, and analysis.",
        source_name="Directory",
    )

    merged = merge_entities(primary, duplicate)

    assert merged.id == primary.id
    assert merged.name == "ChatGPT"
    assert merged.description == "AI assistant for writing, coding, and analysis."
    assert merged.categories == ["developer-tools", "productivity"]
    assert len(merged.sources) == 2
    assert merged.metadata["supported_modalities"] == ["text", "voice"]


def test_merge_entities_records_irreconcilable_metadata_conflicts() -> None:
    merged = merge_entities(
        make_entity(EntityType.COMPANY, "Acme", metadata={"headquarters": "Paris"}),
        make_entity(EntityType.COMPANY, "Acme", metadata={"headquarters": "Berlin"}),
    )

    assert merged.metadata["headquarters"] == "Paris"
    assert merged.metadata["conflicts"] == [
        {"field": "headquarters", "primary": "Paris", "duplicate": "Berlin", "chosen": "primary"}
    ]


def test_merge_entities_prefers_higher_priority_source_metadata() -> None:
    directory = make_entity(
        EntityType.TOOL,
        "Example Tool",
        metadata={"provider": "Open AI"},
        source_name="Directory",
    )
    official = make_entity(
        EntityType.TOOL,
        "Example Tool",
        metadata={"provider": "OpenAI"},
        source_name="Official product page",
    )
    official.sources[0].source_type = "official_site"
    official.sources[0].is_official = True
    directory.sources[0].source_type = "directory"

    merged = merge_entities(directory, official)

    assert merged.metadata["provider"] == "OpenAI"
    assert merged.metadata["conflicts"][0]["chosen"] == "duplicate"


def test_entity_resolver_merges_duplicates_and_flags_reviews() -> None:
    entities = [
        make_entity(EntityType.COMPANY, "OpenAI"),
        make_entity(EntityType.COMPANY, "Open AI"),
        make_entity(EntityType.COMPANY, "Meta"),
        make_entity(EntityType.COMPANY, "Meta AI"),
        make_entity(EntityType.COMPANY, "Anthropic"),
    ]

    result = EntityResolver(review_threshold=0.70).resolve(entities)

    assert result.merged_count == 1
    assert len(result.entities) == 4
    assert len(result.possible_duplicates) >= 1
