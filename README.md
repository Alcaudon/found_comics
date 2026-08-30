# Found Comics

App web local para saber si el siguiente número de las series de tu colección
de cómics ya está a la venta en Amazon España.

## Características

- **Gestión de colección**: alta, edición y borrado de series (título, volumen,
  editorial, último número poseído).
- **Importación CSV/Excel**: sube tu colección desde una hoja de cálculo con
  vista previa y mapeo de columnas (sugerido automáticamente).
- **Comprobación en Amazon**: para cada serie construye la consulta
  `"{título} {volumen} {siguiente número}"`, consulta amazon.es y marca el
  resultado como **posible** (con enlace y precio) para que confirmes
  visualmente.
- **Comprobación masiva** en segundo plano con pausa de 2,5 s entre peticiones
  y rotación de User-Agents para evitar bloqueos.
- **Historial** de comprobaciones por serie.

## Instalación

Requiere **Python 3.10 o superior** (FastAPI y pydantic recientes ya no
soportan 3.9).

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
uvicorn app.main:app --reload
```

Abre <http://localhost:8000>.

## Tests

```bash
python -m pytest tests/
```

Los tests usan una BD temporal propia y no tocan `found_comics.db`.

## Notas importantes

- Amazon no ofrece API pública sin cuenta de Afiliados, por lo que se consulta
  la página pública de búsqueda. Esto es **frágil por diseño**: si Amazon
  cambia su HTML o intensifica su anti-bot (`bm-verify`, CAPTCHA), las series
  quedarán en estado `error` sin romper nada. Toda esa lógica está aislada en
  `app/services/amazon.py` (parseo) y `app/services/detector.py` (coincidencia),
  con tests basados en fixtures HTML para poder repararla fácilmente.
- La comprobación es **semiautomática**: se marca "posible" cuando un
  resultado contiene el título de la serie y una referencia clara al número
  buscado; el enlace permite descartar falsos positivos (ediciones en otros
  idiomas, formatos digitales, etc.).
- Variable de entorno `FOUND_COMICS_DB` para cambiar la ruta de la base de
  datos (por defecto `./found_comics.db`).
- Nota de entorno (Windows): en algún equipo Windows Defender ha bloqueado
  por reputación el binario `pydantic-core==2.46.5`. Si ocurre, instala una
  versión de `pydantic` cuyo `pydantic-core` no esté marcado (por ejemplo
  `pip install "pydantic==2.14.0b1"`, que trae core 2.48.0). En macOS/Linux
  no aplica y se usa el `pydantic` estable de `requirements.txt`.