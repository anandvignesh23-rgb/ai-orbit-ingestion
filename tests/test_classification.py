from __future__ import annotations

from pathlib import Path

from src.classification import EntityClassifier
from src.models import Entity, EntityType, SourceReference
from src.utils.ids import generate_entity_id


def make_entity(
    entity_type: EntityType,
    name: str,
    *,
    description: str | None = None,
    url: str | None = None,
    categories: list[str] | None = None,
    metadata: dict | None = None,
) -> Entity:
    return Entity(
        id=generate_entity_id(str(entity_type), url or name),
        entity_type=entity_type,
        name=name,
        description=description,
        url=url,
        categories=categories or [],
        sources=[
            SourceReference(
                name="Fixture",
                url=url or "https://example.com/source",
            )
        ],
        metadata=metadata or {},
    )


def test_classifier_canonicalizes_existing_category_aliases() -> None:
    entity = make_entity(
        EntityType.TOOL,
        "Agent Tool",
        categories=["ai-agents", "devtools", "unknown-category"],
    )

    classified = EntityClassifier().classify(entity)

    assert classified.categories == ["agents", "developer-tools"]


def test_classifier_uses_text_keywords_for_tool_categories() -> None:
    entity = make_entity(
        EntityType.TOOL,
        "Cursor",
        description="AI coding assistant for developer workflows and agents.",
    )

    classified = EntityClassifier().classify(entity)

    assert "agents" in classified.categories
    assert "code-generation" in classified.categories
    assert "developer-tools" in classified.categories


def test_classifier_uses_model_pipeline_task_and_license_metadata() -> None:
    entity = make_entity(
        EntityType.MODEL,
        "Stable Diffusion",
        metadata={
            "pipeline_task": "text-to-image",
            "license": "apache-2.0",
            "tags": ["diffusion", "multimodal"],
        },
    )

    classified = EntityClassifier().classify(entity)

    assert "image-generation" in classified.categories
    assert "multimodal" in classified.categories
    assert "open-source" in classified.categories
    assert "research" in classified.categories


def test_classifier_uses_repository_type_metadata_and_github_domain() -> None:
    entity = make_entity(
        EntityType.REPOSITORY,
        "LangChain",
        description="Framework for RAG and agent applications.",
        url="https://github.com/langchain-ai/langchain",
        metadata={"primary_language": "Python", "topics": ["rag", "llm"]},
    )

    classified = EntityClassifier().classify(entity)

    assert "agents" in classified.categories
    assert "developer-tools" in classified.categories
    assert "open-source" in classified.categories
    assert "rag" in classified.categories


def test_classifier_uses_entity_type_defaults_for_hardware_robotics_and_personal() -> None:
    classifier = EntityClassifier()

    device = classifier.classify(make_entity(EntityType.DEVICE, "NVIDIA Jetson"))
    robot = classifier.classify(make_entity(EntityType.ROBOT, "Figure 02"))
    personal = classifier.classify(make_entity(EntityType.PERSONAL, "Pi"))

    assert device.categories == ["hardware"]
    assert robot.categories == ["robotics"]
    assert personal.categories == ["productivity"]


def test_classifier_marks_creative_tools_for_generation_categories() -> None:
    entity = make_entity(
        EntityType.CREATIVE,
        "Runway",
        description="Video generation and image generation tools.",
    )

    classified = EntityClassifier().classify(entity)

    assert "image-generation" in classified.categories
    assert "video-generation" in classified.categories


def test_classifier_uses_domain_rules_for_huggingface_models() -> None:
    entity = make_entity(
        EntityType.MODEL,
        "Qwen3",
        url="https://huggingface.co/Qwen/Qwen3-0.6B",
    )

    classified = EntityClassifier().classify(entity)

    assert "open-source" in classified.categories
    assert "research" in classified.categories


def test_classifier_can_load_custom_category_config(tmp_path: Path) -> None:
    config = tmp_path / "categories.yaml"
    config.write_text(
        """
categories:
  - research
  - productivity
aliases:
  papers: research
""",
        encoding="utf-8",
    )
    entity = make_entity(EntityType.NEWS, "Paper roundup", categories=["papers"])

    classified = EntityClassifier(config_path=config).classify(entity)

    assert classified.categories == ["research"]


def test_classifier_returns_new_entity_without_mutating_input() -> None:
    entity = make_entity(EntityType.TOOL, "Notebook assistant", categories=["productivity"])

    classified = EntityClassifier().classify(entity)

    assert entity.categories == ["productivity"]
    assert classified is not entity


def test_classifier_classify_many() -> None:
    entities = [
        make_entity(EntityType.ROBOT, "Robot arm"),
        make_entity(EntityType.DEVICE, "AI device"),
    ]

    classified = EntityClassifier().classify_many(entities)

    assert [entity.categories for entity in classified] == [["robotics"], ["hardware"]]
