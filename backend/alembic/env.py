"""Alembic environment (async). URL precedence: config.attributes["database_url"] (tests),
then DATABASE_URL_DIRECT, then DATABASE_URL."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import get_settings
from app.db.engine import build_engine_spec, create_engine
from app.db.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    override = config.attributes.get("database_url")
    if override:
        return str(override)
    settings = get_settings()
    url = settings.database_url_direct or settings.database_url
    return url.get_secret_value()


def run_migrations_offline() -> None:
    spec = build_engine_spec(_database_url(), pooled=False)
    context.configure(
        url=spec.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # Migrations should use a direct connection; pooled=False keeps prepared statements on.
    engine = create_engine(_database_url(), pooled=False, null_pool=True)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
