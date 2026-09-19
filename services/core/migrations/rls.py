"""Shared helper so every migration enables RLS the same way.

CLAUDE.md rule 1 / GUARDRAILS.md §1: every tenant table gets
`ENABLE ROW LEVEL SECURITY` plus a policy reading `app.tenant_id` from the session
(set by app/db/session.py's `tenant_session`). The app connects as `app_rw`, which is
never the table owner, so it cannot bypass RLS -- only a superuser or the owning
`migrator` role could, and neither is used by the running application.
"""

from alembic import op


def enable_rls(table_name: str, policy_name: str = "tenant_isolation") -> None:
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    # missing_ok=true (the second arg to current_setting) makes an unset app.tenant_id
    # return NULL instead of raising -- a session that forgot to call tenant_session
    # sees zero rows instead of an error, which fails closed either way.
    op.execute(
        f'CREATE POLICY "{policy_name}" ON "{table_name}" '
        f"USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        f"WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    )


def disable_rls(table_name: str, policy_name: str = "tenant_isolation") -> None:
    op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON "{table_name}"')
    op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')
