from __future__ import annotations

from src.models.entity import Entity
from src.models.enums import EntityType, RelationshipType
from src.models.relationship import Evidence, Relationship
from src.relationships.rules import build_entity_index, metadata_name_values
from src.utils.ids import generate_relationship_id
from src.normalization.names import normalize_name


class RelationshipMapper:
    def map_relationships(self, entities: list[Entity]) -> list[Relationship]:
        index = build_entity_index(entities)
        relationships: dict[str, Relationship] = {}

        for entity in entities:
            entity_type = EntityType(str(entity.entity_type))
            if entity_type == EntityType.TOOL:
                self._map_company_develops_product(
                    entity,
                    index,
                    relationships,
                )
                self._map_tool_solves_tasks(entity, index, relationships)
            elif entity_type == EntityType.MODEL:
                self._map_company_develops_product(
                    entity,
                    index,
                    relationships,
                )
            elif entity_type == EntityType.MCP:
                self._map_mcp_integrations(entity, index, relationships)
            elif entity_type == EntityType.DEVICE:
                self._map_device_runs_models(entity, index, relationships)
            if entity_type != EntityType.COLLECTION:
                self._map_entity_collections(entity, index, relationships)
            else:
                self._map_collection_members(entity, index, relationships)

        return sorted(relationships.values(), key=lambda relationship: relationship.id)

    def _map_company_develops_product(
        self,
        entity: Entity,
        index: dict[EntityType, dict[str, Entity]],
        relationships: dict[str, Relationship],
    ) -> None:
        for field, company_name in metadata_name_values(entity, "provider", "company", "developer"):
            company = self._find_entity(index, EntityType.COMPANY, company_name)
            if company is None:
                continue
            self._add_relationship(
                relationships,
                source=company,
                relationship_type=RelationshipType.DEVELOPS,
                target=entity,
                confidence=0.95,
                note=f"{_metadata_label(field)} metadata links {company.name} to {entity.name}",
            )

    def _map_tool_solves_tasks(
        self,
        tool: Entity,
        index: dict[EntityType, dict[str, Entity]],
        relationships: dict[str, Relationship],
    ) -> None:
        for field, task_name in metadata_name_values(tool, "tasks", "solves", "task"):
            task = self._find_entity(index, EntityType.TASK, task_name)
            if task is None:
                continue
            self._add_relationship(
                relationships,
                source=tool,
                relationship_type=RelationshipType.SOLVES,
                target=task,
                confidence=0.92,
                note=f"{_metadata_label(field)} metadata links {tool.name} to {task.name}",
            )

    def _map_mcp_integrations(
        self,
        mcp: Entity,
        index: dict[EntityType, dict[str, Entity]],
        relationships: dict[str, Relationship],
    ) -> None:
        for field, tool_name in metadata_name_values(mcp, "integrates_with", "tools", "supported_tools"):
            tool = self._find_entity(index, EntityType.TOOL, tool_name)
            if tool is None:
                continue
            self._add_relationship(
                relationships,
                source=mcp,
                relationship_type=RelationshipType.INTEGRATES_WITH,
                target=tool,
                confidence=0.9,
                note=f"{_metadata_label(field)} metadata links {mcp.name} to {tool.name}",
            )

    def _map_device_runs_models(
        self,
        device: Entity,
        index: dict[EntityType, dict[str, Entity]],
        relationships: dict[str, Relationship],
    ) -> None:
        for field, model_name in metadata_name_values(device, "runs_models", "supported_models", "models"):
            model = self._find_entity(index, EntityType.MODEL, model_name)
            if model is None:
                continue
            self._add_relationship(
                relationships,
                source=device,
                relationship_type=RelationshipType.RUNS,
                target=model,
                confidence=0.9,
                note=f"{_metadata_label(field)} metadata links {device.name} to {model.name}",
            )

    def _map_entity_collections(
        self,
        entity: Entity,
        index: dict[EntityType, dict[str, Entity]],
        relationships: dict[str, Relationship],
    ) -> None:
        for field, collection_name in metadata_name_values(entity, "collection", "collections", "member_of"):
            collection = self._find_entity(index, EntityType.COLLECTION, collection_name)
            if collection is None:
                continue
            self._add_relationship(
                relationships,
                source=entity,
                relationship_type=RelationshipType.PART_OF_COLLECTION,
                target=collection,
                confidence=0.88,
                note=f"{_metadata_label(field)} metadata links {entity.name} to {collection.name}",
            )

    def _map_collection_members(
        self,
        collection: Entity,
        index: dict[EntityType, dict[str, Entity]],
        relationships: dict[str, Relationship],
    ) -> None:
        for field, member_name in metadata_name_values(collection, "items", "members", "includes"):
            member = self._find_collection_member(index, member_name)
            if member is None:
                continue
            self._add_relationship(
                relationships,
                source=member,
                relationship_type=RelationshipType.PART_OF_COLLECTION,
                target=collection,
                confidence=0.88,
                note=f"{_metadata_label(field)} metadata links {member.name} to {collection.name}",
            )

    def _find_entity(
        self,
        index: dict[EntityType, dict[str, Entity]],
        entity_type: EntityType,
        name: str,
    ) -> Entity | None:
        return index.get(entity_type, {}).get(normalize_name(name, entity_type=str(entity_type)))

    def _find_collection_member(
        self,
        index: dict[EntityType, dict[str, Entity]],
        name: str,
    ) -> Entity | None:
        for entity_type in [
            EntityType.TOOL,
            EntityType.MODEL,
            EntityType.REPOSITORY,
            EntityType.MCP,
            EntityType.TASK,
            EntityType.CREATIVE,
            EntityType.PERSONAL,
            EntityType.DEVICE,
            EntityType.ROBOT,
            EntityType.NEWS,
            EntityType.VIDEO,
            EntityType.COMPANY,
        ]:
            entity = self._find_entity(index, entity_type, name)
            if entity is not None:
                return entity
        return None

    def _add_relationship(
        self,
        relationships: dict[str, Relationship],
        *,
        source: Entity,
        relationship_type: RelationshipType,
        target: Entity,
        confidence: float,
        note: str,
    ) -> None:
        if source.id == target.id:
            return

        relationship_id = generate_relationship_id(
            source.id,
            str(relationship_type),
            target.id,
        )
        evidence = _evidence_for_entities(source, target, note=note)
        if relationship_id in relationships:
            relationship = relationships[relationship_id]
            added = _append_unique_evidence(relationship, evidence)
            if added:
                relationship.confidence = min(
                    1.0,
                    max(relationship.confidence, confidence) + (0.01 * added),
                )
            return

        relationships[relationship_id] = Relationship(
            id=relationship_id,
            source_id=source.id,
            relationship_type=relationship_type,
            target_id=target.id,
            confidence=confidence,
            evidence=evidence,
        )


def _evidence_for_entities(*entities: Entity, note: str) -> list[Evidence]:
    evidence: list[Evidence] = []
    for entity in entities:
        if entity.sources:
            evidence.extend(
                Evidence(source_name=source.name, source_url=source.url, note=note)
                for source in entity.sources
            )
        elif entity.url:
            evidence.append(Evidence(source_name="Entity URL", source_url=entity.url, note=note))

    if evidence:
        return _unique_evidence(evidence)
    return [
        Evidence(
            source_name="Relationship mapper",
            source_url="https://example.com",
            note=note,
        )
    ]


def _append_unique_evidence(relationship: Relationship, evidence: list[Evidence]) -> int:
    existing_keys = {_evidence_key(item) for item in relationship.evidence}
    added = 0
    for item in evidence:
        key = _evidence_key(item)
        if key in existing_keys:
            continue
        relationship.evidence.append(item)
        existing_keys.add(key)
        added += 1
    return added


def _unique_evidence(evidence: list[Evidence]) -> list[Evidence]:
    unique: list[Evidence] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in evidence:
        key = _evidence_key(item)
        if key in seen:
            continue
        unique.append(item)
        seen.add(key)
    return unique


def _evidence_key(evidence: Evidence) -> tuple[str, str, str | None]:
    return (evidence.source_name, str(evidence.source_url), evidence.note)


def _metadata_label(field: str) -> str:
    return field.replace("_", " ").capitalize()
