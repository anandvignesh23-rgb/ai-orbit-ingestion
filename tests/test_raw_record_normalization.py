from __future__ import annotations

from src.models import EntityType
from src.normalization import RawRecordNormalizer
from src.sources.base import RawRecord


def test_normalizes_github_repository_record_to_entity() -> None:
    record = RawRecord(
        source_name="github",
        source_url="https://github.com/langchain-ai/langchain",
        record_type="repository",
        payload={
            "name": "langchain",
            "full_name": "langchain-ai/langchain",
            "owner": "langchain-ai",
            "description": "Framework for <b>agents</b>.",
            "html_url": "https://www.github.com/langchain-ai/langchain/",
            "stars": 100,
            "primary_language": "Python",
            "last_updated": "2026-08-01T00:00:00Z",
            "topics": ["llm", "agents"],
        },
    )

    entity = RawRecordNormalizer().normalize(record)

    assert entity.entity_type == "repository"
    assert entity.name == "langchain"
    assert str(entity.url).rstrip("/") == "https://github.com/langchain-ai/langchain"
    assert entity.description == "Framework for agents."
    assert entity.metadata["owner"] == "langchain-ai"
    assert entity.metadata["primary_language"] == "Python"
    assert entity.sources[0].name == "github"


def test_normalizes_huggingface_model_record_to_entity() -> None:
    record = RawRecord(
        source_name="huggingface",
        source_url="https://huggingface.co/Qwen/Qwen3-0.6B",
        record_type="model",
        payload={
            "model_id": "Qwen/Qwen3-0.6B",
            "name": "Qwen3-0.6B",
            "provider": "Qwen",
            "downloads": 1000,
            "pipeline_task": "text-generation",
            "tags": ["license:apache-2.0"],
            "license": "apache-2.0",
            "last_modified": "2026-08-01T00:00:00Z",
            "model_url": "https://huggingface.co/Qwen/Qwen3-0.6B",
        },
    )

    entity = RawRecordNormalizer().normalize(record)

    assert entity.entity_type == "model"
    assert entity.metadata["provider"] == "Qwen"
    assert entity.metadata["pipeline_task"] == "text-generation"
    assert entity.metadata["modalities"] == ["text"]
    assert entity.metadata["model_id"] == "Qwen/Qwen3-0.6B"


def test_normalizes_rss_news_record_to_entity() -> None:
    record = RawRecord(
        source_name="rss",
        source_url="https://example.com/news?utm_source=test",
        record_type="news",
        payload={
            "title": "OpenAI releases model",
            "description": "<p>Model&nbsp;news</p>",
            "article_url": "https://example.com/news?utm_source=test",
            "published_at": "Mon, 17 Aug 2026 10:00:00 GMT",
            "publisher": "Example AI",
            "feed_name": "Example AI",
            "feed_url": "https://example.com/feed.xml",
        },
    )

    entity = RawRecordNormalizer().normalize(record)

    assert entity.entity_type == "news"
    assert entity.name == "OpenAI releases model"
    assert entity.description == "Model news"
    assert str(entity.url).rstrip("/") == "https://example.com/news"
    assert entity.metadata["publisher"] == "Example AI"


def test_normalizes_youtube_video_record_to_entity() -> None:
    record = RawRecord(
        source_name="youtube",
        source_url="https://www.youtube.com/watch?v=abc123",
        record_type="video",
        payload={
            "video_id": "abc123",
            "title": "AI agents explained",
            "description": "A video about agents.",
            "channel": "AI Channel",
            "channel_id": "channel-1",
            "published_at": "2026-08-01T00:00:00Z",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "query": "AI agents",
        },
    )

    entity = RawRecordNormalizer().normalize(record)

    assert entity.entity_type == "video"
    assert entity.metadata["video_id"] == "abc123"
    assert entity.metadata["channel"] == "AI Channel"


def test_normalizes_curated_seed_record_to_entity_with_provenance() -> None:
    record = RawRecord(
        source_name="curated",
        source_url="https://openai.com",
        record_type="company",
        payload={
            "name": "OpenAI",
            "description": "AI company.",
            "url": "https://openai.com",
            "categories": ["research"],
            "metadata": {"official_domain": "openai.com"},
            "sources": [{"name": "Official site", "url": "https://openai.com"}],
            "seed_file": "companies.json",
        },
    )

    entity = RawRecordNormalizer().normalize(record)

    assert entity.entity_type == "company"
    assert entity.categories == ["research"]
    assert entity.metadata["official_domain"] == "openai.com"
    assert entity.metadata["seed_file"] == "companies.json"
    assert entity.sources[0].name == "Official site"


def test_normalizes_product_metadata_first_seen_recently_added_and_multiple_sources() -> None:
    record = RawRecord(
        source_name="curated",
        source_url="https://chatgpt.com",
        record_type="tool",
        payload={
            "name": "ChatGPT",
            "description": "AI assistant for writing, coding, and analysis.",
            "url": "https://chatgpt.com",
            "categories": ["productivity"],
            "metadata": {"provider": "OpenAI"},
            "sources": [
                {
                    "name": "Official product page",
                    "url": "https://chatgpt.com",
                    "source_type": "official_site",
                    "is_official": True,
                },
                {
                    "name": "AI Orbit curated seed",
                    "url": "https://example.com/chatgpt",
                    "source_type": "curated",
                },
            ],
        },
    )

    entity = RawRecordNormalizer().normalize(record)

    assert entity.display is not None
    assert entity.display.provider_name == "OpenAI"
    assert entity.display.short_description == "AI assistant for writing, coding, and analysis."
    assert entity.display.recently_added is True
    assert entity.pipeline_metadata is not None
    assert entity.pipeline_metadata.first_seen_at is not None
    assert entity.pipeline_metadata.last_seen_at is not None
    assert entity.pipeline_metadata.source_count == 2
    assert [source.source_type for source in entity.sources] == ["official_site", "curated"]
    assert entity.sources[0].is_official is True
    assert all(source.retrieved_at is not None for source in entity.sources)


def test_raw_record_normalization_ids_are_deterministic() -> None:
    record = RawRecord(
        source_name="curated",
        source_url="https://example.com/task",
        record_type="task",
        payload={"name": "Summarization", "url": "https://example.com/task"},
    )
    normalizer = RawRecordNormalizer()

    assert normalizer.normalize(record).id == normalizer.normalize(record).id


def test_raw_record_normalizer_rejects_unknown_record_type() -> None:
    record = RawRecord(source_name="fixture", record_type="unknown", payload={})

    try:
        RawRecordNormalizer().normalize(record)
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_normalize_many_preserves_order() -> None:
    records = [
        RawRecord(
            source_name="curated",
            record_type="task",
            source_url=f"https://example.com/task-{index}",
            payload={"name": f"Task {index}", "url": f"https://example.com/task-{index}"},
        )
        for index in range(2)
    ]

    entities = RawRecordNormalizer().normalize_many(records)

    assert [entity.name for entity in entities] == ["Task 0", "Task 1"]
    assert all(entity.entity_type == EntityType.TASK for entity in entities)
