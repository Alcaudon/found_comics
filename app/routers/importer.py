from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import csv_import

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/preview", response_model=schemas.ImportPreview)
async def preview(file: UploadFile = File(...)):
    """Sube un CSV/Excel y devuelve columnas, primeras filas y mapeo sugerido."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fichero vacío")
    try:
        df = csv_import.read_table(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el fichero: {exc}") from exc
    if df.empty:
        raise HTTPException(400, "El fichero no contiene filas")
    return schemas.ImportPreview(
        columns=[str(c) for c in df.columns],
        rows=csv_import.rows_preview(df),
        suggested_mapping=csv_import.suggest_mapping(list(df.columns)),
    )


@router.post("/confirm-file", response_model=schemas.ImportResult)
async def confirm_file(
    file: UploadFile = File(...),
    mapping: str = Form("{}"),
    db: Session = Depends(get_db),
):
    """Importa el fichero aplicando el mapeo {columna: campo} en JSON."""
    import json

    try:
        mapping_dict = json.loads(mapping) if mapping else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Mapeo JSON inválido: {exc}") from exc
    if not mapping_dict:
        raise HTTPException(400, "Mapeo vacío")

    data = await file.read()
    try:
        df = csv_import.read_table(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el fichero: {exc}") from exc

    created, errors = csv_import.import_dataframe(db, df, mapping_dict)
    return schemas.ImportResult(created=created, skipped=errors)