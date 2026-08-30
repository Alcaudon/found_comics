"""Orquesta la comprobación de una serie: busca en Amazon el
siguiente número, aplica el detector semiautomático y guarda
el resultado en el historial.
"""

import asyncio
import logging
import random

import httpx
from sqlalchemy.orm import Session

from app import models
from app.services import amazon
from app.services.detector import find_match

logger = logging.getLogger(__name__)

# Pausa base entre peticiones en comprobación masiva (segundos). Se le suma
# un jitter aleatorio para no caer en un patrón regular que dispare el
# anti-bot de Amazon.
BULK_DELAY_SECONDS = 3.0
BULK_DELAY_JITTER_SECONDS = 2.0

STATUS_DISPONIBLE = "disponible"
STATUS_POSIBLE = "posible"
STATUS_NO_ENCONTRADO = "no_encontrado"
STATUS_ERROR = "error"


async def check_series(
    db: Session,
    series: models.Series,
    client: httpx.AsyncClient | None = None,
) -> models.CheckResult:
    """Comprueba una serie contra Amazon y guarda el CheckResult.

    Es una corrutina: se ejecuta directamente sobre el event loop, tanto
    desde la ruta individual como desde la comprobación masiva. No usa
    ``asyncio.run`` porque anidarlo dentro de un loop ya en marcha lanza
    ``RuntimeError`` (era el motivo de que «Comprobar todas» fallara).

    Si se pasa ``client``, se reutiliza esa sesión HTTP (con sus cookies)
    para todas las consultas; la comprobación masiva lo aprovecha para
    parecer una única sesión de navegador y reducir bloqueos.

    Genera varias consultas (con y sin volumen) porque el campo volumen
    a veces es un año o saga que no forma parte del título en Amazon.
    """
    number = series.next_number
    queries = amazon.build_queries(series.title, series.volume, number)

    all_results: list[amazon.AmazonSearchResult] = []
    last_error: Exception | None = None
    for query in queries:
        try:
            results = await amazon.search(query, client=client)
            if results:
                all_results.extend(results)
        except amazon.AmazonBlockedError as exc:
            logger.error("Amazon bloqueado al comprobar %r: %s", series.title, exc)
            return _save(
                db, series, number, STATUS_ERROR,
                message=f"Amazon bloqueó la petición: {exc}",
            )
        except Exception as exc:
            logger.exception("Error inesperado comprobando %r con query %r", series.title, query)
            last_error = exc

    if last_error and not all_results:
        return _save(
            db, series, number, STATUS_ERROR,
            message=f"Error inesperado: {last_error}",
        )

    if not all_results:
        return _save(
            db, series, number, STATUS_NO_ENCONTRADO,
            message="Sin resultados en Amazon",
        )

    # Elimina duplicados por URL manteniendo el orden.
    seen = set()
    unique_results = [r for r in all_results if not (r.url in seen or seen.add(r.url))]

    match = find_match(series.title, series.volume, number, unique_results)
    if match is None:
        return _save(
            db, series, number, STATUS_NO_ENCONTRADO,
            message=f"{len(unique_results)} resultados, ninguno coincide con el número {number}",
        )

    return _save(
        db, series, number, STATUS_POSIBLE,
        url=match.url, result_title=match.title, price=match.price,
    )


async def check_series_bulk(db: Session, series_list: list[models.Series]) -> list[models.CheckResult]:
    """Comprueba varias series reutilizando una sola sesión HTTP y con una
    pausa (con jitter) entre peticiones, para no ser bloqueado por Amazon."""
    results = []
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=amazon.REQUEST_TIMEOUT_SECONDS,
        headers=amazon._random_headers(),
    ) as client:
        for i, series in enumerate(series_list):
            if i > 0:
                await asyncio.sleep(
                    BULK_DELAY_SECONDS + random.uniform(0, BULK_DELAY_JITTER_SECONDS)
                )
            results.append(await check_series(db, series, client=client))
    return results


def _save(
    db: Session,
    series: models.Series,
    number: int,
    status: str,
    url: str | None = None,
    result_title: str | None = None,
    price: float | None = None,
    message: str | None = None,
) -> models.CheckResult:
    check = models.CheckResult(
        series_id=series.id,
        number_searched=number,
        status=status,
        url=url,
        result_title=result_title,
        price=price,
        message=message,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check