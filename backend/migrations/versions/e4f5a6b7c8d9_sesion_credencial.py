"""Añade la versión de credencial a cada sesión de usuario.

La ruta Bearer ya comparaba ``cred`` contra ``password_changed_at``, pero la
cookie HttpOnly no tenía forma de detectar un cambio de contraseña concurrente
con el inicio de sesión. Esta columna aditiva guarda la versión vigente al
crear la sesión; las filas heredadas quedan en NULL y se rechazan (fail closed)
hasta que el usuario inicie sesión de nuevo.

No modifica datos existentes y no admite downgrade automático.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_session",
        sa.Column("credential_version", sa.Integer(), nullable=True),
        schema="seg",
    )


def downgrade() -> None:
    raise RuntimeError(
        "La columna de versión de credencial no admite downgrade automático; "
        "requiere ticket y aprobación explícita."
    )
