from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from core.config import settings
from models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _ensure_version_table_capacity(connection) -> None:
    """Keep Alembic revision identifiers safe on PostgreSQL.

    Alembic creates ``alembic_version.version_num`` as VARCHAR(32) by default.
    No Name 4.x uses descriptive revision identifiers longer than 32 characters,
    so PostgreSQL would otherwise roll back a perfectly valid migration when it
    tries to persist the new revision id.  Prepare/widen the table before Alembic
    starts its migration transaction.
    """
    if connection.dialect.name != "postgresql":
        return
    connection.execute(text(
        "CREATE TABLE IF NOT EXISTS public.alembic_version "
        "(version_num VARCHAR(128) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    ))
    connection.execute(text(
        "ALTER TABLE public.alembic_version "
        "ALTER COLUMN version_num TYPE VARCHAR(128)"
    ))
    connection.commit()


def _run_with_connection(connection) -> None:
    _ensure_version_table_capacity(connection)
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Application startup supplies a connection that has already passed a
    # connectivity check. CLI Alembic keeps the traditional behavior.
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_with_connection(supplied_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
