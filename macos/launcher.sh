#!/bin/bash
# Contents/MacOS/yt-down: open Terminal with the engine window, like start-mac.command.
# Terminal gets a small script we write ourselves (no quarantine flag), so Gatekeeper does
# not re-check it; that script runs the start-mac.command bundled in the app.
if [ "$(uname -m)" != "arm64" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
  osascript -e 'display alert "yt down" message "Questa app funziona solo sui Mac con chip Apple (M1 o successivi)."' >/dev/null
  exit 1
fi
APP_DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
SUPPORT="$HOME/Library/Application Support/yt down"
mkdir -p "$SUPPORT"
LAUNCH="$SUPPORT/launch.command"
printf '#!/bin/bash\nexec /bin/bash %q\n' "$APP_DIR/start-mac.command" > "$LAUNCH"
chmod +x "$LAUNCH"
open -a Terminal "$LAUNCH"
