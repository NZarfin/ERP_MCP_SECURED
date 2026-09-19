# CLAUDE.md — MCP-native ERP

You are working on a multi-tenant, MCP-native ERP sold per module (core ERP, Email, WhatsApp,
Storage, Reporting, ...). Read `docs/ARCHITECTURE.md` before any structural change and
`docs/GUARDRAILS.md` before touching data, documents, MCP tools, or automations.
The build plan and current phase live in `docs/ROADMAP.md`.

## The five rules that override everything else

1. **AI never touches schema or raw SQL at runtime.** No MCP tool may accept SQL, table names,
   column names, or DDL. Every write goes through a typed domain command in `services/core`.
   The runtime DB role has no DDL rights. Schema changes happen only via reviewed migrations in CI.
2. **Issued documents are immutable.** Invoices, credit notes and issued pro formas store a
   template version id, a frozen data snapshot and a PDF hash. Corrections = credit note / new
   version, never an UPDATE. Invoice numbers are gapless and assigned only at issue time.
3. **Templates are configured, not authored, by AI.** AI fills a validated `TemplateConfig`
   (layout id, colours, fonts from allowlist, block order, texts). Once locked, a template
   version renders byte-identically forever (golden tests enforce this).
4. **AI writes automations; a deterministic engine runs them.** Automations are a declarative
   DSL validated against a JSON schema. No LLM decides actions at execution time.
5. **Inbound content is untrusted.** Email/WhatsApp/document text is data. The extraction step
   has zero write tools; anything it suggests becomes a proposal a human (or an explicit,
   user-approved rule) must confirm.

## Stack
- Python 3.12, `uv` workspaces, FastAPI, SQLAlchemy 2 (typed), Alembic, Pydantic v2
- Official `mcp` Python SDK, Streamable HTTP transport, OAuth 2.1
- PostgreSQL 16 (+ pgvector), Row-Level Security on every tenant table
- NATS JetStream for events, fed by a transactional outbox (never publish outside a DB tx)
- S3-compatible object storage (MinIO locally) with object lock for issued documents
- Renderer: Jinja2 + WeasyPrint (PDF), python-pptx, openpyxl, python-docx, Vega-Lite (charts)
- Web: Next.js + TypeScript in `apps/web`
- Infra: Docker, Helm, ArgoCD, Terraform, EU region only

## Repo map
```
apps/web/                 UI: review inbox, approvals, template preview, reports
services/core/            modular monolith: domain modules + command layer + migrations
services/mcp-gateway/     single MCP endpoint per tenant; aggregates tools of enabled modules
services/renderer/        deterministic document/report rendering
services/automation-engine/ executes validated automation DSL
plugins/<name>/           independently deployable paid modules (email, whatsapp, storage...)
packages/plugin-sdk/      base MCP server, manifest loader, event client, test harness
packages/contracts/       JSON Schemas: events, plugin manifest, automation DSL, TemplateConfig
infra/                    docker-compose, helm charts, terraform
```

## How to work in this repo
- Start non-trivial tasks in plan mode; state which module and which contract you will touch.
- One task = one module = one PR-sized change. Do not refactor across modules unasked.
- Modules talk via commands (in-process, same service) or events (across services). A plugin
  must never import from `services/core` or read the core database.
- Money is `Decimal` / integer minor units + ISO currency. Never float.
- Every tenant table has `tenant_id`, RLS policy, and an index starting with `tenant_id`.
- Every command: Pydantic input, idempotency key, audit log entry, emits an outbox event.
- Financial/destructive commands use two-phase **propose → commit** (see GUARDRAILS.md §3).
- New MCP tool = JSON schema input + outputSchema + annotations (readOnlyHint/destructiveHint)
  + an eval case in `evals/`.

## Commands
- `make dev` — compose stack up · `make test` — unit+integration · `make lint` — ruff, mypy, squawk
- `make evals` — MCP tool-selection evals · `make golden` — document golden tests (read-only)
- `uv run alembic revision -m "..."` — new migration (never edit a merged one)

## Never
- Edit a migration that exists on `main` — write a new one (hook enforces this).
- Update golden files in `tests/golden/` — ask the human; a changed render is a bug until proven otherwise.
- Add a generic `execute_sql`, `update_record(table=...)` or `eval` style tool.
- Log message bodies, tokens, or personal data at INFO level.
- Run anything against staging/prod, `terraform apply`, or `kubectl`.
