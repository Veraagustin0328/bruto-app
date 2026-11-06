"""clave de idempotencia en pedidos

Revision ID: a1c4e9d2b7f3
Revises: 2ff116c7dfc0
Create Date: 2026-11-06 19:40:00

A1 de la tarea 3: el celu manda un Idempotency-Key por intento de checkout
y si con mala señal reintenta, no se crea otro pedido. Columna vacía en los
pedidos viejos (NULL no choca con el índice único, ni en Postgres ni en SQLite).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c4e9d2b7f3'
down_revision: Union[str, Sequence[str], None] = '2ff116c7dfc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pedidos', sa.Column('clave_idempotencia', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_pedidos_clave_idempotencia'), 'pedidos', ['clave_idempotencia'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_pedidos_clave_idempotencia'), table_name='pedidos')
    op.drop_column('pedidos', 'clave_idempotencia')
