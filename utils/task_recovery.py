"""
Механизм восстановления задач после сбоев
"""

import json
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class TaskRecoveryManager:
    """Менеджер восстановления задач после сбоев"""

    def __init__(self, recovery_file: str = "task_recovery.json"):
        self.recovery_file = Path(recovery_file)
        self.recovery_tasks = {}  # task_id: task_data
        self.load_recovery_tasks()

    def load_recovery_tasks(self):
        """Загрузить задачи для восстановления"""
        try:
            if self.recovery_file.exists():
                with open(self.recovery_file, 'r', encoding='utf-8') as f:
                    self.recovery_tasks = json.load(f)
                logger.info(f"Loaded {len(self.recovery_tasks)} tasks for recovery")
        except Exception as e:
            logger.error(f"Failed to load recovery tasks: {e}")
            self.recovery_tasks = {}

    def save_recovery_tasks(self):
        """Сохранить задачи для восстановления"""
        try:
            with open(self.recovery_file, 'w', encoding='utf-8') as f:
                json.dump(self.recovery_tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save recovery tasks: {e}")

    def add_task_for_recovery(
        self,
        task_id: str,
        task_type: str,
        user_id: int,
        data: Dict[str, Any],
        max_retries: int = 3
    ):
        """Добавить задачу для восстановления"""
        recovery_data = {
            'task_type': task_type,
            'user_id': user_id,
            'data': data,
            'created_at': datetime.now().isoformat(),
            'retry_count': 0,
            'max_retries': max_retries,
            'last_error': None,
            'status': 'pending'
        }

        self.recovery_tasks[task_id] = recovery_data
        self.save_recovery_tasks()
        logger.info(f"Task {task_id} added for recovery")

    def mark_task_completed(self, task_id: str):
        """Отметить задачу как выполненную"""
        if task_id in self.recovery_tasks:
            del self.recovery_tasks[task_id]
            self.save_recovery_tasks()
            logger.info(f"Task {task_id} marked as completed")

    def mark_task_failed(self, task_id: str, error: str):
        """Отметить задачу как проваленную"""
        if task_id in self.recovery_tasks:
            self.recovery_tasks[task_id]['retry_count'] += 1
            self.recovery_tasks[task_id]['last_error'] = error
            self.recovery_tasks[task_id]['status'] = 'failed'

            if self.recovery_tasks[task_id]['retry_count'] >= self.recovery_tasks[task_id]['max_retries']:
                logger.warning(f"Task {task_id} exceeded max retries, removing from recovery")
                del self.recovery_tasks[task_id]
            else:
                logger.info(f"Task {task_id} failed, will retry later")

            self.save_recovery_tasks()

    def get_pending_tasks(self) -> Dict[str, Dict]:
        """Получить задачи, ожидающие восстановления"""
        return {
            task_id: data
            for task_id, data in self.recovery_tasks.items()
            if data['status'] == 'pending'
        }

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Очистить старые задачи"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []

        for task_id, data in self.recovery_tasks.items():
            created_at = datetime.fromisoformat(data['created_at'])
            if created_at < cutoff_time:
                to_remove.append(task_id)

        for task_id in to_remove:
            del self.recovery_tasks[task_id]
            logger.info(f"Removed old recovery task: {task_id}")

        if to_remove:
            self.save_recovery_tasks()

    async def retry_task(
        self,
        task_id: str,
        retry_function: Callable,
        *args,
        **kwargs
    ) -> bool:
        """Повторить выполнение задачи"""
        if task_id not in self.recovery_tasks:
            logger.warning(f"Task {task_id} not found for retry")
            return False

        task_data = self.recovery_tasks[task_id]

        try:
            logger.info(f"Retrying task {task_id} (attempt {task_data['retry_count'] + 1})")

            # Выполняем задачу
            result = await retry_function(task_data, *args, **kwargs)

            # Если успешно, отмечаем как выполненную
            self.mark_task_completed(task_id)
            return True

        except Exception as e:
            error_msg = f"Retry failed: {str(e)}"
            logger.error(f"Task {task_id} retry failed: {error_msg}")
            self.mark_task_failed(task_id, error_msg)
            return False

    def get_task_statistics(self) -> Dict[str, int]:
        """Получить статистику задач"""
        stats = {
            'pending': 0,
            'failed': 0,
            'total': len(self.recovery_tasks)
        }

        for data in self.recovery_tasks.values():
            if data['status'] == 'pending':
                stats['pending'] += 1
            elif data['status'] == 'failed':
                stats['failed'] += 1

        return stats


# Функции для восстановления различных типов задач

async def recover_file_processing_task(task_data: Dict, file_manager, process_function):
    """Восстановить обработку файла"""
    from utils.safe_file_operations import FileProcessingError

    try:
        # Получаем данные задачи
        user_id = task_data['user_id']
        file_path = task_data['data']['file_path']
        copies_count = task_data['data']['copies_count']

        # Проверяем, существует ли файл
        if not Path(file_path).exists():
            raise FileProcessingError("Файл не найден для восстановления")

        # Повторно выполняем обработку
        await process_function(file_path, copies_count, user_id)

        return True

    except Exception as e:
        raise FileProcessingError(f"Не удалось восстановить обработку файла: {str(e)}")


async def recover_compression_task(task_data: Dict, file_manager, compress_function):
    """Восстановить задачу сжатия"""
    try:
        # Получаем данные задачи
        user_id = task_data['user_id']
        file_path = task_data['data']['file_path']

        # Проверяем, существует ли файл
        if not Path(file_path).exists():
            raise FileProcessingError("Файл не найден для восстановления")

        # Повторно выполняем сжатие
        await compress_function(file_path, user_id)

        return True

    except Exception as e:
        raise FileProcessingError(f"Не удалось восстановить сжатие: {str(e)}")


# Глобальный экземпляр менеджера восстановления
recovery_manager = TaskRecoveryManager()
