"""Fase 3: notificaciones en vivo (§4.12) y certificados con verificación pública (§4.7).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18 18:35:14.217144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notifications',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=48), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('link', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index('ix_notifications_user_created', ['user_id', 'created_at'], unique=False)

    op.create_table('certificates',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('enrollment_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('folio', sa.String(length=48), nullable=False),
    sa.Column('verification_code', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('final_grade', sa.Float(), nullable=True),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('issued_by', sa.Uuid(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_by', sa.Uuid(), nullable=True),
    sa.Column('revoke_reason', sa.Text(), nullable=True),
    sa.Column('replaces_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('emitido', 'anulado')", name=op.f('ck_certificates_status')),
    sa.ForeignKeyConstraint(['enrollment_id'], ['enrollments.id'], name=op.f('fk_certificates_enrollment_id_enrollments'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_certificates')),
    sa.UniqueConstraint('folio', name=op.f('uq_certificates_folio')),
    sa.UniqueConstraint('verification_code', name=op.f('uq_certificates_verification_code'))
    )
    with op.batch_alter_table('certificates', schema=None) as batch_op:
        batch_op.create_index('ix_certificates_enrollment_status', ['enrollment_id', 'status'], unique=False)
        batch_op.create_index(batch_op.f('ix_certificates_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_certificates_student_id'), ['student_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('certificates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_certificates_student_id'))
        batch_op.drop_index(batch_op.f('ix_certificates_organization_id'))
        batch_op.drop_index('ix_certificates_enrollment_status')

    op.drop_table('certificates')
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('ix_notifications_user_created')
        batch_op.drop_index(batch_op.f('ix_notifications_organization_id'))

    op.drop_table('notifications')
