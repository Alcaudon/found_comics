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
- **Comprobación en Amazon**: para cada serie construye la consulta
  `"{título} {volumen} {siguiente número}"`, consulta amazon.es y marca el
  resultado como **posible** (con enlace y precio) para que confirmes
  visualmente.
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