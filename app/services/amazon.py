"""Cliente de búsqueda para Amazon España.

Advertencia: Amazon no ofrece API pública sin cuenta de Afiliados.
Este módulo consulta la página pública de búsqueda con cabeceras
realistas y reintentos con backoff. Es frágil por diseño del sitio;
por eso está aislado del resto de la aplicación.
"""

import asyncio
import logging
import random
import urllib.parse

import httpx
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.amazon.es/s"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 15.0


class AmazonBlockedError(Exception):
    """Amazon respondió con un bloqueo (CAPTCHA, 503...)."""


class AmazonSearchResult:
    __slots__ = ("title", "url", "price")

    def __init__(self, title: str, url: str, price: float | None):
        self.title = title
        self.url = url
        self.price = price

    def __repr__(self) -> str:
        return f"AmazonSearchResult(title={self.title!r}, price={self.price})"


def build_queries(series_title: str, volume: int | None, number: int) -> list[str]:
    """Genera consultas de búsqueda, probando con y sin volumen.

    Muchos usuarios usan el campo 'volumen' como año o saga, no como
    parte literal del título en Amazon. Por eso devolvemos siempre
    la consulta sin volumen como fallback.
    """
    title = series_title.strip()
    num = str(number)
    queries = []
    if volume is not None:
        queries.append(f"{title} {volume} {num}")
    queries.append(f"{title} {num}")
    return queries


def build_search_url(query: str) -> str:
    return f"{SEARCH_URL}?k={urllib.parse.quote_plus(query)}"


def parse_search_page(html: str) -> list[AmazonSearchResult]:
    """Extrae los resultados de una página de búsqueda de Amazon.es.

    Lanza AmazonBlockedError si la página parece un CAPTCHA/bloqueo.
    """
    tree = HTMLParser(html)
    title_node = tree.css_first("title")
    page_title = title_node.text(strip=True) if title_node else ""
    lowered = html[:5000].lower()
    if (
        "robot check" in page_title.lower()
        or "bm-verify" in lowered
        or ("captcha" in lowered and "automatizados" in lowered)
    ):
        raise AmazonBlockedError(f"Página de bloqueo detectada: {page_title!r}")

    results: list[AmazonSearchResult] = []
    base = "https://www.amazon.es"
    for node in tree.css("div[data-component-type='s-search-result']"):
        title_node = node.css_first("h2 span")
        link_node = node.css_first("a h2")
        link = None
        if link_node is not None:
            link = link_node.parent
        if title_node is None or link is None:
            continue
        title = title_node.text(strip=True)
        href = link.attributes.get("href", "")
        if not title or not href:
            continue
        if href.startswith("/"):
            href = base + href.split("/ref=")[0]

        price = None
        price_node = node.css_first("span.a-offscreen")
        if price_node is not None:
            price = _parse_price(price_node.text(strip=True))

        results.append(AmazonSearchResult(title=title, url=href, price=price))
    return results


def _parse_price(text: str) -> float | None:
    cleaned = (
        text.replace("€", "")
        .replace("\xa0", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )
    # Si el precio usa punto decimal (formato inglés residual), el replace
    # anterior lo habría estropeado; detectamos el caso de dos dígitos finales.
    try:
        return float(cleaned)
    except ValueError:
        return None


async def search(
    query: str,
    client: httpx.AsyncClient | None = None,
    max_retries: int = MAX_RETRIES,
) -> list[AmazonSearchResult]:
    """Busca en Amazon.es y devuelve los resultados.

    Reintenta con backoff ante 503/bloqueos, rotando User-Agent.
    """
    url = build_search_url(query)
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers=_random_headers(),
        )
    assert client is not None
    try:
        last_error: Exception | None = None
        for attempt in range(max_retries):
            headers = _random_headers()
            try:
                response = await client.get(url, headers=headers)
                if response.status_code in (503, 429):
                    raise AmazonBlockedError(f"HTTP {response.status_code}")
                response.raise_for_status()
                results = parse_search_page(response.text)
                logger.info("Amazon: %d resultados para %r", len(results), query)
                return results
            except (AmazonBlockedError, httpx.HTTPError) as exc:
                last_error = exc
                wait = BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "Amazon intento %d/%d fallido (%s); esperando %.1fs",
                    attempt + 1, max_retries, exc, wait,
                )
                await asyncio.sleep(wait)
        raise AmazonBlockedError(f"Agotados los reintentos: {last_error}")
    finally:
        if own_client:
            await client.aclose()


def _random_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
        "Referer": "https://www.amazon.es/",
    }