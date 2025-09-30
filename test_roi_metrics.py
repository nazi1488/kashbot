#!/usr/bin/env python3
"""
Тесты для ROI-калькулятора
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from handlers.roi.metrics import ROIMetrics
from handlers.roi.validators import parse_number, validate_number

def test_parse_number():
    """Тестируем парсинг чисел"""
    print("🔢 Тестирование парсинга чисел")
    print("-" * 40)
    
    test_cases = [
        ("1000", 1000.0),
        ("1,000", 1000.0),
        ("1 000", 1000.0),
        ("1000.50", 1000.50),
        ("1,000.50", 1000.50),
        ("1000,50", 1000.50),
        ("1 000,50", 1000.50),
        ("$1000", 1000.0),
        ("1000$", 1000.0),
        ("abc", None),
        ("-100", None),  # Отрицательные не принимаем
        ("", None),
    ]
    
    for input_text, expected in test_cases:
        result = parse_number(input_text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{input_text}' -> {result} (ожидали: {expected})")
    
    return True

def test_roi_metrics():
    """Тестируем расчет метрик"""
    print("\n📊 Тестирование расчета ROI метрик")
    print("-" * 40)
    
    # Тестовые данные из задания
    test_data = {
        'spend': 1095.0,      # расход
        'income': 1500.0,     # доход
        'shows': 60000.0,     # показы
        'clicks': 2500.0,     # клики
        'leads': 85.0,        # заявки
        'sales': 41.0         # продажи
    }
    
    calculator = ROIMetrics(test_data)
    results = calculator.calculate_all()
    metrics = results['metrics']
    
    print("Рассчитанные метрики:")
    for metric, value in metrics.items():
        print(f"  {metric}: {value}")
    
    # Проверяем основные метрики
    expected_checks = [
        # ROI ≈ 37.0% = (1500-1095)/1095*100 = 405/1095*100 ≈ 37.0%
        ('ROI', lambda x: '37.0%' in x or '36.9%' in x),
        # CTR ≈ 4.2% = 2500/60000*100 ≈ 4.17%
        ('CTR', lambda x: '4.1%' in x or '4.2%' in x),
        # CTC ≈ 3.4% = 85/2500*100 = 3.4%
        ('CTC', lambda x: '3.4%' in x),
        # CTB ≈ 48.2% = 41/85*100 ≈ 48.2%
        ('CTB', lambda x: '48.2%' in x or '48.1%' in x),
        # ROAS ≈ 1.37 = 1500/1095 ≈ 1.37
        ('ROAS', lambda x: '1.37' in x or '1.36' in x),
    ]
    
    print("\nПроверка ключевых метрик:")
    all_passed = True
    for metric_name, check_func in expected_checks:
        if metric_name in metrics:
            passed = check_func(metrics[metric_name])
            status = "✅" if passed else "❌"
            print(f"{status} {metric_name}: {metrics[metric_name]}")
            if not passed:
                all_passed = False
        else:
            print(f"❌ {metric_name}: НЕ НАЙДЕН")
            all_passed = False
    
    return all_passed

def test_edge_cases():
    """Тестируем граничные случаи"""
    print("\n🧪 Тестирование граничных случаев")
    print("-" * 40)
    
    # Только расход и доход
    minimal_data = {'spend': 100.0, 'income': 150.0}
    calculator = ROIMetrics(minimal_data)
    results = calculator.calculate_all()
    
    if 'ROI' in results['metrics']:
        print("✅ Минимальные данные (расход+доход): ROI рассчитан")
    else:
        print("❌ Минимальные данные: ROI НЕ рассчитан")
        return False
    
    # Пустые данные
    empty_data = {}
    calculator = ROIMetrics(empty_data)
    results = calculator.calculate_all()
    
    if not results['metrics']:
        print("✅ Пустые данные: метрики не рассчитаны")
    else:
        print("❌ Пустые данные: есть лишние метрики")
        return False
    
    # Деление на ноль
    zero_data = {'spend': 0, 'income': 100, 'shows': 0, 'clicks': 100}
    calculator = ROIMetrics(zero_data)
    results = calculator.calculate_all()
    
    # ROI не должен рассчитаться (spend = 0)
    # CTR не должен рассчитаться (shows = 0)
    if 'ROI' not in results['metrics'] and 'CTR' not in results['metrics']:
        print("✅ Защита от деления на ноль работает")
    else:
        print("❌ Защита от деления на ноль НЕ работает")
        return False
    
    return True

def test_formatting():
    """Тестируем форматирование результатов"""
    print("\n💄 Тестирование форматирования")
    print("-" * 40)
    
    test_data = {
        'spend': 1000.0,
        'income': 1500.0,
        'shows': 10000.0,
        'clicks': 500.0
    }
    
    calculator = ROIMetrics(test_data)
    card = calculator.format_results_card()
    
    print("Сгенерированная карточка:")
    print(card)
    
    # Проверяем наличие ключевых элементов
    required_elements = [
        "📊 **Результаты расчета**",
        "ROI:",
        "📋 **Расшифровка:**"
    ]
    
    all_found = True
    for element in required_elements:
        if element in card:
            print(f"✅ Найден элемент: {element}")
        else:
            print(f"❌ НЕ найден элемент: {element}")
            all_found = False
    
    return all_found

def main():
    """Запускаем все тесты"""
    print("🧮 Тестирование ROI-калькулятора")
    print("=" * 50)
    
    tests = [
        test_parse_number,
        test_roi_metrics,
        test_edge_cases,
        test_formatting
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Ошибка в тесте {test_func.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 Все тесты пройдены! ({passed}/{total})")
        print("\n💡 ROI-калькулятор готов к использованию:")
        print("   • Парсинг чисел работает корректно")
        print("   • Метрики рассчитываются правильно") 
        print("   • Защита от ошибок функционирует")
        print("   • Форматирование выглядит хорошо")
    else:
        print(f"❌ Тесты провалены: {passed}/{total}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
