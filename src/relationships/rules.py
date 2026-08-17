from __future__ import annotations

from src.models.entity import Entity
from src.models.enums import EntityType
from src.normalization.names import normalize_name


def entity_key(entity: Entity) -> str:
    return normalize_name(entity.name, entity_type=str(entity.entity_type))


def metadata_names(entity: Entity, *fields: str) -> list[str]:
    names: list[str] = []
    for _, name in metadata_name_values(entity, *fields):
        names.append(name)
    return names


def metadata_name_values(entity: Entity, *fields: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for field in fields:
        value = entity.metadata.get(field)
        if isinstance(value, list):
            values.extend((field, str(item)) for item in value if str(item).strip())
        elif value is not None and str(value).strip():
            values.append((field, str(value)))
    return values


def build_entity_index(entities: list[Entity]) -> dict[EntityType, dict[str, Entity]]:
    index: dict[EntityType, dict[str, Entity]] = {}
    for entity in entities:
        entity_type = EntityType(str(entity.entity_type))
        index.setdefault(entity_type, {})[entity_key(entity)] = entity
    return index
