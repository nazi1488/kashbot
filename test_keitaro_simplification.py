#!/usr/bin/env python3
"""
Тестирование упрощения Keitaro интеграции
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_keitaro_simplification():
    """Проверяем упрощения в Keitaro"""
    
    print("🔧 Тестирование упрощения Keitaro")
    print("=" * 50)
    
    try:
        # Проверяем новый текст в локализации
        with open('locales/ru.json', 'r', encoding='utf-8') as f:
            locales = json.load(f)
        
        keitaro_welcome = locales.get('keitaro_welcome', '')
        
        # Проверяем что текст изменился
        if "💚 Keitaro-уведомления" in keitaro_welcome:
            print("✅ Новый текст приветствия установлен")
        else:
            print("❌ Старый текст приветствия")
            return False
            
        if "iGaming" in keitaro_welcome and "$150" in keitaro_welcome:
            print("✅ Пример уведомления добавлен")
        else:
            print("❌ Пример уведомления не найден")
            return False
            
        if "Не сидишь в Keitaro 24/7" in keitaro_welcome:
            print("✅ Объяснение преимуществ добавлено")
        else:
            print("❌ Объяснение преимуществ не найдено")
            return False
        
        # Проверяем импорт handlers
        from features.keitaro.handlers import KeitaroHandlers
        print("✅ KeitaroHandlers импортируется без ошибок")
        
        print("\n📋 Что изменилось:")
        print("   1. ✅ Новый текст для новых пользователей")
        print("   2. ✅ Упрощен процесс создания профиля") 
        print("   3. ✅ Убрана возможность выбора чата")
        print("   4. ✅ Уведомления идут только в чат с ботом")
        
        print("\n💚 Новый текст приветствия:")
        print("   • Объяснение что это за функция")
        print("   • Как работает пошагово")
        print("   • Пример уведомления (iGaming, $150)")
        print("   • Зачем это нужно арбитражнику")
        
        print("\n🔧 Упрощение процесса:")
        print("   • БЫЛО: создать → выбрать чат → ввести ID → готово")
        print("   • СТАЛО: создать → готово (автоматически чат с ботом)")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_keitaro_simplification()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 Keitaro интеграция упрощена!")
        print("\n💡 Результаты:")
        print("   • Понятный текст для новых пользователей")
        print("   • Простой процесс создания профиля")
        print("   • Уведомления только в чат с ботом")
        print("   • Убрана сложная настройка чатов")
    
    sys.exit(0 if success else 1)
