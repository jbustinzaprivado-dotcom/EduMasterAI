"""Fase 2: core académico (cursos, contenidos, ofertas, matrículas, evaluaciones y eventos de aprendizaje).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17 19:33:55.227124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('courses',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('level', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("level IN ('basico', 'intermedio', 'avanzado')", name=op.f('ck_courses_level')),
    sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name=op.f('ck_courses_status')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_courses_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_courses')),
    sa.UniqueConstraint('organization_id', 'code', name='uq_courses_org_code')
    )
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_courses_organization_id'), ['organization_id'], unique=False)

    op.create_table('course_offerings',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('instructor_id', sa.Uuid(), nullable=False),
    sa.Column('period', sa.String(length=16), nullable=False),
    sa.Column('cohort', sa.String(length=64), nullable=False),
    sa.Column('starts_on', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_on', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('planned', 'active', 'closed')", name=op.f('ck_course_offerings_status')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_course_offerings_course_id_courses'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['instructor_id'], ['users.id'], name=op.f('fk_course_offerings_instructor_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_course_offerings_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_course_offerings'))
    )
    with op.batch_alter_table('course_offerings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_course_offerings_course_id'), ['course_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_course_offerings_instructor_id'), ['instructor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_course_offerings_organization_id'), ['organization_id'], unique=False)

    op.create_table('course_units',
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_course_units_course_id_courses'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_course_units'))
    )
    with op.batch_alter_table('course_units', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_course_units_course_id'), ['course_id'], unique=False)

    op.create_table('assessments',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('instructions', sa.Text(), nullable=False),
    sa.Column('max_score', sa.Float(), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("kind IN ('opcion_multiple', 'verdadero_falso', 'respuesta_corta', 'archivo', 'practica')", name=op.f('ck_assessments_kind')),
    sa.CheckConstraint('max_score > 0', name=op.f('ck_assessments_max_score')),
    sa.CheckConstraint('weight > 0 AND weight <= 1', name=op.f('ck_assessments_weight')),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_assessments_offering_id_course_offerings'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assessments'))
    )
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assessments_offering_id'), ['offering_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_assessments_organization_id'), ['organization_id'], unique=False)

    op.create_table('course_activities',
    sa.Column('unit_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('estimated_minutes', sa.Integer(), nullable=False),
    sa.Column('required', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("kind IN ('lectura', 'video', 'practica')", name=op.f('ck_course_activities_kind')),
    sa.ForeignKeyConstraint(['unit_id'], ['course_units.id'], name=op.f('fk_course_activities_unit_id_course_units'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_course_activities'))
    )
    with op.batch_alter_table('course_activities', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_course_activities_unit_id'), ['unit_id'], unique=False)

    op.create_table('enrollments',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('active', 'completed', 'dropped')", name=op.f('ck_enrollments_status')),
    sa.CheckConstraint('progress >= 0 AND progress <= 1', name=op.f('ck_enrollments_progress')),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_enrollments_offering_id_course_offerings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_enrollments_student_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_enrollments')),
    sa.UniqueConstraint('offering_id', 'student_id', name='uq_enrollments_offering_student')
    )
    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_enrollments_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index('ix_enrollments_student_offering', ['student_id', 'offering_id'], unique=False)

    op.create_table('learning_events',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('activity_id', sa.Uuid(), nullable=True),
    sa.Column('event_type', sa.String(length=48), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('payload_schema_version', sa.Integer(), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.CheckConstraint('duration_seconds >= 0 AND duration_seconds <= 14400', name=op.f('ck_learning_events_duration')),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_learning_events_offering_id_course_offerings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_learning_events_student_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_learning_events'))
    )
    with op.batch_alter_table('learning_events', schema=None) as batch_op:
        batch_op.create_index('ix_learning_events_org_occurred', ['organization_id', 'occurred_at'], unique=False)
        batch_op.create_index('ix_learning_events_student_offering', ['student_id', 'offering_id'], unique=False)

    op.create_table('assessment_attempts',
    sa.Column('assessment_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('attempt_no', sa.Integer(), nullable=False),
    sa.Column('answer', sa.Text(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('late', sa.Boolean(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('feedback', sa.Text(), nullable=True),
    sa.Column('graded_by', sa.Uuid(), nullable=True),
    sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_assessment_attempts_assessment_id_assessments'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_assessment_attempts_student_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assessment_attempts')),
    sa.UniqueConstraint('assessment_id', 'student_id', 'attempt_no', name='uq_attempts_assessment_student_no')
    )
    with op.batch_alter_table('assessment_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assessment_attempts_assessment_id'), ['assessment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_assessment_attempts_student_id'), ['student_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('assessment_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assessment_attempts_student_id'))
        batch_op.drop_index(batch_op.f('ix_assessment_attempts_assessment_id'))

    op.drop_table('assessment_attempts')
    with op.batch_alter_table('learning_events', schema=None) as batch_op:
        batch_op.drop_index('ix_learning_events_student_offering')
        batch_op.drop_index('ix_learning_events_org_occurred')

    op.drop_table('learning_events')
    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.drop_index('ix_enrollments_student_offering')
        batch_op.drop_index(batch_op.f('ix_enrollments_organization_id'))

    op.drop_table('enrollments')
    with op.batch_alter_table('course_activities', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_course_activities_unit_id'))

    op.drop_table('course_activities')
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assessments_organization_id'))
        batch_op.drop_index(batch_op.f('ix_assessments_offering_id'))

    op.drop_table('assessments')
    with op.batch_alter_table('course_units', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_course_units_course_id'))

    op.drop_table('course_units')
    with op.batch_alter_table('course_offerings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_course_offerings_organization_id'))
        batch_op.drop_index(batch_op.f('ix_course_offerings_instructor_id'))
        batch_op.drop_index(batch_op.f('ix_course_offerings_course_id'))

    op.drop_table('course_offerings')
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_courses_organization_id'))

    op.drop_table('courses')
