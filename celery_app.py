"""
Celery приложение для обработки тяжелых задач
"""

import os
import logging
from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from kombu import Queue
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем Celery приложение
app = Celery('bot_tasks')

# Конфигурация
app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # Сериализация
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Временные лимиты
    task_soft_time_limit=300,  # 5 минут soft limit
    task_time_limit=600,  # 10 минут hard limit
    
    # Поведение воркеров
    worker_prefetch_multiplier=1,  # По одной задаче за раз
    worker_max_tasks_per_child=10,  # Рестарт после 10 задач (освобождение памяти)
    
    # Очереди с приоритетами
    task_routes={
        'tasks.video.*': {'queue': 'video', 'priority': 5},
        'tasks.image.*': {'queue': 'image', 'priority': 3},
        'tasks.download.*': {'queue': 'download', 'priority': 7},
        'tasks.compress.*': {'queue': 'compress', 'priority': 4},
    },
    
    task_queues=(
        Queue('video', priority=5),
        Queue('image', priority=3),
        Queue('download', priority=7),
        Queue('compress', priority=4),
        Queue('default', priority=1),
    ),
    
    # Retry политика
    task_annotations={
        '*': {
            'rate_limit': '100/m',  # Максимум 100 задач в минуту
            'max_retries': 3,
            'default_retry_delay': 60,
        }
    },
    
    # Результаты
    result_expires=3600,  # Результаты хранятся час
    
    # Мониторинг
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Настройка beat schedule для периодических задач
app.conf.beat_schedule = {
    'cleanup-temp-files': {
        'task': 'tasks.maintenance.cleanup_temp_files',
        'schedule': 3600.0,  # Каждый час
    },
    'check-zombie-processes': {
        'task': 'tasks.maintenance.check_zombie_processes',
        'schedule': 300.0,  # Каждые 5 минут
    },
}

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Обработчик готовности воркера"""
    logger.info(f"Worker ready: {sender}")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Обработчик остановки воркера"""
    logger.info(f"Worker shutting down: {sender}")
