"""horario y configuracion

Revision ID: 2ff116c7dfc0
Revises: b886e8d1f535
Create Date: 2026-11-04 21:41:51.869345

Tablas para lo que Renzo cambia desde el panel, con valores iniciales:
todos los días de 18:00 a 00:30, sin link de PedidosYa y sin pausa.
"""
from datetime import time
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ff116c7dfc0'
down_revision: Union[str, Sequence[str], None] = 'b886e8d1f535'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copiados acá a propósito: si después cambian en el modelo, la migración no tiene que cambiar
MENSAJE_CERRADO = "La cantina está cerrada. ¡Te esperamos en el próximo turno!"
MENSAJE_PAUSADO = "Estamos a full en la cocina. Pausamos los pedidos un ratito, probá en unos minutos"


def upgrade() -> None:
    configuracion = op.create_table(
        'configuracion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('link_pedidosya', sa.String(length=500), nullable=True),
        sa.Column('pedidos_pausados', sa.Boolean(), nullable=False),
        sa.Column('mensaje_cerrado', sa.String(length=300), nullable=False),
        sa.Column('mensaje_pausado', sa.String(length=300), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    horarios = op.create_table(
        'horarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dia_semana', sa.Integer(), nullable=False),
        sa.Column('abierto', sa.Boolean(), nullable=False),
        sa.Column('abre', sa.Time(), nullable=False),
        sa.Column('cierra', sa.Time(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dia_semana'),
    )

    op.bulk_insert(configuracion, [{
        'id': 1,
        'link_pedidosya': None,
        'pedidos_pausados': False,
        'mensaje_cerrado': MENSAJE_CERRADO,
        'mensaje_pausado': MENSAJE_PAUSADO,
    }])
    # 0 = lunes ... 6 = domingo. Abre 18:00 y cierra 00:30 del día siguiente
    op.bulk_insert(horarios, [
        {'dia_semana': dia, 'abierto': True, 'abre': time(18, 0), 'cierra': time(0, 30)}
        for dia in range(7)
    ])


def downgrade() -> None:
    op.drop_table('horarios')
    op.drop_table('configuracion')
