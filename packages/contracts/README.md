# packages/contracts

JSON Schemas that every AI-generated artefact is validated against, per
`docs/ARCHITECTURE.md` §1 principle 2: "Everything the AI creates is a declarative
artefact validated by a schema." Nothing here is generated code or SQL.

Populated starting phase 2+ (plugin manifests, event envelopes, automation DSL,
`TemplateConfig`) — see `docs/PLUGIN_CONTRACT.md`, `docs/ARCHITECTURE.md` §5/§7, and
`docs/ROADMAP.md`. CI validates every `*.schema.json` here is a well-formed JSON
Schema and checks backward compatibility against `main` (`docs/CICD.md` stage 2).
