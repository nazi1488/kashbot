"""Add unique constraint to keitaro_profiles.owner_user_id

Revision ID: 5827a9274de4
Revises: keitaro_integration_001
Create Date: 2025-09-28 21:35:59.155669

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5827a9274de4'
down_revision = 'keitaro_integration_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Сначала удаляем существующий не-уникальный индекс
    op.drop_index('idx_keitaro_profile_owner', table_name='keitaro_profiles')
    
    # Создаем уникальный индекс
    op.create_index('idx_keitaro_profile_owner', 'keitaro_profiles', ['owner_user_id'], unique=True)


def downgrade() -> None:
    # Удаляем уникальный индекс
    op.drop_index('idx_keitaro_profile_owner', table_name='keitaro_profiles')
    
    # Восстанавливаем обычный индекс
    op.create_index('idx_keitaro_profile_owner', 'keitaro_profiles', ['owner_user_id'])
