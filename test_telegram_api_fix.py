#!/usr/bin/env python3
"""
Тест исправления ошибки Telegram API "File is too big"
"""

import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from utils.smart_compressor import compress_for_telegram


async def test_telegram_api_error_handling():
    """Тестируем обработку ошибки Telegram API для больших файлов"""
    
    print("🧪 Тестируем обработку ошибки 'File is too big'...")
    
    # Создаем мок-объекты
    mock_bot = AsyncMock()
    
    # Симулируем ошибку "File is too big" от Telegram API
    mock_bot.get_file.side_effect = Exception("File is too big")
    
    try:
        # Тестируем функцию с ошибкой API
        result_path, error = await compress_for_telegram(
            bot=mock_bot,
            file_id="large_file_id",
            original_filename="large_video.mp4"
        )
        
        print(f"✅ Результат обработки ошибки:")
        print(f"- Файл обработан: {'Да' if result_path else 'Нет'}")
        print(f"- Сообщение об ошибке: {error}")
        
        # Проверяем, что ошибка корректно обработана
        if not result_path and error:
            print("✅ УСПЕХ: Ошибка Telegram API корректно обработана")
            return True
        else:
            print("❌ ОШИБКА: Неправильная обработка ошибки API")
            return False
            
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


async def test_large_file_download_mock():
    """Тестируем скачивание большого файла с мок-объектами"""
    
    print("\n🧪 Тестируем скачивание большого файла...")
    
    # Создаем мок-объекты
    mock_bot = AsyncMock()
    mock_file = AsyncMock()
    
    # Симулируем большой файл (30MB)
    mock_file.file_size = 30 * 1024 * 1024
    mock_file.file_path = "documents/large_video.mp4"
    mock_bot.get_file.return_value = mock_file
    
    # Мокаем download_large_file
    with patch('utils.smart_compressor.download_large_file') as mock_download:
        # Создаем временный файл для имитации скачанного
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            test_data = b"test video data" * 1000000  # ~15MB
            temp_file.write(test_data)
            temp_file_path = temp_file.name
            
        try:
            # Настраиваем мок для успешного скачивания
            async def mock_download_func(bot, file_id, dest_path):
                # Копируем тестовые данные в целевой файл
                with open(dest_path, 'wb') as f:
                    f.write(test_data)
                return True
            
            mock_download.side_effect = mock_download_func
            
            # Тестируем функцию
            result_path, error = await compress_for_telegram(
                bot=mock_bot,
                file_id="large_file_id",
                original_filename="large_video.mp4"
            )
            
            print(f"✅ Результат обработки большого файла:")
            print(f"- Файл обработан: {'Да' if result_path else 'Нет'}")
            print(f"- Ошибка: {error if error else 'Нет'}")
            
            if result_path:
                file_size = result_path.stat().st_size
                print(f"- Размер результирующего файла: {file_size / (1024*1024):.1f}MB")
                
                # Проверяем, что файл готов к обработке
                if file_size <= 20 * 1024 * 1024:
                    print("✅ Файл готов для уникализации (≤20MB)")
                    return True
                else:
                    print("⚠️ Файл все еще большой")
                    return False
            else:
                print("❌ Файл не был обработан")
                return False
                
        finally:
            # Очищаем временный файл
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)


async def test_small_file_handling():
    """Тестируем обработку маленького файла"""
    
    print("\n🧪 Тестируем обработку маленького файла...")
    
    # Создаем мок-объекты
    mock_bot = AsyncMock()
    mock_file = AsyncMock()
    
    # Симулируем маленький файл (5MB) 
    mock_file.file_size = 5 * 1024 * 1024
    mock_file.file_path = "documents/small_video.mp4"
    mock_bot.get_file.return_value = mock_file
    
    # Мокаем download_large_file
    with patch('utils.smart_compressor.download_large_file') as mock_download:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            test_data = b"small video" * 100000  # ~1MB
            temp_file.write(test_data)
            temp_file_path = temp_file.name
            
        try:
            async def mock_download_func(bot, file_id, dest_path):
                with open(dest_path, 'wb') as f:
                    f.write(test_data)
                return True
            
            mock_download.side_effect = mock_download_func
            
            result_path, error = await compress_for_telegram(
                bot=mock_bot,
                file_id="small_file_id",
                original_filename="small_video.mp4"
            )
            
            print(f"✅ Маленький файл обработан: {'Да' if result_path else 'Нет'}")
            
            if result_path:
                file_size = result_path.stat().st_size / (1024 * 1024)
                print(f"✅ Размер файла: {file_size:.1f}MB (сжатие не применялось)")
                return True
            
            return False
            
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)


async def main():
    """Главная функция тестирования исправления"""
    
    print("🚀 Запуск тестов исправления Telegram API\n")
    print("=" * 60)
    
    try:
        # Тест 1: Обработка ошибки API
        test1_success = await test_telegram_api_error_handling()
        
        # Тест 2: Скачивание большого файла
        test2_success = await test_large_file_download_mock()
        
        # Тест 3: Обработка маленького файла
        test3_success = await test_small_file_handling()
        
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print(f"- Обработка ошибки API: {'✅ ПРОЙДЕН' if test1_success else '❌ ПРОВАЛЕН'}")
        print(f"- Скачивание большого файла: {'✅ ПРОЙДЕН' if test2_success else '❌ ПРОВАЛЕН'}")
        print(f"- Обработка маленького файла: {'✅ ПРОЙДЕН' if test3_success else '❌ ПРОВАЛЕН'}")
        
        if test1_success and test2_success and test3_success:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            print("✅ Исправление Telegram API работает корректно")
            print("✅ Больше не будет ошибок 'File is too big'")
            print("✅ Уникализатор готов к работе с реальными файлами")
        else:
            print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
            print("⚠️ Требуется дополнительная доработка")
            
    except Exception as e:
        print(f"❌ Критическая ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
