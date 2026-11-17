"""Fase 1: identidad (instituciones, usuarios, roles, permisos, sesiones) y bitácora de auditoría.

Revision ID: 0001
Revises: 
Create Date: 2026-11-17 17:20:07.728957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_logs',
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('resource', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=64), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('correlation_id', sa.String(length=64), nullable=True),
    sa.Column('details', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index('ix_audit_logs_org_occurred', ['organization_id', 'occurred_at'], unique=False)

    op.create_table('organizations',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('is_platform', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('active', 'suspended')", name=op.f('ck_organizations_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
    sa.UniqueConstraint('code', name=op.f('uq_organizations_code'))
    )
    op.create_table('permissions',
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_permissions')),
    sa.UniqueConstraint('code', name=op.f('uq_permissions_code'))
    )
    op.create_table('roles',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=240), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
    sa.UniqueConstraint('code', name=op.f('uq_roles_code'))
    )
    op.create_table('role_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], name=op.f('fk_role_permissions_permission_id_permissions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_permissions_role_id_roles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'permission_id', name=op.f('pk_role_permissions'))
    )
    op.create_table('users',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('active', 'disabled')", name=op.f('ck_users_status')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_users_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('organization_id', 'email', name='uq_users_org_email')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_organization_id'), ['organization_id'], unique=False)

    op.create_table('refresh_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('family_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_refresh_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash'))
    )
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index('ix_refresh_tokens_family', ['family_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_refresh_tokens_user_id'), ['user_id'], unique=False)

    op.create_table('user_roles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_user_roles_role_id_roles'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_roles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id', name=op.f('pk_user_roles'))
    )
    # §11: bitácora protegida contra alteración. En PostgreSQL se bloquean UPDATE y DELETE.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION audit_logs_inmutable() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs es de solo inserción';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER audit_logs_inmutable
                BEFORE UPDATE OR DELETE ON audit_logs
                FOR EACH ROW EXECUTE FUNCTION audit_logs_inmutable();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_inmutable ON audit_logs; "
                   "DROP FUNCTION IF EXISTS audit_logs_inmutable();")

    op.drop_table('user_roles')
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_user_id'))
        batch_op.drop_index('ix_refresh_tokens_family')

    op.drop_table('refresh_tokens')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_organization_id'))

    op.drop_table('users')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('permissions')
    op.drop_table('organizations')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_audit_logs_org_occurred')
        batch_op.drop_index(batch_op.f('ix_audit_logs_actor_id'))

    op.drop_table('audit_logs')
