-- Bootstrap for local/CI Postgres: creates the two roles CLAUDE.md rule 1 requires.
-- Run once per database by docker-compose (postgres image's /docker-entrypoint-initdb.d)
-- or by CI before migrations. Never run by application migrations (see 0001_role_grants.py).
--
--   migrator  - owns all schema objects, DDL rights, used only by `alembic upgrade`
--   app_rw    - DML only (SELECT/INSERT/UPDATE/DELETE via default privileges), no DDL,
--               no BYPASSRLS; this is the only role the running application uses.
--
-- Passwords here are local/CI development defaults, not used anywhere else.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'migrator') THEN
        CREATE ROLE migrator LOGIN PASSWORD 'migrator_dev_pw' CREATEDB;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
        CREATE ROLE app_rw LOGIN PASSWORD 'app_rw_dev_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;

SELECT 'CREATE DATABASE erp_core OWNER migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'erp_core')\gexec

GRANT CONNECT ON DATABASE erp_core TO app_rw;
