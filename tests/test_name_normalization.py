from src.normalization import normalize_name


def test_normalize_name_case_and_spacing() -> None:
    assert normalize_name("OpenAI") == "openai"
    assert normalize_name("OPENAI") == "openai"
    assert normalize_name("Open AI") == "openai"


def test_normalize_name_removes_punctuation() -> None:
    assert normalize_name("Hugging-Face!") == "huggingface"


def test_normalize_name_removes_company_suffixes_for_companies() -> None:
    assert normalize_name("OpenAI Inc.", entity_type="company") == "openai"
    assert normalize_name("Acme Corporation LLC", entity_type="company") == "acme"


def test_normalize_name_does_not_strip_product_qualifiers() -> None:
    assert normalize_name("Claude") != normalize_name("Claude Desktop")
    assert normalize_name("Claude Desktop") == "claudedesktop"


def test_normalize_name_keeps_meta_ai_distinct_from_meta() -> None:
    assert normalize_name("Meta") != normalize_name("Meta AI")
