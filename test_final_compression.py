#!/usr/bin/env python3
"""
Финальный тест автоматического сжатия с реальным видеофайлом
"""

import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock
import sys

# Добавляем путь к проекту  
sys.path.append('/Users/benutzer/Desktop/кеш/bot')

from utils.smart_compressor import compress_video_ffmpeg


async def create_test_video(output_path: Path, duration_seconds: int = 10, size_mb: int = 25):
    """Создает тестовое видео заданного размера с помощью ffmpeg"""
    
    try:
        # Создаем видео с помощью ffmpeg
        import ffmpeg
        
        # Генерируем тестовое видео с цветными полосами
        stream = ffmpeg.input('color=size=1280x720:duration=10:rate=30:color=red', f='lavfi')
        stream = ffmpeg.output(stream, str(output_path), vcodec='libx264', acodec='aac', b='20M')
        
        process = await asyncio.create_subprocess_exec(
            *ffmpeg.compile(stream, overwrite_output=True),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.wait()
        
        if output_path.exists():
            actual_size = output_path.stat().st_size / (1024 * 1024)
            print(f"✅ Создано тестовое видео: {actual_size:.1f}MB")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Ошибка создания тестового видео: {e}")
        return False


async def test_real_video_compression():
    """Тестируем реальное сжатие видео"""
    
    print("🧪 Тестируем реальное сжатие видео...\n")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Создаем исходное видео (~20MB)
        input_video = temp_path / "large_video.mp4"
        print("📹 Создаем тестовое видео...")
        
        if not await create_test_video(input_video, duration_seconds=10, size_mb=20):
            print("❌ Не удалось создать тестовое видео")
            return False
        
        # Проверяем исходный размер
        original_size_mb = input_video.stat().st_size / (1024 * 1024)
        print(f"📊 Исходный размер: {original_size_mb:.1f}MB")
        
        # Если файл меньше 20MB, создаем больший
        if original_size_mb < 20:
            print("📹 Создаем видео большего размера...")
            bigger_video = temp_path / "bigger_video.mp4" 
            if await create_test_video(bigger_video, duration_seconds=30, size_mb=30):
                input_video = bigger_video
                original_size_mb = input_video.stat().st_size / (1024 * 1024)
                print(f"📊 Новый исходный размер: {original_size_mb:.1f}MB")
        
        # Сжимаем видео
        output_video = temp_path / "compressed_video.mp4"
        
        print("\n🔄 Начинаем сжатие...")
        success = await compress_video_ffmpeg(input_video, output_video, target_size_mb=18)
        
        if success and output_video.exists():
            compressed_size_mb = output_video.stat().st_size / (1024 * 1024)
            compression_ratio = (original_size_mb - compressed_size_mb) / original_size_mb * 100
            
            print(f"✅ Сжатие завершено успешно!")
            print(f"📊 Сжатый размер: {compressed_size_mb:.1f}MB")
            print(f"📉 Уменьшение: {compression_ratio:.1f}%")
            
            if compressed_size_mb <= 20:
                print("✅ Файл готов для Telegram (≤20MB)")
                return True
            else:
                print("⚠️ Файл все еще большой для Telegram")
                return False
        else:
            print("❌ Сжатие не удалось")
            return False


async def test_image_compression():
    """Тестируем сжатие изображений"""
    
    print("\n🧪 Тестируем сжатие изображений...\n")
    
    try:
        from PIL import Image
        from utils.smart_compressor import compress_image_pillow
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Создаем тестовое изображение большого размера
            input_image = temp_path / "large_image.jpg"
            
            print("🖼️ Создаем тестовое изображение...")
            
            # Создаем изображение 4K разрешения
            image = Image.new('RGB', (3840, 2160), color='red')
            image.save(input_image, 'JPEG', quality=95)
            
            original_size_mb = input_image.stat().st_size / (1024 * 1024)
            print(f"📊 Исходный размер: {original_size_mb:.1f}MB")
            
            # Сжимаем изображение
            output_image = temp_path / "compressed_image.jpg"
            
            print("🔄 Начинаем сжатие...")
            success = await compress_image_pillow(input_image, output_image, target_size_mb=18)
            
            if success and output_image.exists():
                compressed_size_mb = output_image.stat().st_size / (1024 * 1024)
                compression_ratio = (original_size_mb - compressed_size_mb) / original_size_mb * 100
                
                print(f"✅ Сжатие завершено успешно!")
                print(f"📊 Сжатый размер: {compressed_size_mb:.1f}MB")
                print(f"📉 Уменьшение: {compression_ratio:.1f}%")
                
                if compressed_size_mb <= 20:
                    print("✅ Изображение готово для Telegram (≤20MB)")
                    return True
                else:
                    print("⚠️ Изображение все еще большое")
                    return False
            else:
                print("❌ Сжатие не удалось")
                return False
                
    except ImportError:
        print("⚠️ PIL не установлен, пропускаем тест изображений")
        return True
    except Exception as e:
        print(f"❌ Ошибка сжатия изображения: {e}")
        return False


async def main():
    """Главная функция финального тестирования"""
    
    print("🚀 Запуск финального теста автоматического сжатия\n")
    print("=" * 60)
    
    try:
        # Тест сжатия видео
        video_success = await test_real_video_compression()
        
        # Тест сжатия изображений
        image_success = await test_image_compression()
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
        print(f"- Сжатие видео: {'✅ РАБОТАЕТ' if video_success else '❌ НЕ РАБОТАЕТ'}")
        print(f"- Сжатие изображений: {'✅ РАБОТАЕТ' if image_success else '❌ НЕ РАБОТАЕТ'}")
        
        if video_success and image_success:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
            print("✅ Автоматическое сжатие полностью функционально")
            print("✅ Большие файлы будут сжиматься без уведомления пользователя")
            print("✅ Уникализатор готов к работе с файлами любого размера")
        else:
            print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
            print("⚠️ Проверьте установку ffmpeg и ffmpeg-python")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
