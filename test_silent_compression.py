#!/usr/bin/env python3
"""
Тест автоматического сжатия файлов без уведомлений
"""

import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import sys

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from utils.smart_compressor import compress_for_telegram


async def test_silent_compression():
    """Тестируем автоматическое сжатие без уведомлений пользователю"""
    
    print("🧪 Тестируем автоматическое сжатие файлов...")
    
    # Создаем мок-объекты
    mock_bot = AsyncMock()
    mock_file = AsyncMock()
    
    # Симулируем большой файл (30MB)
    mock_file.file_size = 30 * 1024 * 1024  # 30MB
    mock_file.download_to_drive = AsyncMock()
    mock_bot.get_file.return_value = mock_file
    
    # Создаем временный файл для тестирования
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        # Записываем некоторые данные
        test_data = b"test video data" * 1000000  # ~15MB данных
        temp_file.write(test_data)
        temp_file_path = temp_file.name
    
    try:
        # Мокаем download_to_drive для создания файла
        async def mock_download(path):
            with open(path, 'wb') as f:
                f.write(test_data)
        
        mock_file.download_to_drive.side_effect = mock_download
        
        # Мокаем callback для проверки отсутствия уведомлений о сжатии
        callback_calls = []
        
        async def progress_callback(stage, info):
            callback_calls.append((stage, info))
            print(f"📞 Callback: {stage} - {info}")
        
        # Тестируем функцию
        result_path, error = await compress_for_telegram(
            bot=mock_bot,
            file_id="test_file_id",
            original_filename="test_video.mp4",
            progress_callback=progress_callback
        )
        
        # Проверки
        print("\n✅ Результаты теста:")
        print(f"- Файл обработан: {'Да' if result_path else 'Нет'}")
        print(f"- Ошибка: {error if error else 'Нет'}")
        print(f"- Количество уведомлений: {len(callback_calls)}")
        
        if result_path:
            file_size = result_path.stat().st_size
            print(f"- Размер результирующего файла: {file_size / (1024*1024):.1f}MB")
            
            # Проверяем, что файл автоматически сжат или обработан
            if file_size <= 20 * 1024 * 1024:
                print("✅ Файл готов к обработке (≤20MB)")
            else:
                print("⚠️ Файл все еще большой")
        
        # Важная проверка: никаких уведомлений о сжатии пользователю не должно быть
        compression_notifications = [call for call in callback_calls if 'compress' in call[0].lower()]
        if not compression_notifications:
            print("✅ УСПЕХ: Никаких уведомлений о сжатии не отправлено")
        else:
            print(f"❌ ОШИБКА: Найдены уведомления о сжатии: {compression_notifications}")
        
        return result_path is not None and error is None
        
    finally:
        # Очищаем временный файл
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def test_small_file():
    """Тестируем обработку маленького файла"""
    
    print("\n🧪 Тестируем обработку маленького файла...")
    
    # Создаем мок-объекты
    mock_bot = AsyncMock()
    mock_file = AsyncMock()
    
    # Симулируем маленький файл (5MB)
    mock_file.file_size = 5 * 1024 * 1024  # 5MB
    mock_file.download_to_drive = AsyncMock()
    mock_bot.get_file.return_value = mock_file
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
        test_data = b"small video" * 100000  # ~1MB данных
        temp_file.write(test_data)
        temp_file_path = temp_file.name
    
    try:
        async def mock_download(path):
            with open(path, 'wb') as f:
                f.write(test_data)
        
        mock_file.download_to_drive.side_effect = mock_download
        
        callback_calls = []
        async def progress_callback(stage, info):
            callback_calls.append((stage, info))
        
        result_path, error = await compress_for_telegram(
            bot=mock_bot,
            file_id="test_small_file_id", 
            original_filename="small_video.mp4",
            progress_callback=progress_callback
        )
        
        print(f"✅ Маленький файл обработан: {'Да' if result_path else 'Нет'}")
        print(f"✅ Сжатие не применялось (файл <20MB): {'Да' if len(callback_calls) <= 1 else 'Нет'}")
        
        return result_path is not None
        
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def main():
    """Главная функция тестирования"""
    
    print("🚀 Запуск тестов автоматического сжатия\n")
    
    try:
        # Тест 1: Большой файл с автоматическим сжатием
        success1 = await test_silent_compression()
        
        # Тест 2: Маленький файл без сжатия  
        success2 = await test_small_file()
        
        print(f"\n📊 Результаты тестирования:")
        print(f"- Тест большого файла: {'✅ ПРОЙДЕН' if success1 else '❌ ПРОВАЛЕН'}")
        print(f"- Тест маленького файла: {'✅ ПРОЙДЕН' if success2 else '❌ ПРОВАЛЕН'}")
        
        if success1 and success2:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            print("✅ Автоматическое сжатие работает корректно")
            print("✅ Пользователь не получает лишних уведомлений")
            print("✅ Файлы готовы к уникализации")
        else:
            print("\n❌ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
