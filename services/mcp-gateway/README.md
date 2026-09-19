# services/mcp-gateway

Single MCP endpoint per tenant: OAuth 2.1, entitlement checks, rate/cost limits, tool
registry (core + enabled plugins), audit of every tool call. See
`docs/ARCHITECTURE.md` §9. Phase 2 of `docs/ROADMAP.md` — needs `services/core`'s
command layer (phase 0, done) and domain modules (phase 1) to have something to expose.
