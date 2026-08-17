from src.normalization import canonical_domain, normalize_url


def test_normalize_url_unifies_scheme_www_and_trailing_slash() -> None:
    expected = "https://openai.com"
    assert normalize_url("https://www.openai.com/") == expected
    assert normalize_url("http://openai.com") == expected
    assert normalize_url("openai.com/") == expected


def test_normalize_url_removes_tracking_query_params_and_fragments() -> None:
    assert (
        normalize_url(
            "https://openai.com/research?utm_source=test&id=42&gclid=x#section"
        )
        == "https://openai.com/research?id=42"
    )


def test_normalize_url_preserves_meaningful_repository_paths() -> None:
    langchain = normalize_url("https://github.com/langchain-ai/langchain/")
    openai_python = normalize_url("https://github.com/openai/openai-python")

    assert langchain == "https://github.com/langchain-ai/langchain"
    assert openai_python == "https://github.com/openai/openai-python"
    assert langchain != openai_python


def test_canonical_domain_extracts_normalized_domain() -> None:
    assert canonical_domain("https://www.openai.com/?utm_source=test") == "openai.com"
    assert canonical_domain("http://github.com/openai/openai-python") == "github.com"


def test_normalize_url_handles_empty_values() -> None:
    assert normalize_url(None) == ""
    assert normalize_url("  ") == ""
    assert canonical_domain(None) == ""
