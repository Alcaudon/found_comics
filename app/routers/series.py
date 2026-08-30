from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/series", tags=["series"])


@router.get("", response_model=list[schemas.SeriesWithLastCheckOut])
def list_series(db: Session = Depends(get_db)):
    series_list = db.scalars(
        select(models.Series).order_by(models.Series.title)
    ).all()

    # Última comprobación de cada serie en una sola consulta (evita el N+1).
    # El id es autoincremental y checked_at se fija al insertar, así que el
    # mayor id por serie coincide con la comprobación más reciente.
    latest_ids = (
        select(func.max(models.CheckResult.id))
        .group_by(models.CheckResult.series_id)
        .scalar_subquery()
    )
    latest_by_series = {
        c.series_id: c
        for c in db.scalars(
            select(models.CheckResult).where(models.CheckResult.id.in_(latest_ids))
        )
    }

    out = []
    for s in series_list:
        item = schemas.SeriesWithLastCheckOut.model_validate(s)
        last = latest_by_series.get(s.id)
        item.last_check = schemas.CheckResultOut.model_validate(last) if last else None
        out.append(item)
    return out


@router.post("", response_model=schemas.SeriesOut, status_code=201)
def create_series(payload: schemas.SeriesIn, db: Session = Depends(get_db)):
    series = models.Series(**payload.model_dump())
    db.add(series)
    db.commit()
    db.refresh(series)
    return series


# Editoriales habituales del cómic en España, para que el desplegable sea
# útil desde el primer día aunque la colección esté vacía.
COMMON_PUBLISHERS = (
    "Panini", "ECC Ediciones", "Norma Editorial", "Planeta Cómic",
    "Astiberri", "Dolmen", "Yermo Ediciones", "SD Distribuciones",
    "Ivrea", "Milky Way Ediciones", "Distrito Manga", "Kamite",
    "La Cúpula", "Reservoir Books", "Salamandra Graphic",
)


# OJO: esta ruta debe ir antes que '/{series_id}', o FastAPI intentaría
# interpretar "publishers" como un entero y respondería 422.
@router.get("/publishers", response_model=list[str])
def list_publishers(db: Session = Depends(get_db)):
    """Editoriales para el desplegable: las que ya usas más las habituales."""
    used = db.scalars(
        select(models.Series.publisher)
        .where(models.Series.publisher.is_not(None))
        .distinct()
    ).all()

    # Las tuyas mandan sobre la lista base si solo cambian en mayúsculas.
    merged: dict[str, str] = {}
    for name in list(used) + list(COMMON_PUBLISHERS):
        clean = (name or "").strip()
        if clean:
            merged.setdefault(clean.casefold(), clean)
    return sorted(merged.values(), key=str.casefold)


@router.get("/{series_id}", response_model=schemas.SeriesWithLastCheckOut)
def get_series(series_id: int, db: Session = Depends(get_db)):
    series = db.get(models.Series, series_id)
    if series is None:
        raise HTTPException(404, "Serie no encontrada")
    item = schemas.SeriesWithLastCheckOut.model_validate(series)
    last = (
        db.query(models.CheckResult)
        .filter(models.CheckResult.series_id == series_id)
        .order_by(models.CheckResult.checked_at.desc(), models.CheckResult.id.desc())
        .first()
    )
    item.last_check = schemas.CheckResultOut.model_validate(last) if last else None
    return item


@router.put("/{series_id}", response_model=schemas.SeriesOut)
def update_series(
    series_id: int, payload: schemas.SeriesIn, db: Session = Depends(get_db)
):
    series = db.get(models.Series, series_id)
    if series is None:
        raise HTTPException(404, "Serie no encontrada")
    for field, value in payload.model_dump().items():
        setattr(series, field, value)
    db.commit()
    db.refresh(series)
    return series


@router.delete("/{series_id}", status_code=204)
def delete_series(series_id: int, db: Session = Depends(get_db)):
    series = db.get(models.Series, series_id)
    if series is None:
        raise HTTPException(404, "Serie no encontrada")
    db.delete(series)
    db.commit()


@router.get("/{series_id}/checks", response_model=list[schemas.CheckResultOut])
def series_checks(series_id: int, db: Session = Depends(get_db)):
    series = db.get(models.Series, series_id)
    if series is None:
        raise HTTPException(404, "Serie no encontrada")
    stmt = (
        select(models.CheckResult)
        .where(models.CheckResult.series_id == series_id)
        .order_by(models.CheckResult.checked_at.desc())
    )
    return db.scalars(stmt).all()