"""Importación de colecciones desde CSV/Excel con mapeo flexible
de columnas y vista previa.
"""

import io
import logging

import pandas as pd
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)

TARGET_FIELDS = ("title", "volume", "publisher", "last_number", "notes")

# Nombres habituales de columnas en exportaciones de colecciones
COLUMN_HINTS = {
    "title": ["titulo", "título", "serie", "series", "title", "name", "nombre"],
    "volume": ["volumen", "volume", "vol", "saga"],
    "publisher": ["editorial", "publisher", "distribuidora"],
    "last_number": ["ultimo numero", "último número", "ultimo", "último",
                    "last number", "numero", "número", "number", "num"],
    "notes": ["notas", "notes", "comentarios", "observaciones"],
}


def read_table(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Lee CSV o Excel según extensión."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    # UTF-8 con fallback a latin-1 (exportaciones españolas típicas)
    try:
        return pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")


def suggest_mapping(columns: list[str]) -> dict[str, str]:
    """Sugiere mapeo columna_fichero -> campo aplicando pistas de nombres."""
    mapping: dict[str, str] = {}
    norm_columns = {c.strip().lower(): c for c in columns}
    for field, hints in COLUMN_HINTS.items():
        for hint in hints:
            for norm, original in norm_columns.items():
                if norm == hint or norm.startswith(hint):
                    mapping[original] = field
                    break
            if field in mapping.values():
                break
    return mapping


def rows_preview(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    head = df.head(limit).fillna("")
    return head.to_dict(orient="records")


def import_dataframe(db: Session, df: pd.DataFrame, mapping: dict[str, str]) -> tuple[int, list[str]]:
    """Crea las series a partir del DataFrame usando el mapeo dado.

    Devuelve (creadas, errores)."""
    created = 0
    errors: list[str] = []
    for idx, row in df.iterrows():
        record = {}
        for col, field in mapping.items():
            if field in TARGET_FIELDS and col in df.columns:
                value = row[col]
                record[field] = value
        title = record.get("title")
        if not title or pd.isna(title) or not str(title).strip():
            errors.append(f"Fila {idx + 2}: sin título, omitida")
            continue
        try:
            series = models.Series(
                title=str(title).strip(),
                volume=_to_int_or_none(record.get("volume")),
                publisher=_clean_str(record.get("publisher")),
                last_number=_to_int_or_none(record.get("last_number")) or 1,
                notes=_clean_str(record.get("notes")),
            )
            db.add(series)
            created += 1
        except Exception as exc:
            errors.append(f"Fila {idx + 2}: {exc}")
    db.commit()
    return created, errors


def _clean_str(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _to_int_or_none(value) -> int | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None