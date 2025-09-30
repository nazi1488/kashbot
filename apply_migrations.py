#!/usr/bin/env python3
"""
Скрипт для применения миграций базы данных
"""

import os
import sys
import logging
from alembic import command
from alembic.config import Config

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_migrations():
    """Применяет все миграции"""
    try:
        # Путь к конфигурации alembic
        alembic_cfg = Config("alembic.ini")
        
        # Применяем все миграции
        logger.info("Applying database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Migrations applied successfully!")
        
        # Показываем текущую версию
        command.current(alembic_cfg)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error applying migrations: {e}")
        return False

def check_migrations():
    """Проверяет статус миграций"""
    try:
        alembic_cfg = Config("alembic.ini")
        
        logger.info("Current migration status:")
        command.current(alembic_cfg)
        
        logger.info("\nMigration history:")
        command.history(alembic_cfg)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking migrations: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration manager")
    parser.add_argument("--check", action="store_true", help="Check migration status")
    parser.add_argument("--apply", action="store_true", help="Apply all migrations")
    
    args = parser.parse_args()
    
    if args.check:
        check_migrations()
    elif args.apply:
        apply_migrations()
    else:
        # По умолчанию применяем миграции
        apply_migrations()
