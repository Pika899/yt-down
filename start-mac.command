#!/bin/bash
# Double-click to start yt down on macOS (also used by "yt down.app").
cd "$(dirname "$0")" || exit 1

# The .app ships uv in bin/; the ZIP version installs it once if missing.
export PATH="$PWD/bin:$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installo uv (solo la prima volta)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERRORE: installazione di uv non riuscita. Vedi README.md, sezione \"Problemi\"."
  read -r -p "Premi Invio per chiudere."
  exit 1
fi

# Inside the .app the bundle may be read-only or moved (App Translocation): keep the
# environment outside it and run the sources in place instead of installing them.
SYNC_ARGS=(--frozen --no-dev --quiet)
VENV=".venv"
case "$PWD" in
  *.app/Contents/*)
    VENV="$HOME/Library/Application Support/yt down/venv"
    export UV_PROJECT_ENVIRONMENT="$VENV"
    export PYTHONPATH="$PWD/src"
    SYNC_ARGS+=(--no-install-project)
    ;;
esac

echo "Preparo yt down (la prima volta richiede qualche minuto)..."
if ! uv sync "${SYNC_ARGS[@]}"; then
  echo "ERRORE: installazione delle dipendenze non riuscita. Controlla la connessione e riprova."
  read -r -p "Premi Invio per chiudere."
  exit 1
fi

# YouTube changes often: keep yt-dlp current. Offline is fine, the installed version is used.
uv pip install --quiet --python "$VENV/bin/python" --upgrade "yt-dlp[default]" 2>/dev/null || true

uv run --no-sync python -m ytdown "$@" || read -r -p "Premi Invio per chiudere."
