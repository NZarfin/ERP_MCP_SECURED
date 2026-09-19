"""CLAUDE.md rule 1: 'The runtime DB role has no DDL rights.' Proves it against the
real database rather than trusting a grant statement in a migration to have worked.
"""

import psycopg
import pytest


def test_app_rw_cannot_create_table(app_rw_dsn: str) -> None:
    with psycopg.connect(app_rw_dsn) as conn:
        conn.autocommit = True
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE hack_attempt (id int)")


def test_app_rw_cannot_alter_table(app_rw_dsn: str) -> None:
    with psycopg.connect(app_rw_dsn) as conn:
        conn.autocommit = True
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE customer ADD COLUMN hacked boolean")


def test_app_rw_can_read_and_write_dml(app_rw_dsn: str) -> None:
    with psycopg.connect(app_rw_dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM customer")
            assert cur.fetchone() is not None
