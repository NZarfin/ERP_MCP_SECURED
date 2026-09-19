"""Role separation: migrator (DDL, owns objects) vs app_rw (DML only).

Revision ID: 0001
Revises:
Create Date: 2026-09-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Roles themselves are created once by infra/docker/init-db.sql (local/CI) or
    # Terraform (cloud) -- never by application migrations, since that needs
    # superuser and must not repeat on every deploy. This migration only wires up
    # grants, assuming both roles already exist.
    #
    # Every table `migrator` creates from now on automatically grants DML to
    # app_rw; app_rw itself is never granted CREATE, so it cannot issue DDL.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw"
    )
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA public TO app_rw")


def downgrade() -> None:
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_rw")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_rw"
    )
