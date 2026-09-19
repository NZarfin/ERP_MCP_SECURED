---
description: Add a domain command (+ MCP tool) to a core module following the command layer rules
argument-hint: <module>.<verb_noun> <what it does>
---
Add core command: $ARGUMENTS

Follow CLAUDE.md rules. Deliver, in this order:
1. Pydantic input/output models and domain invariants (list them to me first).
2. Command implementation (idempotency, audit, outbox event, propose/commit if it affects money,
   stock, documents or outbound messages).
3. Event schema in packages/contracts if a new event is emitted.
4. Unit + integration tests including a cross-tenant access test.
5. MCP tool exposure via the mcp-tool-designer subagent, with eval cases.
