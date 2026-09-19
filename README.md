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

## Status: Phase 0 done, Phase 1 vertical slice done

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

## Running it

```
make dev      # Postgres+pgvector, NATS, MinIO, IdP via docker compose, then migrate
make seed     # populate the demo tenant (produce/herbs wholesaler)
make serve    # REST API on :8000
make test     # tests against the migrated database
make stress   # concurrent load + tenant-isolation-under-load check
make lint     # ruff + mypy --strict (Python); `cd apps/web && npm run lint` for the UI
```

Web UI: `cd apps/web && npm install && npm run dev` (needs `make serve` running).

Without Docker (e.g. a local `postgres` service already running):

```
sudo -u postgres psql -f infra/docker/init-db.sql   # once, creates migrator/app_rw roles
cd services/core && uv run alembic upgrade head
cd services/core && uv run pytest -q
```

## Repo map

See `CLAUDE.md`. Directories for later phases exist with a one-line README pointing at
the roadmap item that fills them in.
