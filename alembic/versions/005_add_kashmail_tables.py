"""Add KashMail tables

Revision ID: 005_add_kashmail_tables
Revises: 004_add_gmail_alias_usage_table
Create Date: 2025-09-26 23:54:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_kashmail_tables'
down_revision = '004_add_gmail_alias_usage_table'
branch_labels = None
depends_on = None


def upgrade():
    # Создаем таблицу для сессий KashMail
    op.create_table('kashmail_sessions',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('jwt', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # Создаем таблицу для дневных счетчиков
    op.create_table('kashmail_daily_counters',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('user_id', 'day')
    )
    
    # Создаем индекс для быстрого поиска по дате
    op.create_index('ix_kashmail_daily_counters_day', 'kashmail_daily_counters', ['day'])


def downgrade():
    # Удаляем таблицы в обратном порядке
    op.drop_index('ix_kashmail_daily_counters_day', table_name='kashmail_daily_counters')
    op.drop_table('kashmail_daily_counters')
    op.drop_table('kashmail_sessions')
