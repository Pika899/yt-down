"""PreToolUse guard: block reading secrets/cookies and committing downloaded media."""

import json
import re
import sys

event = json.load(sys.stdin)
tool = event.get("tool_name", "")
inp = event.get("tool_input", {})

SECRET = re.compile(r"(^|[/\s'\"])(\.env(\.[\w-]+)?|cookies[\w.-]*\.txt)(\s|$|['\"])")
MEDIA_ADD = re.compile(r"git\s+add\b.*(downloads/|\.(mp4|mkv|webm|m4a|part)\b|\s-A\b|\s\.(\s|$))")

reason = None
if tool == "Read":
    path = inp.get("file_path", "")
    if SECRET.search(" " + path + " "):
        reason = "Reading .env or cookie files is not allowed in this project."
elif tool == "Bash":
    cmd = inp.get("command", "")
    if re.search(r"\b(cat|less|head|tail|more|bat|grep|source)\b", cmd) and SECRET.search(cmd):
        reason = "Reading .env or cookie files is not allowed; reference variable names only."
    elif MEDIA_ADD.search(cmd):
        reason = (
            "git add of downloaded media or blanket 'git add -A/.' is blocked; "
            "add source files explicitly."
        )

if reason:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
sys.exit(0)
