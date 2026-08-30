"""Lógica semiautomática de coincidencia entre una serie y los
resultados de búsqueda de Amazon.

Estrategia: un resultado es "posible" si su título normalizado
contiene el título de la serie y una referencia inequívoca al
número buscado. El usuario confirma visualmente con el enlace.
"""

import os
import re
import unicodedata

from app.services.amazon import AmazonSearchResult

NOISE_TOKENS = {
    "tp", "tomo", "cartoné", "cartone", "tapa", "dura", "blanda",
    "edición", "edicion", "especial", "libro", "novela", "gráfica",
    "grafica", "cómics", "comics", "comic", "panini", "ecc", "editorial",
}

# Palabras genéricas que no distinguen una editorial de otra.
PUBLISHER_NOISE = {
    "comics", "comic", "editorial", "ediciones", "edicion",
    "espana", "iberica", "sa", "sl", "the",
}

# Marcadores de resultados que casi nunca son lo que buscas: ediciones en
# otro idioma y formatos digitales o de audio. Se comparan con límite de
# palabra sobre el título ya normalizado (minúsculas y sin tildes), así que
# "tome" (francés) no colisiona con "tomo" (español).
DEFAULT_EXCLUDED_MARKERS = (
    "tome", "tomes",
    "english", "french", "francais", "francaise",
    "deutsch", "german", "italiano", "italiana",
    "kindle", "ebook", "audible", "audiolibro",
)


def _load_excluded_markers() -> tuple[str, ...]:
    """Lista de exclusiones, ajustable sin tocar el código con la variable
    de entorno FOUND_COMICS_EXCLUDE (separada por comas; vacía = ninguna)."""
    raw = os.environ.get("FOUND_COMICS_EXCLUDE")
    if raw is None:
        return DEFAULT_EXCLUDED_MARKERS
    return tuple(m.strip().lower() for m in raw.split(",") if m.strip())


EXCLUDED_MARKERS = _load_excluded_markers()

# Peso de cada señal a favor de un candidato (ver find_match).
PUBLISHER_SCORE = 3
VOLUME_SCORE = 2
CONTEXTUAL_NUMBER_SCORE = 1


def normalize(text: str) -> str:
    """Minúsculas, sin tildes, espacios colapsados."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def title_tokens_match(series_title: str, result_title: str) -> bool:
    """Comprueba que las palabras significativas del título de la serie
    (fuera ruido editorial) aparecen en el título del resultado."""
    series_tokens = [
        t for t in normalize(series_title).split() if t not in NOISE_TOKENS
    ]
    if not series_tokens:
        return False
    result_norm = normalize(result_title)
    return all(token in result_norm for token in series_tokens)


def number_in_context(number: int, result_title: str) -> bool:
    """El número aparece citado explícitamente ("nº 3", "vol. 3", "#3"),
    no suelto. Es una señal mucho más fuerte que un número perdido en el
    título (que puede ser un año, un precio o parte del nombre)."""
    contextual = re.compile(
        r"(?:n[º°]\s*|n[uú]m(?:ero)?\.?\s*|vol(?:umen)?\.?\s*|#\s*|n\s+)"
        + str(number)
        + r"\b"
    )
    return bool(contextual.search(normalize(result_title)))


def is_excluded(result_title: str) -> bool:
    """Descarta ediciones en otro idioma y formatos digitales/audio."""
    norm = normalize(result_title)
    return any(
        re.search(r"\b" + re.escape(marker) + r"\b", norm)
        for marker in EXCLUDED_MARKERS
    )


def publisher_matches(publisher: str | None, result_title: str) -> bool:
    """La editorial que has anotado aparece en el título del resultado.

    Basta con que coincida una palabra significativa ("Panini" de "Panini
    Comics"), porque Amazon rara vez repite el nombre completo.
    """
    if not publisher:
        return False
    tokens = [t for t in normalize(publisher).split() if t not in PUBLISHER_NOISE]
    if not tokens:
        return False
    norm = normalize(result_title)
    return any(re.search(r"\b" + re.escape(t) + r"\b", norm) for t in tokens)


def number_matches(number: int, result_title: str) -> bool:
    """Comprueba si el título del resultado referencia el número buscado.

    Acepta contextos habituales (n°, núm., vol., #), guiones/paréntesis,
    números sueltos y números con ceros a la izquierda ("02" → 2).
    title_tokens_match ya exige que el título de la serie esté presente,
    con lo que se reduce el riesgo de falsos positivos.
    """
    norm = normalize(result_title)
    num = str(number)
    padded = num.zfill(2)  # 2 → "02"
    padded3 = num.zfill(3)

    if number_in_context(number, result_title):
        return True
    loose = re.compile(r"(?:[-–]\s*|\(\s*)" + num + r"\b")
    if loose.search(norm):
        return True
    # Números con ceros a la izquierda separados por espacio/puntuación.
    padded_patterns = [
        r"\b0+" + num + r"\b",
        r"(?:^|\s)" + padded + r"\b",
        r"(?:^|\s)" + padded3 + r"\b",
    ]
    for pat in padded_patterns:
        if re.search(pat, norm):
            return True
    # Número suelto.
    return bool(re.search(r"\b" + num + r"\b", norm))


def find_match(
    series_title: str,
    volume: int | None,
    number: int,
    results: list[AmazonSearchResult],
    publisher: str | None = None,
) -> AmazonSearchResult | None:
    """Devuelve el resultado que MEJOR encaja con serie+número, o None.

    Antes se devolvía el primero que casara, con lo que la decisión quedaba
    en manos del orden de Amazon (patrocinados incluidos). Ahora se puntúan
    todos los candidatos válidos y gana el que reúne más señales a favor:
    la editorial anotada, el volumen y el número citado en contexto. A
    igualdad de puntos manda el orden de Amazon, que es su relevancia.
    """
    best: AmazonSearchResult | None = None
    best_key: tuple[int, int] | None = None

    for position, result in enumerate(results):
        if is_excluded(result.title):
            continue
        if not title_tokens_match(series_title, result.title):
            continue
        if not number_matches(number, result.title):
            continue

        score = 0
        if publisher_matches(publisher, result.title):
            score += PUBLISHER_SCORE
        if volume is not None and re.search(
            r"\b" + str(volume) + r"\b", normalize(result.title)
        ):
            score += VOLUME_SCORE
        if number_in_context(number, result.title):
            score += CONTEXTUAL_NUMBER_SCORE

        # Más puntos primero; a igualdad, el que Amazon puso antes.
        key = (-score, position)
        if best_key is None or key < best_key:
            best, best_key = result, key

    return best