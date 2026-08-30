"""Lógica semiautomática de coincidencia entre una serie y los
resultados de búsqueda de Amazon.

Estrategia: un resultado es "posible" si su título normalizado
contiene el título de la serie y una referencia inequívoca al
número buscado. El usuario confirma visualmente con el enlace.
"""

import re
import unicodedata

from app.services.amazon import AmazonSearchResult

NOISE_TOKENS = {
    "tp", "tomo", "cartoné", "cartone", "tapa", "dura", "blanda",
    "edición", "edicion", "especial", "libro", "novela", "gráfica",
    "grafica", "cómics", "comics", "comic", "panini", "ecc", "editorial",
}


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

    contextual = re.compile(
        r"(?:n[º°]\s*|n[uú]m(?:ero)?\.?\s*|vol(?:umen)?\.?\s*|#\s*|n\s+)" + num + r"\b"
    )
    if contextual.search(norm):
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
) -> AmazonSearchResult | None:
    """Devuelve el primer resultado que encaja con serie+número, o None."""
    for result in results:
        if title_tokens_match(series_title, result.title) and number_matches(
            number, result.title
        ):
            return result
    return None