"""Contenido de lecciones con versión (§4.3) y gestión de contraseñas (cambio obligatorio tras restablecer).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-18 20:37:01.968682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Valores por defecto en el servidor: la migración se aplica sobre bases que ya tienen datos (despliegue).
    with op.batch_alter_table('course_activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content', sa.Text(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('resources', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, server_default=sa.text("'[]'")))
        batch_op.add_column(sa.Column('video_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('content_version', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('content_updated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('content_updated_by', sa.Uuid(), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('password_changed_at')
        batch_op.drop_column('must_change_password')

    with op.batch_alter_table('course_activities', schema=None) as batch_op:
        batch_op.drop_column('content_updated_by')
        batch_op.drop_column('content_updated_at')
        batch_op.drop_column('content_version')
        batch_op.drop_column('video_url')
        batch_op.drop_column('resources')
        batch_op.drop_column('content')

