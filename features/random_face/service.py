"""
Random Face Service

Источник: https://thispersondoesnotexist.com/image (неофициальный endpoint).
Каждый запрос возвращает новое синтетическое лицо (GAN/StyleGAN). 
SLA нет → таймауты/ретраи обязательны.

Модуль обеспечивает:
- HTTP-клиент с ретраями и валидацией
- Ограничения по размеру файла (≤5 МБ)
- Антиспам и квотирование через Redis
"""

import asyncio
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional, Tuple

import httpx
from redis.asyncio import Redis

from config import settings

logger = logging.getLogger(__name__)

# Константы
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2
BACKOFF_DELAYS = [0.5, 1.5]  # Экспоненциальный бэкофф
ANTISPAM_SECONDS = 2

# Пользовательский агент
USER_AGENT = f"KashHub/1.0 (+https://t.me/kashhub_bot)"


class RandomFaceService:
    """Сервис для генерации случайных лиц"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.endpoint_url = "https://thispersondoesnotexist.com/"
    
    async def fetch_face_image(self, user_id: int) -> Tuple[Optional[BytesIO], Optional[str]]:
        """
        Получить случайное лицо с сервиса
        
        Args:
            user_id: ID пользователя для логирования
            
        Returns:
            Tuple[BytesIO, None] при успехе или (None, error_message) при ошибке
        """
        # Проверяем антиспам
        if await self._is_rate_limited(user_id):
            return None, "Слишком часто, подожди 2 сек"
        
        # Проверяем дневную квоту
        if await self._is_quota_exceeded(user_id):
            return None, "Лимит на сегодня исчерпан. Доступ снова завтра."
        
        # Устанавливаем антиспам флаг
        await self._set_rate_limit(user_id)
        
        # Пытаемся получить изображение с ретраями
        image_data = await self._fetch_with_retries(user_id)
        
        if image_data is None:
            return None, "Сервис недоступен, попробуй ещё раз позже"
        
        # Увеличиваем счетчик только при успешной загрузке
        await self._increment_quota(user_id)
        
        return BytesIO(image_data), None
    
    async def _fetch_with_retries(self, user_id: int) -> Optional[bytes]:
        """Получить изображение с ретраями"""
        
        headers = {"User-Agent": USER_AGENT}
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers) as client:
            for attempt in range(MAX_RETRIES + 1):  # +1 для первой попытки
                try:
                    logger.info(f"Fetching face image for user {user_id}, attempt {attempt + 1}")
                    
                    response = await client.get(self.endpoint_url)
                    
                    # Проверяем статус код
                    if response.status_code == 200:
                        # Валидируем Content-Type
                        content_type = response.headers.get("content-type", "")
                        if not content_type.startswith("image/"):
                            logger.warning(f"Invalid content-type for user {user_id}: {content_type}")
                            if attempt < MAX_RETRIES:
                                await asyncio.sleep(BACKOFF_DELAYS[attempt])
                                continue
                            return None
                        
                        # Читаем данные с ограничением размера
                        image_data = b""
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            image_data += chunk
                            if len(image_data) > MAX_FILE_SIZE:
                                logger.warning(f"Image too large for user {user_id}: {len(image_data)} bytes")
                                return None
                        
                        if not image_data:
                            logger.warning(f"Empty image data for user {user_id}")
                            if attempt < MAX_RETRIES:
                                await asyncio.sleep(BACKOFF_DELAYS[attempt])
                                continue
                            return None
                        
                        logger.info(f"Successfully fetched image for user {user_id}: {len(image_data)} bytes")
                        return image_data
                    
                    # Ретраи для 5xx ошибок
                    elif response.status_code >= 500:
                        logger.warning(f"Server error {response.status_code} for user {user_id}")
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(BACKOFF_DELAYS[attempt])
                            continue
                    else:
                        logger.error(f"HTTP error {response.status_code} for user {user_id}")
                        return None
                
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.warning(f"Network error for user {user_id}: {type(e).__name__}")
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(BACKOFF_DELAYS[attempt])
                        continue
                
                except Exception as e:
                    logger.error(f"Unexpected error for user {user_id}: {type(e).__name__}: {e}")
                    return None
        
        logger.error(f"All retry attempts failed for user {user_id}")
        return None
    
    async def _is_rate_limited(self, user_id: int) -> bool:
        """Проверить антиспам флаг"""
        key = f"face:lock:{user_id}"
        return await self.redis.exists(key)
    
    async def _set_rate_limit(self, user_id: int) -> None:
        """Установить антиспам флаг на 2 секунды"""
        key = f"face:lock:{user_id}"
        await self.redis.setex(key, ANTISPAM_SECONDS, "1")
    
    async def _is_quota_exceeded(self, user_id: int) -> bool:
        """Проверить превышение дневной квоты"""
        key = self._get_quota_key(user_id)
        current_count = await self.redis.get(key)
        
        if current_count is None:
            return False
        
        return int(current_count) >= settings.FACE_QUOTA_PER_DAY
    
    async def _increment_quota(self, user_id: int) -> None:
        """Увеличить счетчик дневной квоты"""
        key = self._get_quota_key(user_id)
        
        # Увеличиваем счетчик или создаем новый
        current_count = await self.redis.incr(key)
        
        # Устанавливаем TTL только для нового ключа
        if current_count == 1:
            # Устанавливаем срок до конца дня
            tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = tomorrow.replace(day=tomorrow.day + 1)
            ttl_seconds = int((tomorrow - datetime.now()).total_seconds())
            await self.redis.expire(key, ttl_seconds)
    
    async def get_remaining_quota(self, user_id: int) -> int:
        """Получить оставшуюся квоту пользователя"""
        key = self._get_quota_key(user_id)
        current_count = await self.redis.get(key)
        
        if current_count is None:
            return settings.FACE_QUOTA_PER_DAY
        
        remaining = settings.FACE_QUOTA_PER_DAY - int(current_count)
        return max(0, remaining)
    
    def _get_quota_key(self, user_id: int) -> str:
        """Получить ключ квоты для пользователя"""
        today = datetime.now().strftime("%Y%m%d")
        return f"face:quota:{user_id}:{today}"
