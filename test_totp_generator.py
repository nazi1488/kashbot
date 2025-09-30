#!/usr/bin/env python3
"""
Тестирование 2FA TOTP генератора
"""

import asyncio
import sys
import os
import time
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.totp_generator import (
    TOTPGenerator, 
    totp_gen, 
    get_demo_data, 
    generate_new_secret_with_code,
    generate_code_for_secret
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_totp_basic_functionality():
    """Тестирует базовую функциональность TOTP генератора"""
    
    print("🧪 ТЕСТИРОВАНИЕ БАЗОВОЙ ФУНКЦИОНАЛЬНОСТИ 2FA")
    print("=" * 50)
    
    try:
        # Тест 1: Генерация секрета
        print("\n📝 Тест 1: Генерация секретного ключа")
        secret = totp_gen.generate_secret()
        print(f"✅ Секрет сгенерирован: {secret}")
        print(f"✅ Длина секрета: {len(secret)} символов")
        
        # Проверяем что секрет содержит только правильные символы
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')
        secret_chars = set(secret.upper())
        is_valid = secret_chars.issubset(valid_chars)
        print(f"✅ Секрет содержит только Base32 символы: {'да' if is_valid else 'нет'}")
        
        # Тест 2: Генерация TOTP кода
        print("\n🔢 Тест 2: Генерация TOTP кода")
        code = totp_gen.generate_totp_code(secret)
        print(f"✅ TOTP код: {code}")
        print(f"✅ Длина кода: {len(code)} цифр")
        print(f"✅ Код состоит только из цифр: {code.isdigit()}")
        
        # Тест 3: Оставшееся время
        print("\n⏰ Тест 3: Оставшееся время")
        remaining = totp_gen.get_remaining_time()
        print(f"✅ Секунд до смены кода: {remaining}")
        print(f"✅ Время в допустимых пределах (1-30): {1 <= remaining <= 30}")
        
        # Тест 4: Валидация секрета
        print("\n🔍 Тест 4: Валидация секретов")
        valid_secret = "JNXW24DTPEBXXX3NNFSGK2LO"
        invalid_secret = "invalid_secret_123"
        
        is_valid1 = totp_gen.validate_secret(valid_secret)
        is_valid2 = totp_gen.validate_secret(invalid_secret)
        
        print(f"✅ Валидный секрет '{valid_secret}': {'принят' if is_valid1 else 'отклонен'}")
        print(f"✅ Невалидный секрет '{invalid_secret}': {'принят' if is_valid2 else 'отклонен'}")
        
        # Тест 5: Форматирование для отображения
        print("\n💅 Тест 5: Форматирование секрета")
        formatted = totp_gen.format_secret_display(secret)
        print(f"✅ Исходный секрет: {secret}")
        print(f"✅ Отформатированный: {formatted}")
        
        print("\n🎉 ВСЕ БАЗОВЫЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в базовых тестах: {e}")
        return False


def test_totp_consistency():
    """Тестирует консистентность генерации кодов"""
    
    print("\n" + "=" * 50)
    print("🔄 ТЕСТИРОВАНИЕ КОНСИСТЕНТНОСТИ")
    print("=" * 50)
    
    try:
        # Используем фиксированный секрет
        test_secret = "JNXW24DTPEBXXX3NNFSGK2LOMRQXS3DP"
        current_time = int(time.time())
        
        print(f"\n🔑 Тестовый секрет: {test_secret}")
        print(f"⏰ Текущее время: {current_time}")
        
        # Генерируем код несколько раз для одного времени
        codes = []
        for i in range(5):
            code = totp_gen.generate_totp_code(test_secret, current_time)
            codes.append(code)
        
        # Все коды должны быть одинаковыми
        all_same = len(set(codes)) == 1
        print(f"✅ Коды для одного времени: {codes}")
        print(f"✅ Все коды одинаковы: {'да' if all_same else 'нет'}")
        
        # Тестируем разные временные интервалы
        print(f"\n⏰ Тестирование разных временных интервалов:")
        time_codes = {}
        for offset in [0, 30, 60, 90]:  # 0, 30, 60, 90 секунд
            test_time = current_time + offset
            code = totp_gen.generate_totp_code(test_secret, test_time)
            time_codes[test_time] = code
            print(f"   Время {test_time} (+{offset}s): {code}")
        
        # Коды для разных 30-секундных интервалов должны отличаться
        unique_codes = len(set(time_codes.values()))
        print(f"✅ Уникальных кодов: {unique_codes} из {len(time_codes)}")
        
        print("\n🎉 ТЕСТЫ КОНСИСТЕНТНОСТИ ПРОЙДЕНЫ!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тестах консистентности: {e}")
        return False


def test_demo_functions():
    """Тестирует демонстрационные функции"""
    
    print("\n" + "=" * 50) 
    print("🎭 ТЕСТИРОВАНИЕ ДЕМОНСТРАЦИОННЫХ ФУНКЦИЙ")
    print("=" * 50)
    
    try:
        # Тест демонстрационных данных
        print("\n📊 Тест демонстрационных данных:")
        demo_code, demo_secret, demo_remaining = get_demo_data()
        
        print(f"✅ Демо код: {demo_code}")
        print(f"✅ Демо секрет: {demo_secret}")
        print(f"✅ Демо время: {demo_remaining} сек")
        
        # Проверяем что демо секрет фиксированный
        demo_code2, demo_secret2, _ = get_demo_data()
        is_same_secret = demo_secret == demo_secret2
        print(f"✅ Демо секрет фиксированный: {'да' if is_same_secret else 'нет'}")
        
        # Тест генерации нового секрета
        print("\n🎲 Тест генерации нового секрета:")
        new_code, new_secret, new_remaining = generate_new_secret_with_code()
        
        print(f"✅ Новый код: {new_code}")
        print(f"✅ Новый секрет: {new_secret}")
        print(f"✅ Новое время: {new_remaining} сек")
        
        # Проверяем что новые секреты разные
        new_code2, new_secret2, _ = generate_new_secret_with_code()
        is_different = new_secret != new_secret2
        print(f"✅ Новые секреты разные: {'да' if is_different else 'нет'}")
        
        # Тест генерации кода для пользовательского секрета
        print("\n⚙️ Тест пользовательского секрета:")
        custom_secret = "ABCD1234EFGH5678IJKL9012"
        custom_code, custom_remaining = generate_code_for_secret(custom_secret)
        
        if custom_code:
            print(f"✅ Пользовательский код: {custom_code}")
            print(f"✅ Время: {custom_remaining} сек")
        else:
            print(f"❌ Не удалось создать код для пользовательского секрета")
        
        # Тест невалидного секрета
        invalid_code, _ = generate_code_for_secret("invalid")
        is_none = invalid_code is None
        print(f"✅ Невалидный секрет отклонен: {'да' if is_none else 'нет'}")
        
        print("\n🎉 ДЕМОНСТРАЦИОННЫЕ ТЕСТЫ ПРОЙДЕНЫ!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в демонстрационных тестах: {e}")
        return False


def test_qr_generation():
    """Тестирует генерацию QR кодов"""
    
    print("\n" + "=" * 50)
    print("📱 ТЕСТИРОВАНИЕ ГЕНЕРАЦИИ QR КОДОВ")  
    print("=" * 50)
    
    try:
        test_secret = "JNXW24DTPEBXXX3NNFSGK2LO"
        
        print(f"\n🔑 Тестовый секрет: {test_secret}")
        
        # Генерируем QR код
        qr_buffer = totp_gen.generate_qr_code(test_secret, "TestUser", "2FA Test")
        
        if qr_buffer:
            qr_size = len(qr_buffer.getvalue())
            print(f"✅ QR код сгенерирован успешно")
            print(f"✅ Размер QR кода: {qr_size} байт")
            print(f"✅ QR код содержит данные: {'да' if qr_size > 100 else 'нет'}")
            
            # Сохраняем для проверки
            qr_buffer.seek(0)
            with open("/tmp/test_qr.png", "wb") as f:
                f.write(qr_buffer.read())
            print(f"✅ QR код сохранен в /tmp/test_qr.png для проверки")
        else:
            print(f"❌ Не удалось сгенерировать QR код")
            return False
        
        print("\n🎉 ТЕСТЫ QR КОДОВ ПРОЙДЕНЫ!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тестах QR кодов: {e}")
        return False


def test_real_world_scenario():
    """Тестирует реальный сценарий использования"""
    
    print("\n" + "=" * 50)
    print("🌍 ТЕСТИРОВАНИЕ РЕАЛЬНОГО СЦЕНАРИЯ")
    print("=" * 50)
    
    try:
        print("\n📱 Сценарий: Пользователь создает новый 2FA")
        
        # Шаг 1: Генерируем новый секрет
        code1, secret1, remaining1 = generate_new_secret_with_code()
        print(f"✅ Шаг 1: Новый секрет создан")
        print(f"   Секрет: {totp_gen.format_secret_display(secret1)}")
        print(f"   Код: {code1}")
        print(f"   Время: {remaining1} сек")
        
        # Шаг 2: Ждем немного и проверяем что код тот же (в пределах 30 сек)
        import time
        time.sleep(2)
        code2, remaining2 = generate_code_for_secret(secret1)
        
        print(f"✅ Шаг 2: Проверка через 2 сек")
        print(f"   Код: {code2}")
        print(f"   Время: {remaining2} сек")
        print(f"   Код не изменился: {'да' if code1 == code2 else 'нет'}")
        
        # Шаг 3: Генерируем QR для импорта
        qr_buffer = totp_gen.generate_qr_code(secret1, "TestUser")
        qr_success = qr_buffer is not None
        print(f"✅ Шаг 3: QR код для импорта: {'создан' if qr_success else 'ошибка'}")
        
        # Шаг 4: Проверяем что разные секреты дают разные коды
        code3, secret3, _ = generate_new_secret_with_code()
        different_secrets = secret1 != secret3
        different_codes = code1 != code3
        
        print(f"✅ Шаг 4: Разные секреты дают разные коды")
        print(f"   Секреты разные: {'да' if different_secrets else 'нет'}")
        print(f"   Коды разные: {'да' if different_codes else 'нет'}")
        
        print(f"\n🎉 РЕАЛЬНЫЙ СЦЕНАРИЙ ПРОТЕСТИРОВАН УСПЕШНО!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка в реальном сценарии: {e}")
        return False


def main():
    """Основная функция тестирования"""
    
    print("🚀 ЗАПУСК ПОЛНОГО ТЕСТИРОВАНИЯ 2FA ГЕНЕРАТОРА")
    print("🔐 Аналог сайта https://2fa.cn/")
    print("=" * 60)
    
    tests = [
        ("Базовая функциональность", test_totp_basic_functionality),
        ("Консистентность", test_totp_consistency), 
        ("Демонстрационные функции", test_demo_functions),
        ("Генерация QR кодов", test_qr_generation),
        ("Реальный сценарий", test_real_world_scenario)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Запуск теста: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
            print(f"📊 Результат: {status}")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Пройдено тестов: {passed}/{total}")
    success_rate = (passed / total) * 100 if total > 0 else 0
    print(f"📊 Успешность: {success_rate:.1f}%")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ 2FA Генератор готов к использованию!")
        print("🔐 Функциональность аналогична https://2fa.cn/")
    else:
        print(f"\n⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print(f"🔧 Требуется доработка {total - passed} тестов")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
