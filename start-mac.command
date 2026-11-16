#!/bin/bash
# Double-click to start yt down on macOS from the ZIP (the .app uses macos/launcher.sh).
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

export UV_PYTHON_PREFERENCE=only-managed  # uv's own Python, pinned in .python-version
echo "Preparo yt down (la prima volta richiede qualche minuto)..."
if ! uv sync --frozen --no-dev --quiet; then
  echo "ERRORE: installazione delle dipendenze non riuscita. Controlla la connessione e riprova."
  read -r -p "Premi Invio per chiudere."
  exit 1
fi

# The app updates yt-dlp itself at every start, using this uv.
YTDOWN_UV="$(command -v uv)"
export YTDOWN_UV
uv run --no-sync python -m ytdown "$@" || read -r -p "Premi Invio per chiudere."
