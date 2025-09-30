"""
Миграция для создания/обновления таблицы platform_cookies
"""

import os
import asyncio
import logging
from datetime import datetime
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_cookies_table(db: Database):
    """Создает или обновляет таблицу platform_cookies"""
    
    try:
        # Проверяем существование таблицы
        check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'platform_cookies'
            );
        """
        
        result = await db.execute(check_table_query, fetch=True)
        table_exists = result[0]['exists'] if result else False
        
        if not table_exists:
            logger.info("Создаем таблицу platform_cookies...")
            
            create_table_query = """
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
            """
            
            await db.execute(create_table_query)
            
            # Создаем индексы
            indexes = [
                "CREATE INDEX idx_platform_cookies_platform ON platform_cookies(platform);",
                "CREATE INDEX idx_platform_cookies_active ON platform_cookies(is_active, deleted_at);",
                "CREATE INDEX idx_platform_cookies_expires ON platform_cookies(expires_at);",
                "CREATE INDEX idx_platform_cookies_platform_active ON platform_cookies(platform, is_active, deleted_at);",
            ]
            
            for index_query in indexes:
                await db.execute(index_query)
                
            logger.info("✅ Таблица platform_cookies создана успешно")
            
        else:
            logger.info("Таблица platform_cookies существует, проверяем колонки...")
            
            # Проверяем наличие колонки deleted_at
            check_column_query = """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'platform_cookies' 
                    AND column_name = 'deleted_at'
                );
            """
            
            result = await db.execute(check_column_query, fetch=True)
            column_exists = result[0]['exists'] if result else False
            
            if not column_exists:
                logger.info("Добавляем колонку deleted_at...")
                
                add_column_query = """
                    ALTER TABLE platform_cookies 
                    ADD COLUMN deleted_at TIMESTAMP NULL;
                """
                
                await db.execute(add_column_query)
                
                # Создаем индекс для новой колонки
                await db.execute("CREATE INDEX idx_platform_cookies_deleted ON platform_cookies(deleted_at);")
                
                logger.info("✅ Колонка deleted_at добавлена")
            else:
                logger.info("✅ Колонка deleted_at уже существует")
                
            # Проверяем и добавляем другие недостающие колонки
            required_columns = {
                'success_count': 'INTEGER DEFAULT 0',
                'error_count': 'INTEGER DEFAULT 0',
                'last_used': 'TIMESTAMP',
                'expires_at': 'TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT NOW()'
            }
            
            for column_name, column_definition in required_columns.items():
                check_query = f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'platform_cookies' 
                        AND column_name = '{column_name}'
                    );
                """
                
                result = await db.execute(check_query, fetch=True)
                exists = result[0]['exists'] if result else False
                
                if not exists:
                    logger.info(f"Добавляем колонку {column_name}...")
                    add_query = f"ALTER TABLE platform_cookies ADD COLUMN {column_name} {column_definition};"
                    await db.execute(add_query)
                    logger.info(f"✅ Колонка {column_name} добавлена")
        
        logger.info("🎉 Миграция завершена успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        raise


async def main():
    """Основная функция для запуска миграции"""
    
    # Получаем DATABASE_URL из переменных окружения
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ Переменная окружения DATABASE_URL не установлена")
        logger.info("Установите её так: export DATABASE_URL='postgresql://user:password@host:port/dbname'")
        return
    
    db = Database(database_url)
    
    try:
        await migrate_cookies_table(db)
    except Exception as e:
        logger.error(f"❌ Миграция не удалась: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
