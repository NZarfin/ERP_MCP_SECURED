# Roadmap — built with Claude Code

## How to run each phase with Claude Code
1. New session per phase (or per task). Start with: "Read CLAUDE.md and docs/ROADMAP.md
   phase N. Enter plan mode and propose the task breakdown." Review the plan before any code.
2. Let it work task by task; commit after each green task. Ask for the `security-reviewer`
   subagent on every PR touching auth, tenancy, commands, documents or plugins.
3. A phase is done only when its exit criteria pass in CI — not when it "looks done".
4. Update this file's checkboxes and write an ADR in `docs/adr/` for any decision that changed.

Principle for ordering: get the guardrails in *before* the features that need them. The core
command layer, RLS and audit exist before any AI touches data.

---

## Phase 0 — Foundations (1–2 weeks)
- [ ] Monorepo skeleton per CLAUDE.md, `uv` workspace, Makefile, docker-compose
      (Postgres+pgvector, NATS, MinIO, IdP)
- [ ] CI pipeline stages 1–4 from CICD.md
- [ ] Tenancy seam: middleware token → tenant → `SET app.tenant_id`; RLS helper for models;
      test that fails when any tenant table lacks a policy
- [ ] DB roles: `migrator` (DDL) vs `app_rw` (DML only)
- [ ] Audit log + transactional outbox + NATS relay
- [ ] Command base class (idempotency, propose/commit, audit, outbox)
**Exit:** a demo command writes a row, audit entry and event in one tx; cross-tenant read test
fails as expected; app role cannot `CREATE TABLE`.

> Prompt: "Implement phase 0 from docs/ROADMAP.md. Start in plan mode. Pay special attention to
> the RLS coverage test and the DB role separation; show me the SQL for roles and policies
> before writing Python."

## Phase 1 — Core domain (3–4 weeks)
- [ ] parties, catalog, price lists
- [ ] sales (quote, pro forma draft, order), purchasing (PO, receipt)
- [ ] inventory stock-move ledger with lots/best-before
- [ ] custom fields + custom entity types (JSON Schema validated)
- [ ] REST API for web app, generated OpenAPI
**Exit:** order-to-delivery and PO-to-receipt flows covered by integration tests; custom field
added at runtime without a migration.

## Phase 2 — MCP gateway (2 weeks)
- [ ] OAuth 2.1 with IdP, scoped tokens, per-tenant endpoint
- [ ] Tool registry from core modules; annotations; propose/commit with confirm_token
- [ ] Entitlements table (tenant ↔ SKU) enforced on list + call
- [ ] Rate limits, cost budgets, tool-call audit
- [ ] `evals/` harness + first 30 eval cases (incl. "no commit without confirm")
**Exit:** Claude Desktop/claude.ai connects as a custom connector, creates a customer and a
sales order through propose → confirm; disabled module's tools are invisible.

## Phase 3 — Documents & invoicing (3 weeks)
- [ ] CompanyProfile + brand kit; logo colour extraction
- [ ] TemplateConfig schema + 3 base layouts (modern, classic, compact) with required blocks
- [ ] Renderer service (WeasyPrint, pinned fonts), preview endpoint
- [ ] Voice/image → CompanyProfile + TemplateConfig flow (propose → user confirms)
- [ ] Template lock/versioning; numbering series; issue; credit note; object-locked storage
- [ ] Golden tests
**Exit:** user creates a pro forma template from a spoken description + logo, locks it, issues
10 invoices; re-rendering any of them gives the identical hash; gapless numbering under
concurrent issue test.

## Phase 4 — Plugin SDK + Email module (3 weeks)
- [ ] `packages/plugin-sdk`: base MCP server, manifest loader, core client, event client,
      contract test suite
- [ ] `/new-module` scaffold works end to end
- [ ] Email plugin: Gmail + Microsoft Graph OAuth, sync, threading, send (two-phase)
- [ ] Ingestion pipeline: extractor (no tools) → resolver → TaskProposal → review inbox
- [ ] Injection eval fixtures
**Exit:** a real mailbox produces sensible task proposals linked to the right customers; the
malicious-email fixtures produce zero write actions.

## Phase 5 — WhatsApp module (2 weeks)
- [ ] Meta Cloud API: webhook receiver (signature verified), media download to storage,
      message templates, 24-hour service window handling
- [ ] Same ingestion pipeline; outbound via two-phase tool
- [ ] Metering of messages
**Exit:** customer order via WhatsApp → task proposal → sales order draft → confirmed reply.

## Phase 6 — Automations (3 weeks)
- [ ] DSL JSON Schema + JSONLogic conditions + templated params
- [ ] Engine (event + schedule triggers), run log, limits, loop protection, kill switch
- [ ] NL → DSL generator, explanation, 30-day dry run
**Exit:** "When stock of any herb drops under its reorder point, draft a PO to the default
supplier and give the purchaser a task" works from a single sentence, with dry-run output.

## Phase 7 — Reporting, knowledge, import/export (3 weeks)
- [ ] Semantic layer + `reporting.query`
- [ ] Vega-Lite chart specs, server rendering
- [ ] Report definitions + narrative with number check
- [ ] Exports PDF/PPTX/XLSX/DOCX with brand kit; CSV/XLSX import mappings with dry run
- [ ] Knowledge import (PDF/DOCX/PPTX) → pgvector, `knowledge.search`
**Exit:** "Monthly margin report per customer group as a PowerPoint" produces a branded deck
whose numbers match the ledger.

## Phase 8 — Commercial readiness (2–3 weeks)
- [ ] Billing (subscriptions + usage meters), self-serve onboarding, module marketplace page
- [ ] GDPR tooling: tenant export, deletion, retention jobs; DPA
- [ ] Load test, pen test, backups + restore drill, runbooks, status page
**Exit:** a stranger can sign up, connect email, issue an invoice and pay — without us.

## MVP cut
If time is short, ship phases 0–3 + 4 (email only) to a single design partner — ideally a fresh
produce/herbs wholesaler whose workflows you know — and let their real usage decide whether
WhatsApp or Automations comes next.
