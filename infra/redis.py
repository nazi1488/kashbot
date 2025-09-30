"""
Redis клиент для приложения

Инициализация и управление подключением к Redis для кэширования,
квотирования и других операций.
"""

import logging
from typing import Optional

import redis.asyncio as redis
from config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Менеджер подключений к Redis"""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
    
    async def initialize(self, max_retries: int = 3) -> redis.Redis:
        """
        Инициализировать подключение к Redis с ретраями
        
        Args:
            max_retries: Максимальное количество попыток подключения
            
        Returns:
            redis.Redis: Подключение к Redis
        """
        if self._redis is None:
            import asyncio
            
            for attempt in range(max_retries):
                try:
                    self._redis = redis.from_url(
                        settings.REDIS_URL,
                        encoding="utf-8",
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5
                    )
                    
                    # Проверяем подключение
                    await self._redis.ping()
                    logger.info(f"Redis connected successfully to {settings.REDIS_URL}")
                    break
                    
                except Exception as e:
                    logger.warning(f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}")
                    
                    if attempt < max_retries - 1:
                        # Ждем перед повторной попыткой
                        wait_time = 2 ** attempt  # Экспоненциальная задержка
                        logger.info(f"Retrying Redis connection in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} Redis connection attempts failed")
                        raise
        
        return self._redis
    
    async def close(self):
        """Закрыть подключение к Redis"""
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
    
    @property
    def redis(self) -> Optional[redis.Redis]:
        """Получить текущее подключение к Redis"""
        return self._redis


# Глобальный экземпляр менеджера Redis
redis_manager = RedisManager()
