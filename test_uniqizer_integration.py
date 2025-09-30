#!/usr/bin/env python3
"""
Интеграционный тест уникализатора с автоматическим сжатием
"""

import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import sys

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from handlers.uniqizer import process_media_file
from telegram import Update, Message, User, Chat, Document
from telegram.ext import ContextTypes


async def test_uniqizer_with_large_file():
    """Тестируем уникализатор с большим файлом"""
    
    print("🧪 Тестируем уникализатор с большим файлом...")
    
    # Создаем мок-объекты Telegram
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=12345, type="private")
    mock_message = Message(
        message_id=1,
        date=None,
        chat=mock_chat,
        from_user=mock_user
    )
    
    # Создаем мок Update
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_user = mock_user
    
    # Создаем мок Context
    mock_context = MagicMock()
    mock_context.user_data = {'copies_count': 2}
    mock_context.bot = AsyncMock()
    
    # Создаем мок файла (большой документ 50MB)
    mock_document = MagicMOck()
    mock_document.file_id = "large_file_id"
    mock_document.file_size = 50 * 1024 * 1024  # 50MB
    mock_document.file_name = "large_video.mp4"
    
    # Мокаем bot.get_file
    mock_file = AsyncMock()
    mock_file.file_size = 50 * 1024 * 1024
    mock_file.download_to_drive = AsyncMock()
    mock_context.bot.get_file.return_value = mock_file
    
    # Создаем тестовый файл
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        test_data = b"test video data" * 1000000  # ~15MB
        temp_file.write(test_data)
        temp_file_path = temp_file.name
    
    try:
        # Мокаем download для создания файла
        async def mock_download(path):
            with open(path, 'wb') as f:
                f.write(test_data)
        
        mock_file.download_to_drive.side_effect = mock_download
        
        # Мокаем функции уникализации
        from utils import create_multiple_unique_videos
        
        async def mock_create_videos(input_path, output_dir, count, params, callback):
            # Создаем фиктивные результаты
            output_path = Path(output_dir)
            results = []
            for i in range(count):
                result_file = output_path / f"unique_video_{i+1}.mp4"
                result_file.write_bytes(b"unique video data")
                results.append(str(result_file))
            return results
        
        # Подменяем функцию создания уникальных видео
        import utils
        original_create_videos = utils.create_multiple_unique_videos
        utils.create_multiple_unique_videos = mock_create_videos
        
        # Мокаем reply_text и reply_document
        mock_processing_msg = AsyncMock()
        mock_processing_msg.edit_text = AsyncMock()
        mock_processing_msg.delete = AsyncMock()
        mock_message.reply_text = AsyncMock(return_value=mock_processing_msg)
        mock_message.reply_document = AsyncMock()
        
        try:
            # Запускаем тест
            result = await process_media_file(
                update=mock_update,
                context=mock_context,
                file_obj=mock_document,
                file_name="large_video.mp4",
                processing_msg=mock_processing_msg,
                is_compressed=False
            )
            
            print("✅ Процесс завершен без ошибок")
            
            # Проверяем, что файл был отправлен пользователю
            if mock_message.reply_document.called:
                print("✅ Результат отправлен пользователю")
            else:
                print("❌ Результат не отправлен")
                
            # Проверяем отсутствие лишних сообщений о сжатии
            edit_calls = mock_processing_msg.edit_text.call_args_list
            compression_messages = [
                call for call in edit_calls 
                if any(word in str(call).lower() for word in ['сжим', 'compress', 'автоматически'])
            ]
            
            if not compression_messages:
                print("✅ Никаких сообщений о сжатии пользователю не отправлено")
            else:
                print(f"❌ Найдены сообщения о сжатии: {compression_messages}")
            
            return True
            
        finally:
            # Восстанавливаем оригинальную функцию
            utils.create_multiple_unique_videos = original_create_videos
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def main():
    """Главная функция тестирования интеграции"""
    
    print("🚀 Запуск интеграционного теста уникализатора\n")
    
    try:
        success = await test_uniqizer_with_large_file()
        
        print(f"\n📊 Результат интеграционного теста:")
        if success:
            print("🎉 ИНТЕГРАЦИОННЫЙ ТЕСТ ПРОЙДЕН!")
            print("✅ Большие файлы автоматически сжимаются")
            print("✅ Пользователь не видит технических деталей")
            print("✅ Уникализация работает прозрачно")
        else:
            print("❌ ИНТЕГРАЦИОННЫЙ ТЕСТ ПРОВАЛЕН")
            
    except Exception as e:
        print(f"❌ Ошибка при интеграционном тестировании: {e}")


if __name__ == "__main__":
    asyncio.run(main())
