# services/automation-engine

Executes the validated automation DSL (event/schedule triggers, JSONLogic conditions,
templated params). No LLM decides actions at execution time (CLAUDE.md rule 4). Run
log, per-automation kill switch, loop protection, 30-day dry run before activation.
See `docs/ARCHITECTURE.md` §7. Phase 6 of `docs/ROADMAP.md`.
