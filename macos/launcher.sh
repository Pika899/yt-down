#!/bin/bash
# Contents/MacOS/yt-down: prepare the Python environment, then become the app process
# (exec), so the app window belongs to "yt down" in the Dock. No Terminal window.
# The bundle may be read-only or translocated: the environment lives in Application Support
# and the sources run in place (PYTHONPATH), never installed.

alert() {
  osascript -e "display alert \"yt down\" message \"$1\"" >/dev/null 2>&1
}

if [ "$(uname -m)" != "arm64" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
  alert "Questa app funziona solo sui Mac con chip Apple (M1 o successivi)."
  exit 1
fi

APP_DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
SUPPORT="$HOME/Library/Application Support/yt down"
VENV="$SUPPORT/venv"
mkdir -p "$SUPPORT"

export UV_PROJECT_ENVIRONMENT="$VENV"
export PYTHONPATH="$APP_DIR/src"
export YTDOWN_UV="$APP_DIR/bin/uv"
unset VIRTUAL_ENV
cd "$APP_DIR" || exit 1

notice_pid=""
if [ ! -x "$VENV/bin/python" ]; then
  osascript -e 'display dialog "Primo avvio: preparo yt down (un paio di minuti, serve internet). La finestra si apre da sola." with title "yt down" buttons {"OK"} default button "OK" giving up after 300' >/dev/null 2>&1 &
  notice_pid=$!
fi

if ! "$YTDOWN_UV" sync --frozen --no-dev --no-install-project --quiet >"$SUPPORT/setup.log" 2>&1; then
  if [ ! -x "$VENV/bin/python" ]; then
    [ -n "$notice_pid" ] && kill "$notice_pid" 2>/dev/null
    alert "Non sono riuscito a preparare yt down. Controlla la connessione a internet e riaprilo."
    exit 1
  fi
  # Offline with an existing environment: start with what is installed.
fi
[ -n "$notice_pid" ] && kill "$notice_pid" 2>/dev/null

# A sync interrupted halfway (e.g. connection lost) can leave a venv without packages.
if ! "$VENV/bin/python" -c "import ytdown, webview, yt_dlp, imageio_ffmpeg" >>"$SUPPORT/setup.log" 2>&1; then
  alert "yt down non è completo. Controlla la connessione a internet e riaprilo."
  exit 1
fi

exec "$VENV/bin/python" -m ytdown "$@"
