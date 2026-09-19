#!/usr/bin/env python3
"""PreToolUse guard for Claude Code.

Convenience layer only: the real enforcement lives in CI and DB permissions.
Blocks:
  * edits to migrations that already exist on origin/main
  * edits to golden render fixtures
  * edits to generated contract bundles
  * shell commands aimed at staging/prod or doing raw destructive SQL
"""
import json
import os
import re
import subprocess
import sys

PROJECT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
MIGRATION_DIRS = ("services/core/migrations/versions/", "plugins/")  # plugins/*/migrations/versions/
PROTECTED_PREFIXES = ("tests/golden/", "packages/contracts/dist/")

DANGEROUS_BASH = [
    (r"\b(DROP|TRUNCATE)\s+(TABLE|SCHEMA|DATABASE)\b", "Raw destructive SQL is not allowed. Write a reviewed migration."),
    (r"\bALTER\s+TABLE\b", "Schema changes go through Alembic migrations, not ad-hoc SQL."),
    (r"(staging|prod|production)[\w.-]*\.(internal|cloud|com|nl|eu)", "Commands against staging/prod are not allowed from Claude Code."),
    (r"\balembic\s+downgrade\b.*--sql\s*$|\balembic\s+stamp\b", "alembic stamp/offline downgrade must be run by a human."),
    (r"\bgit\s+push\b.*\b(main|master)\b", "Push to a branch and open a PR; never push to main."),
]


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def rel(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), PROJECT).replace(os.sep, "/")


def exists_on_main(relpath: str) -> bool:
    for ref in ("origin/main", "main"):
        r = subprocess.run(["git", "-C", PROJECT, "cat-file", "-e", f"{ref}:{relpath}"],
                           capture_output=True)
        if r.returncode == 0:
            return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input", {}) or {}

    if tool in ("Edit", "Write", "MultiEdit"):
        path = tin.get("file_path") or ""
        if not path:
            return
        r = rel(path)
        if r.startswith(PROTECTED_PREFIXES):
            deny(f"{r} is protected. Golden/contract artefacts are updated by a human only.")
        is_migration = "/migrations/versions/" in r and r.startswith(MIGRATION_DIRS)
        if is_migration and exists_on_main(r):
            deny(f"{r} is already merged on main. Never edit applied migrations; create a new one "
                 f"with `uv run alembic revision -m ...`.")
        return

    if tool == "Bash":
        cmd = tin.get("command", "")
        for pattern, reason in DANGEROUS_BASH:
            if re.search(pattern, cmd, flags=re.IGNORECASE):
                deny(reason)


if __name__ == "__main__":
    main()
