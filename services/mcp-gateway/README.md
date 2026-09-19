# services/mcp-gateway

A protocol-compliant MCP server (Streamable HTTP transport) that exposes `services/core`'s
command and query layer as MCP tools, one endpoint per tenant. This is the feature that
makes the product MCP-native rather than "an ERP with an API": an MCP client -- Claude
Desktop, claude.ai, or any other MCP-compatible AI client -- authenticates with a bearer
token and can list a tenant's entitled tools, create records, and drive a sales/purchase
order through the same propose → commit flow the web UI uses, without the AI ever
touching SQL (CLAUDE.md rule 1).

## Scope of this pass (Phase 2 of `docs/ROADMAP.md`)

Full Phase 2 includes OAuth 2.1 against a real IdP and LLM-driven tool-selection evals.
Two deliberate cuts, documented here so they're not mistaken for oversights:

- **Auth is a bearer access-token table, not full OAuth 2.1.** `gateway.create_access_token`
  (`services/core/app/modules/gateway/commands/create_access_token.py`) issues a token
  shaped `"<tenant_id>.<random secret>"`; only its sha256 hash is ever stored. The
  tenant id prefix solves the chicken-and-egg problem of verifying an RLS-scoped token
  table without already knowing the tenant (see that command's docstring). Swapping this
  for real OAuth 2.1 token introspection later is a contained change to `gateway/auth.py`
  only -- the tool set, entitlement model and command layer don't change.
- **Evals are structural, not LLM-driven.** `evals/test_gateway.py` proves the gateway's
  own contract against a real MCP client: right tools visible per entitlement, no commit
  without a matching confirm_token, cross-tenant isolation, rate limiting. It does not
  drive a real LLM to check it picks the right tool from a natural-language prompt --
  that needs an LLM API key in CI, which this repo doesn't add without asking.

## Layout

- `gateway/auth.py` -- `GatewayTokenVerifier`: bearer token → `(tenant_id, scopes)`.
- `gateway/rate_limit.py` -- per-tenant fixed-window limiter (in-process; a placeholder,
  see its own docstring for why a horizontally-scaled deployment needs Redis instead).
- `gateway/registry.py` -- `call_command_tool` / `call_query_tool`: the auth → scope
  check → entitlement check → rate limit → command/query layer → `gateway_call_log`
  pipeline every tool in `gateway/tools/*.py` goes through. Also installs the
  entitlement filter on `tools/list` so a module the caller isn't entitled to is
  invisible, not just rejected on call.
- `gateway/tools/{parties,catalog,sales,purchasing}.py` -- the 13 tools themselves, each
  a thin `@server.tool()` wrapper around one command or query.
- `gateway/main.py` -- builds the `MCPServer` and its ASGI app.

This package is named `gateway`, not `app`, because it shares a venv with `erp-core`
(`services/core`), whose own top-level package **is** `app` -- these files' `from app.X
import Y` lines reach erp-core's command/query layer, not this package.

## Running it

```
uv run uvicorn gateway.main:app --port 8100          # from this directory
make serve-gateway                                    # from the repo root
```

Needs a migrated database (`make migrate`) and a tenant with entitlements and an access
token. `make seed` grants the demo tenant (`app/seed.py`'s `DEMO_TENANT_ID`) all four
entitlements and prints a fresh access token.

## Tools

13 tools across four SKUs. A tenant only sees the tools for SKUs it's entitled to
(`entitlement` table); calling a tool for an unentitled SKU is rejected even if the
caller somehow knows its name.

| SKU | Scope(s) | Tools |
|---|---|---|
| `core.parties` | `parties:write` | `parties.create_customer`, `parties.create_supplier` |
| `core.catalog` | `catalog:write` | `catalog.create_product` |
| `core.sales` | `sales:read`, `sales:write` | `sales.create_order`, `sales.confirm_order`, `sales.deliver_order`, `sales.cancel_order`, `sales.list_orders` |
| `core.purchasing` | `purchasing:read`, `purchasing:write` | `purchasing.create_po`, `purchasing.confirm_po`, `purchasing.receive_po`, `purchasing.cancel_po`, `purchasing.list_pos` |

`create_order`/`create_po` are single-phase (a draft commits nothing yet). Every other
write tool is two-phase (GUARDRAILS.md §3): call with `mode="propose"` to get back a
`confirm_token`, a human-readable `summary`, and an `idempotency_key`; call again with
`mode="commit"` and both of those values to actually write. The `idempotency_key` is
generated and echoed back on propose specifically so an MCP caller -- often an LLM
mid-conversation with no memory of an id it wasn't handed -- never has to invent one
itself; it just passes back what propose returned. Calling `mode="commit"` without a
valid `confirm_token`/`idempotency_key` pair is rejected before anything reaches the
database.

## Connecting Claude Desktop

Issue a token for the tenant (via `gateway.create_access_token`, or `make seed` for the
demo tenant), then add to Claude Desktop's MCP config:

```json
{
  "mcpServers": {
    "erp": {
      "url": "http://localhost:8100/mcp/",
      "headers": {
        "Authorization": "Bearer <tenant_id>.<secret>"
      }
    }
  }
}
```

## Testing

- `services/mcp-gateway/tests/` -- unit tests for `auth.py` (token verification against
  a real database: valid, malformed, unknown-hash, revoked, cross-tenant-forged) and
  `rate_limit.py` (pure, no I/O). Run with `make test` or `uv run pytest -q
  services/mcp-gateway/tests`.
- `evals/test_gateway.py` -- boots a real gateway subprocess and drives it with the
  real `mcp` SDK client: tool visibility per entitlement, full propose→commit round
  trip, commit-without-token rejection, cross-tenant isolation, rate limiting. Run with
  `make evals`.
