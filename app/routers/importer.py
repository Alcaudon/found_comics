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


@router.post("/confirm", response_model=schemas.ImportResult)
async def confirm(payload: schemas.ImportConfirm, db: Session = Depends(get_db)):
    """Confirma la importación... requiere re-subir el fichero con el mapeo.

    Nota: como el fichero no se persiste entre llamadas, este endpoint
    espera que el frontend vuelva a enviar el fichero con el mapeo en
    multipart. Ver /api/import/confirm-file.
    """
    raise HTTPException(
        400,
        "Usa /api/import/confirm-file enviando el fichero y el mapeo JSON juntos",
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