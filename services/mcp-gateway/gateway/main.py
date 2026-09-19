"""The MCP gateway: single MCP endpoint per tenant, aggregating tools of enabled
modules (CLAUDE.md repo map; ARCHITECTURE.md §9). Auth is a bearer access-token
placeholder (gateway/auth.py) for Phase 2 -- real OAuth 2.1 against an IdP is a
contained follow-up, not a rewrite, per services/mcp-gateway/README.md.

This package is named `gateway`, not `app`, because it shares a venv with
erp-core, whose own top-level package IS `app` -- these files' `from app.X
import Y` lines reach erp-core's command/query layer, not this package.

Run with: uv run uvicorn gateway.main:app --port 8100
"""

from __future__ import annotations

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl

from gateway.auth import GatewayTokenVerifier
from gateway.registry import install_entitlement_filter
from gateway.tools import catalog, parties, purchasing, sales

server: MCPServer = MCPServer(
    name="erp-gateway",
    version="0.1.0",
    title="ERP MCP Gateway",
    description="Sales, purchasing, parties and catalog tools for one tenant's ERP.",
    token_verifier=GatewayTokenVerifier(),
    auth=AuthSettings(
        # Resource-server-only: no auth_server_provider is configured, so there is
        # no dynamic client registration or token endpoint here -- these URLs are
        # identity/metadata only. GatewayTokenVerifier does the actual verification.
        issuer_url=AnyHttpUrl("http://localhost:8100/"),
        resource_server_url=AnyHttpUrl("http://localhost:8100/"),
        # GatewayTokenVerifier's tokens carry no `resource` claim (there's no
        # resource-indicator concept in the bearer-access-token placeholder scheme
        # this phase ships -- see its own docstring); disable the audience check
        # explicitly rather than let every token start failing when the SDK's
        # default flips in 3.0.
        validate_token_resource=False,
    ),
)

parties.register(server)
catalog.register(server)
sales.register(server)
purchasing.register(server)

install_entitlement_filter(server)

app = server.streamable_http_app()
