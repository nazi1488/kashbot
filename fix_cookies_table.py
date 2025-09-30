#!/usr/bin/env python3
"""
Быстрое исправление таблицы platform_cookies
Добавляет недостающую колонку deleted_at
"""

import os
import sys
import asyncio
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Database
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_cookies_table():
    """Быстрое исправление таблицы cookies"""
    
    # Получаем DATABASE_URL из конфига
    database_url = DATABASE_URL
    if not database_url:
        logger.error("❌ DATABASE_URL не найден в конфигурации")
        logger.info("Проверьте файл .env и config.py")
        return False
    
    logger.info(f"🔗 Подключаемся к базе данных...")
    
    try:
        db = Database(database_url)
        logger.info("🔧 Исправляем таблицу platform_cookies...")
        
        # Проверяем существование таблицы
        check_table = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'platform_cookies'
            );
        """
        
        result = await db.execute(check_table, fetch=True)
        table_exists = result[0]['exists'] if result else False
        
        if not table_exists:
            logger.info("📋 Создаем таблицу platform_cookies...")
            
            create_table = """
                CREATE TABLE platform_cookies (
                    id SERIAL PRIMARY KEY,
                    platform VARCHAR(50) NOT NULL,
                    cookies_json TEXT NOT NULL,
                    user_agent TEXT,
                    proxy TEXT,
                    notes TEXT,
                    added_by INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    deleted_at TIMESTAMP NULL
                );
                
                CREATE INDEX idx_platform_cookies_platform ON platform_cookies(platform);
                CREATE INDEX idx_platform_cookies_active ON platform_cookies(is_active, deleted_at);
            """
            
            await db.execute(create_table)
            logger.info("✅ Таблица создана успешно!")
            
        else:
            logger.info("📋 Таблица существует, проверяем колонку deleted_at...")
            
            # Проверяем колонку deleted_at
            check_column = """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'platform_cookies' 
                    AND column_name = 'deleted_at'
                );
            """
            
            result = await db.execute(check_column, fetch=True)
            column_exists = result[0]['exists'] if result else False
            
            if not column_exists:
                logger.info("➕ Добавляем колонку deleted_at...")
                
                add_column = """
                    ALTER TABLE platform_cookies 
                    ADD COLUMN deleted_at TIMESTAMP NULL;
                """
                
                await db.execute(add_column)
                logger.info("✅ Колонка deleted_at добавлена!")
            else:
                logger.info("✅ Колонка deleted_at уже существует")
        
        # Проверяем статистику
        logger.info("📊 Проверяем статистику куков...")
        
        stats_query = """
            SELECT 
                platform,
                COUNT(*) as total,
                SUM(CASE WHEN is_active AND deleted_at IS NULL THEN 1 ELSE 0 END) as active
            FROM platform_cookies
            WHERE deleted_at IS NULL
            GROUP BY platform
        """
        
        stats = await db.execute(stats_query, fetch=True)
        
        if stats:
            logger.info("📈 Статистика куков:")
            for row in stats:
                logger.info(f"  {row['platform']}: {row['active']}/{row['total']} активных")
        else:
            logger.info("📭 Куки не найдены")
        
        logger.info("🎉 Исправление завершено успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Исправление таблицы platform_cookies...")
    print("=" * 50)
    
    success = asyncio.run(fix_cookies_table())
    
    if success:
        print("\n✅ Готово! Теперь можно добавлять куки через бота.")
    else:
        print("\n❌ Исправление не удалось. Проверьте логи выше.")
        sys.exit(1)
