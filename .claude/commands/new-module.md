---
description: Scaffold a new paid plugin module from the plugin SDK
argument-hint: <module-name> <one-line purpose>
---
Scaffold a new plugin: $ARGUMENTS

1. Read docs/PLUGIN_CONTRACT.md and packages/plugin-sdk/README.md.
2. Enter plan mode and propose: manifest (tools, events, core_permissions, config schema,
   metering), storage model, and which tools are two-phase. Wait for my approval.
3. After approval create `plugins/<module-name>/` with: manifest.yaml, schemas/, src/, tests/
   (including the SDK contract test suite), migrations/, Dockerfile, README.md, CLAUDE.md
   (module-specific rules, <40 lines).
4. Add event schemas to packages/contracts, CI path filter, Helm values, and 3+ eval cases.
5. Run `make lint test` for the module and ask the security-reviewer subagent to review.
