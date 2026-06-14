from search_country import normalize_country


def test_normalize_italy() -> None:
    assert normalize_country("Italia") == "Italy"


def test_normalize_germany() -> None:
    assert normalize_country("Germania") == "Germany"


def test_normalize_usa() -> None:
    assert normalize_country("USA") == "United States"


def test_unknown_passthrough() -> None:
    assert normalize_country("Canada") == "Canada"


def test_empty_country() -> None:
    assert normalize_country("") == ""
