"""Add cookies table for video downloader

Revision ID: 003_add_cookies
Revises: 
Create Date: 2024-01-10 10:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_cookies'
down_revision = None  # Это первая миграция
branch_labels = None
depends_on = None


def upgrade():
    # Создаем таблицу для хранения куков
    op.create_table('platform_cookies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),  # instagram, youtube, tiktok
        sa.Column('cookies_json', sa.Text(), nullable=False),  # JSON с куками
        sa.Column('user_agent', sa.String(500), nullable=True),  # User-Agent для этих куков
        sa.Column('proxy', sa.String(200), nullable=True),  # Прокси если есть
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('success_count', sa.Integer(), default=0),  # Счетчик успешных использований
        sa.Column('error_count', sa.Integer(), default=0),  # Счетчик ошибок
        sa.Column('last_used', sa.DateTime(), nullable=True),  # Последнее использование
        sa.Column('last_error', sa.Text(), nullable=True),  # Последняя ошибка
        sa.Column('added_by', sa.Integer(), nullable=True),  # ID админа который добавил
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),  # Когда истекают куки
        sa.Column('notes', sa.Text(), nullable=True),  # Заметки (например, email аккаунта)
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы
    op.create_index('idx_platform_active', 'platform_cookies', ['platform', 'is_active'])
    op.create_index('idx_last_used', 'platform_cookies', ['last_used'])
    
    # Таблица для логов скачиваний
    op.create_table('download_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('cookie_id', sa.Integer(), nullable=True),  # ID использованных куков
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('download_time', sa.Float(), nullable=True),  # Время скачивания в секундах
        sa.Column('file_size', sa.BigInteger(), nullable=True),  # Размер файла в байтах
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['cookie_id'], ['platform_cookies.id'], )
    )
    
    # Индексы для логов
    op.create_index('idx_download_user', 'download_logs', ['user_id', 'created_at'])
    op.create_index('idx_download_platform', 'download_logs', ['platform', 'success'])


def downgrade():
    op.drop_index('idx_download_platform', 'download_logs')
    op.drop_index('idx_download_user', 'download_logs')
    op.drop_table('download_logs')
    
    op.drop_index('idx_last_used', 'platform_cookies')
    op.drop_index('idx_platform_active', 'platform_cookies')
    op.drop_table('platform_cookies')
