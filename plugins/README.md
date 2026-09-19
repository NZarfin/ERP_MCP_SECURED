# plugins/

Independently deployable paid modules (Email, WhatsApp, Storage, Reporting, ...). Each
is one container image, one MCP server, one manifest, one SKU — see
`docs/PLUGIN_CONTRACT.md`. Scaffold a new one with `/new-module` (see
`.claude/commands/new-module.md`); the first one (Email) lands in phase 4 of
`docs/ROADMAP.md`, after the plugin SDK exists.
