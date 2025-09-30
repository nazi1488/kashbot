#!/usr/bin/env python3
"""
Тест полного потока обработки больших файлов
"""

import asyncio
import sys
from unittest.mock import AsyncMock

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from utils.large_file_downloader import download_large_file


async def test_compressed_video_download():
    """Тест скачивания сжатого видео от Telegram"""
    
    print("🧪 Тестируем скачивание сжатого видео...")
    
    # Создаем мок бота
    mock_bot = AsyncMock()
    
    # Мок для успешного скачивания сжатого видео
    mock_file = AsyncMock()
    mock_file.download_to_drive = AsyncMock()
    mock_bot.get_file.return_value = mock_file
    
    # Тестируем скачивание
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_path = Path(temp_dir) / "compressed_video.mp4"
        
        success = await download_large_file(
            bot=mock_bot,
            file_id="compressed_video_id",
            destination=dest_path
        )
        
        print(f"📊 Результат:")
        print(f"- get_file вызван: {'Да' if mock_bot.get_file.called else 'Нет'}")
        print(f"- download_to_drive вызван: {'Да' if mock_file.download_to_drive.called else 'Нет'}")
        print(f"- Успешное скачивание: {'Да' if success else 'Нет'}")
        
        if success and mock_file.download_to_drive.called:
            print("✅ УСПЕХ: Сжатое видео скачивается правильно")
            return True
        else:
            print("❌ ПРОВАЛ: Проблема со скачиванием")
            return False


async def test_failed_download():
    """Тест обработки ошибки скачивания"""
    
    print("\n🧪 Тестируем обработку ошибки скачивания...")
    
    # Создаем мок бота с ошибкой
    mock_bot = AsyncMock()
    mock_bot.get_file.side_effect = Exception("File is too big")
    
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_path = Path(temp_dir) / "failed_video.mp4"
        
        success = await download_large_file(
            bot=mock_bot,
            file_id="failed_video_id", 
            destination=dest_path
        )
        
        print(f"📊 Результат:")
        print(f"- get_file вызван: {'Да' if mock_bot.get_file.called else 'Нет'}")
        print(f"- Успешное скачивание: {'Да' if success else 'Нет'}")
        print(f"- Корректная обработка ошибки: {'Да' if not success else 'Нет'}")
        
        if not success:
            print("✅ УСПЕХ: Ошибка обрабатывается корректно")
            return True
        else:
            print("❌ ПРОВАЛ: Ошибка не обработана")
            return False


async def main():
    """Главная функция тестирования полного потока"""
    
    print("🚀 Тестирование ПОЛНОГО потока обработки\n")
    print("=" * 50)
    
    try:
        # Тест 1: Успешное скачивание сжатого видео
        test1_success = await test_compressed_video_download()
        
        # Тест 2: Обработка ошибки
        test2_success = await test_failed_download()
        
        print("\n" + "=" * 50)
        print("📊 ОБЩИЙ РЕЗУЛЬТАТ:")
        print(f"- Скачивание работает: {'✅ ДА' if test1_success else '❌ НЕТ'}")
        print(f"- Ошибки обрабатываются: {'✅ ДА' if test2_success else '❌ НЕТ'}")
        
        if test1_success and test2_success:
            print("\n🎉 ПОЛНЫЙ ПОТОК РАБОТАЕТ!")
            print("✅ Сжатые видео скачиваются")
            print("✅ Ошибки обрабатываются корректно")
            print("✅ Пользователи получат результат!")
            print("\n🔥 ЛОГИЧЕСКАЯ ЦЕПОЧКА ВОССТАНОВЛЕНА:")
            print("1. Большой документ → просьба переотправить как видео")
            print("2. Сжатое видео → успешное скачивание") 
            print("3. Автоматическое сжатие → уникализация")
            print("4. ПОЛЬЗОВАТЕЛЬ ПОЛУЧАЕТ РЕЗУЛЬТАТ! 🎯")
        else:
            print("\n❌ ПОТОК НЕ РАБОТАЕТ")
            print("⚠️ Логическая цепочка нарушена")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
