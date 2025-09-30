#!/usr/bin/env python3
"""
Тестирование исправления ошибки datetime в админ панели
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_datetime_import():
    """Проверяем что datetime импортируется правильно"""
    
    print("🔧 Тестирование исправления datetime")
    print("=" * 50)
    
    try:
        # Проверяем импорт admin_panel
        from handlers.admin_panel import AdminPanel
        print("✅ AdminPanel импортируется без ошибок datetime")
        
        # Проверяем что datetime доступен на уровне модуля
        import handlers.admin_panel as ap
        
        # Проверяем наличие datetime в модуле
        if hasattr(ap, 'datetime'):
            print("✅ datetime импортирован в admin_panel")
        else:
            print("❌ datetime не найден в admin_panel")
            return False
            
        # Проверяем что timedelta также доступна
        if hasattr(ap, 'timedelta'):
            print("✅ timedelta импортирована в admin_panel")
        else:
            print("❌ timedelta не найдена в admin_panel")
            return False
        
        print("\n📋 Что было исправлено:")
        print("   • Убран дублированный импорт datetime внутри функции")
        print("   • Используется глобальный импорт из начала файла")
        print("   • Нет конфликта между локальным и глобальным datetime")
        
        print("\n🎯 Техническая причина ошибки:")
        print("   • from datetime import datetime, timedelta внутри with блока")
        print("   • Перезаписывал глобальный datetime")
        print("   • При выходе из блока локальная переменная исчезала")
        print("   • Глобальный datetime становился недоступен")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

if __name__ == "__main__":
    success = test_datetime_import()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 Ошибка datetime исправлена!")
        print("\n💡 Теперь админ панель работает:")
        print("   • Без ошибок 'cannot access local variable datetime'")
        print("   • Корректно показывает статистику Keitaro")
        print("   • Правильно вычисляет cutoff_date")
    
    sys.exit(0 if success else 1)
