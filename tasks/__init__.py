"""
Celery задачи для асинхронной обработки
"""

from .video_tasks import (
    process_video_uniqueness_task,
    compress_video_task,
    download_video_task
)
from .image_tasks import process_image_uniqueness_task
from .maintenance_tasks import cleanup_temp_files, check_zombie_processes

__all__ = [
    'process_video_uniqueness_task',
    'compress_video_task',
    'download_video_task',
    'process_image_uniqueness_task',
    'cleanup_temp_files',
    'check_zombie_processes',
]
