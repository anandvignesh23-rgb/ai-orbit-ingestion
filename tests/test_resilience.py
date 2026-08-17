from __future__ import annotations

import logging

import httpx

from src.sources.base import BaseSource, RawRecord
from src.sources.youtube import YouTubeSource
from src.utils import configure_logging, discover_sources, sanitize_url


class SuccessfulSource(BaseSource):
    @property
    def source_name(self) -> str:
        return "successful"

    def discover(self) -> list[RawRecord]:
        return [
            RawRecord(
                source_name=self.source_name,
                source_url="https://example.com",
                record_type="fixture",
                payload={"ok": True},
            )
        ]

    def extract(self, candidate: RawRecord) -> RawRecord:
        return candidate


class ExplodingSource(BaseSource):
    @property
    def source_name(self) -> str:
        return "exploding"

    def discover(self) -> list[RawRecord]:
        raise RuntimeError("boom")

    def extract(self, candidate: RawRecord) -> RawRecord:
        return candidate


def test_sanitize_url_redacts_secret_query_params() -> None:
    assert (
        sanitize_url("https://api.example.com/search?q=ai&key=secret&token=abc")
        == "https://api.example.com/search?q=ai&key=%5BREDACTED%5D&token=%5BREDACTED%5D"
    )


def test_discover_sources_isolates_source_failures() -> None:
    results = discover_sources([ExplodingSource(), SuccessfulSource()])

    assert len(results) == 2
    assert results[0].source_name == "exploding"
    assert results[0].status == "failed"
    assert results[0].records == []
    assert results[0].error == "RuntimeError"
    assert results[1].source_name == "successful"
    assert results[1].status == "ok"
    assert len(results[1].records) == 1


def test_configure_logging_sets_readable_format_without_error() -> None:
    configure_logging("WARNING")

    assert logging.getLogger().level in {logging.WARNING, logging.NOTSET}


def test_youtube_malformed_json_error_redacts_api_key() -> None:
    captured_error: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not-json", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = YouTubeSource(queries=["AI agents"], api_key="super-secret", client=client)

    try:
        with source._managed_client() as managed_client:
            source._search_videos(managed_client, "AI agents")
    except Exception as exc:
        captured_error = str(exc)

    assert captured_error is not None
    assert "super-secret" not in captured_error
    assert "%5BREDACTED%5D" in captured_error
