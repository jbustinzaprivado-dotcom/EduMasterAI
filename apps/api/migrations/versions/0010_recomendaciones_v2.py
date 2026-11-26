"""Recomendaciones v2 (D55): nuevos tipos de sugerencia, el porqué de su orden y el motivo de cierre.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-26 01:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_KINDS = ('siguiente_actividad', 'entrega_proxima', 'reforzar', 'retomar')
NEW_KINDS = OLD_KINDS + ('vencida', 'mejorar_nota', 'competencia', 'certificado', 'ruta', 'anuncio')


def _kinds(kinds) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    # Columnas nuevas con valor por defecto en el servidor: la migración corre sobre bases con datos (D38).
    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('priority_reason', sa.String(length=160), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('resolution_note', sa.String(length=200), nullable=True))
        batch_op.drop_constraint(op.f('ck_recommendations_kind'), type_='check')
        batch_op.create_check_constraint('kind', _kinds(NEW_KINDS))


def downgrade() -> None:
    op.execute("DELETE FROM recommendations WHERE NOT (" + _kinds(OLD_KINDS) + ")")
    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_recommendations_kind'), type_='check')
        batch_op.create_check_constraint('kind', _kinds(OLD_KINDS))
        batch_op.drop_column('resolution_note')
        batch_op.drop_column('priority_reason')
