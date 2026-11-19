"""Fase 2: rutas de aprendizaje con etapas, asignaciones y excepciones (§4.2).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-18 19:08:10.986839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('learning_paths',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('objective', sa.Text(), nullable=False),
    sa.Column('competencies', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('target_weeks', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name=op.f('ck_learning_paths_status')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_learning_paths_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_paths')),
    sa.UniqueConstraint('organization_id', 'code', name='uq_learning_paths_org_code')
    )
    with op.batch_alter_table('learning_paths', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_paths_organization_id'), ['organization_id'], unique=False)

    op.create_table('learning_path_assignments',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('path_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('assigned_by', sa.Uuid(), nullable=False),
    sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source', sa.String(length=80), nullable=False),
    sa.Column('target_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('exceptions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('active', 'completed', 'cancelled')", name=op.f('ck_learning_path_assignments_status')),
    sa.ForeignKeyConstraint(['path_id'], ['learning_paths.id'], name=op.f('fk_learning_path_assignments_path_id_learning_paths'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_learning_path_assignments_student_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_path_assignments'))
    )
    with op.batch_alter_table('learning_path_assignments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_path_assignments_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_path_assignments_path_id'), ['path_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_path_assignments_student_id'), ['student_id'], unique=False)

    op.create_table('learning_path_steps',
    sa.Column('path_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('min_grade', sa.Float(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_learning_path_steps_course_id_courses'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['path_id'], ['learning_paths.id'], name=op.f('fk_learning_path_steps_path_id_learning_paths'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_path_steps'))
    )
    with op.batch_alter_table('learning_path_steps', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_path_steps_path_id'), ['path_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('learning_path_steps', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_path_steps_path_id'))

    op.drop_table('learning_path_steps')
    with op.batch_alter_table('learning_path_assignments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_path_assignments_student_id'))
        batch_op.drop_index(batch_op.f('ix_learning_path_assignments_path_id'))
        batch_op.drop_index(batch_op.f('ix_learning_path_assignments_organization_id'))

    op.drop_table('learning_path_assignments')
    with op.batch_alter_table('learning_paths', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_paths_organization_id'))

    op.drop_table('learning_paths')
