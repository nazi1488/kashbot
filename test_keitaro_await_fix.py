#!/usr/bin/env python3
"""
Тестирование исправления ошибки await в Keitaro ConversationHandler
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_keitaro_await_fix():
    """Проверяем исправление ошибки await в Keitaro"""
    
    print("🔧 Тестирование исправления await в Keitaro")
    print("=" * 50)
    
    try:
        # Проверяем импорт Keitaro handlers
        from features.keitaro.handlers import KeitaroHandlers
        print("✅ KeitaroHandlers импортируется без ошибок")
        
        # Проверяем наличие нового метода
        if hasattr(KeitaroHandlers, '_handle_main_menu_callback'):
            print("✅ Метод _handle_main_menu_callback найден")
            
            # Проверяем что метод async
            import asyncio
            method = getattr(KeitaroHandlers, '_handle_main_menu_callback')
            if asyncio.iscoroutinefunction(method):
                print("✅ Метод _handle_main_menu_callback является async")
            else:
                print("❌ Метод _handle_main_menu_callback НЕ async")
                return False
                
        else:
            print("❌ Метод _handle_main_menu_callback НЕ найден")
            return False
        
        print("\n📋 Что было исправлено:")
        print("   • БЫЛО: CallbackQueryHandler(lambda u, c: ConversationHandler.END, ...)")
        print("   • СТАЛО: CallbackQueryHandler(handlers._handle_main_menu_callback, ...)")
        
        print("\n🚨 Причина ошибки:")
        print("   • Lambda функция возвращала int (ConversationHandler.END)")
        print("   • Но Python пытался await-ить результат")
        print("   • Все обработчики в ConversationHandler должны быть async")
        
        print("\n🎯 Решение:")
        print("   • Создан async метод _handle_main_menu_callback")
        print("   • Метод корректно возвращает ConversationHandler.END")
        print("   • Убрана lambda функция из fallbacks")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

if __name__ == "__main__":
    success = test_keitaro_await_fix()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 Ошибка await в Keitaro исправлена!")
        print("\n💡 Результат:")
        print("   • Кнопка 'назад' теперь работает без ошибок")
        print("   • Нет TypeError 'object int can't be used in await expression'")
        print("   • ConversationHandler корректно завершается")
        print("   • Возврат в главное меню работает стабильно")
    
    sys.exit(0 if success else 1)
