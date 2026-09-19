#!/usr/bin/env python3
"""PostToolUse: format the edited file. Never blocks."""
import json
import subprocess
import sys

data = json.load(sys.stdin)
path = (data.get("tool_input") or {}).get("file_path", "")
if path.endswith(".py"):
    subprocess.run(["uv", "run", "ruff", "format", path], capture_output=True)
    subprocess.run(["uv", "run", "ruff", "check", "--fix", path], capture_output=True)
elif path.endswith((".ts", ".tsx", ".json", ".md", ".yaml", ".yml")):
    subprocess.run(["pnpm", "exec", "prettier", "--write", path], capture_output=True)
