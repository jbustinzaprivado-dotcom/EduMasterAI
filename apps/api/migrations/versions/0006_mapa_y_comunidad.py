"""Fase 3: región del estudiante para el mapa agregado (§4.1) y comunidad por curso (§4.8).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-18 18:51:04.923880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('community_reports',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('target_type', sa.String(length=8), nullable=False),
    sa.Column('target_id', sa.Uuid(), nullable=False),
    sa.Column('reporter_id', sa.Uuid(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resolved_by', sa.Uuid(), nullable=True),
    sa.Column('resolution', sa.String(length=32), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('abierto', 'resuelto')", name=op.f('ck_community_reports_status')),
    sa.CheckConstraint("target_type IN ('post', 'comment')", name=op.f('ck_community_reports_target_type')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_community_reports')),
    sa.UniqueConstraint('target_id', 'reporter_id', name='uq_community_reports_target_reporter')
    )
    with op.batch_alter_table('community_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_community_reports_offering_id'), ['offering_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_community_reports_organization_id'), ['organization_id'], unique=False)

    op.create_table('community_mutes',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_community_mutes_offering_id_course_offerings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_community_mutes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'offering_id', name=op.f('pk_community_mutes'))
    )
    op.create_table('community_posts',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('offering_id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('hidden_reason', sa.Text(), nullable=True),
    sa.Column('hidden_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("kind IN ('anuncio', 'debate')", name=op.f('ck_community_posts_kind')),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_community_posts_author_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_community_posts_offering_id_course_offerings'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_community_posts'))
    )
    with op.batch_alter_table('community_posts', schema=None) as batch_op:
        batch_op.create_index('ix_community_posts_offering_created', ['offering_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_community_posts_organization_id'), ['organization_id'], unique=False)

    op.create_table('community_comments',
    sa.Column('post_id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('hidden_reason', sa.Text(), nullable=True),
    sa.Column('hidden_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_community_comments_author_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], name=op.f('fk_community_comments_post_id_community_posts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_community_comments'))
    )
    with op.batch_alter_table('community_comments', schema=None) as batch_op:
        batch_op.create_index('ix_community_comments_post_created', ['post_id', 'created_at'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('region', sa.String(length=32), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('region')

    with op.batch_alter_table('community_comments', schema=None) as batch_op:
        batch_op.drop_index('ix_community_comments_post_created')

    op.drop_table('community_comments')
    with op.batch_alter_table('community_posts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_community_posts_organization_id'))
        batch_op.drop_index('ix_community_posts_offering_created')

    op.drop_table('community_posts')
    op.drop_table('community_mutes')
    with op.batch_alter_table('community_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_community_reports_organization_id'))
        batch_op.drop_index(batch_op.f('ix_community_reports_offering_id'))

    op.drop_table('community_reports')
