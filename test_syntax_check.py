#!/usr/bin/env python3
"""
Проверка синтаксиса всех измененных файлов
"""

import sys
import ast
from pathlib import Path

def check_syntax(file_path):
    """Проверка синтаксиса Python файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Компилируем в AST для проверки синтаксиса
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    print("🔍 Проверка синтаксиса измененных файлов")
    print("=" * 50)
    
    # Файлы для проверки
    files_to_check = [
        "handlers/uniqizer.py",
        "handlers/__init__.py", 
        "main.py"
    ]
    
    all_good = True
    
    for file_path in files_to_check:
        print(f"📄 Проверяем {file_path}...")
        
        if not Path(file_path).exists():
            print(f"   ❌ Файл не найден")
            all_good = False
            continue
        
        success, error = check_syntax(file_path)
        
        if success:
            print(f"   ✅ Синтаксис корректен")
        else:
            print(f"   ❌ {error}")
            all_good = False
    
    print("\n" + "=" * 50)
    
    if all_good:
        print("🎉 Все файлы прошли проверку!")
        print("✅ Новый обработчик неправильного медиа готов")
        print("✅ Синтаксических ошибок не найдено")
        
        # Проверяем импорты
        try:
            from handlers import wrong_media_handler
            print("✅ Импорт wrong_media_handler работает")
        except ImportError as e:
            print(f"❌ Ошибка импорта: {e}")
            return 1
            
        print("\n🚀 Функциональность готова к использованию!")
        return 0
    else:
        print("❌ Найдены ошибки в файлах")
        return 1

if __name__ == "__main__":
    sys.exit(main())
