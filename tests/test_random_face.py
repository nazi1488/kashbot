"""
Тесты для модуля Random Face

Юнит и интеграционные тесты для проверки работы сервиса генерации случайных лиц.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
    from features.random_face.service import RandomFaceService
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


@pytest.fixture
def redis_mock():
    """Мок Redis клиента"""
    redis = AsyncMock()
    redis.exists.return_value = False
    redis.get.return_value = None
    redis.incr.return_value = 1
    redis.setex.return_value = True
    redis.expire.return_value = True
    return redis


@pytest.fixture
def service(redis_mock):
    """Экземпляр сервиса для тестирования"""
    return RandomFaceService(redis_mock)


class TestRandomFaceService:
    """Тесты сервиса Random Face"""
    
    @pytest.mark.asyncio
    async def test_fetch_face_image_success(self, service, redis_mock):
        """Тест успешного получения изображения"""
        # Подготавливаем моки
        fake_image_data = b"fake_image_data_jpeg_format"
        
        with patch('httpx.AsyncClient') as mock_client:
            # Настраиваем мок HTTP-клиента
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            
            # Правильный мок для aiter_bytes
            async def mock_aiter_bytes(chunk_size=8192):
                yield fake_image_data
            mock_response.aiter_bytes = mock_aiter_bytes
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            # Выполняем тест
            result, error = await service.fetch_face_image(user_id=12345)
            
            # Проверяем результат
            assert error is None
            assert result is not None
            assert isinstance(result, BytesIO)
            assert result.getvalue() == fake_image_data
            
            # Проверяем что квота увеличилась
            redis_mock.incr.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limit_check(self, service, redis_mock):
        """Тест проверки антиспама"""
        # Устанавливаем что флаг антиспама активен
        redis_mock.exists.return_value = True
        
        result, error = await service.fetch_face_image(user_id=12345)
        
        assert result is None
        assert error == "Слишком часто, подожди 2 сек"
        
        # Проверяем что HTTP-запрос не делался
        redis_mock.incr.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_quota_exceeded(self, service, redis_mock):
        """Тест превышения дневной квоты"""
        # Устанавливаем что квота превышена (10 >= 10)
        redis_mock.get.return_value = "10"
        
        with patch('config.settings') as mock_settings:
            mock_settings.FACE_QUOTA_PER_DAY = 10
            
            result, error = await service.fetch_face_image(user_id=12345)
        
        assert result is None
        assert error == "Лимит на сегодня исчерпан. Доступ снова завтра."
        
        # Проверяем что HTTP-запрос не делался
        redis_mock.incr.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_invalid_content_type(self, service, redis_mock):
        """Тест валидации Content-Type"""
        with patch('httpx.AsyncClient') as mock_client:
            # Настраиваем мок с неправильным content-type
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            result, error = await service.fetch_face_image(user_id=12345)
            
            assert result is None
            assert error == "Сервис недоступен, попробуй ещё раз позже"
            
            # Квота не должна увеличиваться при ошибке
            redis_mock.incr.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_file_size_limit(self, service, redis_mock):
        """Тест ограничения размера файла"""
        # Создаем данные размером больше 5 МБ
        large_data = b"a" * (6 * 1024 * 1024)  # 6 МБ
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            
            # Правильный мок для aiter_bytes с большими данными
            async def mock_aiter_bytes_large(chunk_size=8192):
                yield large_data
            mock_response.aiter_bytes = mock_aiter_bytes_large
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            result, error = await service.fetch_face_image(user_id=12345)
            
            assert result is None
            assert error == "Сервис недоступен, попробуй ещё раз позже"
            
            # Квота не должна увеличиваться при ошибке
            redis_mock.incr.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_server_error_with_retries(self, service, redis_mock):
        """Тест ретраев при серверной ошибке"""
        with patch('httpx.AsyncClient') as mock_client:
            # Настраиваем мок для ошибки 503
            mock_response = Mock()
            mock_response.status_code = 503
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            with patch('asyncio.sleep') as mock_sleep:  # Ускоряем тесты
                result, error = await service.fetch_face_image(user_id=12345)
            
            assert result is None
            assert error == "Сервис недоступен, попробуй ещё раз позже"
            
            # Проверяем что было 3 попытки (1+2 ретрая)
            assert mock_context.__aenter__.return_value.get.call_count == 3
            
            # Проверяем что были задержки
            assert mock_sleep.call_count == 2  # 2 ретрая с задержками
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, service, redis_mock):
        """Тест обработки таймаутов"""
        with patch('httpx.AsyncClient') as mock_client:
            # Настраиваем мок для таймаута
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            mock_client.return_value = mock_context
            
            with patch('asyncio.sleep'):  # Ускоряем тесты
                result, error = await service.fetch_face_image(user_id=12345)
            
            assert result is None
            assert error == "Сервис недоступен, попробуй ещё раз позже"
            
            # Проверяем что было 3 попытки
            assert mock_context.__aenter__.return_value.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_get_remaining_quota(self, service, redis_mock):
        """Тест получения оставшейся квоты"""
        with patch('config.settings') as mock_settings:
            mock_settings.FACE_QUOTA_PER_DAY = 10
            
            # Тест когда использовано 3 из 10
            redis_mock.get.return_value = "3"
            remaining = await service.get_remaining_quota(user_id=12345)
            assert remaining == 7
            
            # Тест когда ничего не использовано
            redis_mock.get.return_value = None
            remaining = await service.get_remaining_quota(user_id=12345)
            assert remaining == 10
            
            # Тест когда квота превышена
            redis_mock.get.return_value = "12"
            remaining = await service.get_remaining_quota(user_id=12345)
            assert remaining == 0
    
    def test_quota_key_generation(self, service):
        """Тест генерации ключа квоты"""
        with patch('features.random_face.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20231227"
            
            key = service._get_quota_key(user_id=12345)
            assert key == "face:quota:12345:20231227"


@pytest.mark.integration
class TestRandomFaceIntegration:
    """Интеграционные тесты с моками внешних сервисов"""
    
    @pytest.mark.asyncio
    async def test_successful_image_fetch_integration(self, redis_mock):
        """Интеграционный тест успешного получения изображения"""
        service = RandomFaceService(redis_mock)
        
        # Мокаем успешный ответ от thispersondoesnotexist.com
        fake_jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # JPEG header
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "image/jpeg"}
            
            # Правильный мок для aiter_bytes
            async def mock_aiter_bytes(chunk_size=8192):
                yield fake_jpeg_data
            mock_response.aiter_bytes = mock_aiter_bytes
            
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context
            
            # Выполняем полный flow
            result, error = await service.fetch_face_image(user_id=12345)
            
            # Проверяем результат
            assert error is None
            assert result is not None
            assert result.getvalue() == fake_jpeg_data
            
            # Проверяем взаимодействие с Redis
            redis_mock.setex.assert_called_once()  # антиспам флаг
            redis_mock.incr.assert_called_once()   # квота
    
    @pytest.mark.asyncio
    async def test_service_unavailable_integration(self, redis_mock):
        """Интеграционный тест недоступности сервиса"""
        service = RandomFaceService(redis_mock)
        
        with patch('httpx.AsyncClient') as mock_client:
            # Мокаем недоступность сервиса
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )
            mock_client.return_value = mock_context
            
            with patch('asyncio.sleep'):  # Ускоряем тесты
                result, error = await service.fetch_face_image(user_id=12345)
            
            assert result is None
            assert error == "Сервис недоступен, попробуй ещё раз позже"
            
            # Проверяем что антиспам все равно был установлен
            redis_mock.setex.assert_called_once()
            # Но квота не увеличилась
            redis_mock.incr.assert_not_called()
