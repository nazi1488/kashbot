#!/usr/bin/env python3
"""
Миграция для добавления поля language в таблицу users
"""

import asyncio
import sys
import os
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Database
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_language_column():
    """Добавляет колонку language в таблицу users"""
    
    try:
        print("🔧 МИГРАЦИЯ: Добавление поля language в таблицу users")
        print("=" * 50)
        
        db = Database(DATABASE_URL)
        
        # Проверяем, есть ли уже колонка language
        check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='language';
        """
        
        result = await db.execute(check_query, fetch=True)
        
        if result:
            print("✅ Колонка language уже существует")
            return
        
        # Добавляем колонку language
        alter_query = """
            ALTER TABLE users 
            ADD COLUMN language VARCHAR(5) DEFAULT NULL;
        """
        
        await db.execute(alter_query)
        print("✅ Колонка language успешно добавлена")
        
        # Проверяем, что колонка добавлена
        verify_result = await db.execute(check_query, fetch=True)
        if verify_result:
            print("🎉 Миграция выполнена успешно!")
        else:
            print("❌ Ошибка: колонка не была добавлена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Основная функция миграции"""
    await add_language_column()


if __name__ == "__main__":
    asyncio.run(main())
