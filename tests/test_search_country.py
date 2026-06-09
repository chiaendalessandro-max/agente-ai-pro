from search_country import normalize_country_for_apollo


def test_normalize_italy() -> None:
    assert normalize_country_for_apollo("Italia") == "Italy"


def test_normalize_germany() -> None:
    assert normalize_country_for_apollo("Germania") == "Germany"


def test_normalize_usa() -> None:
    assert normalize_country_for_apollo("USA") == "United States"


def test_unknown_passthrough() -> None:
    assert normalize_country_for_apollo("Canada") == "Canada"
