"""Fase 4: catálogo de competencias, vínculos con cursos y evaluaciones, y validación docente (§4.9).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-18 19:41:31.701388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('skills',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_skills_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['parent_id'], ['skills.id'], name=op.f('fk_skills_parent_id_skills'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skills')),
    sa.UniqueConstraint('organization_id', 'code', name='uq_skills_org_code')
    )
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_skills_organization_id'), ['organization_id'], unique=False)

    op.create_table('course_skills',
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_course_skills_course_id_courses'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_course_skills_skill_id_skills'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('course_id', 'skill_id', name=op.f('pk_course_skills'))
    )
    op.create_table('skill_validations',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('estimated_level_at_validation', sa.Integer(), nullable=True),
    sa.Column('validated_by', sa.Uuid(), nullable=False),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('level >= 1 AND level <= 5', name=op.f('ck_skill_validations_level')),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_skill_validations_skill_id_skills'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_skill_validations_student_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_validations'))
    )
    with op.batch_alter_table('skill_validations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_skill_validations_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_skill_validations_student_id'), ['student_id'], unique=False)

    op.create_table('assessment_skills',
    sa.Column('assessment_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_assessment_skills_assessment_id_assessments'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_assessment_skills_skill_id_skills'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('assessment_id', 'skill_id', name=op.f('pk_assessment_skills'))
    )


def downgrade() -> None:
    op.drop_table('assessment_skills')
    with op.batch_alter_table('skill_validations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_skill_validations_student_id'))
        batch_op.drop_index(batch_op.f('ix_skill_validations_organization_id'))

    op.drop_table('skill_validations')
    op.drop_table('course_skills')
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_skills_organization_id'))

    op.drop_table('skills')
