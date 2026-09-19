# CI/CD

## Repository
Monorepo, `uv` workspaces (Python) + pnpm (web). Each deployable (`services/*`, `plugins/*`,
`apps/web`) has its own Dockerfile, version and pipeline, triggered by path filters plus
changes to shared `packages/*` it depends on.

## Pipeline per pull request (GitHub Actions)
1. **Static:** ruff, mypy --strict (core, sdk), eslint/tsc (web), gitleaks, semgrep.
2. **Contracts:** JSON Schema validation of manifests/events/DSL; backward-compat schema diff
   against `main` (breaking change ⇒ major version bump required).
3. **Migrations:** squawk lint; check that no migration already on `main` was modified;
   `alembic upgrade head` + `downgrade -1` + `upgrade head` on an empty DB; RLS-coverage test.
4. **Tests:** unit + integration (testcontainers: Postgres, NATS, MinIO).
5. **Golden renders:** documents and charts must match stored hashes.
6. **Evals:** MCP tool-selection and injection evals (nightly full set; PR runs a smoke subset
   to control cost).
7. **Build:** images, SBOM (syft), vulnerability scan (trivy), sign (cosign).

## Delivery
- Trunk-based; `main` always deployable. GitOps with ArgoCD: merge → staging automatically;
  promotion to prod via tag, canary 10% → 100% with automated rollback on error-rate SLO.
- Migrations run as a pre-deploy Job, must be backward compatible with the previous app version
  (expand/contract), so rollback never needs a down-migration.
- Plugins release independently; gateway picks up new manifests on deploy.
- Environments: local (compose) → preview (optional, per PR) → staging (seeded demo tenants)
  → prod (EU). Silo tenants = same chart, own values file.
- Infra changes (Terraform) via separate pipeline with plan output on PR and manual apply.
