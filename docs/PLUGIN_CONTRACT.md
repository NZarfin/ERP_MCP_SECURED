# Plugin contract

A plugin is a paid module: one container image, one MCP server, one manifest, one SKU.

## manifest.yaml
```yaml
name: whatsapp
version: 1.4.0                 # semver; breaking tool/event change = major
sku: mod_whatsapp
display_name: WhatsApp Business
requires_core: ">=1.8 <2"
tools:
  - name: whatsapp.send_message
    input_schema: schemas/send_message.json
    output_schema: schemas/send_message_result.json
    annotations: { destructiveHint: false, idempotentHint: true, openWorldHint: true }
    scopes: [whatsapp:send]
    two_phase: true            # outbound messages to customers need confirmation by default
  - name: whatsapp.search_conversations
    input_schema: schemas/search.json
    annotations: { readOnlyHint: true }
    scopes: [whatsapp:read]
events:
  emits:    [message.received.v1, message.sent.v1]
  consumes: [task.created.v1]
core_permissions:              # which core commands the plugin may call
  - parties.lookup
  - tasks.propose
config_schema: schemas/config.json   # per-tenant settings (phone number id, templates, ...)
secrets: [meta_access_token]         # stored encrypted by platform, injected at runtime
metering:
  - { meter: messages_sent, unit: message }
```

## Rules
1. The plugin never reads core's database and never imports core code. It uses core's API with
   a service token limited to `core_permissions`.
2. Its own data lives in its own schema/database, still tenant-scoped with RLS.
3. Events are versioned (`*.v1`), JSON-Schema-defined in `packages/contracts`, published via the
   plugin's own outbox. Consumers must be idempotent.
4. Tools follow the gateway's naming (`<plugin>.<verb>_<noun>`), schemas and annotations.
5. Must pass the shared contract test suite from `packages/plugin-sdk/testing`: manifest valid,
   schemas backward compatible with the previous release (schema diff), health/readiness,
   tenant isolation, idempotent event handling.
6. Released independently; the gateway reads manifests from the registry at deploy time.
   Enabling/disabling for a tenant is a billing/entitlement change, never a deploy.

## Lifecycle
scaffold (`/new-module`) → contracts → implement with SDK → contract tests → evals →
staging with a test tenant → canary → GA → SKU active in billing.
