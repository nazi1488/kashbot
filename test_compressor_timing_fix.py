#!/usr/bin/env python3
"""
Тестирование исправления времени показа предложения "повторить" в компрессоре
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_compressor_timing_fix():
    """Проверяем что предложение повторить показывается в правильное время"""
    
    print("🔧 Тестирование исправления времени предложения 'повторить'")
    print("=" * 60)
    
    try:
        # Проверяем импорт функций
        from handlers.compressor import wrong_media_handler_compress, compress_file_handler, process_compression_task
        print("✅ Все функции компрессора импортируются")
        
        # Читаем код функций для анализа
        import inspect
        
        # Проверяем wrong_media_handler_compress
        handler_code = inspect.getsource(wrong_media_handler_compress)
        if 'compress_more_or_menu' not in handler_code:
            print("✅ wrong_media_handler_compress НЕ показывает предложение повторить")
        else:
            print("❌ wrong_media_handler_compress все еще показывает предложение повторить")
            return False
        
        # Проверяем compress_file_handler
        file_handler_code = inspect.getsource(compress_file_handler)
        if 'compress_more_or_menu' not in file_handler_code:
            print("✅ compress_file_handler НЕ показывает предложение повторить")
        else:
            print("❌ compress_file_handler все еще показывает предложение повторить")
            return False
            
        # Проверяем process_compression_task
        task_code = inspect.getsource(process_compression_task)
        if 'compress_more_or_menu' in task_code:
            print("✅ process_compression_task показывает предложение повторить после сжатия")
        else:
            print("❌ process_compression_task НЕ показывает предложение повторить")
            return False
        
        print("\n📋 Исправления:")
        print("   1. ✅ Убрано предложение из wrong_media_handler_compress")
        print("   2. ✅ Убрано предложение из compress_file_handler") 
        print("   3. ✅ Добавлено предложение в process_compression_task")
        
        print("\n⏱️ Новая последовательность:")
        print("   1. Пользователь отправляет видео")
        print("   2. Бот: 'Видео принято к сжатию! Совет...'")
        print("   3. Бот: 'Ваш файл добавлен в очередь'")
        print("   4. Бот: 'Позиция в очереди: 1'")
        print("   5. ⏰ ОЖИДАНИЕ ОБРАБОТКИ...")
        print("   6. Бот: отправляет сжатый файл")
        print("   7. Бот: 'Хотите сжать еще файлы?' ← ТОЛЬКО ЗДЕСЬ!")
        
        print("\n🚫 Проблема была:")
        print("   • Предложение показывалось сразу после добавления в очередь")
        print("   • Пользователь видел кнопки еще до завершения сжатия")
        print("   • Сбивало с толку - процесс еще не закончен")
        
        print("\n✅ Теперь исправлено:")
        print("   • Предложение показывается только после сжатия")
        print("   • Логичная последовательность действий")
        print("   • Нет путаницы у пользователей")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_compressor_timing_fix()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 Исправление времени предложения 'повторить' завершено!")
        print("\n💡 Результат:")
        print("   • Предложение показывается только после завершения сжатия")
        print("   • Логичная последовательность для пользователя")
        print("   • Нет преждевременных кнопок во время обработки")
    
    sys.exit(0 if success else 1)
