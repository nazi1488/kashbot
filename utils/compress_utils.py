"""
Утилиты для умного сжатия медиафайлов для Facebook
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Tuple, Optional
from PIL import Image
import ffmpeg

logger = logging.getLogger(__name__)


def get_file_size_mb(file_path: str) -> float:
    """Получает размер файла в МБ"""
    return os.path.getsize(file_path) / (1024 * 1024)


def compress_image_for_facebook(
    input_path: str,
    output_dir: str,
    target_format: str = 'webp'
) -> Tuple[str, Dict[str, float]]:
    """
    Сжимает изображение для Facebook Ads
    
    Args:
        input_path: Путь к исходному изображению
        output_dir: Директория для сохранения
        target_format: Целевой формат (webp или avif)
    
    Returns:
        Tuple[str, Dict]: Путь к сжатому файлу и статистика сжатия
    """
    try:
        original_size = get_file_size_mb(input_path)
        
        # Открываем изображение
        img = Image.open(input_path)
        
        # Конвертируем в RGB если нужно
        if img.mode in ('RGBA', 'P'):
            # Создаем белый фон для прозрачных изображений
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Ресайз до оптимального размера для Facebook (1080x1080 для квадрата)
        # Сохраняем соотношение сторон
        max_size = 1080
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            logger.info(f"Resized image to {img.width}x{img.height}")
        
        # Генерируем имя выходного файла
        output_filename = f"fb_optimized_{Path(input_path).stem}.{target_format}"
        output_path = os.path.join(output_dir, output_filename)
        
        # Сохраняем с оптимальными настройками
        if target_format == 'webp':
            # WebP с высоким качеством но хорошим сжатием
            img.save(output_path, 'WEBP', quality=85, method=6, lossless=False)
        elif target_format == 'avif':
            # AVIF для еще лучшего сжатия (если поддерживается)
            try:
                import pillow_avif
                img.save(output_path, 'AVIF', quality=85, speed=6)
            except ImportError:
                logger.warning("AVIF not supported, falling back to WebP")
                target_format = 'webp'
                output_filename = f"fb_optimized_{Path(input_path).stem}.webp"
                output_path = os.path.join(output_dir, output_filename)
                img.save(output_path, 'WEBP', quality=85, method=6, lossless=False)
        else:
            # Fallback на оптимизированный JPEG
            img.save(output_path, 'JPEG', quality=85, optimize=True, progressive=True)
        
        new_size = get_file_size_mb(output_path)
        
        stats = {
            'original_size': round(original_size, 2),
            'new_size': round(new_size, 2),
            'saved': round(original_size - new_size, 2),
            'percent': round((1 - new_size/original_size) * 100, 1)
        }
        
        logger.info(f"Image compressed: {original_size:.2f}MB -> {new_size:.2f}MB ({stats['percent']}% reduction)")
        
        return output_path, stats
        
    except Exception as e:
        logger.error(f"Error compressing image: {e}")
        raise


async def compress_video_for_facebook(
    input_path: str,
    output_dir: str
) -> Tuple[str, Dict[str, float]]:
    """
    Сжимает видео для Facebook Ads используя H.265
    
    Args:
        input_path: Путь к исходному видео
        output_dir: Директория для сохранения
    
    Returns:
        Tuple[str, Dict]: Путь к сжатому файлу и статистика сжатия
    """
    try:
        original_size = get_file_size_mb(input_path)
        
        # Получаем информацию о видео
        probe = ffmpeg.probe(input_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        
        width = int(video_info['width'])
        height = int(video_info['height'])
        
        # Генерируем имя выходного файла
        output_filename = f"fb_optimized_{Path(input_path).stem}.mp4"
        output_path = os.path.join(output_dir, output_filename)
        
        # Создаем ffmpeg команду
        stream = ffmpeg.input(input_path)
        
        # Масштабируем если больше 1080p
        if width > 1920 or height > 1080:
            # Сохраняем соотношение сторон
            if width > height:
                stream = stream.filter('scale', 1920, -1)
            else:
                stream = stream.filter('scale', -1, 1080)
            logger.info("Scaling video to 1080p")
        
        # Настройки для H.265 (HEVC)
        # CRF 23 - хороший баланс качества и размера
        # preset fast - хорошая скорость кодирования
        output_params = {
            'vcodec': 'libx265',
            'crf': 23,
            'preset': 'fast',
            'tag:v': 'hvc1',  # Для совместимости с Apple устройствами
            'movflags': '+faststart',  # Для быстрого начала воспроизведения
            'pix_fmt': 'yuv420p'
        }
        
        # Аудио настройки - AAC 128k
        audio_params = {
            'acodec': 'aac',
            'audio_bitrate': '128k',
            'ar': '44100'  # Частота дискретизации
        }
        
        # Объединяем параметры
        output_params.update(audio_params)
        
        # Создаем выходной поток
        output = ffmpeg.output(stream, output_path, **output_params)
        output = output.overwrite_output()
        
        # Получаем команду
        cmd = output.compile()
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        # Выполняем команду асинхронно
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception(f"FFmpeg processing failed")
        
        new_size = get_file_size_mb(output_path)
        
        stats = {
            'original_size': round(original_size, 2),
            'new_size': round(new_size, 2),
            'saved': round(original_size - new_size, 2),
            'percent': round((1 - new_size/original_size) * 100, 1) if original_size > 0 else 0
        }
        
        logger.info(f"Video compressed: {original_size:.2f}MB -> {new_size:.2f}MB ({stats['percent']}% reduction)")
        
        return output_path, stats
        
    except Exception as e:
        logger.error(f"Error compressing video: {e}")
        raise


def is_video_file(filename: str) -> bool:
    """Проверяет, является ли файл видео"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    return Path(filename).suffix.lower() in video_extensions


def is_image_file(filename: str) -> bool:
    """Проверяет, является ли файл изображением"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']
    return Path(filename).suffix.lower() in image_extensions
