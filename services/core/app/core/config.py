from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for services/core.

    `database_url` is the app_rw connection: DML only, no DDL, no BYPASSRLS. It is the
    only connection string the running application ever uses. Migrations run separately
    as the `migrator` role via `migrator_database_url` (see migrations/env.py) and are
    never invoked from application code.
    """

    model_config = SettingsConfigDict(env_prefix="ERP_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app_rw:app_rw_dev_pw@localhost:5432/erp_core"
    migrator_database_url: str = (
        "postgresql+psycopg://migrator:migrator_dev_pw@localhost:5432/erp_core"
    )
    environment: str = "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
