#!/usr/bin/env python3
"""
Тестирование исправлений в админ-панели
"""

import asyncio
import sys
import os
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analytics import Analytics
from database import Database
from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_analytics_methods():
    """Тестируем исправленные методы аналитики"""
    
    try:
        print("🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ В АДМИН-ПАНЕЛИ")
        print("=" * 50)
        
        # Инициализируем компоненты
        db = Database(DATABASE_URL)
        analytics = Analytics(db)
        
        print("\n📊 1. Тестируем get_total_users()...")
        total_users = await analytics.get_total_users()
        print(f"✅ Результат: {total_users}")
        
        print("\n📊 2. Тестируем get_dau_wau_mau()...")
        dau_wau_mau = await analytics.get_dau_wau_mau()
        print(f"✅ Результат: {dau_wau_mau}")
        
        print("\n📊 3. Тестируем get_users_for_broadcast()...")
        users_broadcast = await analytics.get_users_for_broadcast()
        print(f"✅ Результат: {len(users_broadcast)} пользователей для рассылки")
        if users_broadcast:
            print(f"   Пример: {users_broadcast[0]}")
        
        print("\n📊 4. Тестируем get_new_users()...")
        new_users = await analytics.get_new_users(7)
        print(f"✅ Результат: {new_users}")
        
        print("\n📊 5. Тестируем get_hourly_activity()...")
        hourly_activity = await analytics.get_hourly_activity(7)
        print(f"✅ Результат: {len(hourly_activity)} часовых интервалов")
        active_hours = [h for h, count in hourly_activity.items() if count > 0]
        print(f"   Активные часы: {active_hours}")
        
        print("\n📊 6. Тестируем get_average_retention()...")
        retention_1d = await analytics.get_average_retention(1, 30)
        retention_7d = await analytics.get_average_retention(7, 30)
        retention_30d = await analytics.get_average_retention(30, 30)
        print(f"✅ Retention D1: {retention_1d}%, D7: {retention_7d}%, D30: {retention_30d}%")
        
        print("\n📊 7. Тестируем get_churn_rate()...")
        churn_rate = await analytics.get_churn_rate(30)
        print(f"✅ Churn rate: {churn_rate}%")
        
        print("\n🎉 ВСЕ МЕТОДЫ АНАЛИТИКИ РАБОТАЮТ КОРРЕКТНО!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_data_types():
    """Тестируем типы данных возвращаемых методами"""
    
    try:
        print("\n🔍 ПРОВЕРКА ТИПОВ ДАННЫХ")
        print("=" * 30)
        
        db = Database(DATABASE_URL)
        analytics = Analytics(db)
        
        # Проверяем get_new_users возвращает dict
        new_users = await analytics.get_new_users(7)
        print(f"get_new_users() тип: {type(new_users)}")
        assert isinstance(new_users, dict), "get_new_users должен возвращать dict"
        assert 'total' in new_users and 'active' in new_users, "get_new_users должен содержать 'total' и 'active'"
        print("✅ get_new_users() - корректный тип")
        
        # Проверяем get_hourly_activity возвращает dict
        hourly_activity = await analytics.get_hourly_activity(7)
        print(f"get_hourly_activity() тип: {type(hourly_activity)}")
        assert isinstance(hourly_activity, dict), "get_hourly_activity должен возвращать dict"
        assert len(hourly_activity) == 24, "get_hourly_activity должен содержать 24 часа"
        print("✅ get_hourly_activity() - корректный тип")
        
        # Проверяем get_users_for_broadcast возвращает list
        users_broadcast = await analytics.get_users_for_broadcast()
        print(f"get_users_for_broadcast() тип: {type(users_broadcast)}")
        assert isinstance(users_broadcast, list), "get_users_for_broadcast должен возвращать list"
        print("✅ get_users_for_broadcast() - корректный тип")
        
        print("\n✅ ВСЕ ТИПЫ ДАННЫХ КОРРЕКТНЫ!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки типов: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    
    print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ ИСПРАВЛЕНИЙ...")
    
    success = True
    
    # Тест 1: Методы аналитики
    if not await test_analytics_methods():
        success = False
    
    # Тест 2: Типы данных
    if not await test_data_types():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Админ-панель должна работать без ошибок")
    else:
        print("❌ ОБНАРУЖЕНЫ ОШИБКИ!")
        print("🔧 Требуются дополнительные исправления")
    
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
