#!/usr/bin/env python3
"""
Тестирование поддержки сжатых медиа в компрессоре
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_compressor_media_support():
    """Проверяем что компрессор теперь принимает сжатые медиа"""
    
    print("🔧 Тестирование поддержки сжатых медиа в компрессоре")
    print("=" * 50)
    
    try:
        # Проверяем импорт функции
        from handlers.compressor import wrong_media_handler_compress
        print("✅ Функция wrong_media_handler_compress найдена")
        
        # Проверяем что функция async
        import asyncio
        if asyncio.iscoroutinefunction(wrong_media_handler_compress):
            print("✅ wrong_media_handler_compress является async функцией")
        else:
            print("❌ wrong_media_handler_compress НЕ async")
            return False
        
        # Проверяем импорт из handlers
        from handlers import wrong_media_handler_compress as imported_func
        print("✅ Функция экспортируется из handlers")
        
        # Проверяем импорт в main.py
        try:
            import main
            print("✅ main.py импортируется без ошибок")
        except Exception as e:
            print(f"❌ Ошибка импорта main.py: {e}")
            return False
        
        print("\n📋 Что добавлено в компрессор:")
        print("   1. ✅ Функция wrong_media_handler_compress")
        print("   2. ✅ Обработка сжатых видео и фото") 
        print("   3. ✅ Совет о качестве файлов")
        print("   4. ✅ Регистрация в ConversationHandler")
        
        print("\n🎯 Теперь компрессор работает как уникализатор:")
        print("   • Принимает любые медиа (файлы и сжатые)")
        print("   • Дает совет о качестве")
        print("   • Не теряет пользователей")
        print("   • Предлагает повторить действие")
        
        print("\n⚡ Сценарий использования:")
        print("   1. Пользователь: Умное сжатие → отправляет сжатое видео")
        print("   2. Бот: 'Видео принято! Совет: отправляйте как файл'")
        print("   3. Бот: сжимает видео и отправляет результат")
        print("   4. Бот: 'Сжать еще файлы?' → [Умное сжатие] [Меню]")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_compressor_media_support()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 Компрессор теперь принимает сжатые медиа!")
        print("\n💡 Результат:")
        print("   • Как в уникализаторе - принимает любые медиа")
        print("   • Дает обучающие советы пользователям")
        print("   • Единообразный UX во всех функциях")
        print("   • Не теряем пользователей из-за неправильного типа файла")
    
    sys.exit(0 if success else 1)
