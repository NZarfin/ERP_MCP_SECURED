# ERP MCP Secured

An ERP whose primary interface is [MCP](https://modelcontextprotocol.io/): you (or your
AI client — Claude, ChatGPT, our own web app) run the business through tools, while the
system *guarantees* — by architecture, not by prompting — that data structure, legal
documents and money flows stay correct no matter what the AI does.

**Why this is worth building:** every small business already talks to an LLM about
their invoices, stock and customer emails today, informally, with copy-paste. Nobody
has given that LLM *safe, direct write access* to the actual business — because doing
that safely is hard, not because it isn't wanted. This repo is the "safely" part: a
deterministic core (schema, money, legal documents, automations) with LLMs doing only
what LLMs are good at (interpreting, drafting, summarising, proposing) at the edges.
Revenue is a **core** subscription plus **paid modules** (Email, WhatsApp, Storage,
Reporting, Automations Pro) — see `docs/ARCHITECTURE.md` for the full model.

Read `CLAUDE.md` first — it has the five rules that override everything else. Then
`docs/ARCHITECTURE.md` (what/why), `docs/GUARDRAILS.md` (how safety is enforced) and
`docs/ROADMAP.md` (build order and current phase).

## Status: Phase 0 done, Phase 1 vertical slice done, Phase 2 MCP gateway done

**Phase 0 — Foundations** (`docs/ROADMAP.md`), fully implemented and verified against
a real PostgreSQL 16 database (not mocked):

- **Tenancy seam** (`services/core/app/db/session.py`): the *only* place a request
  resolves a tenant id. `tenant_session()` opens one transaction and scopes it with
  `SELECT set_config('app.tenant_id', ..., true)` — the parameterized equivalent of
  `SET LOCAL`, so it can't be SQL-injected and is automatically undone when the
  transaction ends.
- **Row-Level Security on every tenant table**, policy generated the same way by every
  migration (`services/core/migrations/rls.py`), enforced whether the write goes
  through the command layer or raw SQL.
- **DB role separation**: `migrator` owns the schema and runs migrations; `app_rw` — the
  only role the running application ever uses — has DML rights only, no DDL, no
  `BYPASSRLS`. Verified by a test that tries `CREATE TABLE` as `app_rw` and asserts it
  fails.
- **Command layer** (`services/core/app/commands/base.py`): the single write path.
  Idempotency keys, audit log + transactional outbox in the same DB transaction, and a
  generic **propose → confirm_token → commit** flow for anything that should require
  confirmation (GUARDRAILS.md §3).

**Phase 1 — vertical slice** (not the full phase; see the scope cuts in the git log for
this work): sales and purchasing order lifecycles, a filterable web UI, seed/stress
data. Not started yet: the full catalog/price-list model, full custom-entity types,
and the remaining Phase 1 exit criteria beyond this slice.

- **Domain modules**: `parties` (customers + suppliers), `catalog` (products),
  `inventory` (locations + an append-only stock-move ledger, no mutable balance
  table), `sales` (quote-free order lifecycle: draft → confirmed → delivered/
  cancelled), `purchasing` (mirrors sales: draft → confirmed → received/cancelled),
  `custom` (tenant-defined fields, validated JSON-Schema-style on every write, proven
  on `sales_order.custom`). Every write goes through the command layer; anything
  touching money/stock is two-phase propose→commit.
- **REST API** (`services/core/app/api/`): filterable `GET /api/sales/orders` and
  `GET /api/purchasing/pos` (status, date range, counterparty, amount range,
  free-text search, sort, pagination, plus an accurate `total_value` aggregate over
  the whole filtered set) behind the same `X-Tenant-Id` placeholder auth as Phase 0.
- **`apps/web`**: Next.js 15 + Tailwind `/sales` and `/purchases` pages — read/filter
  only this pass, see `apps/web/README.md` for the design system.
- **Seed data** (`make seed`): a deterministic produce/herbs wholesaler demo tenant —
  10 suppliers, 25 customers, 30 products, 200 sales orders, 100 purchase orders.
- **Stress test** (`make stress`): concurrent read/write load against a running API,
  asserting tenant isolation holds under concurrency, not just one request at a time.
- **Autonomous roadmap loop** (`.github/workflows/roadmap-loop.yml`): nightly, picks
  the next roadmap item, implements it as one PR-sized change, opens a PR for
  review. Needs a `CLAUDE_CODE_OAUTH_TOKEN` repo secret to actually run — see that
  file and `docs/CICD.md`.
- **27 passing tests** (`make test`) across both phases, plus a real production
  `next build` and headless-browser verification of both web pages.

**Phase 2 — MCP gateway** (`services/mcp-gateway/`): a real, protocol-compliant MCP
server over the command layer above — the feature that makes this "MCP-native," not
"an ERP with a REST API." Two deliberate scope cuts from the full phase (documented,
not silent): bearer access tokens instead of OAuth 2.1 against a real IdP, and
structural evals instead of LLM-driven tool-selection evals — see
`services/mcp-gateway/README.md` for why and what a follow-up needs to change.

- **13 MCP tools** across `parties`, `catalog`, `sales`, `purchasing` — the same
  commands and queries the REST API uses, each its own domain-named tool (never a
  generic `execute_command`, per CLAUDE.md). Two-phase tools (everything but the two
  `create_*` drafts) return a `confirm_token` and `idempotency_key` on propose that
  the caller passes back to commit; committing without them is rejected before
  anything reaches the database.
- **Bearer access tokens** (`gateway.create_access_token`): tenant-scoped, hashed
  (sha256, raw token shown once), scoped, revocable. The token embeds its tenant id
  so verifying it can open the right RLS scope before looking up its hash — no
  bypass role needed.
- **Per-tenant entitlements** (`entitlement` table, one row per SKU a tenant has
  bought): a tool for a SKU the tenant isn't entitled to is invisible in `tools/list`
  and rejected on `tools/call`, verified end-to-end against a live gateway, not just
  asserted.
- **Full audit trail**: every command commit still writes `audit_log`
  (tenant/actor/idempotency-key/input/result) exactly as the REST API does; every
  tool call, including a rejected or read-only one, gets its own `gateway_call_log`
  row.
- **Per-tenant rate limiting** (in-process fixed window; a placeholder — see
  `gateway/rate_limit.py` for why a horizontally-scaled deployment needs Redis).
- Verified against a **real `mcp` SDK client**, not just unit-tested in isolation:
  `evals/test_gateway.py` boots a live gateway subprocess and drives tool visibility,
  a full propose→commit round trip, commit-without-token rejection, cross-tenant
  isolation and rate limiting, all through the real Streamable HTTP transport.

## Running it

This is a monorepo: a Python API, an MCP gateway and a separate Next.js web app --
long-running processes you run in their own terminals, no single binary.

```
make quickstart   # needs Docker: brings up Postgres, migrates, seeds the demo tenant
```

`make seed` prints a fresh bearer access token for the demo tenant -- keep it, you'll
need it for the gateway.

Then, in separate terminals:

```
make serve                                   # REST API on :8000
make serve-gateway                           # MCP gateway on :8100 (needs the token above)
cd apps/web && npm install && npm run dev    # web UI on :3000, needs the API running
```

Point an MCP client (Claude Desktop, or `evals/test_gateway.py`'s own client) at
`http://localhost:8100/mcp/` with `Authorization: Bearer <token>` -- see
`services/mcp-gateway/README.md` for the exact Claude Desktop config block.

Other commands:

```
make test     # tests against the migrated database (core + gateway)
make evals    # structural MCP gateway evals against a live gateway subprocess
make stress   # concurrent load + tenant-isolation-under-load check
make lint     # ruff + mypy --strict (Python, incl. the gateway); `cd apps/web && npm run lint` for the UI
```

Without Docker (e.g. a local `postgres` service already running -- the exact
superuser/auth setup varies by OS and install method, so this step isn't scripted):

```
sudo -u postgres psql -f infra/docker/init-db.sql   # once, creates migrator/app_rw roles
cd services/core && uv run alembic upgrade head
uv run --extra dev python -m app.seed               # from services/core
cd services/core && uv run pytest -q
```

## Repo map

See `CLAUDE.md`. Directories for later phases exist with a one-line README pointing at
the roadmap item that fills them in.
