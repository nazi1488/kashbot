"""Add Keitaro integration tables

Revision ID: keitaro_integration_001
Revises: 005_add_kashmail_tables
Create Date: 2025-09-28 01:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'keitaro_integration_001'
down_revision = '005_add_kashmail_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Keitaro integration tables"""
    
    # Create keitaro_profiles table
    op.create_table('keitaro_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('owner_user_id', sa.BigInteger(), nullable=False),
        sa.Column('secret', sa.String(length=64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('default_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('default_topic_id', sa.Integer(), nullable=True),
        sa.Column('rate_limit_rps', sa.Integer(), nullable=False, default=27),
        sa.Column('dedup_ttl_sec', sa.Integer(), nullable=False, default=3600),
        sa.Column('pull_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('pull_base_url', sa.Text(), nullable=True),
        sa.Column('pull_api_key', sa.Text(), nullable=True),
        sa.Column('pull_filters', sa.JSON(), nullable=True),
        sa.Column('pull_last_check', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_keitaro_profile_owner', 'keitaro_profiles', ['owner_user_id'], unique=True)
    op.create_index('idx_keitaro_profile_secret', 'keitaro_profiles', ['secret'], unique=True)
    
    # Create keitaro_routes table
    op.create_table('keitaro_routes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('match_by', sa.Enum('CAMPAIGN_ID', 'SOURCE', 'ANY', name='matchbytype'), nullable=False),
        sa.Column('match_value', sa.Text(), nullable=False),
        sa.Column('is_regex', sa.Boolean(), nullable=False, default=False),
        sa.Column('target_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('target_topic_id', sa.Integer(), nullable=True),
        sa.Column('status_filter', sa.JSON(), nullable=True),
        sa.Column('geo_filter', sa.JSON(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, default=100),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['profile_id'], ['keitaro_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_keitaro_route_lookup', 'keitaro_routes', ['profile_id', 'match_by', 'match_value'])
    op.create_index('idx_keitaro_route_priority', 'keitaro_routes', ['profile_id', 'priority'])
    
    # Create keitaro_events table for deduplication
    op.create_table('keitaro_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=64), nullable=True),
        sa.Column('campaign_id', sa.String(length=128), nullable=True),
        sa.Column('source', sa.String(length=128), nullable=True),
        sa.Column('country', sa.String(length=10), nullable=True),
        sa.Column('revenue', sa.String(length=64), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False),
        sa.Column('sent_to_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('sent_to_topic_id', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.ForeignKeyConstraint(['profile_id'], ['keitaro_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_keitaro_event_dedup', 'keitaro_events', ['profile_id', 'transaction_id', 'created_at'])


def downgrade() -> None:
    """Drop Keitaro integration tables"""
    op.drop_table('keitaro_events')
    op.drop_table('keitaro_routes')
    op.drop_table('keitaro_profiles')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS matchbytype")
