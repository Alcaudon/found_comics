from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/series", tags=["series"])


@router.get("", response_model=list[schemas.SeriesWithLastCheckOut])
def list_series(db: Session = Depends(get_db)):
    stmt = select(models.Series).order_by(models.Series.title)
    series_list = db.scalars(stmt).all()
    out = []
    for s in series_list:
        item = schemas.SeriesWithLastCheckOut.model_validate(s)
        last = (
            db.query(models.CheckResult)
            .filter(models.CheckResult.series_id == s.id)
            .order_by(models.CheckResult.checked_at.desc(), models.CheckResult.id.desc())
            .first()
        )
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