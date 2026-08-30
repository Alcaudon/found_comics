from pathlib import Path

from app.services.amazon import (
    AmazonBlockedError,
    build_queries,
    build_search_url,
    parse_search_page,
)
from app.services.amazon import AmazonSearchResult
from app.services.detector import (
    find_match,
    is_excluded,
    number_matches,
    normalize,
    publisher_matches,
    title_tokens_match,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _results():
    html = (FIXTURES / "amazon_search.html").read_text(encoding="utf-8")
    return parse_search_page(html)


def test_build_queries():
    assert build_queries("Amazing Spider-Man", 2, 62) == ["Amazing Spider-Man 2 62", "Amazing Spider-Man 62"]
    assert build_queries("Daredevil", None, 41) == ["Daredevil 41"]


def test_build_search_url():
    url = build_search_url("Amazing Spider-Man 62")
    assert url.startswith("https://www.amazon.es/s?k=")
    assert "Amazing+Spider-Man+62" in url


def test_parse_search_page_extracts_results():
    results = _results()
    assert len(results) == 4
    first = results[0]
    assert "Amazing Spider-Man" in first.title
    assert first.url.startswith("https://www.amazon.es/")
    assert first.price == 14.95


def test_parse_search_page_blocked():
    html = (FIXTURES / "amazon_blocked.html").read_text(encoding="utf-8")
    try:
        parse_search_page(html)
        raise AssertionError("Debería haber lanzado AmazonBlockedError")
    except AmazonBlockedError:
        pass


def test_normalize():
    assert normalize("Cómics Últimos  NÚMERO") == "comics ultimos numero"


def test_title_tokens_match():
    assert title_tokens_match("Amazing Spider-Man", "Amazing Spider-Man (2022) 62 – Panini Comics")
    assert not title_tokens_match("Daredevil", "Amazing Spider-Man (2022) 62")


def test_number_matches_contextual():
    assert number_matches(62, "Amazing Spider-Man (2022) Nº 62 – Panini")
    assert number_matches(62, "Amazing Spider-Man vol. 62")
    assert number_matches(62, "Amazing Spider-Man #62")
    assert not number_matches(61, "Amazing Spider-Man (2022) Nº 62")
    assert not number_matches(62, "Daredevil (2022) Nº 40")


def test_find_match_picks_right_result():
    results = _results()
    match = find_match("Amazing Spider-Man", 2022, 62, results)
    assert match is not None
    assert "62" in match.title
    assert "Spider-Man" in match.title


def test_find_match_ignores_other_series():
    results = _results()
    assert find_match("Batman", None, 62, results) is None


def test_is_excluded_filters_language_and_digital():
    # Ediciones en otro idioma y formatos digitales/audio.
    assert is_excluded("BATMAN - Tome 2")
    assert is_excluded("Batman #2 (English Edition)")
    assert is_excluded("Batman 2 Versión Kindle")
    # "tomo" (español) no debe confundirse con "tome" (francés).
    assert not is_excluded("Batman nº 2 (tomo cartoné) - ECC")


def test_publisher_matches_significant_token():
    assert publisher_matches("Panini Comics", "Batman nº 2 - Panini")
    assert publisher_matches("ECC Ediciones", "Batman nº 2 (ECC)")
    # "Comics"/"Ediciones" solos no bastan: no distinguen una editorial.
    assert not publisher_matches("Panini Comics", "Batman nº 2 - ECC Comics")
    assert not publisher_matches(None, "Batman nº 2 - Panini")


def test_find_match_prefers_publisher_and_skips_excluded():
    """El primero que casa no siempre es el bueno: debe ganar el que
    coincide en editorial, y las ediciones extranjeras ni se consideran."""
    results = [
        AmazonSearchResult("Batman - Tome 2", "https://a/fr", 20.0),      # francés
        AmazonSearchResult("Batman 2", "https://a/generico", 15.0),       # casa, sin editorial
        AmazonSearchResult("Batman nº 2 - ECC Ediciones", "https://a/ecc", 17.0),
    ]
    match = find_match("Batman", None, 2, results, publisher="ECC")
    assert match is not None
    assert match.url == "https://a/ecc"

    # Sin editorial anotada, gana el orden de Amazon entre los válidos.
    match_sin_editorial = find_match("Batman", None, 2, results)
    assert match_sin_editorial.url == "https://a/generico"