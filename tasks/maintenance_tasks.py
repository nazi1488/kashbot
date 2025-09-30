"""
Периодические задачи обслуживания
"""

import os
import shutil
import psutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

from celery_app import app

logger = logging.getLogger(__name__)


@app.task(name='tasks.maintenance.cleanup_temp_files')
def cleanup_temp_files():
    """
    Очистка временных файлов старше 1 часа
    """
    temp_dirs = ['/tmp', '/var/tmp']
    patterns = ['video_unique_*', 'image_unique_*', 'compress_*', 'download_*']
    cleaned_count = 0
    
    try:
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue
                
            for pattern_prefix in patterns:
                # Ищем директории по паттерну
                for path in Path(temp_dir).glob(pattern_prefix):
                    try:
                        # Проверяем время модификации
                        mtime = datetime.fromtimestamp(path.stat().st_mtime)
                        
                        if mtime < cutoff_time:
                            if path.is_dir():
                                shutil.rmtree(path, ignore_errors=True)
                            else:
                                path.unlink(missing_ok=True)
                            cleaned_count += 1
                            logger.info(f"Cleaned old temp: {path}")
                    except Exception as e:
                        logger.error(f"Error cleaning {path}: {e}")
        
        logger.info(f"Cleaned {cleaned_count} temporary files/directories")
        
        return {
            'success': True,
            'cleaned': cleaned_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.task(name='tasks.maintenance.check_zombie_processes')
def check_zombie_processes():
    """
    Проверка и убийство зомби-процессов FFmpeg
    """
    killed_count = 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'status', 'create_time']):
            try:
                # Ищем процессы ffmpeg
                if 'ffmpeg' in proc.info['name'].lower():
                    # Проверяем статус
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        proc.kill()
                        killed_count += 1
                        logger.warning(f"Killed zombie ffmpeg process: {proc.info['pid']}")
                    else:
                        # Убиваем процессы старше 10 минут
                        age = datetime.now().timestamp() - proc.info['create_time']
                        if age > 600:  # 10 минут
                            proc.terminate()
                            proc.wait(timeout=5)
                            killed_count += 1
                            logger.warning(f"Killed old ffmpeg process: {proc.info['pid']} (age: {age}s)")
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        logger.info(f"Killed {killed_count} zombie/old processes")
        
        # Также собираем статистику системы
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'success': True,
            'killed': killed_count,
            'system_stats': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024**3)
            },
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Zombie check failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@app.task(name='tasks.maintenance.check_redis_memory')
def check_redis_memory():
    """
    Мониторинг памяти Redis и очистка при необходимости
    """
    import redis
    
    try:
        r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
        
        # Получаем информацию о памяти
        info = r.info('memory')
        used_memory_mb = info['used_memory'] / (1024 * 1024)
        
        logger.info(f"Redis memory usage: {used_memory_mb:.2f} MB")
        
        # Если используется больше 500MB, чистим старые результаты
        if used_memory_mb > 500:
            # Удаляем результаты задач старше 24 часов
            deleted = 0
            for key in r.scan_iter("celery-task-meta-*"):
                ttl = r.ttl(key)
                if ttl == -1:  # Нет TTL
                    r.expire(key, 3600)  # Устанавливаем TTL 1 час
                    deleted += 1
            
            logger.warning(f"Redis memory cleanup: set TTL for {deleted} keys")
        
        return {
            'success': True,
            'memory_mb': used_memory_mb,
            'max_memory_mb': info.get('maxmemory', 0) / (1024 * 1024),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Redis check failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
