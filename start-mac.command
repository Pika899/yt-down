#!/bin/bash
# Double-click to start yt down on macOS.
cd "$(dirname "$0")" || exit 1

# uv manages Python and every dependency; install it once if missing.
export PATH="$HOME/.local/bin:$PATH"
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

echo "Preparo yt down (la prima volta richiede qualche minuto)..."
if ! uv sync --frozen --no-dev --quiet; then
  echo "ERRORE: installazione delle dipendenze non riuscita. Controlla la connessione e riprova."
  read -r -p "Premi Invio per chiudere."
  exit 1
fi

# YouTube changes often: keep yt-dlp current. Offline is fine, the installed version is used.
uv pip install --quiet --upgrade "yt-dlp[default]" 2>/dev/null || true

uv run --no-sync python -m ytdown || read -r -p "Premi Invio per chiudere."
