"""Async engine construction shared by the app and Alembic.

Handles the differences between local Postgres and managed providers (Neon, RDS, Cloud SQL):
- normalises postgres:// / postgresql:// URLs to the asyncpg driver
- translates libpq-style ``sslmode`` (which asyncpg does not understand) into ``ssl``
- requires SSL for non-local hosts unless the URL says otherwise
- disables prepared-statement caching behind transaction poolers (PgBouncer / Neon pooler)
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

LOCAL_HOSTS = frozenset({None, "", "localhost", "127.0.0.1", "::1", "db", "postgres"})
_DROP_QUERY_KEYS = ("sslmode", "channel_binding")


@dataclass(frozen=True)
class EngineSpec:
    url: URL
    connect_args: dict[str, Any] = field(default_factory=dict)


def build_engine_spec(raw_url: str, *, pooled: bool | None = None) -> EngineSpec:
    url = make_url(raw_url)
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2", "postgresql+psycopg"}:
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)
    sslmode = query.get("sslmode")
    explicit_ssl = query.pop("ssl", None)
    url = url.set(query={k: v for k, v in query.items() if k not in _DROP_QUERY_KEYS})

    connect_args: dict[str, Any] = {}
    ssl = explicit_ssl or sslmode
    if isinstance(ssl, str):
        if ssl not in {"disable", "allow"}:
            connect_args["ssl"] = ssl
    elif url.host not in LOCAL_HOSTS:
        connect_args["ssl"] = "require"

    is_pooled = pooled if pooled is not None else "-pooler" in (url.host or "")
    if is_pooled:
        # Transaction poolers cannot keep server-side prepared statements across checkouts.
        url = url.update_query_dict({"prepared_statement_cache_size": "0"})
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid4()}__"

    return EngineSpec(url=url, connect_args=connect_args)


def create_engine(
    raw_url: str,
    *,
    pooled: bool | None = None,
    pool_size: int = 5,
    max_overflow: int = 5,
    null_pool: bool = False,
) -> AsyncEngine:
    spec = build_engine_spec(raw_url, pooled=pooled)
    if null_pool:
        return create_async_engine(spec.url, connect_args=spec.connect_args, poolclass=NullPool)
    return create_async_engine(
        spec.url,
        connect_args=spec.connect_args,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # serverless DBs (Neon) suspend; drop dead connections
        pool_recycle=300,
    )
