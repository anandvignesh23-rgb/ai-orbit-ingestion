from __future__ import annotations

import httpx

from src.sources.github import GITHUB_SEARCH_URL, GitHubSource


def repository_item(
    *,
    name: str = "langchain",
    full_name: str = "langchain-ai/langchain",
    html_url: str = "https://github.com/langchain-ai/langchain",
) -> dict:
    return {
        "name": name,
        "full_name": full_name,
        "owner": {"login": full_name.split("/")[0]},
        "description": "Build context-aware reasoning applications.",
        "html_url": html_url,
        "stargazers_count": 100000,
        "language": "Python",
        "updated_at": "2026-08-01T00:00:00Z",
        "topics": ["llm", "agents"],
    }


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_github_discover_successful_response_maps_repository_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(GITHUB_SEARCH_URL)
        return httpx.Response(200, json={"items": [repository_item()]})

    source = GitHubSource(queries=["topic:llm"], client=make_client(handler))

    records = source.discover()

    assert len(records) == 1
    record = records[0]
    assert record.source_name == "github"
    assert record.record_type == "repository"
    assert record.source_url == "https://github.com/langchain-ai/langchain"
    assert record.payload == {
        "name": "langchain",
        "full_name": "langchain-ai/langchain",
        "owner": "langchain-ai",
        "description": "Build context-aware reasoning applications.",
        "html_url": "https://github.com/langchain-ai/langchain",
        "stars": 100000,
        "primary_language": "Python",
        "last_updated": "2026-08-01T00:00:00Z",
        "topics": ["llm", "agents"],
    }


def test_github_discover_supports_pagination() -> None:
    seen_pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_pages.append(request.url.params["page"])
        page = request.url.params["page"]
        return httpx.Response(
            200,
            json={
                "items": [
                    repository_item(
                        name=f"repo-{page}",
                        full_name=f"owner/repo-{page}",
                        html_url=f"https://github.com/owner/repo-{page}",
                    )
                ]
            },
        )

    source = GitHubSource(
        queries=["topic:agents"],
        max_pages=2,
        client=make_client(handler),
    )

    records = source.discover()

    assert seen_pages == ["1", "2"]
    assert [record.payload["name"] for record in records] == ["repo-1", "repo-2"]


def test_github_discover_skips_malformed_and_missing_required_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    repository_item(),
                    {"name": "missing-url"},
                    "not-a-dict",
                ]
            },
        )

    records = GitHubSource(queries=["topic:rag"], client=make_client(handler)).discover()

    assert len(records) == 1
    assert records[0].payload["full_name"] == "langchain-ai/langchain"


def test_github_discover_retries_timeout_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("timed out")
        return httpx.Response(200, json={"items": [repository_item()]})

    records = GitHubSource(queries=["topic:mcp"], client=make_client(handler)).discover()

    assert attempts == 2
    assert len(records) == 1


def test_github_discover_rate_limit_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "123"},
            json={"message": "API rate limit exceeded"},
        )

    records = GitHubSource(queries=["topic:llm"], client=make_client(handler)).discover()

    assert records == []


def test_github_discover_server_error_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    records = GitHubSource(queries=["topic:llm"], client=make_client(handler)).discover()

    assert records == []


def test_github_discover_malformed_json_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not-json")

    records = GitHubSource(queries=["topic:llm"], client=make_client(handler)).discover()

    assert records == []


def test_github_extract_returns_candidate_without_global_processing() -> None:
    record = GitHubSource(queries=[]).extract(
        GitHubSource(queries=[], client=make_client(lambda request: httpx.Response(200)))._record_from_item(
            repository_item()
        )
    )

    assert record is not None
    assert record.record_type == "repository"
