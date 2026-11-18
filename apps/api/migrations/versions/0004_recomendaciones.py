"""Fase 6: recomendaciones con estado y retroalimentación (§4.11).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-18 00:26:22.497088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('recommendations',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('enrollment_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('target_type', sa.String(length=16), nullable=False),
    sa.Column('target_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('expected_impact', sa.String(length=160), nullable=False),
    sa.Column('priority', sa.Float(), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('useful', sa.Boolean(), nullable=True),
    sa.Column('feedback_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("kind IN ('siguiente_actividad', 'entrega_proxima', 'reforzar', 'retomar')", name=op.f('ck_recommendations_kind')),
    sa.CheckConstraint("status IN ('nueva', 'aceptada', 'descartada', 'completada', 'expirada')", name=op.f('ck_recommendations_status')),
    sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], name=op.f('fk_recommendations_enrollment_id_enrollments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendations')),
    sa.UniqueConstraint('enrollment_id', 'kind', 'target_id', name='uq_recommendations_enrollment_kind_target')
    )
    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recommendations_offering_id'), ['offering_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_recommendations_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index('ix_recommendations_student_status', ['student_id', 'status'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.drop_index('ix_recommendations_student_status')
        batch_op.drop_index(batch_op.f('ix_recommendations_organization_id'))
        batch_op.drop_index(batch_op.f('ix_recommendations_offering_id'))

    op.drop_table('recommendations')
