# AGENTS.md — Memoria del proyecto Found Comics

> **Qué es este fichero.** El estado y la memoria viva del proyecto: decisiones tomadas,
> trampas que ya nos han costado caro, historial de cambios y lo que queda por hacer.
> Está versionado en git y los asistentes lo leen al empezar cada sesión, así que sirve
> tanto de recordatorio para Luis como de contexto para la herramienta que toque.
>
> **Es la base común, independiente de la herramienta.** `CLAUDE.md` lo importa con
> `@AGENTS.md` y solo añade lo específico de Claude Code. No dupliques contenido allí:
> si vale para cualquier asistente, va aquí.
>
> El **README.md** explica *cómo usar* el proyecto (rutas de la API, instalación,
> variables). Este fichero explica *por qué está como está*. Si dudas dónde escribir algo:
> documentación de uso → README; decisión, incidente o estado → aquí.
>
> **Cómo mantenerlo**: ver [Cómo actualizar este fichero](#cómo-actualizar-este-fichero)
> al final. Regla corta: se actualiza en el mismo commit que el cambio que lo motiva.

**Última actualización:** 31 de agosto de 2026

---

## 1. Qué es y dónde está

**Found Comics** es una app web **local** para saber si el siguiente número de las series
de tu colección de cómics ya está a la venta en Amazon España.

| | |
|---|---|
| **Repositorio** | https://github.com/Alcaudon/found_comics (**público**, cuenta `Alcaudon`) |
| **Local** | `/Users/luisbarriga/Dev/found_comics` |
| **Rama principal** | `master` — **ojo, no `main`** |
| **Flujo de trabajo** | Los cambios entran **por Pull Request** contra `master`, no empujando directo |
| **Despliegue** | **Ninguno.** Se ejecuta solo en local; no hay servidor ni CI/CD |

**Estado: funciona en local y estable.** No hay nada desplegado ni pensado para exponerse
a internet.

---

## 2. Arquitectura en una pantalla

Un solo paquete Python, sin monorepo ni build de frontend.

- **Backend** — FastAPI + SQLAlchemy 2 + SQLite.
  - `app/main.py`: arranque, montaje de `/static` y servido de `index.html`.
  - `app/routers/`: `series`, `checks`, `importer`.
  - `app/services/amazon.py`: petición y parseo de amazon.es. **Todo lo frágil vive aquí.**
  - `app/services/detector.py`: decide si un resultado es el número buscado.
  - `app/services/checker.py`: orquesta comprobar una serie y guardar el resultado.
- **Frontend** — `app/web/`: un `index.html`, un `app.js` y un `style.css`. Bootstrap 5
  por CDN. **Sin framework, sin bundler, sin paso de build.**
- **Base de datos** — SQLite en `found_comics.db` (ignorada por git). La ruta se cambia
  con la variable de entorno `FOUND_COMICS_DB`.

Las tablas se crean con `Base.metadata.create_all()` al arrancar. **No hay migraciones**
(ver trampas).

---

## 3. Entorno de desarrollo local

**El Python del sistema (3.9.6) NO sirve.** FastAPI y pydantic recientes exigen ≥3.10, y
`pip install -r requirements.txt` falla con `No matching distribution found for pydantic`.

Se instaló **Python 3.12 con Homebrew** y el entorno virtual vive en `.venv`:

```bash
# si hubiera que rehacerlo
brew install python@3.12
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

No hace falta activar el entorno: se puede invocar por ruta.

```bash
./.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000
./.venv/bin/python -m pytest tests/         # los tests usan su propia BD temporal
```

**Copias de trabajo nuevas (worktrees).** `.venv` y `found_comics.db` están
ignoradas por git, así que un worktree recién creado nace sin entorno y sin datos.
`scripts/setup-worktree.sh` lo rehace: busca un Python ≥3.10, crea el entorno,
instala las dependencias y —si lo lanza Orca, que pasa `$ORCA_ROOT_PATH`— copia la
base de datos del checkout principal. Orca lo ejecuta solo al crear cada worktree
según `orca.yaml`; a mano es `bash scripts/setup-worktree.sh`.

---

## 4. Decisiones tomadas (y por qué)

- **Se raspa la página pública de amazon.es, no una API.** Amazon no ofrece API pública
  sin cuenta de Afiliados. Es frágil por diseño del sitio, y por eso está aislado en
  `services/amazon.py` (parseo) y `services/detector.py` (coincidencia), con tests sobre
  fixtures HTML para poder repararlo sin adivinar.
- **La comprobación es semiautomática y nunca afirma «disponible» por su cuenta.** El
  detector como mucho llega a `posible`; es Luis quien confirma o descarta viendo el
  enlace. Preferimos un falso positivo visible a un falso negativo silencioso.
- **Entre los candidatos gana el que más señales reúne, no el primero.** Devolver el
  primero que casaba dejaba la decisión en manos del orden de Amazon, patrocinados
  incluidos. Ahora puntúa: editorial coincidente (+3), volumen presente (+2) y número
  citado en contexto (+1).
- **Las exclusiones de idioma/formato son una constante + variable de entorno, no un campo
  en la BD.** Un campo por serie obligaría a migrar (que aquí no existe, ver trampas) y a
  rellenar más formulario, para algo que en la práctica es igual en todas las series.
  `FOUND_COMICS_EXCLUDE` permite ajustarlo sin tocar el código.
- **La editorial es un `<datalist>`, no un `<select>` cerrado.** Da la lista cómoda pero
  sigue admitiendo escribir una nueva, sin necesidad de una pantalla de gestión de
  editoriales. El endpoint mezcla las que ya usas con las habituales del cómic español.
- **El cache-busting de `app.js`/`style.css` se calcula solo** (mtime de `/static`), en vez
  de un número de versión a mano que se olvidaría de subir.
- **`requirements.txt` fija pydantic estable**, no la beta. La beta `2.14.0b1` solo es un
  apaño para un equipo Windows concreto (ver README), no la configuración normal.
- **El setup de los worktrees es un script versionado, no un comando en los ajustes
  de Orca.** Puesto en la app solo valdría para esta máquina y no se podría ejecutar a
  mano; en `scripts/setup-worktree.sh` sirve también para preparar un clon nuevo y se
  puede depurar como cualquier otro script. `orca.yaml` se limita a invocarlo.
- **El worktree recibe una copia de la base de datos, no un enlace.** Compartir el
  fichero dejaría que un agente probando cualquier cosa escribiera en la colección de
  verdad; copiarlo da datos reales con los que probar y un destrozo que se arregla
  borrando el worktree.
- **Los cambios entran por Pull Request.** Aunque el repo sea de una sola persona, da la
  pantalla de revisión del diff antes de que nada toque `master`.

---

## 5. Trampas conocidas ⚠️

Cada una de estas ya rompió algo. Antes de tocar el área correspondiente, léela.

### El Python del sistema no vale
El Mac trae 3.9.6 y el proyecto necesita **≥3.10**. El síntoma es un error de pip poco
evidente (`Could not find a version that satisfies pydantic`) porque pip **ignora en
silencio** las versiones que piden un Python mayor. Usa siempre `./.venv/bin/python`.

### FastAPI: el orden de las rutas importa
Una ruta literal debe declararse **antes** que la paramétrica del mismo prefijo. Con
`/{series_id}` declarada primero, `/api/checks/all` intentaba parsear `"all"` como entero
y devolvía **422**: la comprobación masiva ni siquiera llegaba al servidor. Por eso `/all`
y `/api/series/publishers` van declaradas antes que sus `/{id}`.

### `DELETE` devuelve 204 y no lleva cuerpo
El helper `api()` del frontend hacía `res.json()` siempre y reventaba con *Unexpected end
of JSON input*. El servidor **sí borraba**, pero el error impedía refrescar la lista y el
botón *Borrar* parecía roto. Cualquier respuesta sin cuerpo debe devolver `null`.

### Nada de `asyncio.run()` dentro de una tarea en segundo plano
Ya se está sobre el event loop y lanza `RuntimeError: asyncio.run() cannot be called from
a running event loop`, que caía en un `except Exception` genérico y marcaba **todas** las
series como `error`. El checker es una corrutina y se usa con `await`.

### Una tarea de fondo necesita su propia sesión de BD
La sesión que inyecta `get_db` se cierra al responder la petición. Si la tarea la
reutiliza, trabaja sobre una sesión cerrada. Abre y cierra una `SessionLocal()` propia.

### `create_all()` no altera tablas que ya existen
No hay migraciones. Añadir un campo al modelo **no** modifica la tabla en una BD ya
creada: el código espera una columna que no está. Si algún día se añade un campo, hay que
migrar a mano (o borrar la BD local, que aquí es aceptable).

### Amazon bloquea de forma intermitente: no es un bug
Aparece como `Agotados los reintentos: Página de bloqueo detectada: ''` (su anti-bot
`bm-verify`, que devuelve una página con `<title>` vacío). **No es un fallo del código**:
minutos antes y después la misma consulta funciona. Se mitigó (sesión HTTP compartida con
cookies, sin rotar el User-Agent a media sesión, pausa de ~3 s con jitter), pero no se
puede eliminar. La respuesta correcta es reintentar más tarde.

### El navegador cachea `app.js` con ganas
Al cambiar el frontend, recargar no bastaba: seguía ejecutando el JS viejo (la función
nueva ni existía en `window`). De ahí el cache-busting por mtime. Si sospechas que estás
viendo código viejo, comprueba que el `<script>` lleva `?v=` y abre con la query cambiada.

---

## 6. Historial de cambios

De lo más reciente a lo más antiguo.

| Fecha | Cambio |
|---|---|
| 31-ago-2026 | **Setup de worktrees** (#7): `scripts/setup-worktree.sh` (Python ≥3.10, entorno, dependencias y copia de la BD) enganchado a Orca con `orca.yaml`. |
| 30-ago-2026 | **`AGENTS.md` como memoria viva** y `CLAUDE.md` reducido a importarlo. |
| 30-ago-2026 | **Documentación** (#5): referencia completa de la API (12 rutas, contrastadas contra el esquema OpenAPI), estructura del proyecto y trampas conocidas. |
| 30-ago-2026 | **Menos falsos positivos** (#4): puntuación por editorial/volumen/contexto en vez de «el primero que casa», exclusión de ediciones en otro idioma y formatos digitales, y editorial como desplegable (`GET /api/series/publishers`). `publisher` deja de ser decorativo y `volume` de ser un parámetro muerto. |
| 30-ago-2026 | **Botón Borrar** (#2): `api()` ya no revienta con las respuestas 204 sin cuerpo. |
| 30-ago-2026 | Menos bloqueos de Amazon: sesión HTTP compartida con cookies y pausa con jitter. |
| 30-ago-2026 | **Arreglo de «Comprobar todas»** (#1): quitado el `asyncio.run` anidado, `/all` declarada antes que `/{series_id}`, sesión propia en la tarea de fondo. Estado **«Disponible»** confirmable a mano, cache-busting, rutas absolutas, N+1 del listado eliminado y pydantic estable. |
| 30-ago-2026 | Primer commit de la app (v0.1) y publicación del repositorio. |

---

## 7. Pendiente

Sin prioridad asignada:

- **Marcar series como «en seguimiento» o pausadas.** La comprobación masiva consulta
  *todas*, incluidas las terminadas o abandonadas: con ~3 s por serie son minutos y otras
  tantas oportunidades de que Amazon bloquee.
- **`last_number` es un entero**, así que no expresa el número 0, los especiales ni los
  bises.
- **`volume` es ambiguo**: unas veces es el año, otras la saga, otras el volumen real. O se
  usa de verdad en la coincidencia, o se renombra a algo honesto.
- **El formato no se distingue** (grapa, tomo, integral). Hoy `NOISE_TOKENS` los ignora,
  así que un integral puede casar como si fuera el número suelto.
- **No hay tests de frontend**; todos los tests son del backend.
- **Modal propio en vez de `window.confirm`** al borrar.
- Si Amazon cambia su HTML, el sitio por donde empezar es `tests/fixtures/*.html` y
  `parse_search_page`.

---

## Cómo actualizar este fichero

Cuando terminemos un cambio que deje algo de esto desfasado, se actualiza **en el mismo
commit** que el cambio. En concreto:

- **Siempre**: añade una línea al [Historial](#6-historial-de-cambios) y pon al día la
  fecha de «Última actualización» al principio.
- **Si el cambio resuelve o crea un pendiente**: quítalo o añádelo en [Pendiente](#7-pendiente).
- **Si algo te rompió de forma no evidente**: escríbelo en [Trampas conocidas](#5-trampas-conocidas-️),
  explicando el síntoma y la causa, no solo la solución. Es la sección más valiosa.
- **Si elegiste entre dos opciones razonables**: anota cuál y por qué en
  [Decisiones](#4-decisiones-tomadas-y-por-qué). Dentro de seis meses no te acordarás.

Lo que **no** va aquí: cómo se usa la app o la API (eso es el README), lo específico de una
herramienta concreta (eso es `CLAUDE.md`), ni detalles que el propio código ya cuenta con
claridad.
