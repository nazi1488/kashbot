#!/usr/bin/env python3
"""
Симуляция Telegram взаимодействия для Random Face Generator

Этот тест симулирует полный workflow пользователя через Telegram интерфейс
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from io import BytesIO

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from features.random_face.handlers import RandomFaceHandlers
from features.random_face.keyboard import RandomFaceKeyboard
from infra.redis import redis_manager


class MockUpdate:
    """Мок Telegram Update"""
    
    def __init__(self, user_id: int = 12345):
        self.callback_query = Mock()
        self.callback_query.from_user.id = user_id
        self.callback_query.message.chat_id = user_id
        self.callback_query.answer = AsyncMock()
        self.callback_query.edit_message_text = AsyncMock()
        self.callback_query.delete_message = AsyncMock()


class MockContext:
    """Мок Telegram Context"""
    
    def __init__(self):
        self.bot = Mock()
        self.bot.send_photo = AsyncMock()
        self.bot_data = {'FACE_QUOTA_PER_DAY': 10}


async def test_telegram_simulation():
    """Полная симуляция Telegram взаимодействия"""
    
    print("🤖 Симуляция Telegram взаимодействия с Random Face...")
    
    try:
        # Инициализируем Redis и handlers
        redis_client = await redis_manager.initialize()
        handlers = RandomFaceHandlers(redis_client)
        keyboard = RandomFaceKeyboard()
        
        # Создаем моки
        update = MockUpdate(user_id=33333)
        context = MockContext()
        
        print("\n📱 Тест 1: Показ главного меню")
        await handlers.show_random_face_menu(update, context)
        
        # Проверяем что меню было показано
        update.callback_query.edit_message_text.assert_called_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert "Random Face Generator" in call_args[1]['text']
        print("✅ Главное меню отображено корректно")
        
        print("\n📱 Тест 2: Генерация лица")
        update.callback_query.edit_message_text.reset_mock()
        context.bot.send_photo.reset_mock()
        
        await handlers.generate_random_face(update, context)
        
        # Проверяем что было показано сообщение о загрузке
        update.callback_query.edit_message_text.assert_called()
        loading_call = update.callback_query.edit_message_text.call_args_list[0]
        assert "Генерируем новое лицо" in loading_call[1]['text']
        print("✅ Сообщение о загрузке показано")
        
        # Проверяем что фото было отправлено
        context.bot.send_photo.assert_called_once()
        photo_call = context.bot.send_photo.call_args
        assert photo_call[1]['chat_id'] == 33333
        assert "Синтетическое лицо" in photo_call[1]['caption']
        print("✅ Фото отправлено с корректной подписью")
        
        # Проверяем что сообщение загрузки удалено
        update.callback_query.delete_message.assert_called_once()
        print("✅ Сообщение загрузки удалено")
        
        print("\n📱 Тест 3: Проверка клавиатур")
        main_keyboard = keyboard.main_menu()
        after_keyboard = keyboard.after_generation()
        
        # Проверяем кнопки главного меню
        main_buttons = [btn.text for row in main_keyboard.inline_keyboard for btn in row]
        assert "🎲 Сгенерировать" in main_buttons
        assert "🔁 Ещё" in main_buttons
        assert "↩️ Назад" in main_buttons
        print("✅ Кнопки главного меню корректны")
        
        # Проверяем кнопки после генерации
        after_buttons = [btn.text for row in after_keyboard.inline_keyboard for btn in row]
        assert "🔁 Ещё одно" in after_buttons
        assert "↩️ Назад в меню" in after_buttons
        print("✅ Кнопки после генерации корректны")
        
        print("\n📱 Тест 4: Повторная генерация")
        update2 = MockUpdate(user_id=44444)
        context.bot.send_photo.reset_mock()
        
        await handlers.handle_more_generation(update2, context)
        
        # Проверяем что снова было отправлено фото
        context.bot.send_photo.assert_called_once()
        print("✅ Повторная генерация работает")
        
        print("\n📱 Тест 5: Антиспам защита")
        # Быстро делаем второй запрос тем же пользователем
        update3 = MockUpdate(user_id=33333)  # Тот же пользователь
        update3.callback_query.edit_message_text.reset_mock()
        context.bot.send_photo.reset_mock()
        
        await handlers.generate_random_face(update3, context)
        
        # Должна быть показана ошибка антиспама
        error_call = update3.callback_query.edit_message_text.call_args
        assert "Слишком часто" in error_call[1]['text']
        print("✅ Антиспам защита сработала")
        
        await redis_manager.close()
        print("\n🎉 Все тесты Telegram симуляции пройдены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в симуляции: {e}")
        import traceback
        traceback.print_exc()


async def test_edge_cases():
    """Тест граничных случаев"""
    
    print("\n🔍 Тестируем граничные случаи...")
    
    try:
        redis_client = await redis_manager.initialize()
        handlers = RandomFaceHandlers(redis_client)
        
        # Тест с недоступным API (мокаем ошибку)
        update = MockUpdate(user_id=55555)
        context = MockContext()
        
        # Мокаем сервис для имитации ошибки API
        original_service = handlers.service
        mock_service = Mock()
        mock_service.fetch_face_image = AsyncMock(return_value=(None, "Сервис недоступен, попробуй ещё раз позже"))
        handlers.service = mock_service
        
        print("🔍 Тест недоступности API...")
        await handlers.generate_random_face(update, context)
        
        # Проверяем что показана ошибка
        error_call = update.callback_query.edit_message_text.call_args
        assert "Не удалось сгенерировать лицо" in error_call[1]['text']
        print("✅ Ошибка API обработана корректно")
        
        # Восстанавливаем оригинальный сервис
        handlers.service = original_service
        
        await redis_manager.close()
        print("✅ Тест граничных случаев завершен")
        
    except Exception as e:
        print(f"❌ Ошибка в тесте граничных случаев: {e}")


if __name__ == "__main__":
    print("🎭 Запуск полной симуляции Telegram бота")
    print("=" * 50)
    
    asyncio.run(test_telegram_simulation())
    asyncio.run(test_edge_cases())
    
    print("\n" + "=" * 50)
    print("🏁 Симуляция завершена!")
