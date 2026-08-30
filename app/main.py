import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import checks, importer, series

logging.basicConfig(level=logging.INFO)

# Rutas absolutas basadas en la ubicación del módulo: así la app arranca
# desde cualquier directorio de trabajo, no solo desde la raíz del repo.
WEB_DIR = Path(__file__).parent / "web"

app = FastAPI(title="Found Comics", version="0.1.0")
app.include_router(series.router)
app.include_router(checks.router)
app.include_router(importer.router)

app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")


init_db()