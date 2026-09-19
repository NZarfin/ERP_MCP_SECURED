# Guardrails — keeping AI from damaging the business

Prompt instructions are not a safety mechanism. Every guarantee below is enforced by
architecture, permissions or tests, so it holds even if the model misbehaves or is manipulated.

## 1. Schema and data structure
| Guarantee | Enforced by |
|---|---|
| AI cannot change schema | Runtime DB role `app_rw` has no DDL / no ownership; migrations run only in CI as `migrator` |
| AI cannot run arbitrary SQL | No tool accepts SQL or table/column names; reporting uses the semantic layer |
| Tenants cannot see each other | RLS `USING (tenant_id = current_setting('app.tenant_id')::uuid)` on every tenant table; test that fails if a table lacks a policy |
| Custom data stays well-formed | JSON Schema validation on every write to `custom` / `custom_records` |
| Migrations are safe | `squawk` lint in CI; expand → migrate → contract pattern; no destructive migration without an ADR |
| Merged migrations never change | Claude Code hook + CI check comparing against `main` |

## 2. Immutable, consistent documents
- `template_version` rows are insert-only (trigger rejects UPDATE/DELETE).
- Issued documents: insert-only + object-locked PDF + sha256; nightly job re-hashes a sample.
- Invoice numbering: `numbering_series` row locked `FOR UPDATE` inside the issue transaction;
  numbers assigned only at issue; unique constraint `(tenant_id, series_id, number)`.
- **Golden tests:** each base layout × fixture data renders to a stored PDF/PNG hash. Any drift
  fails CI. Fonts and renderer versions pinned in the image.

## 3. Two-phase commit for risky tools
Tools flagged `destructiveHint` or touching money/stock/legal documents:
1. `…(mode="propose")` → validates, returns a diff, human-readable summary and `confirm_token`
   (bound to tenant, actor, input hash; expires in 10 min).
2. `…(mode="commit", confirm_token=…)` → executes only if the input hash matches.
The web app shows proposals as approve/reject cards; MCP clients surface them to the user.

## 4. Idempotency and reversibility
- Every command takes an idempotency key; retries never double-book.
- Deletes are soft for master data; financial records are never deleted — only reversed
  (credit note, stock correction move, payment reversal).
- Full audit log (actor, client, tool, input, result, correlation id).

## 5. Untrusted input (prompt injection)
- Email, WhatsApp, uploaded documents and web content are **data**.
- The extractor LLM has no tools; its output is schema-validated JSON.
- IDs from LLM output are never trusted — the resolver looks them up deterministically within
  the tenant.
- Any action derived from inbound content is a proposal unless a user-approved rule applies.
- Never combine, in one LLM call: untrusted content + write tools + an outbound channel.

## 6. Automations
- DSL only, schema-validated; actions limited to an allowlist of commands the author may call.
- Dry run before activation; rate limits; loop protection; kill switch; run log.
- Upgrading an automation from "draft/propose" to "commit" requires an explicit user action.

## 7. Cost and abuse limits
Per-tenant quotas on tool calls, LLM tokens, renders, messages sent; hard stop + alert.

## 8. Evals (run in CI)
`evals/` contains scripted MCP conversations executed against a seeded tenant, asserting:
- the right tool is selected for common requests,
- no commit happens without a proposal + confirmation,
- injection fixtures (malicious emails/WhatsApps) produce no write actions,
- report narratives contain only numbers present in query results.
