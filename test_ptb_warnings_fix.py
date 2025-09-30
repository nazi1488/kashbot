#!/usr/bin/env python3
"""
Проверка исправлений PTB предупреждений
"""

import sys
import ast
from pathlib import Path

def check_conversation_handlers():
    """Проверяем все ConversationHandler на наличие per_message=True"""
    
    print("🔧 Проверка исправлений PTB предупреждений")
    print("=" * 50)
    
    files_to_check = [
        "main.py",
        "features/keitaro/handlers.py"
    ]
    
    issues_found = 0
    
    for file_path in files_to_check:
        print(f"\n📄 Проверяем {file_path}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Простая проверка - ищем ConversationHandler без per_message
            conv_handlers = []
            lines = content.split('\n')
            
            in_conv_handler = False
            conv_start_line = 0
            conv_lines = []
            
            for i, line in enumerate(lines):
                if 'ConversationHandler(' in line:
                    in_conv_handler = True
                    conv_start_line = i + 1
                    conv_lines = [line]
                elif in_conv_handler:
                    conv_lines.append(line)
                    if line.strip().endswith(')') and line.count('(') <= line.count(')'):
                        # Конец ConversationHandler
                        conv_text = '\n'.join(conv_lines)
                        
                        if 'per_message=True' in conv_text:
                            print(f"   ✅ ConversationHandler на строке {conv_start_line}: per_message=True найден")
                        else:
                            print(f"   ❌ ConversationHandler на строке {conv_start_line}: per_message=True НЕ найден")
                            issues_found += 1
                        
                        in_conv_handler = False
                        conv_lines = []
            
        except Exception as e:
            print(f"   ❌ Ошибка чтения файла: {e}")
            issues_found += 1
    
    print(f"\n" + "=" * 50)
    if issues_found == 0:
        print("🎉 Все ConversationHandler исправлены!")
        print("✅ Все предупреждения PTB должны исчезнуть")
        
        print("\n📋 Исправленные ConversationHandler:")
        print("   • main.py - уникализация (per_message=True)")
        print("   • main.py - скрытие текста (per_message=True)")  
        print("   • main.py - умное сжатие (per_message=True)")
        print("   • main.py - скачивание видео (per_message=True)")
        print("   • keitaro/handlers.py - Keitaro интеграция (per_message=True)")
        
        return True
    else:
        print(f"❌ Найдено {issues_found} проблем")
        return False

if __name__ == "__main__":
    success = check_conversation_handlers()
    sys.exit(0 if success else 1)
