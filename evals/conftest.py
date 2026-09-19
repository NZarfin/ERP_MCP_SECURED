"""Session-scoped live MCP gateway for evals/test_gateway.py.

Boots a real `uvicorn gateway.main:app` subprocess against whatever database
ERP_DATABASE_URL points at (same "migrations already applied" assumption as
services/core/tests/conftest.py -- CICD.md runs "Migrations" before "Tests").
A subprocess, not an in-process ASGI transport, because the streamable-HTTP
session manager needs the app's real ASGI lifespan to start its task group;
this is also closer to how the gateway actually runs, and it's already been
hand-verified to work end-to-end this way.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

GATEWAY_DIR = Path(__file__).resolve().parent.parent / "services" / "mcp-gateway"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture(scope="session")
def gateway_url() -> Iterator[str]:
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "gateway.main:app", "--port", str(port)],
        cwd=GATEWAY_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}/mcp/"
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                output = proc.stdout.read() if proc.stdout else ""
                raise RuntimeError(f"gateway process exited early:\n{output}")
            try:
                httpx.get(url, timeout=1)
                break
            except httpx.TransportError:
                time.sleep(0.2)
        else:
            raise RuntimeError("gateway did not start listening within 20s")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
