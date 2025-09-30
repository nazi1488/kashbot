"""
Умное сжатие больших файлов для обработки в уникализаторе
"""

import asyncio
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional, Tuple
import config

logger = logging.getLogger(__name__)


async def compress_for_telegram(
    bot,
    file_id: str, 
    original_filename: str,
    progress_callback: Optional[callable] = None
) -> Tuple[Optional[Path], Optional[str]]:
    """
    Скачивает файл, автоматически сжимая большие файлы без уведомлений
    
    Args:
        bot: Telegram Bot instance
        file_id: ID файла для скачивания/сжатия
        original_filename: Оригинальное имя файла
        progress_callback: Функция для уведомления о прогрессе
    
    Returns:
        Tuple[Path, str]: (путь к готовому файлу, сообщение об ошибке)
    """
    try:
        # С self-hosted API можем скачивать файлы до 2GB
        file = await bot.get_file(file_id)
        file_size_mb = file.file_size / (1024 * 1024)
        
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / original_filename
        
        if progress_callback:
            await progress_callback("downloading", file_size_mb)
        
        # Скачиваем файл напрямую
        await file.download_to_drive(temp_path)
        
        logger.info(f"Downloaded file: {temp_path.name} ({file_size_mb:.1f}MB)")
        
        # Возвращаем скачанный файл
        return temp_path, None
        
    except Exception as e:
        logger.error(f"Error in compress_for_telegram: {e}")
        return None, f"Ошибка обработки файла: {str(e)}"


async def compress_video_ffmpeg(
    input_path: Path,
    output_path: Path,
    target_size_mb: int = 18,
    progress_callback: Optional[callable] = None
) -> bool:
    """
    Сжимает видео до указанного размера с помощью FFmpeg
    """
    try:
        if progress_callback:
            await progress_callback("compressing", target_size_mb)
        
        # Получаем информацию о видео
        import ffmpeg
        
        probe = ffmpeg.probe(str(input_path))
        duration = float(probe['streams'][0]['duration'])
        current_size_mb = input_path.stat().st_size / (1024 * 1024)
        
        # Рассчитываем нужный битрейт
        target_bitrate = int((target_size_mb * 8 * 1024) / duration * 0.9)  # 90% от целевого для запаса
        
        # Сжимаем видео
        stream = ffmpeg.input(str(input_path))
        stream = ffmpeg.output(
            stream, 
            str(output_path),
            vcodec='libx264',
            video_bitrate=f'{target_bitrate}k',
            acodec='aac',
            audio_bitrate='128k',
            preset='medium',
            crf=28,  # Более агрессивное сжатие
            maxrate=f'{int(target_bitrate * 1.2)}k',
            bufsize=f'{int(target_bitrate * 2)}k'
        )
        
        # Запускаем сжатие
        process = await asyncio.create_subprocess_exec(
            *ffmpeg.compile(stream, overwrite_output=True),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.wait()
        
        # Проверяем результат
        if output_path.exists():
            compressed_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Video compressed: {current_size_mb:.1f}MB -> {compressed_size_mb:.1f}MB")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error compressing video: {e}")
        return False


async def compress_image_pillow(
    input_path: Path,
    output_path: Path,
    target_size_mb: int = 18,
    progress_callback: Optional[callable] = None
) -> bool:
    """
    Сжимает изображение до указанного размера
    """
    try:
        if progress_callback:
            await progress_callback("compressing_image", target_size_mb)
        
        from PIL import Image
        
        with Image.open(input_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Начинаем с высокого качества
            quality = 95
            
            while quality > 20:
                img.save(output_path, 'JPEG', quality=quality, optimize=True)
                
                # Проверяем размер
                size_mb = output_path.stat().st_size / (1024 * 1024)
                if size_mb <= target_size_mb:
                    logger.info(f"Image compressed to {size_mb:.1f}MB with quality {quality}")
                    return True
                
                quality -= 10
            
            # Если все еще большое, уменьшаем разрешение
            width, height = img.size
            scale_factor = 0.8
            
            while scale_factor > 0.3:
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                resized_img.save(output_path, 'JPEG', quality=85, optimize=True)
                
                size_mb = output_path.stat().st_size / (1024 * 1024)
                if size_mb <= target_size_mb:
                    logger.info(f"Image resized and compressed to {size_mb:.1f}MB")
                    return True
                
                scale_factor -= 0.1
            
            return output_path.exists()
        
    except Exception as e:
        logger.error(f"Error compressing image: {e}")
        return False


async def try_alternative_approach(
    file_size: int,
    progress_callback: Optional[callable] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Пытается предложить альтернативные подходы для больших файлов
    
    Returns:
        Tuple[suggestion, error]: (предложение пользователю, ошибка)
    """
    file_size_mb = file_size / (1024 * 1024)
    
    if progress_callback:
        await progress_callback("analyzing", file_size_mb)
    
    if file_size_mb > 100:
        suggestion = (
            f"📁 **Файл очень большой ({file_size_mb:.1f}МБ)**\n\n"
            f"🔧 **Рекомендации:**\n"
            f"• Используйте внешний сервис сжатия\n"
            f"• Разделите файл на части <20МБ\n"
            f"• Отправьте файл через веб-интерфейс\n\n"
            f"💡 Максимальный размер: {config.MAX_FILE_SIZE / (1024*1024):.0f}МБ"
        )
        return suggestion, "Файл слишком большой"
    
    # Для файлов 20-100МБ
    suggestion = (
        f"⚠️ **Большой файл ({file_size_mb:.1f}МБ)**\n\n"
        f"🤖 Telegram Bot API ограничивает скачивание до 20МБ\n\n"
        f"🔧 **Что можно сделать:**\n"
        f"• Сожмите файл до 20МБ в любом видеоредакторе\n"
        f"• Используйте онлайн-компрессоры\n"
        f"• Отправьте файл частями\n\n"
        f"💡 После сжатия отправьте файл снова"
    )
    return suggestion, None


def estimate_compression_ratio(file_extension: str) -> float:
    """
    Оценивает возможную степень сжатия для разных типов файлов
    """
    video_extensions = {'.mp4': 0.3, '.avi': 0.2, '.mov': 0.35, '.mkv': 0.25}
    image_extensions = {'.jpg': 0.8, '.png': 0.4, '.bmp': 0.1}
    
    return video_extensions.get(file_extension.lower(), 0.3)


async def suggest_compression_settings(file_size: int, file_extension: str) -> str:
    """
    Предлагает настройки сжатия для пользователя
    """
    file_size_mb = file_size / (1024 * 1024)
    target_size_mb = 18  # Оставляем запас
    
    compression_ratio = estimate_compression_ratio(file_extension)
    estimated_result = file_size_mb * compression_ratio
    
    if file_extension.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
        if estimated_result > target_size_mb:
            # Нужно больше сжатия
            return (
                f"🎬 **Настройки для видео сжатия:**\n\n"
                f"📊 Текущий размер: {file_size_mb:.1f}МБ\n"
                f"🎯 Целевой размер: ≤{target_size_mb}МБ\n\n"
                f"⚙️ **Рекомендуемые настройки:**\n"
                f"• Разрешение: 720p или меньше\n"
                f"• Битрейт: 1000-1500 kbps\n"
                f"• Кодек: H.264\n"
                f"• Частота кадров: 24-30 fps"
            )
        else:
            return f"✅ После стандартного сжатия размер будет ~{estimated_result:.1f}МБ"
    
    elif file_extension.lower() in ['.jpg', '.png', '.bmp']:
        return (
            f"🖼 **Настройки для изображения:**\n\n"
            f"📊 Текущий размер: {file_size_mb:.1f}МБ\n"
            f"🎯 Целевой размер: ≤{target_size_mb}МБ\n\n"
            f"⚙️ **Рекомендации:**\n"
            f"• Качество JPEG: 80-90%\n"
            f"• Размер: до 1920x1080\n"
            f"• Формат: JPG для фото, PNG для графики"
        )
    
    return f"📁 Сожмите файл с {file_size_mb:.1f}МБ до {target_size_mb}МБ"
