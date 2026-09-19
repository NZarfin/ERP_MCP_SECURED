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

## Status: Phase 0 — Foundations ✅

Everything in `docs/ROADMAP.md`'s Phase 0 is implemented and verified against a real
PostgreSQL 16 database (not mocked):

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
  confirmation (GUARDRAILS.md §3) — proven end-to-end by a test.
- **Reference module** `parties.create_customer` (`services/core/app/modules/parties/`)
  exercises the whole stack: a row, an audit entry and an outbox event in one
  transaction.
- **11 passing tests** (`make test`) covering RLS coverage, cross-tenant isolation
  (including a raw-SQL cross-tenant insert rejected by `WITH CHECK`), DB role
  restrictions, and the full command lifecycle.

Phases 1–8 (core domain, MCP gateway, documents & invoicing, plugins, automations,
reporting, commercial readiness) are scoped in `docs/ROADMAP.md` and not started.

## Running it

```
make dev      # Postgres+pgvector, NATS, MinIO, IdP via docker compose, then migrate
make test     # 11 tests against the migrated database
make lint     # ruff + mypy --strict
```

Without Docker (e.g. a local `postgres` service already running):

```
sudo -u postgres psql -f infra/docker/init-db.sql   # once, creates migrator/app_rw roles
cd services/core && uv run alembic upgrade head
cd services/core && uv run pytest -q
```

## Repo map

See `CLAUDE.md`. Directories for later phases exist with a one-line README pointing at
the roadmap item that fills them in.
