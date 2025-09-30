"""Add gmail_alias_usage table

Revision ID: 004_add_gmail_alias_usage_table
Revises: 003_add_cookies_table
Create Date: 2025-09-25 16:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Date


# revision identifiers, used by Alembic.
revision = '004_add_gmail_alias_usage_table'
down_revision = '003_add_cookies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create gmail_alias_usage table for tracking daily quotas"""
    op.create_table(
        'gmail_alias_usage',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger, nullable=False, comment='Telegram user ID'),
        sa.Column('usage_date', Date, nullable=False, comment='Date of usage'),
        sa.Column('count', sa.Integer, nullable=False, default=0, comment='Number of aliases generated'),
        sa.UniqueConstraint('user_id', 'usage_date', name='unique_user_date'),
        comment='Track daily Gmail alias generation quota per user'
    )


def downgrade() -> None:
    """Drop gmail_alias_usage table"""
    op.drop_table('gmail_alias_usage')
