from __future__ import annotations

import httpx

from src.sources.youtube import YOUTUBE_SEARCH_URL, YouTubeSource


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def video_item(
    *,
    video_id: str = "abc123",
    title: str = "AI agents explained",
    channel: str = "AI Channel",
) -> dict:
    return {
        "id": {"kind": "youtube#video", "videoId": video_id},
        "snippet": {
            "publishedAt": "2026-08-01T00:00:00Z",
            "channelId": "channel-1",
            "title": title,
            "description": "A video about AI agents.",
            "channelTitle": channel,
        },
    }


def test_youtube_discover_skips_when_api_key_missing() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"items": [video_item()]})

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="",
        client=make_client(handler),
    ).discover()

    assert records == []
    assert called is False


def test_youtube_discover_successful_response_maps_video_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(YOUTUBE_SEARCH_URL)
        assert request.url.params["q"] == "AI agents"
        assert request.url.params["key"] == "test-key"
        return httpx.Response(200, json={"items": [video_item()]})

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    record = records[0]
    assert record.source_name == "youtube"
    assert record.record_type == "video"
    assert record.source_url == "https://www.youtube.com/watch?v=abc123"
    assert record.payload == {
        "video_id": "abc123",
        "title": "AI agents explained",
        "description": "A video about AI agents.",
        "channel": "AI Channel",
        "channel_id": "channel-1",
        "published_at": "2026-08-01T00:00:00Z",
        "video_url": "https://www.youtube.com/watch?v=abc123",
        "query": "AI agents",
    }


def test_youtube_discover_queries_each_configured_query() -> None:
    seen_queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        seen_queries.append(query)
        return httpx.Response(
            200,
            json={"items": [video_item(video_id=f"{query}-id", title=query)]},
        )

    records = YouTubeSource(
        queries=["AI agents", "AI robotics"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert seen_queries == ["AI agents", "AI robotics"]
    assert [record.payload["title"] for record in records] == ["AI agents", "AI robotics"]


def test_youtube_discover_deduplicates_video_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [video_item(video_id="same-id")]})

    records = YouTubeSource(
        queries=["AI agents", "large language models"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert len(records) == 1


def test_youtube_discover_retries_timeout_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("timed out")
        return httpx.Response(200, json={"items": [video_item()]})

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert attempts == 2
    assert len(records) == 1


def test_youtube_discover_skips_malformed_and_missing_required_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    video_item(),
                    {"id": {"videoId": "missing-title"}, "snippet": {}},
                    "not-a-dict",
                ]
            },
        )

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    assert records[0].payload["video_id"] == "abc123"


def test_youtube_discover_rate_limit_or_forbidden_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "quota exceeded"}})

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert records == []


def test_youtube_discover_server_error_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert records == []


def test_youtube_discover_malformed_json_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not-json")

    records = YouTubeSource(
        queries=["AI agents"],
        api_key="test-key",
        client=make_client(handler),
    ).discover()

    assert records == []


def test_youtube_extract_returns_candidate_without_global_processing() -> None:
    source = YouTubeSource(queries=[], api_key="test-key")
    record = source._record_from_item(video_item(), query="AI agents")

    assert record is not None
    assert source.extract(record) is record
