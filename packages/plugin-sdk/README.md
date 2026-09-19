# packages/plugin-sdk

Base MCP server, manifest loader, core API client, event client and the contract test
suite every plugin must pass (manifest valid, schemas backward compatible, tenant
isolation, idempotent event handling). See `docs/PLUGIN_CONTRACT.md`. Phase 4 of
`docs/ROADMAP.md`, built alongside the first real plugin (Email) so the SDK's shape
is proven by a real consumer rather than guessed upfront.
