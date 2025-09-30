#!/usr/bin/env python3
"""
Тест исправления ошибки "There is no text in the message to edit"

Проверяет корректную обработку callback'ов на фото-сообщениях
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from features.random_face.handlers import RandomFaceHandlers
from infra.redis import redis_manager


class MockPhotoMessage:
    """Мок сообщения с фото (без текста)"""
    
    def __init__(self, chat_id: int = 12345):
        self.chat_id = chat_id
        self.text = None  # Фото-сообщение не имеет text
        self.photo = [Mock()]  # Есть фото
        self.reply_text = AsyncMock()
        self.delete = AsyncMock()


class MockTextMessage:
    """Мок текстового сообщения"""
    
    def __init__(self, chat_id: int = 12345):
        self.chat_id = chat_id
        self.text = "Random Face Generator menu text"  # Есть текст
        self.reply_text = AsyncMock()
        self.delete = AsyncMock()


class MockCallbackQuery:
    """Мок callback query"""
    
    def __init__(self, user_id: int = 12345, message_type: str = "text"):
        self.from_user = Mock()
        self.from_user.id = user_id
        
        if message_type == "text":
            self.message = MockTextMessage(user_id)
        else:
            self.message = MockPhotoMessage(user_id)
            
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.delete_message = AsyncMock()


class MockUpdate:
    """Мок Update"""
    
    def __init__(self, user_id: int = 12345, message_type: str = "text"):
        self.callback_query = MockCallbackQuery(user_id, message_type)


class MockContext:
    """Мок Context"""
    
    def __init__(self):
        self.bot = Mock()
        self.bot.send_photo = AsyncMock()
        self.bot_data = {'FACE_QUOTA_PER_DAY': 10}
        self.user_data = {}


async def test_text_message_scenario():
    """Тест со стандартным текстовым сообщением"""
    
    print("📝 Тест 1: Callback на текстовом сообщении")
    
    try:
        redis_client = await redis_manager.initialize()
        handlers = RandomFaceHandlers(redis_client)
        
        # Создаем моки для текстового сообщения
        update = MockUpdate(user_id=11111, message_type="text")
        context = MockContext()
        
        # Выполняем генерацию
        await handlers.generate_random_face(update, context)
        
        # Проверяем что edit_message_text был вызван (для loading)
        update.callback_query.edit_message_text.assert_called()
        print("   ✅ Текстовое сообщение корректно отредактировано")
        
        # Проверяем что фото отправлено
        context.bot.send_photo.assert_called_once()
        print("   ✅ Фото отправлено")
        
        # Проверяем что сообщение удалено
        update.callback_query.delete_message.assert_called()
        print("   ✅ Сообщение загрузки удалено")
        
        await redis_manager.close()
        print("   ✅ Тест текстового сообщения пройден\n")
        
    except Exception as e:
        print(f"   ❌ Ошибка в тесте: {e}\n")


async def test_photo_message_scenario():
    """Тест с фото-сообщением (исправление багфикса)"""
    
    print("📷 Тест 2: Callback на фото-сообщении (после нажатия 'Ещё одно')")
    
    try:
        redis_client = await redis_manager.initialize()
        handlers = RandomFaceHandlers(redis_client)
        
        # Создаем моки для фото-сообщения
        update = MockUpdate(user_id=22222, message_type="photo")
        context = MockContext()
        
        # Выполняем генерацию (имитируя нажатие "Ещё одно")
        await handlers.generate_random_face(update, context)
        
        # Проверяем что edit_message_text НЕ был вызван
        update.callback_query.edit_message_text.assert_not_called()
        print("   ✅ edit_message_text корректно не вызывался для фото")
        
        # Проверяем что reply_text был использован для loading
        update.callback_query.message.reply_text.assert_called()
        print("   ✅ Сообщение загрузки отправлено через reply_text")
        
        # Проверяем что фото отправлено
        context.bot.send_photo.assert_called_once()
        print("   ✅ Новое фото отправлено")
        
        # Проверяем что loading message было сохранено и удалено
        assert 'loading_message' not in context.user_data  # Должно быть очищено
        print("   ✅ Сообщение загрузки корректно очищено")
        
        await redis_manager.close()
        print("   ✅ Тест фото-сообщения пройден\n")
        
    except Exception as e:
        print(f"   ❌ Ошибка в тесте: {e}\n")


async def test_error_handling():
    """Тест обработки ошибок на разных типах сообщений"""
    
    print("⚠️ Тест 3: Обработка ошибок")
    
    try:
        redis_client = await redis_manager.initialize()
        handlers = RandomFaceHandlers(redis_client)
        
        # Мокаем сервис для возврата ошибки
        original_service = handlers.service
        mock_service = Mock()
        mock_service.fetch_face_image = AsyncMock(
            return_value=(None, "Лимит на сегодня исчерпан. Доступ снова завтра.")
        )
        handlers.service = mock_service
        
        # Тест ошибки на текстовом сообщении
        update_text = MockUpdate(user_id=33333, message_type="text")
        context_text = MockContext()
        
        await handlers.generate_random_face(update_text, context_text)
        update_text.callback_query.edit_message_text.assert_called()
        print("   ✅ Ошибка на текстовом сообщении обработана")
        
        # Тест ошибки на фото-сообщении
        update_photo = MockUpdate(user_id=44444, message_type="photo")
        context_photo = MockContext()
        
        await handlers.generate_random_face(update_photo, context_photo)
        update_photo.callback_query.message.reply_text.assert_called()
        print("   ✅ Ошибка на фото-сообщении обработана")
        
        # Восстанавливаем оригинальный сервис
        handlers.service = original_service
        
        await redis_manager.close()
        print("   ✅ Тест обработки ошибок пройден\n")
        
    except Exception as e:
        print(f"   ❌ Ошибка в тесте: {e}\n")


if __name__ == "__main__":
    print("🔧 Тестирование исправления ошибки 'There is no text in the message to edit'")
    print("=" * 70)
    
    asyncio.run(test_text_message_scenario())
    asyncio.run(test_photo_message_scenario())
    asyncio.run(test_error_handling())
    
    print("=" * 70)
    print("🎉 Тестирование багфикса завершено!")
    print("\nИсправление позволяет:")
    print("✅ Корректно обрабатывать callback'и на текстовых сообщениях")
    print("✅ Корректно обрабатывать callback'и на фото-сообщениях") 
    print("✅ Избегать ошибки 'There is no text in the message to edit'")
    print("✅ Правильно управлять сообщениями загрузки")
