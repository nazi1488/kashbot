"""
Celery задачи для обработки изображений
"""

import os
import shutil
import tempfile
import logging
import zipfile
from typing import Dict, List
from celery import Task

from celery_app import app
from utils.image_utils import create_multiple_unique_images
import config

logger = logging.getLogger(__name__)


@app.task(
    name='tasks.image.uniqueness',
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def process_image_uniqueness_task(
    self,
    file_path: str,
    copies_count: int,
    user_id: int,
    chat_id: int,
    message_id: int,
    **kwargs
) -> Dict:
    """
    Обработка уникализации изображений в отдельном процессе
    
    Эта задача быстрее видео, но все равно выносим в воркер
    для разгрузки основного процесса
    """
    temp_dir = None
    
    try:
        # Создаем временную директорию
        temp_dir = tempfile.mkdtemp(prefix=f"image_unique_{user_id}_")
        output_dir = os.path.join(temp_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Проверяем файл
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
        
        # Обновляем статус
        self.update_state(
            state='PROCESSING',
            meta={
                'current': 0,
                'total': copies_count,
                'status': 'Обрабатываю изображения...'
            }
        )
        
        # Процессим изображения (синхронно, т.к. PIL не async)
        results = create_multiple_unique_images(
            file_path,
            output_dir,
            copies_count,
            config.IMAGE_UNIQUENESS_PARAMS
        )
        
        # Обновляем прогресс
        self.update_state(
            state='PROCESSING',
            meta={
                'current': copies_count,
                'total': copies_count,
                'status': 'Создаю архив...'
            }
        )
        
        # Создаем архив
        zip_path = os.path.join(temp_dir, f"unique_images_{user_id}.zip")
        
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
        logger.error(f"Image uniqueness task failed: {e}")
        
        # Cleanup
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
