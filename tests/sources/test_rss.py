from __future__ import annotations

import httpx
import pytest

from src.sources.rss import RSSSource


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def rss_feed(entries: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AI News</title>
    <link>https://example.com</link>
    <description>AI feed</description>
    {entries}
  </channel>
</rss>
""".encode()


def item(
    *,
    title: str = "OpenAI releases a model",
    link: str = "https://example.com/openai-model",
    description: str = "<p>Model&nbsp;<strong>news</strong></p>",
    pub_date: str = "Mon, 17 Aug 2026 10:00:00 GMT",
) -> str:
    return f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description>{description}</description>
      <pubDate>{pub_date}</pubDate>
    </item>
    """


def test_rss_discover_successful_feed_maps_news_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/feed.xml"
        return httpx.Response(200, content=rss_feed(item()))

    source = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    )

    records = source.discover()

    assert len(records) == 1
    record = records[0]
    assert record.source_name == "rss"
    assert record.record_type == "news"
    assert record.source_url == "https://example.com/openai-model"
    assert record.payload == {
        "title": "OpenAI releases a model",
        "description": "Model news",
        "article_url": "https://example.com/openai-model",
        "published_at": "Mon, 17 Aug 2026 10:00:00 GMT",
        "publisher": "Example AI",
        "feed_name": "Example AI",
        "feed_url": "https://example.com/feed.xml",
    }


def test_rss_discover_handles_missing_description() -> None:
    bare_item = """
    <item>
      <title>No summary</title>
      <link>https://example.com/no-summary</link>
    </item>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=rss_feed(bare_item))

    records = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    assert records[0].payload["description"] == ""
    assert records[0].payload["published_at"] is None


def test_rss_discover_deduplicates_duplicate_articles_by_url() -> None:
    duplicate_entries = item(title="First") + item(title="Second")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=rss_feed(duplicate_entries))

    records = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    assert records[0].payload["title"] == "First"


def test_rss_discover_sanitizes_html_summaries() -> None:
    html_item = item(description="<div>AI &amp; <em>robotics</em><br>update</div>")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=rss_feed(html_item))

    records = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    ).discover()

    assert records[0].payload["description"] == "AI & robotics update"


def test_rss_discover_malformed_feed_returns_no_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<rss><channel><item><title>Broken")

    records = RSSSource(
        feeds=[{"name": "Broken", "url": "https://example.com/broken.xml"}],
        client=make_client(handler),
    ).discover()

    assert records == []


def test_rss_discover_skips_entries_missing_required_fields() -> None:
    bad_entries = """
    <item><title>Missing link</title></item>
    <item><link>https://example.com/missing-title</link></item>
    """ + item()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=rss_feed(bad_entries))

    records = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    ).discover()

    assert len(records) == 1
    assert records[0].payload["article_url"] == "https://example.com/openai-model"


def test_rss_discover_retries_timeout_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.TimeoutException("timed out")
        return httpx.Response(200, content=rss_feed(item()))

    records = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    ).discover()

    assert attempts == 2
    assert len(records) == 1


def test_rss_discover_server_error_fails_gracefully() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"error")

    records = RSSSource(
        feeds=[{"name": "Example AI", "url": "https://example.com/feed.xml"}],
        client=make_client(handler),
    ).discover()

    assert records == []


def test_rss_extract_returns_candidate_without_global_processing() -> None:
    source = RSSSource(feeds=[])
    record = source._record_from_entry(
        {
            "title": "News",
            "link": "https://example.com/news",
            "summary": "Summary",
        },
        source.feeds[0] if source.feeds else type("Feed", (), {"name": "Fixture", "url": "https://example.com/feed"})(),
    )

    assert record is not None
    assert source.extract(record) is record


def test_rss_feed_config_requires_name_and_url() -> None:
    with pytest.raises(ValueError):
        RSSSource(feeds=[{"name": "", "url": "https://example.com/feed.xml"}])
