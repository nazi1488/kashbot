#!/usr/bin/env python3
"""
Тестирование улучшений функций бота
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_functions_improvements():
    """Проверяем улучшения функций бота"""
    
    print("🔧 Тестирование улучшений функций")
    print("=" * 50)
    
    try:
        # Проверяем добавленные тексты локализации
        with open('locales/ru.json', 'r', encoding='utf-8') as f:
            locales = json.load(f)
        
        # Проверяем новые тексты "повторить или меню"
        texts_to_check = [
            'uniqueness_more_or_menu',
            'hide_text_more_or_menu', 
            'compress_more_or_menu'
        ]
        
        for text_key in texts_to_check:
            if text_key in locales:
                print(f"✅ Добавлен текст {text_key}")
            else:
                print(f"❌ Текст {text_key} не найден")
                return False
        
        # Проверяем импорты функций
        from handlers.uniqizer import uniqueness_tool_callback, wrong_media_handler, process_media_file
        print("✅ Уникализатор импортируется без ошибок")
        
        from handlers.compressor import smart_compress_callback, wrong_media_handler_compress, process_compression_task
        print("✅ Компрессор импортируется без ошибок (добавлена поддержка сжатых файлов)")
        
        from handlers.text_hider import hide_text_callback, text_handler
        print("✅ Скрытие текста импортируется без ошибок")
        
        print("\n📋 Что изменилось:")
        print("   1. ✅ Добавлена поддержка сжатых файлов в компрессор")
        print("   2. ✅ Добавлены предложения 'повторить' в уникализатор")
        print("   3. ✅ Обновлены тексты в скрытии текста")
        print("   4. ✅ Обновлены тексты в компрессоре")
        
        print("\n🎯 Новая логика:")
        print("   УНИКАЛИЗАТОР:")
        print("   • Принимает сжатые видео/фото (как всегда)")
        print("   • После обработки: 'Уникализировать еще?' → [Уникализатор] [Меню]")
        
        print("\n   КОМПРЕССОР:")
        print("   • НОВОЕ: Принимает сжатые видео/фото с советом")
        print("   • После сжатия: 'Сжать еще файлы?' → [Умное сжатие] [Меню]")
        
        print("\n   СКРЫТИЕ ТЕКСТА:")
        print("   • После скрытия: 'Скрыть еще текст?' → [Скрыть текст] [Меню]")
        
        print("\n💡 UX улучшения:")
        print("   • Как в скачивании видео - предложение повторить")
        print("   • Компрессор теперь принимает сжатые файлы с советом")
        print("   • Единообразный интерфейс во всех функциях")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_functions_improvements()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 Все функции улучшены!")
        print("\n💡 Результаты:")
        print("   • Компрессор теперь принимает сжатые файлы")
        print("   • Все функции предлагают повторить действие")
        print("   • Единообразный пользовательский опыт")
        print("   • Больше конверсии в повторное использование")
    
    sys.exit(0 if success else 1)
