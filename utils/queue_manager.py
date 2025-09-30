"""
Менеджер очереди для управления нагрузкой на CPU-интенсивные операции
"""

import asyncio
import logging
import psutil
from typing import Optional, Callable, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class QueueManager:
    """Менеджер очереди с ограничением параллельных задач"""
    
    def __init__(
        self,
        max_concurrent_tasks: int = 2,
        max_queue_size: int = 10,
        cpu_threshold: float = 80.0,
        task_timeout: int = 300  # 5 минут
    ):
        """
        Args:
            max_concurrent_tasks: Максимум одновременных задач
            max_queue_size: Максимальный размер очереди
            cpu_threshold: Порог загрузки CPU в процентах
            task_timeout: Таймаут задачи в секундах
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        self.cpu_threshold = cpu_threshold
        self.task_timeout = task_timeout
        
        # Семафор для ограничения параллельных задач
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # Очередь задач
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        
        # Счетчики для статистики
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.current_tasks = 0
        
        # Информация о пользователях в очереди
        self.user_tasks = {}  # user_id: task_count
        
    def get_queue_position(self, user_id: int) -> int:
        """Получает позицию пользователя в очереди"""
        position = 0
        for item in list(self.queue._queue):
            position += 1
            if item.get('user_id') == user_id:
                return position
        return 0
    
    def get_cpu_usage(self) -> float:
        """Получает текущую загрузку CPU"""
        return psutil.cpu_percent(interval=1)
    
    def is_cpu_overloaded(self) -> bool:
        """Проверяет, не перегружен ли CPU"""
        cpu_usage = self.get_cpu_usage()
        is_overloaded = cpu_usage > self.cpu_threshold
        if is_overloaded:
            logger.warning(f"CPU overloaded: {cpu_usage}% > {self.cpu_threshold}%")
        return is_overloaded
    
    async def add_task(
        self,
        user_id: int,
        task_func: Callable,
        *args,
        **kwargs
    ) -> dict:
        """
        Добавляет задачу в очередь
        
        Returns:
            dict: Результат с информацией о статусе
        """
        # Проверяем, не слишком ли много задач у пользователя
        user_task_count = self.user_tasks.get(user_id, 0)
        if user_task_count >= 3:
            return {
                'success': False,
                'error': 'too_many_tasks',
                'message': 'У вас уже есть 3 задачи в обработке'
            }
        
        # Проверяем размер очереди
        if self.queue.full():
            return {
                'success': False,
                'error': 'queue_full',
                'message': f'Очередь переполнена. Попробуйте позже.',
                'queue_size': self.queue.qsize()
            }
        
        # Добавляем задачу в очередь
        task_info = {
            'user_id': user_id,
            'task_func': task_func,
            'args': args,
            'kwargs': kwargs,
            'added_at': datetime.now()
        }
        
        try:
            await self.queue.put(task_info)
            self.user_tasks[user_id] = user_task_count + 1
            
            # Запускаем обработчик, если он еще не запущен
            asyncio.create_task(self._process_queue())
            
            return {
                'success': True,
                'position': self.queue.qsize(),
                'current_tasks': self.current_tasks,
                'max_concurrent': self.max_concurrent_tasks
            }
            
        except Exception as e:
            logger.error(f"Error adding task to queue: {e}")
            return {
                'success': False,
                'error': 'queue_error',
                'message': str(e)
            }
    
    async def _process_queue(self):
        """Обрабатывает задачи из очереди"""
        while not self.queue.empty():
            # Ждем, пока освободится слот
            async with self.semaphore:
                # Проверяем загрузку CPU
                while self.is_cpu_overloaded():
                    logger.info("Waiting for CPU load to decrease...")
                    await asyncio.sleep(5)
                
                try:
                    # Получаем задачу из очереди
                    task_info = await self.queue.get()
                    user_id = task_info['user_id']
                    
                    # Проверяем, не устарела ли задача
                    task_age = datetime.now() - task_info['added_at']
                    if task_age > timedelta(minutes=10):
                        logger.warning(f"Task for user {user_id} is too old, skipping")
                        continue
                    
                    self.current_tasks += 1
                    logger.info(f"Processing task for user {user_id}, "
                              f"current tasks: {self.current_tasks}/{self.max_concurrent_tasks}")
                    
                    # Выполняем задачу с таймаутом
                    try:
                        result = await asyncio.wait_for(
                            task_info['task_func'](*task_info['args'], **task_info['kwargs']),
                            timeout=self.task_timeout
                        )
                        self.tasks_processed += 1
                        logger.info(f"Task completed for user {user_id}")
                        
                    except asyncio.TimeoutError:
                        logger.error(f"Task timeout for user {user_id}")
                        self.tasks_failed += 1
                        raise
                        
                except Exception as e:
                    logger.error(f"Error processing task: {e}")
                    self.tasks_failed += 1
                    
                finally:
                    self.current_tasks -= 1
                    # Уменьшаем счетчик задач пользователя
                    if user_id in self.user_tasks:
                        self.user_tasks[user_id] -= 1
                        if self.user_tasks[user_id] <= 0:
                            del self.user_tasks[user_id]
    
    def get_stats(self) -> dict:
        """Получает статистику очереди"""
        return {
            'queue_size': self.queue.qsize(),
            'current_tasks': self.current_tasks,
            'max_concurrent': self.max_concurrent_tasks,
            'tasks_processed': self.tasks_processed,
            'tasks_failed': self.tasks_failed,
            'cpu_usage': self.get_cpu_usage(),
            'active_users': len(self.user_tasks)
        }


# Импортируем настройки
try:
    import config
    max_concurrent = config.COMPRESSION_MAX_CONCURRENT
    max_queue = config.COMPRESSION_MAX_QUEUE_SIZE
    cpu_threshold = config.COMPRESSION_CPU_THRESHOLD
    timeout = config.COMPRESSION_TASK_TIMEOUT
except:
    # Значения по умолчанию, если config недоступен
    max_concurrent = 2
    max_queue = 10
    cpu_threshold = 80.0
    timeout = 300

# Глобальный экземпляр менеджера очереди для сжатия
compression_queue = QueueManager(
    max_concurrent_tasks=max_concurrent,
    max_queue_size=max_queue,
    cpu_threshold=cpu_threshold,
    task_timeout=timeout
)
