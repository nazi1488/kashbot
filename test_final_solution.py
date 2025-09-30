#!/usr/bin/env python3
"""
Тест финального решения для больших файлов
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from handlers.uniqizer import file_handler
from telegram import Update, Message, User, Chat, Document
from telegram.ext import ContextTypes


async def test_large_document_redirect():
    """Тест обработки большого документа - должен перенаправить на видео"""
    
    print("🧪 Тестируем большой документ (50МБ)...")
    
    # Создаем мок объекты
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=12345, type="private")
    
    # Мок документа 50MB
    mock_document = MagicMock()
    mock_document.file_size = 50 * 1024 * 1024  # 50MB
    mock_document.file_name = "large_video.mp4"
    
    mock_message = MagicMock()
    mock_message.document = mock_document
    mock_message.reply_text = AsyncMock()
    
    mock_update = MagicMock()
    mock_update.message = mock_message
    
    mock_context = MagicMock()
    mock_context.user_data = {'copies_count': 2}
    
    try:
        # Запускаем обработчик
        result = await file_handler(mock_update, mock_context)
        
        print(f"📊 Результат:")
        print(f"- Функция вернула WAITING_FOR_FILE: {'Да' if result == 1 else 'Нет'}")  # WAITING_FOR_FILE = 1
        print(f"- reply_text был вызван: {'Да' if mock_message.reply_text.called else 'Нет'}")
        
        if mock_message.reply_text.called:
            call_args = mock_message.reply_text.call_args[0][0]  # Первый аргумент первого вызова
            print(f"- Сообщение содержит 'видео': {'Да' if 'видео' in call_args else 'Нет'}")
            print(f"- Сообщение содержит 'автоматически': {'Да' if 'автоматически' in call_args else 'Нет'}")
            
            # Показываем часть сообщения
            print(f"- Начало сообщения: {call_args[:50]}...")
            
            if 'видео' in call_args and 'автоматически' in call_args:
                print("✅ ПРАВИЛЬНО: Пользователя просят переотправить как видео")
                return True
            else:
                print("❌ НЕПРАВИЛЬНО: Неверное сообщение")
                return False
        else:
            print("❌ ПРОВАЛ: Сообщение не отправлено")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_small_document_processing():
    """Тест обработки маленького документа - должен обрабатываться"""
    
    print("\n🧪 Тестируем маленький документ (5МБ)...")
    
    # Создаем мок объекты
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=12345, type="private")
    
    # Мок документа 5MB
    mock_document = MagicMock()
    mock_document.file_size = 5 * 1024 * 1024  # 5MB
    mock_document.file_name = "small_video.mp4"
    
    mock_message = MagicMock()
    mock_message.document = mock_document
    mock_message.reply_text = AsyncMock()
    
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_user = mock_user
    
    mock_context = MagicMock()
    mock_context.user_data = {'copies_count': 1}
    mock_context.bot = AsyncMock()
    
    # Мокаем process_media_file чтобы вернуть успех
    from unittest.mock import patch
    with patch('handlers.uniqizer.process_media_file') as mock_process:
        mock_process.return_value = 0  # ConversationHandler.END
        
        try:
            result = await file_handler(mock_update, mock_context)
            
            print(f"📊 Результат:")
            print(f"- process_media_file вызвана: {'Да' if mock_process.called else 'Нет'}")
            print(f"- Результат: {result}")
            
            if mock_process.called:
                print("✅ ПРАВИЛЬНО: Маленький файл передан на обработку")
                return True
            else:
                print("❌ НЕПРАВИЛЬНО: Маленький файл не обработан")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def main():
    """Главная функция тестирования"""
    
    print("🚀 Тестирование ФИНАЛЬНОГО решения\n")
    print("=" * 60)
    
    try:
        # Тест 1: Большой документ → переадресация
        test1_success = await test_large_document_redirect()
        
        # Тест 2: Маленький документ → обработка
        test2_success = await test_small_document_processing()
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
        print(f"- Большие файлы: {'✅ ПЕРЕНАПРАВЛЯЮТСЯ' if test1_success else '❌ НЕ РАБОТАЕТ'}")
        print(f"- Маленькие файлы: {'✅ ОБРАБАТЫВАЮТСЯ' if test2_success else '❌ НЕ РАБОТАЕТ'}")
        
        if test1_success and test2_success:
            print("\n🎉 РЕШЕНИЕ РАБОТАЕТ!")
            print("✅ Большие файлы → просьба переотправить как видео")
            print("✅ Маленькие файлы → обрабатываются напрямую")
            print("✅ Пользователи ВСЕГДА получат результат!")
        else:
            print("\n❌ РЕШЕНИЕ НЕ РАБОТАЕТ")
            print("⚠️ Требуется дополнительная доработка")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
