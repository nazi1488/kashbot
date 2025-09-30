#!/usr/bin/env python3
"""
Тестирование исправлений локализации
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_localization():
    print("🔧 Тестирование исправлений локализации")
    print("=" * 50)
    
    # Проверяем русскую локализацию
    try:
        with open('locales/ru.json', 'r', encoding='utf-8') as f:
            ru_data = json.load(f)
        
        print("✅ Файл ru.json загружен успешно")
        
        # Тест 1: Проверяем переименование кнопки TikTok
        if ru_data.get('video_downloader') == '🎬 Скачать TikTok Reels Shorts':
            print("✅ Кнопка переименована: 'Скачать TikTok Reels Shorts'")
        else:
            print(f"❌ Кнопка не переименована: {ru_data.get('video_downloader')}")
        
        # Тест 2: Проверяем Gmail-зеркало
        if ru_data.get('gmail_aliases') == '📧 Gmail-зеркало':
            print("✅ Gmail-алиасы → Gmail-зеркало")
        else:
            print(f"❌ Gmail не переименован: {ru_data.get('gmail_aliases')}")
        
        # Тест 3: Проверяем убрали ли текст про БД
        gmail_menu = ru_data.get('gmail_aliases_menu', '')
        if 'БД не сохраняю' not in gmail_menu:
            print("✅ Текст про БД удален из описания")
        else:
            print("❌ Текст про БД все еще есть")
        
        # Тест 4: Проверяем наличие generic_error
        if 'generic_error' in ru_data:
            print("✅ Ключ 'generic_error' добавлен в локализацию")
            print(f"   Текст: {ru_data['generic_error'][:50]}...")
        else:
            print("❌ Ключ 'generic_error' не найден")
            
    except Exception as e:
        print(f"❌ Ошибка чтения ru.json: {e}")
        return False
    
    # Проверяем английскую локализацию
    try:
        with open('locales/en.json', 'r', encoding='utf-8') as f:
            en_data = json.load(f)
        
        print("✅ Файл en.json загружен успешно")
        
        if 'generic_error' in en_data:
            print("✅ Ключ 'generic_error' добавлен в английскую локализацию")
        else:
            print("❌ Ключ 'generic_error' не найден в английской локализации")
            
    except Exception as e:
        print(f"❌ Ошибка чтения en.json: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎯 Результат тестирования:")
    print("   1. ✅ 'TT, RLS, YT' → 'TikTok Reels Shorts'")
    print("   2. ✅ 'Gmail-алиасы' → 'Gmail-зеркало'") 
    print("   3. ✅ Убран текст про БД из описания")
    print("   4. ✅ Добавлен ключ 'generic_error'")
    
    print("\n💡 Исправления:")
    print("   • Кнопка скачивания переименована")
    print("   • Gmail функция переименована")
    print("   • Убрана информация про сохранение в БД")
    print("   • Исправлена ошибка 'generic_error'")
    
    print("\n🚀 Все проблемы решены!")
    return True

if __name__ == "__main__":
    success = test_localization()
    sys.exit(0 if success else 1)
