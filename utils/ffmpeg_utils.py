"""
Утилиты для уникализации видео с использованием ffmpeg
"""

import os
import random
import string
import logging
import subprocess
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
import ffmpeg

logger = logging.getLogger(__name__)


def generate_random_filename(extension: str) -> str:
    """Генерирует случайное имя файла"""
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    return f"{random_name}{extension}"


def get_video_info(input_path: str) -> Dict:
    """
    Получает информацию о видео файле
    
    Args:
        input_path: Путь к видео файлу
    
    Returns:
        Dict: Информация о видео
    """
    try:
        probe = ffmpeg.probe(input_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
        
        return {
            'duration': float(probe['format']['duration']),
            'width': int(video_stream['width']) if video_stream else 0,
            'height': int(video_stream['height']) if video_stream else 0,
            'has_audio': audio_stream is not None
        }
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return {}


async def process_video_uniqueness(
    input_path: str,
    output_dir: str,
    params: dict
) -> str:
    """
    Применяет случайные методы уникализации к видео
    
    Args:
        input_path: Путь к исходному видео
        output_dir: Директория для сохранения результата
        params: Параметры уникализации из конфига
    
    Returns:
        str: Путь к обработанному файлу
    """
    try:
        # Получаем информацию о видео
        video_info = get_video_info(input_path)
        
        # Генерируем случайное имя файла
        extension = Path(input_path).suffix
        output_filename = generate_random_filename(extension)
        output_path = os.path.join(output_dir, output_filename)
        
        # Создаем входной поток
        stream = ffmpeg.input(input_path)
        video = stream.video
        audio = stream.audio
        
        # Применяем случайные трансформации к видео
        
        # 1. Микро-поворот
        rotation_angle = random.uniform(*params['rotation_range'])
        video = video.filter('rotate', angle=f'{rotation_angle}*PI/180', fillcolor='black@0')
        logger.debug(f"Applied rotation: {rotation_angle}°")
        
        # 2. Зеркальное отражение убрано по требованию пользователя
        
        # 3. Изменение яркости и контраста
        brightness = random.uniform(*params['brightness_range'])
        contrast = random.uniform(*params['contrast_range'])
        video = video.filter('eq', brightness=brightness-1, contrast=contrast)
        logger.debug(f"Applied brightness: {brightness}, contrast: {contrast}")
        
        # 4. Добавление шума
        noise_level = random.uniform(*params['noise_level_range'])
        video = video.filter('noise', alls=noise_level, allf='t')
        logger.debug(f"Applied noise: {noise_level}")
        
        # 5. Легкая обрезка краев (изменение размера)
        if video_info.get('width') and video_info.get('height'):
            crop_pixels = random.randint(2, 10)
            new_width = video_info['width'] - crop_pixels * 2
            new_height = video_info['height'] - crop_pixels * 2
            # Убедимся, что размеры четные (требование для многих кодеков)
            new_width = new_width - (new_width % 2)
            new_height = new_height - (new_height % 2)
            video = video.filter('crop', w=new_width, h=new_height, x=crop_pixels, y=crop_pixels)
            logger.debug(f"Applied crop: {crop_pixels} pixels")
        
        # 6. Изменение скорости (очень незначительное)
        if video_info.get('has_audio'):
            speed_factor = random.uniform(*params['speed_range'])
            video = video.filter('setpts', f'{1/speed_factor}*PTS')
            audio = audio.filter('atempo', speed_factor)
            logger.debug(f"Applied speed change: {speed_factor}")
        
        # Параметры кодирования
        crf_value = random.randint(*params['crf_range'])
        
        # Собираем выходные параметры
        output_params = {
            'vcodec': 'libx264',
            'crf': crf_value,
            'preset': 'medium',
            'movflags': '+faststart',
            'pix_fmt': 'yuv420p'
        }
        
        # Если есть аудио, добавляем аудио параметры
        if video_info.get('has_audio'):
            output_params.update({
                'acodec': 'aac',
                'audio_bitrate': f'{random.randint(128, 192)}k'
            })
            output = ffmpeg.output(video, audio, output_path, **output_params)
        else:
            output = ffmpeg.output(video, output_path, **output_params)
        
        # Запускаем обработку
        output = output.overwrite_output()
        
        # Выполняем команду асинхронно
        cmd = output.compile()
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception(f"FFmpeg processing failed: {stderr.decode()}")
        
        logger.info(f"Video processed: {output_filename}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise


async def create_multiple_unique_videos(
    input_path: str,
    output_dir: str,
    count: int,
    params: dict,
    progress_callback=None
) -> List[str]:
    """
    Создает несколько уникальных копий видео
    
    Args:
        input_path: Путь к исходному видео
        output_dir: Директория для сохранения
        count: Количество копий
        params: Параметры уникализации
        progress_callback: Функция для отправки прогресса
    
    Returns:
        List[str]: Список путей к созданным файлам
    """
    results = []
    
    for i in range(count):
        try:
            if progress_callback:
                await progress_callback(i + 1, count)
            
            output_path = await process_video_uniqueness(input_path, output_dir, params)
            results.append(output_path)
            logger.info(f"Created unique video {i+1}/{count}")
        except Exception as e:
            logger.error(f"Failed to create unique video {i+1}: {e}")
    
    return results


def check_ffmpeg_installed() -> bool:
    """Проверяет, установлен ли ffmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
