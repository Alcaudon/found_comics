#!/usr/bin/env bash
#
# Deja lista una copia de trabajo del proyecto: entorno virtual, dependencias y,
# si venimos de un worktree, una copia de la base de datos local.
#
# Orca (ver orca.yaml) lo ejecuta solo cada vez que crea un worktree, pero
# también vale para preparar un clon a mano:
#
#     bash scripts/setup-worktree.sh
#
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. Un Python >= 3.10. El del sistema (3.9) no sirve, y pip lo dice de forma
#    poco evidente: "Could not find a version that satisfies pydantic".
buscar_python() {
    local candidato
    for candidato in \
        /opt/homebrew/opt/python@3.12/bin/python3.12 \
        python3.13 python3.12 python3.11 python3.10 python3
    do
        command -v -- "$candidato" >/dev/null 2>&1 || continue
        if "$candidato" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
            command -v -- "$candidato"
            return 0
        fi
    done
    return 1
}

if [ ! -x .venv/bin/python ]; then
    if ! python_bin="$(buscar_python)"; then
        echo "setup-worktree: no encuentro un Python >= 3.10 (el del sistema es 3.9 y no vale)." >&2
        echo "                Instálalo con 'brew install python@3.12' y vuelve a ejecutar." >&2
        exit 1
    fi
    echo "==> Creando .venv con $python_bin"
    "$python_bin" -m venv .venv
fi

echo "==> Instalando dependencias"
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

# 2. found_comics.db está ignorada por git, así que un worktree nuevo nace sin
#    ella. Copiamos (no enlazamos) la del checkout principal: así se prueba con
#    datos reales sin que nada de lo que pase aquí toque tu colección.
principal="${ORCA_ROOT_PATH:-}"
if [ -n "$principal" ] && [ -f "$principal/found_comics.db" ] && [ ! -e found_comics.db ]; then
    cp "$principal/found_comics.db" found_comics.db
    echo "==> Copiada found_comics.db desde el repositorio principal"
fi

cat <<'FIN'
==> Listo. En esta copia de trabajo:
      ./.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000
      ./.venv/bin/python -m pytest tests/
    Si ya tienes otro worktree sirviendo en el 8000, añade --port 8001.
FIN
