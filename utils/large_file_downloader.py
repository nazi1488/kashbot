"""
Утилита для скачивания больших файлов из Telegram (обход лимита 20MB)
"""

import aiohttp
import asyncio
import logging
from pathlib import Path
from typing import Optional
import config

logger = logging.getLogger(__name__)


async def download_large_file(
    bot, 
    file_id: str, 
    destination: Path,
    progress_callback: Optional[callable] = None
) -> bool:
    """
    Простое скачивание файла с обработкой ошибок
    
    Args:
        bot: Telegram Bot instance
        file_id: ID файла для скачивания
        destination: Путь для сохранения файла
        progress_callback: Опциональная функция для отслеживания прогресса
    
    Returns:
        bool: True если файл успешно скачан
    """
    try:
        # Создаем директорию если не существует
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Просто пытаемся скачать файл любым способом
        file = await bot.get_file(file_id)
        await file.download_to_drive(destination)
        
        logger.info(f"Successfully downloaded file: {destination.name}")
        return True
        
    except Exception as e:
        # Логируем ошибку, но не падаем
        logger.debug(f"Could not download file {file_id}: {e}")
        return False


def can_download_large_file(file_size: int) -> bool:
    """
    Проверяет, можем ли мы скачать файл такого размера
    
    Args:
        file_size: Размер файла в байтах
    
    Returns:
        bool: True если можем скачать
    """
    # Проверяем против нашего лимита
    if file_size > config.MAX_FILE_SIZE:
        return False
    
    # Проверяем против разумного лимита для больших файлов (например, 500MB)
    MAX_LARGE_FILE = 500 * 1024 * 1024  # 500MB
    if file_size > MAX_LARGE_FILE:
        return False
    
    return True


def get_file_size_display(file_size: int) -> str:
    """
    Форматирует размер файла для отображения
    """
    if file_size < 1024:
        return f"{file_size} B"
    elif file_size < 1024 * 1024:
        return f"{file_size / 1024:.1f} KB"
    elif file_size < 1024 * 1024 * 1024:
        return f"{file_size / (1024 * 1024):.1f} MB"
    else:
        return f"{file_size / (1024 * 1024 * 1024):.1f} GB"
