"""
Безопасная обработка файловых операций
"""

import os
import logging
import shutil
import tempfile
from typing import Callable, Any, Optional, Dict
from functools import wraps
from pathlib import Path
from utils.error_handler import FileProcessingError, error_handler

logger = logging.getLogger(__name__)


def safe_file_operation(operation_name: str = "file_operation"):
    """
    Декоратор для безопасной обработки файловых операций

    Args:
        operation_name: Название операции для логирования
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except FileNotFoundError as e:
                raise FileProcessingError(
                    f"Файл не найден: {e.filename}",
                    user_message="Файл не найден или был удален",
                    error_code="FILE_NOT_FOUND"
                )
            except PermissionError as e:
                raise FileProcessingError(
                    f"Недостаточно прав доступа: {e.filename}",
                    user_message="Недостаточно прав для обработки файла",
                    error_code="PERMISSION_DENIED"
                )
            except OSError as e:
                raise FileProcessingError(
                    f"Ошибка файловой системы: {str(e)}",
                    user_message="Ошибка при работе с файлами",
                    error_code="FILESYSTEM_ERROR"
                )
            except MemoryError:
                raise FileProcessingError(
                    "Недостаточно памяти для обработки файла",
                    user_message="Файл слишком большой для обработки",
                    error_code="MEMORY_ERROR"
                )
            except Exception as e:
                raise FileProcessingError(
                    f"Неизвестная ошибка при {operation_name}: {str(e)}",
                    user_message="Произошла ошибка при обработке файла",
                    error_code="UNKNOWN_FILE_ERROR"
                )

        return wrapper
    return decorator


class FileManager:
    """Менеджер для безопасной работы с файлами"""

    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "bot_files"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.active_files = {}  # user_id: [file_paths]

    @safe_file_operation("создание временной директории")
    def create_user_temp_dir(self, user_id: int) -> Path:
        """Создать временную директорию для пользователя"""
        user_dir = self.temp_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Очистка старых файлов (старше 1 часа)
        self._cleanup_old_files(user_dir)

        return user_dir

    def _cleanup_old_files(self, directory: Path):
        """Очистить старые файлы в директории"""
        try:
            for file_path in directory.iterdir():
                if file_path.is_file():
                    # Удаляем файлы старше 1 часа
                    if (Path(file_path).stat().st_mtime - Path(file_path).stat().st_ctime) > 3600:
                        file_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup old files in {directory}: {e}")

    @safe_file_operation("сохранение загруженного файла")
    async def save_uploaded_file(self, file_path: str, user_id: int) -> Path:
        """Безопасно сохранить загруженный файл"""
        source_path = Path(file_path)
        user_dir = self.create_user_temp_dir(user_id)

        # Создаем уникальное имя файла
        file_extension = source_path.suffix
        safe_filename = f"upload_{user_id}_{hash(source_path.name) % 10000}{file_extension}"
        dest_path = user_dir / safe_filename

        try:
            # Копируем файл вместо перемещения для безопасности
            shutil.copy2(source_path, dest_path)

            # Регистрируем файл для отслеживания
            if user_id not in self.active_files:
                self.active_files[user_id] = []
            self.active_files[user_id].append(dest_path)

            logger.info(f"File saved successfully: {dest_path}")
            return dest_path

        except Exception as e:
            # Если копирование не удалось, пытаемся переместить
            try:
                shutil.move(source_path, dest_path)
                logger.info(f"File moved successfully: {dest_path}")
                return dest_path
            except Exception:
                raise FileProcessingError(
                    f"Не удалось сохранить файл: {str(e)}",
                    user_message="Не удалось сохранить загруженный файл"
                )

    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Получить информацию о файле"""
        try:
            stat = file_path.stat()
            return {
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'extension': file_path.suffix.lower(),
                'exists': file_path.exists()
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return {'exists': False}

    @safe_file_operation("удаление временных файлов")
    def cleanup_user_files(self, user_id: int, specific_file: Optional[Path] = None):
        """Очистить временные файлы пользователя"""
        try:
            if specific_file:
                # Удаляем конкретный файл
                if specific_file.exists():
                    specific_file.unlink()
                    logger.info(f"File cleaned up: {specific_file}")
            else:
                # Удаляем все файлы пользователя
                user_dir = self.temp_dir / str(user_id)
                if user_dir.exists():
                    shutil.rmtree(user_dir)
                    logger.info(f"User directory cleaned up: {user_dir}")

            # Убираем из отслеживания
            if user_id in self.active_files:
                self.active_files[user_id] = [
                    f for f in self.active_files[user_id]
                    if f.exists()
                ]

        except Exception as e:
            logger.error(f"Failed to cleanup files for user {user_id}: {e}")

    def cleanup_all_temp_files(self):
        """Очистить все временные файлы (для админов)"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                self.active_files.clear()
                logger.info("All temporary files cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup all temp files: {e}")


# Глобальный экземпляр файлового менеджера
file_manager = FileManager()
