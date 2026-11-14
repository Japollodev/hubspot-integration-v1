import asyncio
import os
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import URL, make_url

from app.core.config import BACKEND_DIR, Settings
from app.main import create_app

ClientFactory = Callable[..., TestClient]

DEFAULT_TEST_DB = "postgresql+asyncpg://importer:importer@localhost:5432/importer_test"


def asyncpg_dsn(url: str | URL) -> str:
    """SQLAlchemy URL -> plain DSN that asyncpg.connect() accepts (str(URL) masks the password)."""
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[ClientFactory]:
    with ExitStack() as stack:

        def _make(**overrides: object) -> TestClient:
            overrides.setdefault("frontend_dist", tmp_path / "missing-dist")
            settings = Settings(environment="test", log_json=False, **overrides)  # type: ignore[arg-type]
            # Entering the client runs the app lifespan (DB engine, HubSpot http client).
            return stack.enter_context(TestClient(create_app(settings)))

        yield _make


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


async def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = await asyncpg.connect(asyncpg_dsn(target.set(database="postgres")))
    try:
        exists = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target.database
        )
        if not exists:
            await admin.execute(f'CREATE DATABASE "{target.database}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session")
def database_url() -> str:
    """Migrated test database. Skips locally if Postgres is down (run `make db-up`); fails in CI."""
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB)
    try:
        asyncio.run(_ensure_database(url))
    except OSError as exc:  # connection refused / host down; auth errors should fail loudly
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Postgres not reachable ({exc}); run `make db-up`")

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    return url


@pytest.fixture
def clean_db(database_url: str) -> str:
    async def _truncate() -> None:
        conn = await asyncpg.connect(asyncpg_dsn(database_url))
        try:
            await conn.execute("TRUNCATE uploads CASCADE")
        finally:
            await conn.close()

    asyncio.run(_truncate())
    return database_url
