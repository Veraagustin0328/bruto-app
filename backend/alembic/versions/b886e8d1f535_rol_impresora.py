"""rol impresora

Revision ID: b886e8d1f535
Revises: 3edc39188607
Create Date: 2026-11-04 21:38:47.892285

El rol se guarda como texto (VARCHAR(7), lo largo de "cantina").
"impresora" tiene 9 letras, así que hay que agrandar la columna.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b886e8d1f535'
down_revision: Union[str, Sequence[str], None] = '3edc39188607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.alter_column(
            'rol',
            existing_type=sa.VARCHAR(length=7),
            type_=sa.Enum('admin', 'cantina', 'cocina', 'impresora', name='rol', native_enum=False),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Los usuarios impresora no entran en VARCHAR(7): los paso a cocina y los doy de baja
    op.execute("UPDATE usuarios SET rol = 'cocina', activo = false WHERE rol = 'impresora'")
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.alter_column(
            'rol',
            existing_type=sa.Enum('admin', 'cantina', 'cocina', 'impresora', name='rol', native_enum=False),
            type_=sa.VARCHAR(length=7),
            existing_nullable=False,
        )
