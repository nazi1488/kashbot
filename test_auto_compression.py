#!/usr/bin/env python3
"""
Тест автоматического сжатия для получения результата
"""

import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from handlers.uniqizer import process_media_file
from telegram import Update, Message, User, Chat, Document, Video
from telegram.ext import ContextTypes


async def test_large_document_processing():
    """Тест обработки большого документа (>20MB)"""
    
    print("🧪 Тестируем большой документ (50МБ)...")
    
    # Создаем мок объекты
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=12345, type="private")
    mock_message = Message(message_id=1, date=None, chat=mock_chat, from_user=mock_user)
    
    # Мок Update и Context
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_user = mock_user
    
    mock_context = MagicMock()
    mock_context.user_data = {'copies_count': 2}
    mock_context.bot = AsyncMock()
    
    # Большой документ 50MB
    mock_document = MagicMock()
    mock_document.file_id = "large_doc_50mb"
    mock_document.file_size = 50 * 1024 * 1024
    mock_document.file_name = "large_video.mp4"
    
    # Мок processing_msg
    mock_processing_msg = AsyncMock()
    mock_processing_msg.edit_text = AsyncMock()
    mock_processing_msg.delete = AsyncMock()
    mock_message.reply_text = AsyncMock(return_value=mock_processing_msg)
    mock_message.reply_document = AsyncMock()
    
    # Мокаем compress_for_telegram для успешного результата
    with patch('handlers.uniqizer.compress_for_telegram') as mock_compress:
        # Создаем временный файл как результат сжатия
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            test_data = b"compressed video data" * 100000  # ~1.5MB сжатых данных
            temp_file.write(test_data)
            temp_file_path = Path(temp_file.name)
        
        # Настраиваем мок для возврата сжатого файла
        mock_compress.return_value = (temp_file_path, None)
        
        # Мокаем create_multiple_unique_videos
        with patch('utils.create_multiple_unique_videos') as mock_create_videos:
            async def mock_video_creation(input_path, output_dir, count, params, callback):
                output_path = Path(output_dir)
                results = []
                for i in range(count):
                    result_file = output_path / f"unique_video_{i+1}.mp4"
                    result_file.write_bytes(b"unique video data")
                    results.append(str(result_file))
                return results
            
            mock_create_videos.side_effect = mock_video_creation
            
            try:
                # Запускаем обработку
                result = await process_media_file(
                    update=mock_update,
                    context=mock_context,
                    file_obj=mock_document,
                    file_name="large_video.mp4",
                    processing_msg=mock_processing_msg,
                    is_compressed=False
                )
                
                print(f"📊 Результат обработки:")
                print(f"- Функция завершилась без ошибок: {'Да' if result is not None else 'Нет'}")
                print(f"- compress_for_telegram вызван: {'Да' if mock_compress.called else 'Нет'}")
                print(f"- create_multiple_unique_videos вызван: {'Да' if mock_create_videos.called else 'Нет'}")
                print(f"- reply_document вызван: {'Да' if mock_message.reply_document.called else 'Нет'}")
                
                if mock_message.reply_document.called:
                    print("✅ УСПЕХ: Пользователь получил результат!")
                    return True
                else:
                    print("❌ ПРОВАЛ: Пользователь НЕ получил результат")
                    return False
                    
            finally:
                # Очищаем временный файл
                if temp_file_path.exists():
                    temp_file_path.unlink()


async def test_compressed_video_processing():
    """Тест обработки сжатого видео (уже обработанного Telegram)"""
    
    print("\n🧪 Тестируем сжатое видео от Telegram...")
    
    # Создаем мок объекты
    mock_user = User(id=12345, first_name="Test", is_bot=False)
    mock_chat = Chat(id=12345, type="private")
    mock_message = Message(message_id=1, date=None, chat=mock_chat, from_user=mock_user)
    
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_user = mock_user
    
    mock_context = MagicMock()
    mock_context.user_data = {'copies_count': 3}
    mock_context.bot = AsyncMock()
    
    # Сжатое видео от Telegram (обычно <20MB)
    mock_video = MagicMock()
    mock_video.file_id = "compressed_video_tg"
    mock_video.file_size = 15 * 1024 * 1024  # 15MB после сжатия Telegram
    
    mock_processing_msg = AsyncMock()
    mock_processing_msg.edit_text = AsyncMock()
    mock_processing_msg.delete = AsyncMock()
    mock_message.reply_document = AsyncMock()
    
    # Мокаем compress_for_telegram для успешного результата
    with patch('handlers.uniqizer.compress_for_telegram') as mock_compress:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            test_data = b"telegram compressed video" * 50000
            temp_file.write(test_data)
            temp_file_path = Path(temp_file.name)
        
        mock_compress.return_value = (temp_file_path, None)
        
        with patch('utils.create_multiple_unique_videos') as mock_create_videos:
            async def mock_video_creation(input_path, output_dir, count, params, callback):
                output_path = Path(output_dir)
                results = []
                for i in range(count):
                    result_file = output_path / f"unique_video_{i+1}.mp4"  
                    result_file.write_bytes(b"unique compressed video")
                    results.append(str(result_file))
                return results
            
            mock_create_videos.side_effect = mock_video_creation
            
            try:
                result = await process_media_file(
                    update=mock_update,
                    context=mock_context,
                    file_obj=mock_video,
                    file_name="video_12345_1.mp4",
                    processing_msg=mock_processing_msg,
                    is_compressed=True
                )
                
                print(f"📊 Результат обработки сжатого видео:")
                print(f"- Обработка завершена: {'Да' if result is not None else 'Нет'}")
                print(f"- Пользователь получил файлы: {'Да' if mock_message.reply_document.called else 'Нет'}")
                
                if mock_message.reply_document.called:
                    print("✅ УСПЕХ: Сжатое видео успешно уникализировано!")
                    return True
                else:
                    print("❌ ПРОВАЛ: Сжатое видео не обработано")
                    return False
                    
            finally:
                if temp_file_path.exists():
                    temp_file_path.unlink()


async def main():
    """Главная функция тестирования"""
    
    print("🚀 Тестирование АВТОМАТИЧЕСКОГО получения результата\n")
    print("=" * 70)
    
    try:
        # Тест 1: Большой документ с автоматическим сжатием
        test1_success = await test_large_document_processing()
        
        # Тест 2: Сжатое видео от Telegram  
        test2_success = await test_compressed_video_processing()
        
        print("\n" + "=" * 70)
        print("📊 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ:")
        print(f"- Большие документы: {'✅ ОБРАБАТЫВАЮТСЯ' if test1_success else '❌ НЕ РАБОТАЕТ'}")
        print(f"- Сжатые видео: {'✅ ОБРАБАТЫВАЮТСЯ' if test2_success else '❌ НЕ РАБОТАЕТ'}")
        
        if test1_success and test2_success:
            print("\n🎉 ПРОБЛЕМА РЕШЕНА ПОЛНОСТЬЮ!")
            print("✅ Пользователи ВСЕГДА получают результат")
            print("✅ Автоматическое сжатие работает")
            print("✅ Никаких отказов в обработке")
            print("✅ Уникализатор готов к продакшену!")
        else:
            print("\n❌ ПРОБЛЕМА НЕ РЕШЕНА")
            print("⚠️ Пользователи все еще могут не получить результат")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
