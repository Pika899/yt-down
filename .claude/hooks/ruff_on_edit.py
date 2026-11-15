"""PostToolUse: format and lint an edited project Python file; report remaining issues."""

import json
import os
import subprocess
import sys
from pathlib import Path

event = json.load(sys.stdin)
path = event.get("tool_input", {}).get("file_path", "")
if not path.endswith(".py"):
    sys.exit(0)

# Only files inside this project: scratch scripts elsewhere are not ours to lint.
project = os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[2])
try:
    Path(path).resolve().relative_to(Path(project).resolve())
except ValueError:
    sys.exit(0)

try:
    subprocess.run(["uvx", "ruff", "format", "--quiet", path], check=False, timeout=60)
    check = subprocess.run(
        ["uvx", "ruff", "check", "--fix", "--quiet", path],
        capture_output=True,
        text=True,
        timeout=60,
    )
except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
    print(f"ruff hook skipped: {exc}", file=sys.stderr)
    sys.exit(0)

if check.returncode != 0:
    # exit 2 feeds stderr back to Claude so it fixes the remaining lint errors
    print(check.stdout + check.stderr, file=sys.stderr)
    sys.exit(2)
