# infra/terraform

EU-region cloud infrastructure (`docs/ARCHITECTURE.md` §3, §11). Runs as a separate
pipeline with plan output on PR and manual apply (`docs/CICD.md`) — Claude Code never
runs `terraform apply` (CLAUDE.md "Never", `.claude/hooks/guard.py`). Added at phase 8
commercial readiness; phase 0-7 target local/staging only.
