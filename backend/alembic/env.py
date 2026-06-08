from logging.config import fileConfig
from sqlalchemy import create_engine
from sqlalchemy import pool
from alembic import context
import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import Base metadata from our models
from server.models.database import Base
from server.models import control_plane as _control_plane_models  # noqa: F401
from server.database_urls import (
    get_database_runtime_settings_from_env,
    get_sync_database_url,
    get_sync_engine_options,
)

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

configured_database_url = config.get_main_option("sqlalchemy.url")
db_settings = get_database_runtime_settings_from_env(default_database_url=configured_database_url)
config.set_main_option("sqlalchemy.url", get_sync_database_url(db_settings["database_url"]))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    sync_database_url = get_sync_database_url(db_settings["database_url"])
    engine_options = get_sync_engine_options(
        sync_database_url,
        connect_timeout_seconds=db_settings["connect_timeout_seconds"],
        statement_timeout_seconds=db_settings["statement_timeout_seconds"],
    )
    connectable = create_engine(
        sync_database_url,
        poolclass=pool.NullPool,
        pool_pre_ping=True,
        **engine_options,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
