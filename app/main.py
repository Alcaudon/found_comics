import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import checks, importer, series

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Found Comics", version="0.1.0")
app.include_router(series.router)
app.include_router(checks.router)
app.include_router(importer.router)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("app/web/index.html")


init_db()