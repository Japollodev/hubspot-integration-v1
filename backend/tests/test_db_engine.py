"""URL handling for local vs managed Postgres (Neon / RDS / Cloud SQL). No DB needed."""

from app.db.engine import build_engine_spec


def test_local_url_no_ssl() -> None:
    spec = build_engine_spec("postgresql+asyncpg://u:p@localhost:5432/db")
    assert spec.url.drivername == "postgresql+asyncpg"
    assert spec.connect_args == {}


def test_neon_pooled_url_normalised() -> None:
    spec = build_engine_spec(
        "postgres://u:p@ep-x-pooler.us-east-2.aws.neon.tech/db?sslmode=require&channel_binding=require"
    )
    assert spec.url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in spec.url.query
    assert "channel_binding" not in spec.url.query
    assert spec.url.query["prepared_statement_cache_size"] == "0"
    assert spec.connect_args["ssl"] == "require"
    assert spec.connect_args["statement_cache_size"] == 0


def test_remote_host_requires_ssl_by_default() -> None:
    spec = build_engine_spec("postgresql://u:p@mydb.abc.us-east-1.rds.amazonaws.com/db")
    assert spec.connect_args == {"ssl": "require"}


def test_sslmode_disable_respected_and_pooled_override() -> None:
    spec = build_engine_spec("postgresql://u:p@10.0.0.5/db?sslmode=disable", pooled=True)
    assert "ssl" not in spec.connect_args
    assert spec.connect_args["statement_cache_size"] == 0
