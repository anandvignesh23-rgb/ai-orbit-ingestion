from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.models.entity import Entity
from src.models.enums import EntityType
from src.normalization.urls import canonical_domain

DEFAULT_CATEGORIES = {
    "agents",
    "rag",
    "code-generation",
    "image-generation",
    "video-generation",
    "speech",
    "computer-vision",
    "developer-tools",
    "productivity",
    "research",
    "robotics",
    "hardware",
    "multimodal",
    "open-source",
}

DEFAULT_ALIASES = {
    "agent": "agents",
    "ai-agents": "agents",
    "audio": "speech",
    "code": "code-generation",
    "coding": "code-generation",
    "cv": "computer-vision",
    "developer": "developer-tools",
    "devtools": "developer-tools",
    "device": "hardware",
    "devices": "hardware",
    "image": "image-generation",
    "images": "image-generation",
    "models": "research",
    "oss": "open-source",
    "robot": "robotics",
    "robots": "robotics",
    "vision": "computer-vision",
    "voice": "speech",
}

KEYWORD_RULES = {
    "agents": ["agent", "autonomous", "workflow", "tool use"],
    "rag": ["rag", "retrieval", "vector", "embedding", "knowledge base"],
    "code-generation": ["code", "coding", "developer", "programming", "ide"],
    "image-generation": ["image generation", "text-to-image", "diffusion", "stable diffusion"],
    "video-generation": ["video generation", "text-to-video", "video"],
    "speech": ["speech", "voice", "audio", "transcription", "asr"],
    "computer-vision": ["computer vision", "vision", "object detection", "image classification"],
    "developer-tools": ["developer", "api", "sdk", "repository", "github", "mcp"],
    "productivity": ["assistant", "productivity", "workspace", "meeting", "notes"],
    "research": ["research", "paper", "benchmark", "model", "dataset"],
    "robotics": ["robot", "robotics", "embodied"],
    "hardware": ["hardware", "device", "chip", "gpu", "edge"],
    "multimodal": ["multimodal", "text image", "vision-language", "audio vision"],
    "open-source": ["open source", "open-source", "github", "apache", "mit license"],
}


class EntityClassifier:
    def __init__(self, config_path: str | Path = "config/categories.yaml") -> None:
        self.categories, self.aliases = _load_category_config(Path(config_path))

    def classify(self, entity: Entity) -> Entity:
        categories = set()
        for category in entity.categories:
            canonical = self.canonicalize_category(category)
            if canonical:
                categories.add(canonical)

        categories.update(self._categories_from_entity_type(entity))
        categories.update(self._categories_from_metadata(entity))
        categories.update(self._categories_from_text(entity))
        categories.update(self._categories_from_domain(entity))

        return entity.model_copy(update={"categories": sorted(categories)})

    def classify_many(self, entities: list[Entity]) -> list[Entity]:
        return [self.classify(entity) for entity in entities]

    def canonicalize_category(self, category: str | None) -> str | None:
        if category is None:
            return None
        normalized = str(category).strip().lower().replace("_", "-").replace(" ", "-")
        if not normalized:
            return None
        canonical = self.aliases.get(normalized, normalized)
        if canonical in self.categories:
            return canonical
        return None

    def _categories_from_entity_type(self, entity: Entity) -> set[str]:
        entity_type = EntityType(str(entity.entity_type))
        if entity_type in {EntityType.ROBOT}:
            return {"robotics"}
        if entity_type in {EntityType.DEVICE}:
            return {"hardware"}
        if entity_type in {EntityType.REPOSITORY, EntityType.MCP}:
            return {"developer-tools", "open-source"}
        if entity_type == EntityType.MODEL:
            return {"research"}
        if entity_type == EntityType.CREATIVE:
            return {"image-generation", "video-generation"}
        if entity_type == EntityType.PERSONAL:
            return {"productivity"}
        return set()

    def _categories_from_metadata(self, entity: Entity) -> set[str]:
        metadata_text = _metadata_text(entity.metadata)
        categories = self._categories_from_blob(metadata_text)

        pipeline_task = str(entity.metadata.get("pipeline_task", "")).lower()
        if pipeline_task in {"text-generation", "text-classification", "sentence-similarity"}:
            categories.add("research")
        if pipeline_task == "text-to-image":
            categories.add("image-generation")
        if pipeline_task == "text-to-video":
            categories.add("video-generation")
        if pipeline_task in {"automatic-speech-recognition", "text-to-speech"}:
            categories.add("speech")
        if pipeline_task in {"image-classification", "object-detection"}:
            categories.add("computer-vision")

        language = str(entity.metadata.get("primary_language", "")).strip()
        if language:
            categories.add("developer-tools")

        license_value = str(entity.metadata.get("license", "")).lower()
        if license_value in {"apache-2.0", "mit", "bsd-3-clause"}:
            categories.add("open-source")

        return categories

    def _categories_from_text(self, entity: Entity) -> set[str]:
        text = " ".join(
            value
            for value in [
                entity.name,
                entity.description or "",
                " ".join(str(source.name) for source in entity.sources),
            ]
            if value
        )
        return self._categories_from_blob(text)

    def _categories_from_domain(self, entity: Entity) -> set[str]:
        domain = canonical_domain(str(entity.url)) if entity.url else ""
        if domain == "github.com":
            return {"developer-tools", "open-source"}
        if domain in {"huggingface.co", "arxiv.org", "paperswithcode.com"}:
            return {"research", "open-source"}
        return set()

    def _categories_from_blob(self, text: str) -> set[str]:
        normalized = text.lower().replace("_", "-")
        categories: set[str] = set()
        for category, keywords in KEYWORD_RULES.items():
            if any(keyword in normalized for keyword in keywords):
                categories.add(category)
        return categories


def _load_category_config(path: Path) -> tuple[set[str], dict[str, str]]:
    if not path.exists():
        return set(DEFAULT_CATEGORIES), dict(DEFAULT_ALIASES)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    categories = {
        str(category).strip().lower()
        for category in data.get("categories", [])
        if str(category).strip()
    }
    aliases = {
        str(alias).strip().lower().replace("_", "-").replace(" ", "-"): str(canonical)
        .strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
        for alias, canonical in (data.get("aliases", {}) or {}).items()
    }
    return categories or set(DEFAULT_CATEGORIES), {**DEFAULT_ALIASES, **aliases}


def _metadata_text(metadata: dict[str, Any]) -> str:
    values: list[str] = []
    for value in metadata.values():
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif isinstance(value, dict):
            values.append(_metadata_text(value))
        elif value is not None:
            values.append(str(value))
    return " ".join(values)
