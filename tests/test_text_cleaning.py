from src.cleaning import (
    clean_description,
    normalize_unicode,
    normalize_whitespace,
    strip_html,
)


def test_strip_html_removes_tags_and_decodes_entities() -> None:
    assert strip_html("<p>OpenAI&nbsp;&amp; partners</p>") == "OpenAI & partners"


def test_strip_html_handles_malformed_html() -> None:
    assert strip_html("<div>Broken <strong>markup") == "Broken markup"


def test_clean_description_normalizes_unicode_and_whitespace() -> None:
    raw = "  Full-width ＡＩ&nbsp;\n\n  platform\t "
    assert clean_description(raw) == "Full-width AI platform"


def test_cleaning_functions_handle_none() -> None:
    assert strip_html(None) == ""
    assert normalize_unicode(None) == ""
    assert normalize_whitespace(None) == ""
    assert clean_description(None) == ""
