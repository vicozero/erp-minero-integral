from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base

# Importar modelos para poblar Base.metadata.
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.costing import models as costing_models  # noqa: F401
from app.modules.documentation import models as document_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.integrations import models as integration_models  # noqa: F401
from app.modules.inventory import models as inventory_models  # noqa: F401
from app.modules.maintenance import models as maintenance_models  # noqa: F401
from app.modules.master_data import models as master_models  # noqa: F401
from app.modules.organization import models as organization_models  # noqa: F401
from app.modules.purchasing import models as purchasing_models  # noqa: F401
from app.modules.requisitions import models as requisition_models  # noqa: F401
from app.modules.workflow import models as workflow_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
