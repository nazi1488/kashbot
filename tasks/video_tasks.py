"""
Celery задачи для обработки видео
"""

import os
import shutil
import tempfile
import logging
import asyncio
from typing import Dict, List, Optional
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from celery_app import app
from utils.ffmpeg_utils import process_video_uniqueness
from utils.compress_utils import compress_video_for_facebook
from utils.video_downloader_v2 import VideoDownloaderV2

logger = logging.getLogger(__name__)


class VideoTask(Task):
    """Базовый класс для видео задач с cleanup"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Очистка при ошибке"""
        if 'temp_dir' in kwargs:
            try:
                shutil.rmtree(kwargs['temp_dir'], ignore_errors=True)
            except:
                pass
        logger.error(f"Task {task_id} failed: {exc}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Очистка при успехе"""
        if 'temp_dir' in kwargs and kwargs.get('cleanup', True):
            try:
                shutil.rmtree(kwargs['temp_dir'], ignore_errors=True)
            except:
                pass


@app.task(
    base=VideoTask,
    name='tasks.video.uniqueness',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def process_video_uniqueness_task(
    self,
    file_path: str,
    copies_count: int,
    user_id: int,
    chat_id: int,
    message_id: int,
    **kwargs
) -> Dict:
    """
    Обработка уникализации видео в отдельном процессе
    
    Args:
        file_path: Путь к исходному видео
        copies_count: Количество копий
        user_id: ID пользователя
        chat_id: ID чата для отправки результата
        message_id: ID сообщения для обновления прогресса
    
    Returns:
        Dict с результатами обработки
    """
    temp_dir = None
    
    try:
        # Создаем временную директорию для результатов
        temp_dir = tempfile.mkdtemp(prefix=f"video_unique_{user_id}_")
        output_dir = os.path.join(temp_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
        
        # Получаем параметры из конфига
        from config import VIDEO_UNIQUENESS_PARAMS
        
        # Обновляем прогресс
        self.update_state(
            state='PROCESSING',
            meta={
                'current': 0,
                'total': copies_count,
                'status': 'Начинаю обработку видео...'
            }
        )
        
        results = []
        
        # Обрабатываем каждую копию
        for i in range(copies_count):
            try:
                # Проверка на soft timeout
                if self.request.id:
                    self.update_state(
                        state='PROCESSING',
                        meta={
                            'current': i + 1,
                            'total': copies_count,
                            'status': f'Обработка копии {i + 1}/{copies_count}'
                        }
                    )
                
                # Запускаем обработку в asyncio (для совместимости с async ffmpeg utils)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    output_path = loop.run_until_complete(
                        process_video_uniqueness(
                            file_path,
                            output_dir,
                            VIDEO_UNIQUENESS_PARAMS
                        )
                    )
                    results.append(output_path)
                finally:
                    loop.close()
                    
            except SoftTimeLimitExceeded:
                logger.warning(f"Soft time limit exceeded for video {i+1}/{copies_count}")
                break
            except Exception as e:
                logger.error(f"Error processing video copy {i+1}: {e}")
                continue
        
        # Создаем архив с результатами
        import zipfile
        zip_path = os.path.join(temp_dir, f"unique_videos_{user_id}.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for result_path in results:
                if os.path.exists(result_path):
                    arcname = os.path.basename(result_path)
                    zipf.write(result_path, arcname)
        
        return {
            'success': True,
            'zip_path': zip_path,
            'count': len(results),
            'user_id': user_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'temp_dir': temp_dir
        }
        
    except Exception as e:
        logger.error(f"Video uniqueness task failed: {e}")
        
        # Cleanup on error
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Retry если возможно
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id,
            'chat_id': chat_id
        }


@app.task(
    base=VideoTask,
    name='tasks.video.compress',
    bind=True,
    max_retries=3
)
def compress_video_task(
    self,
    file_path: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    **kwargs
) -> Dict:
    """
    Сжатие видео для Facebook в отдельном процессе
    """
    temp_dir = None
    
    try:
        # Создаем временную директорию
        temp_dir = tempfile.mkdtemp(prefix=f"compress_{user_id}_")
        
        # Обновляем статус
        self.update_state(
            state='COMPRESSING',
            meta={'status': 'Сжимаю видео...', 'progress': 0}
        )
        
        # Запускаем сжатие
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            output_path, stats = loop.run_until_complete(
                compress_video_for_facebook(file_path, temp_dir)
            )
        finally:
            loop.close()
        
        return {
            'success': True,
            'output_path': output_path,
            'stats': stats,
            'user_id': user_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'temp_dir': temp_dir
        }
        
    except Exception as e:
        logger.error(f"Compress task failed: {e}")
        
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id,
            'chat_id': chat_id
        }


@app.task(
    name='tasks.video.download',
    bind=True,
    max_retries=5,
    default_retry_delay=30
)
def download_video_task(
    self,
    url: str,
    platform: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    **kwargs
) -> Dict:
    """
    Скачивание видео из соцсетей в отдельном процессе
    """
    temp_dir = None
    
    try:
        # Создаем временную директорию
        temp_dir = tempfile.mkdtemp(prefix=f"download_{user_id}_")
        
        # Обновляем статус
        self.update_state(
            state='DOWNLOADING',
            meta={'status': 'Скачиваю видео...', 'platform': platform}
        )
        
        # Инициализируем загрузчик
        downloader = VideoDownloaderV2()
        
        # Скачиваем видео
        video_path, error = downloader.download_video(url, temp_dir)
        
        if error:
            raise Exception(error)
        
        return {
            'success': True,
            'video_path': video_path,
            'platform': platform,
            'user_id': user_id,
            'chat_id': chat_id,
            'message_id': message_id,
            'temp_dir': temp_dir
        }
        
    except Exception as e:
        logger.error(f"Download task failed: {e}")
        
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Retry с exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 30 * (2 ** self.request.retries)  # 30, 60, 120, 240...
            raise self.retry(exc=e, countdown=countdown)
        
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id,
            'chat_id': chat_id,
            'platform': platform
        }
