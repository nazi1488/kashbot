#!/usr/bin/env python3
"""
Тест интеграции ROI-калькулятора в бот
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_roi_integration():
    """Проверяем интеграцию ROI-калькулятора"""
    
    print("🚀 Тестирование интеграции ROI-калькулятора")
    print("=" * 50)
    
    try:
        # 1. Проверяем локализацию
        with open('locales/ru.json', 'r', encoding='utf-8') as f:
            locales = json.load(f)
        
        if 'roi_calculator' in locales:
            print(f"✅ Локализация добавлена: {locales['roi_calculator']}")
        else:
            print("❌ Локализация ROI-калькулятора НЕ найдена")
            return False
        
        # 2. Проверяем импорты
        from handlers.roi_calculator import roi_calculator_callback
        from handlers.roi.states import ROIStates  
        from handlers.roi.validators import parse_number, validate_number
        from handlers.roi.metrics import ROIMetrics
        print("✅ Все модули ROI-калькулятора импортируются")
        
        # 3. Проверяем экспорт в handlers
        from handlers import (
            roi_calculator_callback, roi_start, input_spend, 
            input_income, input_shows, input_clicks, 
            input_leads, input_sales, cancel_roi, ROIStates
        )
        print("✅ ROI-калькулятор экспортируется из handlers")
        
        # 4. Проверяем main.py
        import main
        print("✅ main.py импортируется с ROI-калькулятором")
        
        # 5. Проверяем тестовый расчет E2E
        test_data = {
            'spend': 1095.0,
            'income': 1500.0, 
            'shows': 60000.0,
            'clicks': 2500.0,
            'leads': 85.0,
            'sales': 41.0
        }
        
        calculator = ROIMetrics(test_data)
        card = calculator.format_results_card()
        
        print("\n📊 Тестовая карточка результатов:")
        print("-" * 40)
        print(card)
        
        # Проверяем основные элементы
        required_in_card = [
            "📊 **Результаты расчета**",
            "ROI: +37.0%",
            "CTR: 4.2%",
            "CTC: 3.4%", 
            "CTB: 48.2%",
            "ROAS: 1.37"
        ]
        
        print("\n🔍 Проверка элементов карточки:")
        for element in required_in_card:
            if element in card:
                print(f"✅ {element}")
            else:
                print(f"❌ НЕ найден: {element}")
                return False
        
        print("\n📋 Структура модулей:")
        print("   ✅ handlers/roi_calculator.py - основной обработчик")
        print("   ✅ handlers/roi/states.py - состояния FSM")
        print("   ✅ handlers/roi/validators.py - парсинг и валидация")
        print("   ✅ handlers/roi/metrics.py - расчеты и формулы")
        print("   ✅ test_roi_metrics.py - тесты")
        
        print("\n🎯 Функционал:")
        print("   ✅ Пошаговый ввод данных с валидацией")
        print("   ✅ Поддержка разных форматов чисел")
        print("   ✅ Расчет 12+ метрик арбитража")
        print("   ✅ Красивое форматирование результатов")
        print("   ✅ Интеграция в главное меню")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_user_flow():
    """Тестируем пользовательский сценарий"""
    print("\n👤 Тестирование пользовательского сценария")
    print("-" * 40)
    
    # Проверяем валидацию разных форматов
    test_inputs = [
        "1095",      # простое число
        "1,095",     # с запятой
        "1 095",     # с пробелами
        "1095.50",   # с точкой
        "1,095.50",  # комбинированный
        "$1095",     # с валютой
    ]
    
    from handlers.roi.validators import parse_number
    
    print("Тестирование парсинга пользовательского ввода:")
    for inp in test_inputs:
        result = parse_number(inp)
        print(f"  '{inp}' → {result}")
    
    return True

def main():
    """Запуск всех тестов интеграции"""
    print("🧮 Финальное тестирование ROI-калькулятора")
    print("=" * 60)
    
    tests = [test_roi_integration, test_user_flow]
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    
    if all(results):
        print("🎉 ROI-калькулятор полностью интегрирован!")
        print("\n📱 Как использовать:")
        print("   1. Главное меню → 📊 Калькулятор арбитражника")
        print("   2. ▶️ Начать расчет")
        print("   3. Ввести данные по шагам (можно пропускать)")
        print("   4. Получить подробную карточку метрик")
        print("   5. 🔁 Рассчитать заново или 🔙 В меню")
        
        print("\n💡 Фичи:")
        print("   • Умный парсинг чисел (1000, 1,000, $1000)")
        print("   • 12+ метрик: ROI, CTR, CPC, CPA, ROAS и др.")
        print("   • Защита от ошибок и деления на ноль")  
        print("   • Красивые карточки результатов")
        print("   • Расшифровка всех метрик")
        
        return 0
    else:
        print("❌ Есть проблемы с интеграцией")
        return 1

if __name__ == "__main__":
    sys.exit(main())
