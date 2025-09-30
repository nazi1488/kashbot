#!/usr/bin/env python3
"""
Интеграционный тест Gmail-алиасов с базой данных
"""

import asyncio
import sys
import os
from datetime import datetime, date

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gmail_aliases import generate_gmail_aliases, validate_gmail_input
from database import Database
import config


async def test_gmail_aliases_integration():
    """Интеграционный тест Gmail-алиасов"""
    
    print("🧪 ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ GMAIL-АЛИАСОВ")
    print("=" * 60)
    
    try:
        # Подключаемся к базе данных
        db = Database(config.DATABASE_URL)
        
        # Тестовый пользователь
        test_user_id = 999999999
        
        print(f"\n📊 Тест 1: Проверка начального состояния квот")
        
        # Проверяем начальное состояние
        initial_usage = await db.get_gmail_usage_today(test_user_id)
        initial_quota = await db.get_gmail_remaining_quota(test_user_id)
        
        print(f"   📈 Начальное использование: {initial_usage}")
        print(f"   ⚡ Начальная квота: {initial_quota}")
        
        # Должна быть полная квота для нового пользователя
        expected_quota = 10 - initial_usage
        assert initial_quota == expected_quota, f"Ожидалась квота {expected_quota}, получена {initial_quota}"
        
        print(f"\n🎲 Тест 2: Генерация алиасов")
        
        # Генерируем алиасы
        test_email = "john.doe@gmail.com"
        count_to_generate = min(3, initial_quota)
        
        if count_to_generate > 0:
            aliases = generate_gmail_aliases(test_email, count_to_generate)
            
            print(f"   📧 Тестовый email: {test_email}")
            print(f"   🔢 Сгенерировано алиасов: {len(aliases)}")
            print(f"   📋 Алиасы:")
            for i, alias in enumerate(aliases, 1):
                print(f"      {i}. {alias}")
            
            # Проверяем качество алиасов
            assert len(aliases) == count_to_generate
            assert len(set(aliases)) == count_to_generate  # Все уникальные
            
            # Все должны быть на Gmail домене
            for alias in aliases:
                assert alias.endswith("@gmail.com")
            
            print(f"   ✅ Алиасы успешно сгенерированы и проверены")
            
            print(f"\n📊 Тест 3: Обновление квот в БД")
            
            # Обновляем квоту
            success = await db.increment_gmail_usage(test_user_id, count_to_generate)
            assert success, "Не удалось обновить квоту"
            
            # Проверяем обновленные квоты
            new_usage = await db.get_gmail_usage_today(test_user_id)
            new_quota = await db.get_gmail_remaining_quota(test_user_id)
            
            print(f"   📈 Новое использование: {new_usage}")
            print(f"   ⚡ Новая квота: {new_quota}")
            
            expected_new_usage = initial_usage + count_to_generate
            expected_new_quota = 10 - expected_new_usage
            
            assert new_usage == expected_new_usage, f"Ожидалось использование {expected_new_usage}, получено {new_usage}"
            assert new_quota == expected_new_quota, f"Ожидалась квота {expected_new_quota}, получена {new_quota}"
            
            print(f"   ✅ Квоты корректно обновлены")
        else:
            print(f"   ⚠️ Квота исчерпана, пропускаем генерацию")
        
        print(f"\n🔍 Тест 4: Валидация различных email")
        
        test_cases = [
            ("valid@gmail.com", True, True),
            ("test@googlemail.com", True, True), 
            ("user@yahoo.com", True, False),
            ("invalid-email", False, False),
            ("@gmail.com", False, False),
            ("user@", False, False)
        ]
        
        for email, should_be_valid, should_be_gmail in test_cases:
            is_valid, error, is_gmail = validate_gmail_input(email)
            
            print(f"   📧 {email:<20} → {'✅' if is_valid else '❌'} валид, {'📧' if is_gmail else '📄'} Gmail")
            
            assert is_valid == should_be_valid, f"Неверная валидация для {email}"
            if is_valid:
                assert is_gmail == should_be_gmail, f"Неверная проверка Gmail для {email}"
        
        print(f"\n📋 Тест 5: Проверка данных в БД")
        
        # Проверяем запись в базе данных
        today = date.today()
        query = "SELECT * FROM gmail_alias_usage WHERE user_id = %s AND usage_date = %s"
        result = await db.execute(query, (test_user_id, today), fetch=True)
        
        if result:
            usage_record = result[0]
            print(f"   🗄️ Запись в БД найдена:")
            print(f"      📊 ID: {usage_record['id']}")
            print(f"      👤 User ID: {usage_record['user_id']}")
            print(f"      📅 Дата: {usage_record['usage_date']}")
            print(f"      🔢 Количество: {usage_record['count']}")
            
            assert usage_record['user_id'] == test_user_id
            assert usage_record['usage_date'] == today
            assert usage_record['count'] >= 0
        else:
            print(f"   ℹ️ Записи в БД нет (пользователь не генерировал алиасы)")
        
        print(f"\n🧹 Очистка тестовых данных")
        
        # Удаляем тестовые данные
        cleanup_query = "DELETE FROM gmail_alias_usage WHERE user_id = %s"
        await db.execute(cleanup_query, (test_user_id,))
        print(f"   ✅ Тестовые данные удалены")
        
        print(f"\n🎉 ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка интеграционного тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_quota_edge_cases():
    """Тест граничных случаев с квотами"""
    
    print(f"\n" + "=" * 60)
    print(f"🔬 ТЕСТИРОВАНИЕ ГРАНИЧНЫХ СЛУЧАЕВ КВОТ")
    print("=" * 60)
    
    try:
        db = Database(config.DATABASE_URL)
        test_user_id = 888888888
        
        print(f"\n📊 Тест: Исчерпание дневной квоты")
        
        # Устанавливаем максимальную квоту
        today = date.today()
        
        # Вставляем запись с исчерпанной квотой
        insert_query = """
            INSERT INTO gmail_alias_usage (user_id, usage_date, count)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, usage_date) 
            DO UPDATE SET count = EXCLUDED.count
        """
        await db.execute(insert_query, (test_user_id, today, 10))
        
        # Проверяем что квота исчерпана
        remaining = await db.get_gmail_remaining_quota(test_user_id)
        print(f"   ⚡ Оставшаяся квота: {remaining}")
        assert remaining == 0, f"Ожидалась квота 0, получена {remaining}"
        
        # Пытаемся увеличить счетчик
        success = await db.increment_gmail_usage(test_user_id, 1)
        assert success, "Не удалось увеличить счетчик"
        
        # Проверяем что счетчик увеличился (но квота стала отрицательной)
        usage = await db.get_gmail_usage_today(test_user_id)
        remaining = await db.get_gmail_remaining_quota(test_user_id)
        
        print(f"   📈 Использование: {usage}")
        print(f"   ⚡ Квота: {remaining}")
        
        assert usage == 11, f"Ожидалось использование 11, получено {usage}"
        assert remaining == 0, f"Квота должна остаться 0 (не отрицательной)"
        
        # Очистка
        await db.execute("DELETE FROM gmail_alias_usage WHERE user_id = %s", (test_user_id,))
        
        print(f"\n🎉 ГРАНИЧНЫЕ СЛУЧАИ ПРОТЕСТИРОВАНЫ!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка в граничных тестах: {e}")
        return False


async def demo_generation():
    """Демонстрация генерации алиасов"""
    
    print(f"\n" + "=" * 60)
    print(f"🎭 ДЕМОНСТРАЦИЯ ГЕНЕРАЦИИ АЛИАСОВ")
    print("=" * 60)
    
    try:
        demo_emails = [
            "john.doe@gmail.com",
            "simple@googlemail.com", 
            "user123@gmail.com",
            "test.email+tag@gmail.com"
        ]
        
        for email in demo_emails:
            print(f"\n📧 Исходный email: {email}")
            
            aliases = generate_gmail_aliases(email, 5)
            
            print(f"   🎲 Сгенерированные алиасы:")
            for i, alias in enumerate(aliases, 1):
                print(f"      {i}. {alias}")
            
            # Категоризация
            plus_aliases = [a for a in aliases if '+' in a]
            dot_aliases = [a for a in aliases if '+' not in a]
            
            print(f"   📊 Статистика:")
            print(f"      +tag алиасы: {len(plus_aliases)}")
            print(f"      dot алиасы: {len(dot_aliases)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в демонстрации: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    
    print("🚀 ЗАПУСК ПОЛНОГО ИНТЕГРАЦИОННОГО ТЕСТИРОВАНИЯ")
    print("📧 Gmail-алиасы генератор")
    
    tests = [
        ("Основной интеграционный тест", test_gmail_aliases_integration),
        ("Граничные случаи квот", test_quota_edge_cases),
        ("Демонстрация генерации", demo_generation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Запуск теста: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
            print(f"📊 Результат: {status}")
        except Exception as e:
            print(f"💥 Критическая ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    # Итоговая статистика
    print(f"\n" + "=" * 60)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Пройдено тестов: {passed}/{total}")
    success_rate = (passed / total) * 100 if total > 0 else 0
    print(f"📊 Успешность: {success_rate:.1f}%")
    
    if passed == total:
        print(f"\n🎉 ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print(f"✅ Gmail-алиасы готовы к использованию!")
        print(f"🔐 База данных, генерация и квоты работают корректно!")
    else:
        print(f"\n⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print(f"🔧 Требуется доработка {total - passed} компонентов")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
