"""RLS coverage: the test GUARDRAILS.md §1 requires -- fails if any tenant table
lacks a policy. Every table with a `tenant_id` column (per app/db/base.py's
`tenant_table_names`) must have Row-Level Security enabled and at least one policy.
"""

import psycopg
from app.db.base import tenant_table_names
from app.modules import registry  # noqa: F401  (registers every model on Base.metadata)


def test_every_tenant_table_has_rls_enabled(migrator_conn: psycopg.Connection) -> None:
    tables = tenant_table_names()
    assert tables, "expected at least one tenant table to be registered"

    with migrator_conn.cursor() as cur:
        cur.execute(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relname = ANY(%s) AND relkind = 'r'",
            (list(tables),),
        )
        rows = {name: enabled for name, enabled in cur.fetchall()}

    missing = tables - rows.keys()
    assert not missing, f"tenant tables not found in the database: {missing}"
    not_enabled = {name for name, enabled in rows.items() if not enabled}
    assert not not_enabled, f"tenant tables without RLS enabled: {not_enabled}"


def test_every_tenant_table_has_a_policy(migrator_conn: psycopg.Connection) -> None:
    tables = tenant_table_names()

    with migrator_conn.cursor() as cur:
        cur.execute(
            "SELECT tablename, count(*) FROM pg_policies "
            "WHERE tablename = ANY(%s) GROUP BY tablename",
            (list(tables),),
        )
        counts = dict(cur.fetchall())

    missing = {t for t in tables if counts.get(t, 0) == 0}
    assert not missing, f"tenant tables without any RLS policy: {missing}"


def test_every_tenant_table_has_a_tenant_leading_index(migrator_conn: psycopg.Connection) -> None:
    tables = tenant_table_names()

    with migrator_conn.cursor() as cur:
        cur.execute(
            "SELECT t.relname "
            "FROM pg_index ix "
            "JOIN pg_class t ON t.oid = ix.indrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ix.indkey[0] "
            "WHERE t.relname = ANY(%s) AND a.attname = 'tenant_id'",
            (list(tables),),
        )
        covered = {row[0] for row in cur.fetchall()}

    missing = tables - covered
    assert not missing, f"tenant tables without a tenant_id-leading index: {missing}"
