# apps/web

Next.js 14 (App Router) + TypeScript + Tailwind. Phase 1 scope: read/filter only —
`/sales` and `/purchases`, each a filterable, sortable, paginated ledger view over
`services/core`'s REST API (`app/api/sales.py`, `app/api/purchasing.py`). No
create/edit forms yet; order creation stays API/seed-driven until a later phase
(see `docs/ROADMAP.md`'s review-inbox/approvals UI, which needs write flows this
pass deliberately doesn't build).

## Design system: "Market Ledger"

Built for the actual audience — wholesale ops people running a produce/herbs
business, not a marketing site. Dense information layout, tabular numbers, status
color strictly reserved (never repurposed, never color-alone — every badge carries
a text label). Dark charcoal base, one saturated accent (fresh-produce green),
amber/rust reserved for status only. Display type is Fraunces (a serif with real
character, evoking market-stall signage/ledger books); body is IBM Plex Sans; all
numeric columns use IBM Plex Mono with tabular figures so amounts and dates align.

## Running it

```
cp .env.local.example .env.local   # defaults already point at the seeded demo tenant
npm install
npm run dev                         # needs services/core's API running, see `make serve`
```

Full local stack: `make seed` (once, populates the demo tenant) → `make serve`
(services/core's API) → `npm run dev` here.

## Auth

`NEXT_PUBLIC_TENANT_ID` is a placeholder (`lib/api.ts`), mirroring the REST API's own
`X-Tenant-Id` header placeholder (`app/api/deps.py`). Real OAuth 2.1 sessions are
Phase 2 (`docs/ROADMAP.md`) — this is the one place that changes when that lands.
