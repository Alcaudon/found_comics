from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import checker

router = APIRouter(prefix="/api/checks", tags=["checks"])


@router.post("/{series_id}", response_model=schemas.CheckResultOut)
def check_one(series_id: int, db: Session = Depends(get_db)):
    """Comprueba el siguiente número de una serie contra Amazon."""
    series = db.get(models.Series, series_id)
    if series is None:
        raise HTTPException(404, "Serie no encontrada")
    return checker.check_series_sync(db, series)


@router.post("/all", response_model=schemas.CheckAllResponse)
async def check_all(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Comprueba todas las series con pausa entre peticiones.
    Se ejecuta en segundo plano; responde con el número de series en cola."""
    series_list = db.query(models.Series).order_by(models.Series.title).all()

    async def run():
        await checker.check_series_bulk(db, series_list)

    background.add_task(run)
    return schemas.CheckAllResponse(
        results=[], errors=[f"{len(series_list)} series en cola para comprobación"]
    )