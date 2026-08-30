import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import checks, importer, series

logging.basicConfig(level=logging.INFO)

# Rutas absolutas basadas en la ubicación del módulo: así la app arranca
# desde cualquier directorio de trabajo, no solo desde la raíz del repo.
WEB_DIR = Path(__file__).parent / "web"
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(title="Found Comics", version="0.1.0")
app.include_router(series.router)
app.include_router(checks.router)
app.include_router(importer.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _asset_version() -> str:
    """Versión de los assets = mtime más reciente de /static.

    Se inyecta como ?v=... en index.html para invalidar la caché del
    navegador tras cada cambio, sin bumps manuales ni JS/CSS obsoleto.
    """
    try:
        return str(max(int(p.stat().st_mtime) for p in STATIC_DIR.iterdir() if p.is_file()))
    except ValueError:
        return "0"


@app.get("/", include_in_schema=False)
def index():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("__ASSET_VERSION__", _asset_version()))


init_db()