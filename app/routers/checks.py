from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import SessionLocal, get_db
from app.services import checker

router = APIRouter(prefix="/api/checks", tags=["checks"])


# OJO: '/all' debe declararse antes que '/{series_id}'. Si no, FastAPI
# intenta interpretar "all" como el entero series_id y responde 422.
@router.post("/all", response_model=schemas.CheckAllResponse)
async def check_all(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Comprueba todas las series con pausa entre peticiones.
    Se ejecuta en segundo plano; responde con el número de series en cola."""
    count = db.query(models.Series).count()

    async def run():
        # La sesión de la petición (get_db) se cierra al responder, así que
        # la tarea en segundo plano abre y cierra la suya propia.
        task_db = SessionLocal()
        try:
            series_list = (
                task_db.query(models.Series).order_by(models.Series.title).all()
            )
            await checker.check_series_bulk(task_db, series_list)
        finally:
            task_db.close()

    background.add_task(run)
    return schemas.CheckAllResponse(
        results=[], errors=[f"{count} series en cola para comprobación"]
    )


@router.post("/{series_id}", response_model=schemas.CheckResultOut)
async def check_one(series_id: int, db: Session = Depends(get_db)):
    """Comprueba el siguiente número de una serie contra Amazon."""
    series = db.get(models.Series, series_id)
    if series is None:
        raise HTTPException(404, "Serie no encontrada")
    return await checker.check_series(db, series)