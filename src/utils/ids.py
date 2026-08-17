from __future__ import annotations

import uuid

APP_NAMESPACE = uuid.UUID("4e551f44-4a27-5a3b-90c8-3dd7d383a3d9")


def _stable_uuid(key: str) -> str:
    return str(uuid.uuid5(APP_NAMESPACE, key))


def generate_entity_id(entity_type: str, canonical_key: str) -> str:
    normalized_type = entity_type.strip().lower()
    normalized_key = canonical_key.strip().lower()
    if not normalized_type:
        raise ValueError("entity_type is required")
    if not normalized_key:
        raise ValueError("canonical_key is required")
    return _stable_uuid(f"entity:{normalized_type}:{normalized_key}")


def generate_relationship_id(
    source_id: str,
    relationship_type: str,
    target_id: str,
) -> str:
    normalized_source = source_id.strip()
    normalized_type = relationship_type.strip().lower()
    normalized_target = target_id.strip()
    if not normalized_source:
        raise ValueError("source_id is required")
    if not normalized_type:
        raise ValueError("relationship_type is required")
    if not normalized_target:
        raise ValueError("target_id is required")
    return _stable_uuid(
        f"relationship:{normalized_source}|{normalized_type}|{normalized_target}"
    )
