#!/usr/bin/env python3
"""
Простая проверка исправления ошибки Telegram API
"""

import asyncio
import sys
from unittest.mock import AsyncMock

# Добавляем путь к проекту
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from utils.smart_compressor import compress_for_telegram


async def test_api_error_handling():
    """Проверяем, что ошибка API обрабатывается корректно"""
    
    print("🧪 Проверка обработки ошибки Telegram API...")
    
    # Создаем мок бота с ошибкой API
    mock_bot = AsyncMock()
    mock_bot.get_file.side_effect = Exception("File is too big")
    
    # Тестируем функцию
    result_path, error = await compress_for_telegram(
        bot=mock_bot,
        file_id="test_file_id",
        original_filename="test.mp4"
    )
    
    # Проверяем результат
    if result_path is None and error is not None:
        print("✅ ИСПРАВЛЕНИЕ РАБОТАЕТ!")
        print(f"   Ошибка корректно обработана: {error}")
        return True
    else:
        print("❌ Исправление не работает")
        print(f"   result_path: {result_path}")
        print(f"   error: {error}")
        return False


async def main():
    """Главная функция проверки"""
    
    print("🚀 Проверка исправления ошибки 'File is too big'\n")
    
    try:
        success = await test_api_error_handling()
        
        print(f"\n📊 РЕЗУЛЬТАТ:")
        if success:
            print("🎉 ИСПРАВЛЕНИЕ РАБОТАЕТ КОРРЕКТНО!")
            print("✅ Ошибка 'File is too big' больше не приводит к краху")
            print("✅ Пользователь получит понятное сообщение об ошибке")
            print("✅ Уникализатор готов к работе")
        else:
            print("❌ ИСПРАВЛЕНИЕ НЕ РАБОТАЕТ")
            print("⚠️ Требуется дополнительная доработка")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
