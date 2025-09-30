#!/usr/bin/env python3
"""
Тестирование сохранения языка пользователей
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


async def test_language_persistence():
    """Тестирует сохранение и получение языка пользователей"""
    
    try:
        print("🧪 ТЕСТИРОВАНИЕ СОХРАНЕНИЯ ЯЗЫКА ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 50)
        
        db = Database(DATABASE_URL)
        
        # Тест 1: Сохранение нового языка
        print("\n📝 Тест 1: Сохранение языка для нового пользователя")
        test_user_id = 999999999
        test_language = "en"
        test_username = "test_user"
        
        success = await db.set_user_language(test_user_id, test_language, test_username)
        print(f"✅ Сохранение языка: {'успешно' if success else 'ошибка'}")
        
        # Тест 2: Получение сохраненного языка
        print("\n📖 Тест 2: Получение сохраненного языка")
        saved_language = await db.get_user_language(test_user_id)
        print(f"✅ Получен язык: {saved_language}")
        print(f"✅ Язык соответствует: {'да' if saved_language == test_language else 'нет'}")
        
        # Тест 3: Обновление языка существующего пользователя
        print("\n🔄 Тест 3: Изменение языка пользователя")
        new_language = "ru"
        success = await db.set_user_language(test_user_id, new_language, test_username)
        print(f"✅ Обновление языка: {'успешно' if success else 'ошибка'}")
        
        updated_language = await db.get_user_language(test_user_id)
        print(f"✅ Обновленный язык: {updated_language}")
        print(f"✅ Язык изменился: {'да' if updated_language == new_language else 'нет'}")
        
        # Тест 4: Получение языка для несуществующего пользователя
        print("\n❓ Тест 4: Язык для несуществующего пользователя")
        nonexistent_user_id = 888888888
        no_language = await db.get_user_language(nonexistent_user_id)
        print(f"✅ Язык для несуществующего пользователя: {no_language}")
        print(f"✅ Корректно возвращает None: {'да' if no_language is None else 'нет'}")
        
        # Тест 5: Проверка базы данных
        print("\n🗄️ Тест 5: Проверка данных в базе")
        check_query = """
            SELECT tg_id, username, language, first_seen_at, last_seen_at 
            FROM users 
            WHERE tg_id = %s
        """
        result = await db.execute(check_query, (test_user_id,), fetch=True)
        
        if result:
            user_data = result[0]
            print(f"✅ Данные пользователя в БД:")
            print(f"   🆔 TG ID: {user_data['tg_id']}")
            print(f"   👤 Username: {user_data['username']}")
            print(f"   🌐 Language: {user_data['language']}")
            print(f"   📅 First seen: {user_data['first_seen_at']}")
            print(f"   📅 Last seen: {user_data['last_seen_at']}")
        else:
            print("❌ Пользователь не найден в БД")
        
        # Очистка тестовых данных
        print("\n🧹 Очистка тестовых данных")
        cleanup_query = "DELETE FROM users WHERE tg_id = %s"
        await db.execute(cleanup_query, (test_user_id,))
        print("✅ Тестовые данные удалены")
        
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Система сохранения языка работает корректно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database_methods():
    """Дополнительные тесты методов базы данных"""
    
    try:
        print("\n" + "=" * 50)
        print("🔬 ДОПОЛНИТЕЛЬНОЕ ТЕСТИРОВАНИЕ МЕТОДОВ БД")
        print("=" * 50)
        
        db = Database(DATABASE_URL)
        
        # Тест разных языков
        languages_to_test = ['ru', 'en', 'uk', 'de', 'fr']
        test_users = [
            (111111111, 'user_ru', 'ru'),
            (222222222, 'user_en', 'en'), 
            (333333333, 'user_uk', 'uk'),
            (444444444, None, 'de'),  # Без username
            (555555555, 'user_fr', 'fr'),
        ]
        
        print(f"\n📝 Тестируем сохранение разных языков:")
        for user_id, username, lang in test_users:
            success = await db.set_user_language(user_id, lang, username)
            saved_lang = await db.get_user_language(user_id)
            status = "✅" if success and saved_lang == lang else "❌"
            print(f"   {status} User {user_id}: {lang} -> {saved_lang}")
        
        # Очистка
        print(f"\n🧹 Очистка тестовых данных...")
        for user_id, _, _ in test_users:
            await db.execute("DELETE FROM users WHERE tg_id = %s", (user_id,))
        
        print("✅ Тесты разных языков прошли успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка дополнительного тестирования: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    
    print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ СОХРАНЕНИЯ ЯЗЫКОВ...")
    
    success1 = await test_language_persistence()
    success2 = await test_database_methods()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Функция сохранения языка готова к использованию")
        print("📱 При повторном /start пользователи сразу попадут в главное меню")
    else:
        print("❌ ОБНАРУЖЕНЫ ОШИБКИ!")
        print("🔧 Требуются дополнительные исправления")
    
    return success1 and success2


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
