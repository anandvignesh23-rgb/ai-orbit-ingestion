from __future__ import annotations

import httpx

from src.sources.huggingface import HUGGINGFACE_MODELS_URL, HuggingFaceSource


def model_item(
    *,
    model_id: str = "meta-llama/Llama-3.1-8B-Instruct",
    author: str | None = "meta-llama",
    pipeline_tag: str | None = "text-generation",
) -> dict:
    return {
        "modelId": model_id,
        "id": model_id,
        "author": author,
        "downloads": 123456,
        "pipeline_tag": pipeline_tag,
        "tags": ["transformers", "license:llama3.1", "text-generation"],
        "lastModified": "2026-08-01T00:00:00.000Z",
    }


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_huggingface_discover_successful_response_maps_model_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(HUGGINGFACE_MODELS_URL)
        assert request.url.params["pipeline_tag"] == "text-generation"
        return httpx.Response(200, json=[model_item()])

    source = HuggingFaceSource(
        tasks=["text-generation"],
        client=make_client(handler),
    )

    records = source.discover()

    assert len(records) == 1
    record = records[0]
    assert record.source_name == "huggingface"
    assert record.record_type == "model"
    assert record.source_url == "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct"
    assert record.payload == {
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "name": "Llama-3.1-8B-Instruct",
        "provider": "meta-llama",
        "downloads": 123456,
        "pipeline_task": "text-generation",
        "tags": ["transformers", "license:llama3.1", "text-generation"],
        "license": "llama3.1",
        "last_modified": "2026-08-01T00:00:00.000Z",
        "model_url": "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
    }


def test_huggingface_discover_queries_each_configured_task() -> None:
    seen_tasks: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        task = request.url.params["pipeline_tag"]
        seen_tasks.append(task)
        return httpx.Response(
            200,
            json=[
                model_item(
                    model_id=f"owner/{task}-model",
                    pipeline_tag=task,
                )
            ],
        )

    records = HuggingFaceSource(
        tasks=["text-generation", "text-to-image"],
        client=make_client(handler),
    ).discover()

    assert seen_tasks == ["text-generation", "text-to-image"]
    assert [record.payload["pipeline_task"] for record in records] == [
        "text-generation",
        "text-to-image",
    ]


def test_huggingface_discover_retries_timeout_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("timed out")
        return httpx.Response(200, json=[model_item()])

    records = HuggingFaceSource(
        tasks=["automatic-speech-recognition"],
        client=make_client(handler),
    ).discover()

    assert attempts == 2
    assert len(records) == 1


def test_huggingface_discover_handles_missing_optional_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "sentence-transformers/all-MiniLM-L6-v2",
                    "tags": [],
                }
            ],
        )

    records = HuggingFaceSource(
        tasks=["sentence-similarity"],
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    assert records[0].payload["provider"] == "sentence-transformers"
    assert records[0].payload["downloads"] is None
    assert records[0].payload["pipeline_task"] == "sentence-similarity"
    assert records[0].payload["license"] is None


def test_huggingface_discover_skips_malformed_and_missing_required_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                model_item(),
                {"downloads": 50},
                "not-a-dict",
            ],
        )

    records = HuggingFaceSource(
        tasks=["text-generation"],
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    assert records[0].payload["model_id"] == "meta-llama/Llama-3.1-8B-Instruct"


def test_huggingface_discover_rate_limit_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "too many requests"})

    records = HuggingFaceSource(
        tasks=["text-generation"],
        client=make_client(handler),
    ).discover()

    assert records == []


def test_huggingface_discover_server_error_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    records = HuggingFaceSource(
        tasks=["text-generation"],
        client=make_client(handler),
    ).discover()

    assert records == []


def test_huggingface_discover_malformed_json_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not-json")

    records = HuggingFaceSource(
        tasks=["text-generation"],
        client=make_client(handler),
    ).discover()

    assert records == []


def test_huggingface_extract_returns_candidate_without_global_processing() -> None:
    source = HuggingFaceSource(tasks=[])
    record = source._record_from_item(model_item())

    assert record is not None
    assert source.extract(record) is record
