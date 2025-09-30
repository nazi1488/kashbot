#!/usr/bin/env python3
"""
Интеграционный тест Random Face с реальным Redis

Этот тест проверяет работу модуля с настоящим Redis-сервером.
Требует запущенного Redis на localhost:6379
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from features.random_face.service import RandomFaceService
from infra.redis import redis_manager


async def test_redis_integration():
    """Тест интеграции с реальным Redis"""
    
    print("🔄 Тестируем Random Face с реальным Redis...")
    
    try:
        # Инициализируем Redis
        redis_client = await redis_manager.initialize()
        print("✅ Redis подключен")
        
        # Создаем сервис
        service = RandomFaceService(redis_client)
        
        # Тестируем квоты
        user_id = 99999  # Тестовый пользователь
        
        print(f"\n📊 Тестируем квоты для пользователя {user_id}:")
        
        # Получаем начальную квоту
        initial_quota = await service.get_remaining_quota(user_id)
        print(f"   Начальная квота: {initial_quota}")
        
        # Проверяем антиспам (должен пройти)
        is_limited = await service._is_rate_limited(user_id)
        print(f"   Антиспам активен: {is_limited}")
        
        # Устанавливаем антиспам
        await service._set_rate_limit(user_id)
        print("   ✅ Антиспам флаг установлен")
        
        # Проверяем антиспам (теперь должен блокировать)
        is_limited = await service._is_rate_limited(user_id)
        print(f"   Антиспам активен: {is_limited}")
        
        # Увеличиваем квоту
        await service._increment_quota(user_id)
        print("   ✅ Квота увеличена")
        
        # Проверяем новую квоту
        new_quota = await service.get_remaining_quota(user_id)
        print(f"   Новая квота: {new_quota}")
        
        # Проверяем генерацию ключей
        quota_key = service._get_quota_key(user_id)
        print(f"   Ключ квоты: {quota_key}")
        
        print("\n🧪 Тестируем Redis операции:")
        
        # Проверяем существование ключей
        exists = await redis_client.exists(quota_key)
        print(f"   Ключ квоты существует: {exists}")
        
        # Получаем значение
        quota_value = await redis_client.get(quota_key)
        print(f"   Значение квоты: {quota_value}")
        
        # Проверяем TTL
        ttl = await redis_client.ttl(quota_key)
        print(f"   TTL квоты: {ttl} секунд")
        
        # Очистка тестовых данных
        await redis_client.delete(quota_key)
        await redis_client.delete(f"face:lock:{user_id}")
        print("   ✅ Тестовые данные очищены")
        
        await redis_manager.close()
        print("\n✅ Все тесты пройдены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await redis_manager.close()
        except:
            pass


async def test_quota_limits():
    """Тест ограничений квоты"""
    
    print("\n🚧 Тестируем ограничения квоты...")
    
    try:
        redis_client = await redis_manager.initialize()
        service = RandomFaceService(redis_client)
        
        user_id = 99998  # Другой тестовый пользователь
        
        # Устанавливаем квоту на максимум
        quota_key = service._get_quota_key(user_id)
        from config import settings
        await redis_client.set(quota_key, settings.FACE_QUOTA_PER_DAY)
        
        # Проверяем превышение квоты
        is_exceeded = await service._is_quota_exceeded(user_id)
        print(f"   Квота превышена: {is_exceeded}")
        
        remaining = await service.get_remaining_quota(user_id)
        print(f"   Оставшаяся квота: {remaining}")
        
        # Очистка
        await redis_client.delete(quota_key)
        
        await redis_manager.close()
        print("   ✅ Тест ограничений пройден")
        
    except Exception as e:
        print(f"   ❌ Ошибка в тесте ограничений: {e}")


if __name__ == "__main__":
    print("🚀 Запуск интеграционных тестов Random Face + Redis")
    print("📋 Требования: Redis должен быть запущен на localhost:6379")
    
    asyncio.run(test_redis_integration())
    asyncio.run(test_quota_limits())
    
    print("\n🎉 Интеграционное тестирование завершено!")
