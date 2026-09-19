# Architecture

## 1. What we are building

An ERP whose primary interface is MCP: users (and their AI clients — Claude, ChatGPT, our own
web app) run the business through tools, while the system guarantees that data structure,
legal documents and money flows stay correct no matter what the AI does.

Revenue model: a **core** subscription (parties, catalog, buying, selling, stock, invoicing,
tasks) plus **paid modules** (Email, WhatsApp, Storage/Drive, Reporting & Exports, Knowledge,
Automations Pro). Each module = one plugin = one SKU = one set of MCP tools that appear only
when the tenant is entitled to it.

### Design principles
1. **Deterministic core, probabilistic edges.** LLMs interpret, summarise, draft and propose.
   Deterministic code validates, stores, numbers, renders and executes.
2. **Everything the AI creates is a declarative artefact validated by a schema** — template
   configs, automation definitions, chart specs, custom field definitions, report definitions,
   import mappings. Never generated code, never generated SQL.
3. **Metadata-driven flexibility.** Custom fields, custom entities, views, automations,
   templates and reports are tenant *data*, so every tenant can shape the system without
   anyone changing the schema. This is the differentiator vs. classic ERP/CRM.
4. **Independent deployability where it pays off**, not everywhere (§3).

## 2. System overview

```
AI clients (Claude, ChatGPT, own web app)
        │  MCP (Streamable HTTP, OAuth 2.1, tenant-scoped tokens)
        ▼
┌───────────────── mcp-gateway ─────────────────┐
│ auth · entitlement check · rate/cost limits    │
│ tool registry (core + enabled plugins)         │
│ audit of every tool call                       │
└──────┬───────────────────────────┬─────────────┘
       ▼                           ▼
  services/core               plugins/* (email, whatsapp, storage, ...)
  (modular monolith)          each: own MCP server, own schema/db, own deploy
  - command layer             - talk to core ONLY via core's public API
  - domain modules            - consume/emit events on NATS
  - outbox ──► NATS ◄─────────┘
       ├─► automation-engine (consumes events, runs DSL)
       ├─► renderer (PDF/PPTX/XLSX/DOCX, charts)
       └─► ingestion workers (summarise/extract → task proposals)
PostgreSQL (RLS) · pgvector · object storage (object lock) · NATS JetStream
```

## 3. Tenancy and scaling — decision

The draft said "each user scaled horizontally with everything deployed separately". Taken
literally (a full stack per customer) this multiplies hosting cost and ops work by the number
of customers and slows every release. Decision:

| Tier | Isolation | For |
|---|---|---|
| Pooled (default) | Shared services + shared Postgres cluster, RLS on `tenant_id` | Self-serve customers |
| Dedicated DB | Shared services, own database (same schema) | Larger customers, residency asks |
| Silo | Full stack per tenant from the same Helm chart + values file | Enterprise contracts only |

What *is* deployed separately: every **plugin** (own release cadence and scaling — WhatsApp
webhook traffic behaves nothing like invoicing), the **gateway**, **renderer**, **automation
engine** and **ingestion workers**. All stateless, horizontally scaled with HPA; state lives in
Postgres / NATS / object storage.

Tenancy is resolved in exactly one place (token → tenant → DB connection + `SET app.tenant_id`),
so moving a tenant between tiers is a data migration, not a rewrite. Build that seam in phase 0.

## 4. Core domain (services/core)

Modules (each a package with `commands/`, `queries/`, `models/`, `events/`, `tests/`):

- **parties** — customers, suppliers, contacts, addresses, VAT ids (VIES check)
- **catalog** — products, units, packaging, price lists, customer-specific prices
- **sales** — quotes, pro formas, sales orders, deliveries
- **purchasing** — purchase orders, receipts, supplier invoices
- **inventory** — locations, stock moves (append-only ledger), lots / best-before dates
- **invoicing** — invoices, credit notes, numbering series, VAT (NL 21/9/0, EU reverse charge)
- **payments** — payment records, matching, open items
- **documents** — company profile, brand kit, templates, issued documents
- **tasks** — tasks, task proposals, source links (message / email / document / event)
- **custom** — custom field definitions, custom entity types, saved views
- **reporting** — semantic layer (metrics), report definitions
- **audit** — append-only log of every command

### Command layer (the only write path)
```
Command(input: PydanticModel, actor, tenant, idempotency_key, mode: propose|commit)
  → authorize (role + scope + entitlement)
  → validate (schema + domain invariants)
  → propose: return Proposal(diff, human summary, confirm_token, expires_at)   # no writes
  → commit:  one DB transaction → rows + audit entry + outbox event
  → Result
```
The MCP gateway, web app, automation engine and plugins all call the same commands. There is
no second write path, so no client can route around the guardrails.

### Flexibility without schema changes
- `custom_field_definitions(tenant_id, entity, key, type, validation, …)`; values live in a
  `custom` JSONB column on the entity, validated against definitions on every write. Hard limits
  on count, types and key format. AI may *propose* a field via `custom.define_field`; it can
  never alter columns.
- Custom entity types (e.g. "Quality complaint", "Trial shipment") in
  `custom_records(tenant_id, type_id, data jsonb, links)` with a JSON Schema per type, GIN index.
- Saved views, automations, reports, templates — all tenant data.

## 5. Documents: pro formas, invoices, templates

### Creating a template by voice + images
1. User speaks or types ("Pro forma in our green, logo top-left, bank details in the footer,
   payment 14 days"). Speech → transcription.
2. User uploads logo / letterhead photo / business card / an old invoice PDF.
3. AI extracts a **CompanyProfile** (name, address, KvK, VAT, IBAN, contacts) → shown as a form,
   confirmed field by field, stored and reused everywhere.
4. Brand kit derived deterministically from the logo (dominant colours, contrast-checked),
   editable.
5. AI produces a **TemplateConfig** validated against
   `packages/contracts/template-config.schema.json`: base layout id (curated set), colours, font
   (allowlist, bundled in the renderer image), block order, optional blocks on/off, free texts,
   locale, number/date formats.
6. Live preview with sample data; iterate by voice.
7. User **locks** it → `template_version` v1: immutable, content-hashed. Edits create v2.

Legally required blocks (seller identity, VAT ids, number, dates, VAT breakdown, reverse-charge
wording when applicable) are part of the base layouts and cannot be disabled by config. That is
how "always the same and always valid" is guaranteed rather than hoped for.

Sandboxed custom Jinja layouts for power users (with a checker proving required blocks exist)
come much later, not in MVP.

### Issuing
`invoicing.issue(draft_id)` in one transaction: lock the numbering-series row → assign next
number → freeze data snapshot → render with the pinned template version → store PDF in the
object-locked bucket → store sha256 → state `issued`. The record is then read-only; corrections
go through `invoicing.credit_note`. Retention 7 years (NL fiscal).

## 6. Ingestion → summaries → tasks

```
connector (email / whatsapp / storage / internal events) → Message (normalised, stored by plugin)
  → threader (deterministic: headers, chat id, time window)
  → extractor (LLM, NO tools, structured output):
       summary, intent, mentioned entities, action items, dates, confidence
  → resolver (deterministic): match sender/entities to parties, orders, products
  → TaskProposal(source refs, suggested owner, due, links, confidence)
  → auto-accept ONLY if a user-approved rule matches; otherwise review inbox (web + MCP)
  → Task (status, owner, SLA, linked entities, link to source)
```
- Dedup: same thread or embedding similarity to an open task → update, don't duplicate.
- Digest per user on a schedule ("12 new, 3 overdue, 2 customers waiting > 24h").
- Internal outputs (audit events, failed automations, low stock) use the same pipeline.

## 7. Automations

```yaml
id: auto_reorder_basil
version: 3
trigger: { event: inventory.stock_below_threshold, filter: { product.tags: ["herbs"] } }
conditions: { "<": [ { var: "stock.qty" }, { var: "product.reorder_point" } ] }   # JSONLogic
actions:
  - tool: purchasing.create_po_draft
    params: { supplier_id: "{{product.default_supplier_id}}", lines: "{{reorder_lines}}" }
  - tool: tasks.create
    params: { title: "Review PO for {{product.name}}", assignee: "role:purchaser" }
limits: { max_runs_per_hour: 5 }
```
- AI converts natural language into this DSL; validated against schema, entitlements and the
  author's permissions.
- Before activation: plain-language explanation + **dry run on the last 30 days of events**
  ("would have fired 14×, creating 14 PO drafts").
- Actions are the same commands MCP uses → same guardrails. Money-moving actions produce drafts
  or proposals unless the user explicitly opts into commit for that automation version.
- `llm.classify` / `llm.summarize` actions return *data* for later steps; never a tool choice.
- Versioned, kill switch per automation, run history, loop protection.

## 8. Reporting, charts, knowledge, import/export

- **Semantic layer:** metrics in YAML (revenue, gross margin, waste %, stock turnover, DSO,
  top customers) compiled to SQL by our code. Tool: `reporting.query(metrics, dimensions,
  filters, period)`. The AI selects metrics; it never writes SQL.
- **Charts:** AI returns a Vega-Lite spec bound to a query result; validated and rendered
  server-side, so exports look identical everywhere.
- **Reports:** saved definitions (queries + charts + narrative). Numbers in the narrative must
  appear in the query result (automated check) — no hallucinated figures.
- **Export:** PDF, PPTX (tenant brand master), XLSX (real tables/formulas), DOCX, CSV.
- **Import:** CSV/XLSX via validated import mappings (preview, dry run, per-row errors).
  Documents (PDF/DOCX/PPTX) → Knowledge module: parsed, chunked, embedded in pgvector per
  tenant, searchable via `knowledge.search`, citable in reports.

## 9. MCP gateway

- One endpoint per tenant, OAuth 2.1 against our IdP (Zitadel or Keycloak), scoped tokens
  (`sales:read`, `invoicing:write`, …).
- Tool registry = core tools + manifests of enabled plugins. Disabled module ⇒ tools not listed
  and calls rejected.
- Tool design: few, domain-level, well-described tools (`sales.create_order`, not `insert_row`);
  input + output schema, annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`).
- Commit calls require the `confirm_token` from the matching proposal.
- Per-tenant rate limits and LLM cost budgets; every call audited.

## 10. Plugins
See `docs/PLUGIN_CONTRACT.md`.

## 11. Security, privacy, compliance
- EU hosting only. GDPR: DPA, per-tenant export and deletion, retention per data class
  (chat messages ≠ fiscal records).
- Connector credentials (OAuth refresh tokens, WhatsApp tokens) encrypted with per-tenant keys.
- WhatsApp **only via the official WhatsApp Business Platform (Cloud API)**. Unofficial
  WhatsApp-Web libraries break Meta's terms and get numbers banned — fatal for a paid module.
  Budget for business verification, message-template approval and Meta's per-message fees in the
  SKU price.
- Email: Gmail API / Microsoft Graph via OAuth first, IMAP fallback.
- Supply chain: SBOM, signed images, pinned dependencies, secret scanning.

## 12. Observability
OpenTelemetry traces gateway → core → plugins with tenant id; structured logs without personal
data; per-tenant metrics (tool calls, errors, LLM tokens/cost, queue lag, automation runs);
alerts on outbox lag, DLQ growth, render failures, golden-test drift.

## 13. Open decisions (confirm before phase 2)
1. Web frontend: Next.js (assumed) vs. server-rendered (HTMX) for build speed.
2. LLM provider(s) for extraction/summaries; bring-your-own-key per tenant or not.
3. Subscription billing: Mollie vs. Stripe.
4. Accounting depth: in-house double-entry ledger vs. sync to Exact / Twinfield / Moneybird.
5. First design partner and which module they pay for first.
