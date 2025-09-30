#!/usr/bin/env python3
"""
Тестирование обновленной инструкции Keitaro с объяснением макросов
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_keitaro_macros_explanation():
    """Проверяем обновленную инструкцию с объяснением макросов"""
    
    print("🔧 Тестирование объяснения макросов в инструкции")
    print("=" * 50)
    
    try:
        # Проверяем обновленные тексты в локализации
        with open('locales/ru.json', 'r', encoding='utf-8') as f:
            locales = json.load(f)
        
        # Проверяем упрощенный профиль (без доставки)
        profile_info = locales.get('keitaro_profile_info', '')
        if "Как настроить? → Нажми 'Инструкция'" in profile_info:
            print("✅ Профиль упрощен - убрана информация о доставке")
        else:
            print("❌ Профиль не упрощен")
            return False
            
        if "💬 **Доставка по умолчанию:**" not in profile_info:
            print("✅ Информация о чате и топике убрана")
        else:
            print("❌ Информация о доставке все еще есть")
            return False
        
        # Проверяем инструкцию с объяснением макросов
        howto_text = locales.get('keitaro_howto_text', '')
        
        if "🤔 **Что такое макросы?**" in howto_text:
            print("✅ Добавлено объяснение макросов")
        else:
            print("❌ Объяснение макросов не найдено")
            return False
            
        if "Ты ничего не меняешь!" in howto_text:
            print("✅ Четко объяснено что пользователь не меняет {}")
        else:
            print("❌ Не объяснено про неизменность макросов")
            return False
            
        if "payout={{payout}}" in howto_text and "payout=150" in howto_text:
            print("✅ Добавлен понятный пример работы макросов")
        else:
            print("❌ Пример макросов не найден")
            return False
            
        if "больше деталей в уведомлениях" in howto_text:
            print("✅ Объяснено зачем нужны макросы")
        else:
            print("❌ Не объяснено зачем нужны макросы")
            return False
        
        print("\n📋 Что изменилось:")
        print("   1. ✅ Убрана информация о доставке из профиля")
        print("   2. ✅ Добавлено понятное объяснение макросов")
        print("   3. ✅ Четко сказано что пользователь не меняет {}")
        print("   4. ✅ Добавлен пример работы макросов")
        print("   5. ✅ Объяснено зачем макросы нужны")
        
        print("\n💡 Новое объяснение макросов:")
        print("   • Что это (переменные в {{}})")
        print("   • Что делает Keitaro (автоматически заменяет)")
        print("   • Что делает пользователь (ничего не меняет)")
        print("   • Пример: {{payout}} → 150")
        print("   • Зачем: больше деталей в уведомлениях")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_keitaro_macros_explanation()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 Инструкция Keitaro улучшена!")
        print("\n💡 Результаты:")
        print("   • Убрана сложная информация о доставке")
        print("   • Добавлено понятное объяснение макросов")
        print("   • Пользователи поймут что макросы не нужно менять")
        print("   • Понятно зачем нужны макросы")
    
    sys.exit(0 if success else 1)
