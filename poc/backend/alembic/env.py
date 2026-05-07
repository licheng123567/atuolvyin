import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.base import Base  # noqa: E402
import app.models  # noqa: F401, E402 — register all models with metadata
from app.core.config import settings  # noqa: E402

config = context.config

# Honor any URL already set on the alembic Config (e.g. test injecting a
# fresh container URL); only fall back to app settings when alembic.ini
# still holds the placeholder.
_existing_url = config.get_main_option("sqlalchemy.url") or ""
if not _existing_url or _existing_url.startswith("driver://"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Only consider tables defined in ORM metadata.
# Legacy PoC tables (from init.sql) are not in metadata → never dropped.
def include_object(object, name, type_, reflected, compare_to):  # noqa: A002
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
