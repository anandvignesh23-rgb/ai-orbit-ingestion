import uuid

import pytest

from src.utils.ids import (
    APP_NAMESPACE,
    generate_entity_id,
    generate_relationship_id,
)


def test_generate_entity_id_is_deterministic() -> None:
    first = generate_entity_id("company", "openai")
    second = generate_entity_id("company", "openai")

    assert first == second
    assert uuid.UUID(first).version == 5


def test_generate_entity_id_normalizes_type_and_key() -> None:
    assert generate_entity_id(" Company ", " OpenAI ") == generate_entity_id(
        "company",
        "openai",
    )


def test_generate_entity_id_changes_by_type() -> None:
    company_id = generate_entity_id("company", "langchain")
    repository_id = generate_entity_id("repository", "langchain")

    assert company_id != repository_id


def test_generate_relationship_id_uses_stable_edge_key() -> None:
    source_id = generate_entity_id("company", "openai")
    target_id = generate_entity_id("tool", "chatgpt")

    expected = str(
        uuid.uuid5(
            APP_NAMESPACE,
            f"relationship:{source_id}|develops|{target_id}",
        )
    )

    assert (
        generate_relationship_id(source_id, "develops", target_id)
        == expected
    )


def test_id_generators_reject_blank_values() -> None:
    with pytest.raises(ValueError):
        generate_entity_id("company", "")

    with pytest.raises(ValueError):
        generate_relationship_id("", "develops", "target")
