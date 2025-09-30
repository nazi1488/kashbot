#!/usr/bin/env python3
"""
Тест уникального ограничения на owner_user_id в keitaro_profiles
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.models import Database
import config

async def test_unique_constraint():
    """Тестируем уникальное ограничение и ON CONFLICT"""
    
    print("🔧 Тестирование уникального ограничения для Keitaro")
    print("=" * 60)
    
    try:
        # Инициализируем подключение к БД
        db = Database(config.DATABASE_URL)
        
        # Тестовые данные
        test_user_id = 999999999  # Тестовый user_id
        
        # Тест 1: Проверяем, что ON CONFLICT теперь работает
        print("📊 Тест 1: Проверка работы ON CONFLICT с owner_user_id")
        
        query = """
            INSERT INTO keitaro_profiles (
                owner_user_id, secret, default_chat_id, default_topic_id,
                enabled, rate_limit_rps, dedup_ttl_sec, pull_enabled,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (owner_user_id) DO UPDATE SET
                secret = EXCLUDED.secret,
                default_chat_id = EXCLUDED.default_chat_id,
                default_topic_id = EXCLUDED.default_topic_id,
                updated_at = NOW()
            RETURNING id, owner_user_id
        """
        
        # Первая вставка
        result1 = await db.execute(query, (
            test_user_id, 'test_secret_1', -1001234567890, None, True, 27, 3600, False
        ), fetch=True)
        
        profile_id_1 = result1[0]['id']
        print(f"   ✅ Первая вставка успешна, profile_id: {profile_id_1}")
        
        # Вторая вставка (должна сработать UPDATE)
        result2 = await db.execute(query, (
            test_user_id, 'test_secret_2', -1001234567891, 123, True, 27, 3600, False
        ), fetch=True)
        
        profile_id_2 = result2[0]['id']
        print(f"   ✅ Вторая вставка успешна (UPDATE), profile_id: {profile_id_2}")
        
        # Проверяем, что ID остался тот же (это был UPDATE, а не INSERT)
        if profile_id_1 == profile_id_2:
            print("   ✅ ON CONFLICT работает корректно - профиль обновился, а не создался новый")
        else:
            print("   ❌ ON CONFLICT работает неправильно - создался новый профиль")
            return False
        
        # Тест 2: Проверяем актуальные данные
        print("📊 Тест 2: Проверка обновленных данных")
        
        check_query = "SELECT secret, default_chat_id FROM keitaro_profiles WHERE owner_user_id = %s"
        result = await db.execute(check_query, (test_user_id,), fetch=True)
        
        if result and result[0]['secret'] == 'test_secret_2':
            print("   ✅ Данные обновились корректно")
        else:
            print("   ❌ Данные не обновились")
            return False
        
        # Очистка тестовых данных
        cleanup_query = "DELETE FROM keitaro_profiles WHERE owner_user_id = %s"
        await db.execute(cleanup_query, (test_user_id,))
        print("   ✅ Тестовые данные удалены")
        
        print("\n🎉 Все тесты пройдены успешно!")
        print("✅ Уникальное ограничение на owner_user_id работает")
        print("✅ ON CONFLICT теперь функционирует правильно")
        print("✅ Ошибка 'InvalidColumnReference' исправлена")
        
        return True
        
    except Exception as e:
        print(f"❌ Тест не пройден: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_unique_constraint())
    sys.exit(0 if success else 1)
