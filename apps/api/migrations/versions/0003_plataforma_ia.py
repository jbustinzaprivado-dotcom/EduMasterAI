"""Fases 5-6: versiones de modelo, despliegues por institución y predicciones de riesgo.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17 20:02:15.321695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('model_versions',
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('version', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('task', sa.String(length=64), nullable=False),
    sa.Column('artifact_path', sa.String(length=255), nullable=False),
    sa.Column('dataset_version', sa.String(length=64), nullable=False),
    sa.Column('threshold', sa.Double(), nullable=False),
    sa.Column('card', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('registered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions')),
    sa.UniqueConstraint('name', 'version', name='uq_model_versions_name_version')
    )
    op.create_table('model_deployments',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('approved_by', sa.Uuid(), nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('published', 'retired')", name=op.f('ck_model_deployments_status')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], name=op.f('fk_model_deployments_model_version_id_model_versions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_model_deployments_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_deployments'))
    )
    with op.batch_alter_table('model_deployments', schema=None) as batch_op:
        batch_op.create_index('ix_model_deployments_org_status', ['organization_id', 'status'], unique=False)

    op.create_table('predictions',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('enrollment_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('task', sa.String(length=32), nullable=False),
    sa.Column('score', sa.Double(), nullable=False),
    sa.Column('risk_level', sa.String(length=8), nullable=False),
    sa.Column('factors', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('feature_schema_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('review_status', sa.String(length=12), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("review_status IN ('pendiente', 'atendida', 'descartada')", name=op.f('ck_predictions_review_status')),
    sa.CheckConstraint('score >= 0 AND score <= 1', name=op.f('ck_predictions_score')),
    sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], name=op.f('fk_predictions_enrollment_id_enrollments'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], name=op.f('fk_predictions_model_version_id_model_versions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_predictions'))
    )
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_predictions_enrollment_id'), ['enrollment_id'], unique=False)
        batch_op.create_index('ix_predictions_offering_created', ['offering_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_predictions_organization_id'), ['organization_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_predictions_organization_id'))
        batch_op.drop_index('ix_predictions_offering_created')
        batch_op.drop_index(batch_op.f('ix_predictions_enrollment_id'))

    op.drop_table('predictions')
    with op.batch_alter_table('model_deployments', schema=None) as batch_op:
        batch_op.drop_index('ix_model_deployments_org_status')

    op.drop_table('model_deployments')
    op.drop_table('model_versions')
