@AGENTS.md

# Claude-specific

Toda la memoria del proyecto (arquitectura, decisiones, trampas, historial y pendientes)
vive en `AGENTS.md`, que la línea de arriba importa. **No dupliques nada aquí**: si vale
para cualquier asistente, va en `AGENTS.md`. Este fichero es solo para lo que depende de
Claude Code.

## Flujo de trabajo

- **Los cambios entran por Pull Request** contra `master` (no `main`), nunca empujando
  directo. Rama → commits → `gh pr create --base master` → fusionar cuando Luis lo apruebe.
- Al fusionar, borra la rama (`--delete-branch`) y sincroniza `master` en local.

## Comandos

No hay Python moderno en el PATH del sistema: **usa siempre el intérprete del entorno
virtual**, invocado por ruta.

```bash
./.venv/bin/python -m pytest tests/          # tests
./.venv/bin/uvicorn app.main:app --reload    # servidor en el 8000
```

## Verificación de cambios de interfaz

El frontend es HTML/JS servido por la propia app, así que un cambio de interfaz se
comprueba de verdad en el navegador, no solo con tests:

- Levanta el servidor y ábrelo con la herramienta de preview.
- **Añade una query distinta a la URL** (`?v=2`) al recargar: el navegador cachea el HTML
  y `app.js` con ganas, y sin eso puedes estar mirando código viejo (ver la trampa
  correspondiente en `AGENTS.md`).
- El desplegable de editoriales es un `<datalist>`: su lista es un widget nativo que **no
  sale en las capturas**. Verifícalo por DOM (`document.getElementById('publishersList')`),
  no por screenshot.

## Al tocar la búsqueda en Amazon

Amazon bloquea de forma intermitente, así que **una comprobación fallida no demuestra que
tu cambio esté mal**, ni una correcta que esté bien. Para validar `detector.py` usa los
tests y las fixtures de `tests/fixtures/`, que son deterministas, y deja la consulta en
vivo como confirmación final.
