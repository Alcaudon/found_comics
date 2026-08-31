# Found Comics

App web local para saber si el siguiente número de las series de tu colección
de cómics ya está a la venta en Amazon España.

## Características

- **Gestión de colección**: alta, edición y borrado de series (título, volumen,
  editorial, último número poseído). El campo *Editorial* es un desplegable con
  las que ya usas más las habituales del cómic en España, y admite escribir una
  nueva.
- **Importación CSV/Excel**: sube tu colección desde una hoja de cálculo con
  vista previa y mapeo de columnas (sugerido automáticamente).
- **Comprobación en Amazon**: para cada serie busca en amazon.es con
  `"{título} {volumen} {siguiente número}"` y, como reserva, `"{título}
  {siguiente número}"` (el volumen a veces es un año o una saga que no forma
  parte del título real). Marca el resultado como **posible**, con enlace y
  precio, para que lo confirmes visualmente.
- **Confirmación manual**: desde la ficha de una serie con resultado *posible*
  puedes marcarlo como **disponible** (✓ Es este) tras verlo en Amazon, o
  descartarlo como falso positivo (✗ No es). La comprobación automática nunca
  afirma «disponible» por sí sola.
- **Comprobación masiva** en segundo plano: reutiliza una única sesión HTTP
  (con sus cookies), imitando a un navegador, y espera ~3 s más un margen
  aleatorio entre peticiones para reducir los bloqueos de Amazon.
- **Historial** de comprobaciones por serie.

## Instalación

Requiere **Python 3.10 o superior** (FastAPI y pydantic recientes ya no
soportan 3.9).

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### De una vez, con un script

`scripts/setup-worktree.sh` hace todo lo anterior sin preguntar: busca un Python
válido, crea el entorno e instala las dependencias.

```bash
bash scripts/setup-worktree.sh
```

[Orca](https://onorca.dev) lo ejecuta solo cada vez que crea un worktree, según
`orca.yaml`. En ese caso además copia tu `found_comics.db` del checkout
principal, para que el worktree arranque con datos reales sin tocar el original.

## Ejecución

```bash
uvicorn app.main:app --reload
```

Abre <http://localhost:8000>. La documentación interactiva que genera FastAPI
está en <http://localhost:8000/docs>.

## API

Todo lo que hace la interfaz está disponible como API.

### Series

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/series` | Lista las series, cada una con su última comprobación. |
| `POST` | `/api/series` | Crea una serie (`201`). |
| `GET` | `/api/series/publishers` | Editoriales para el desplegable: las ya usadas más las habituales. |
| `GET` | `/api/series/{id}` | Una serie con su última comprobación. |
| `PUT` | `/api/series/{id}` | Actualiza la serie. |
| `DELETE` | `/api/series/{id}` | Borra la serie **y su historial** (`204`, sin cuerpo). |
| `GET` | `/api/series/{id}/checks` | Historial de comprobaciones, de la más reciente a la más antigua. |

Cuerpo de alta y edición: `title` (obligatorio), `volume`, `publisher`,
`last_number`, `notes`. El campo `next_number` es de solo lectura y siempre
vale `last_number + 1`.

### Comprobaciones

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/checks/all` | Lanza la comprobación masiva en segundo plano y responde al momento con cuántas series quedan en cola. |
| `POST` | `/api/checks/{series_id}` | Comprueba una serie y devuelve el resultado. |
| `PATCH` | `/api/checks/{check_id}` | Confirma o descarta un resultado: `{"status": "disponible"}` o `{"status": "no_encontrado"}`. Cualquier otro valor da `422`. |

Estados posibles de una comprobación: `disponible`, `posible`,
`no_encontrado` y `error`. Solo tú puedes fijar `disponible`; la comprobación
automática nunca pasa de `posible`.

### Importación

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/import/preview` | Sube el fichero (multipart) y devuelve columnas, primeras filas y el mapeo sugerido. |
| `POST` | `/api/import/confirm-file` | Importa: el fichero más el mapeo `{columna: campo}` en JSON, juntos en la misma petición multipart. |

El fichero no se guarda entre llamadas, por eso hay que reenviarlo al
confirmar.

## Tests

```bash
python -m pytest tests/
```

Los tests usan una BD temporal propia y no tocan `found_comics.db`.

## Estructura

| Ruta | Qué hay |
|---|---|
| `app/main.py` | Arranque, montaje de `/static` y servido de `index.html`. |
| `app/models.py`, `app/schemas.py` | Modelos SQLAlchemy y esquemas pydantic. |
| `app/routers/` | Rutas HTTP: `series`, `checks`, `importer`. |
| `app/services/amazon.py` | Petición y parseo de amazon.es. **Lo frágil vive aquí.** |
| `app/services/detector.py` | Decide si un resultado es el número buscado. |
| `app/services/checker.py` | Orquesta comprobar una serie y guardar el resultado. |
| `app/web/` | Interfaz: un `index.html`, un `app.js` y un `style.css`. |

### Trampas conocidas ⚠️

Las dos ya rompieron algo; van aquí para no repetirlas.

- **El orden de las rutas importa.** En FastAPI, una ruta literal debe
  declararse **antes** que la paramétrica del mismo prefijo. Si `/{series_id}`
  va primero, `/api/checks/all` y `/api/series/publishers` intentan parsear
  `"all"` y `"publishers"` como enteros y responden **422**. Ya pasó con
  `/all`, y por eso `/publishers` está declarada antes que `/{series_id}`.
- **`DELETE` responde 204, sin cuerpo.** En el frontend, `api()` no debe hacer
  `res.json()` en esas respuestas: reventaba con *Unexpected end of JSON input*
  y el botón *Borrar* parecía no funcionar (el servidor sí borraba, pero la
  lista no se refrescaba).
- **Nada de `asyncio.run()` dentro de una tarea en segundo plano**: ya corre
  sobre el event loop y lanza `RuntimeError`. El checker es una corrutina y se
  usa con `await`. Además, una tarea de fondo debe abrir **su propia** sesión
  de BD: la de la petición se cierra al responder.

## Notas importantes

- Amazon no ofrece API pública sin cuenta de Afiliados, por lo que se consulta
  la página pública de búsqueda. Esto es **frágil por diseño**: si Amazon
  cambia su HTML o intensifica su anti-bot (`bm-verify`, CAPTCHA), las series
  quedarán en estado `error` sin romper nada. Toda esa lógica está aislada en
  `app/services/amazon.py` (parseo) y `app/services/detector.py` (coincidencia),
  con tests basados en fixtures HTML para poder repararla fácilmente.
- La comprobación es **semiautomática**: se marca "posible" cuando un
  resultado contiene el título de la serie y una referencia clara al número
  buscado; el enlace permite confirmar o descartar el resultado.
- Entre los candidatos válidos **no gana el primero, sino el que más señales
  reúne**: editorial que coincide con la que anotaste (+3), volumen presente
  (+2) y número citado en contexto —"nº 3", "vol. 3"— en vez de suelto (+1). A
  igualdad manda el orden de Amazon. Por eso merece la pena rellenar la
  editorial: es la señal que más desempata.
- Se **descartan de entrada** las ediciones en otro idioma y los formatos
  digitales o de audio (`tome`, `english`, `kindle`, `audible`…). La lista se
  puede ajustar con la variable de entorno `FOUND_COMICS_EXCLUDE`
  (separada por comas; vacía = no descartar nada).
- Variable de entorno `FOUND_COMICS_DB` para cambiar la ruta de la base de
  datos (por defecto `./found_comics.db`).
- Nota de entorno (Windows): en algún equipo Windows Defender ha bloqueado
  por reputación el binario `pydantic-core==2.46.5`. Si ocurre, instala una
  versión de `pydantic` cuyo `pydantic-core` no esté marcado (por ejemplo
  `pip install "pydantic==2.14.0b1"`, que trae core 2.48.0). En macOS/Linux
  no aplica y se usa el `pydantic` estable de `requirements.txt`.