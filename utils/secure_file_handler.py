"""
Модуль для безопасной работы с файлами
"""

import os
import tempfile
import shutil
import hashlib
from pathlib import Path
from typing import Optional, List
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SecureFileHandler:
    """Класс для безопасной работы с временными файлами"""
    
    def __init__(self, base_temp_dir: Optional[str] = None):
        """
        Args:
            base_temp_dir: Базовая директория для временных файлов
        """
        self.base_temp_dir = base_temp_dir or tempfile.gettempdir()
        self.temp_files: List[str] = []
        self.temp_dirs: List[str] = []
    
    def create_secure_temp_file(self, suffix: str = "", prefix: str = "bot_") -> str:
        """
        Создает безопасный временный файл
        
        Returns:
            str: Путь к временному файлу
        """
        # Санитизируем суффикс и префикс
        suffix = self._sanitize_filename_part(suffix)
        prefix = self._sanitize_filename_part(prefix)
        
        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=suffix,
                prefix=prefix,
                dir=self.base_temp_dir
            )
            os.close(fd)  # Закрываем файловый дескриптор
            
            # Устанавливаем безопасные права доступа
            os.chmod(temp_path, 0o600)  # rw-------
            
            self.temp_files.append(temp_path)
            logger.debug(f"Created secure temp file: {temp_path}")
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to create secure temp file: {e}")
            raise
    
    def create_secure_temp_dir(self, suffix: str = "", prefix: str = "bot_") -> str:
        """
        Создает безопасную временную директорию
        
        Returns:
            str: Путь к временной директории
        """
        suffix = self._sanitize_filename_part(suffix)
        prefix = self._sanitize_filename_part(prefix)
        
        try:
            temp_dir = tempfile.mkdtemp(
                suffix=suffix,
                prefix=prefix,
                dir=self.base_temp_dir
            )
            
            # Устанавливаем безопасные права доступа
            os.chmod(temp_dir, 0o700)  # rwx------
            
            self.temp_dirs.append(temp_dir)
            logger.debug(f"Created secure temp dir: {temp_dir}")
            
            return temp_dir
            
        except Exception as e:
            logger.error(f"Failed to create secure temp dir: {e}")
            raise
    
    @staticmethod
    def _sanitize_filename_part(filename_part: str) -> str:
        """
        Санитизирует часть имени файла
        
        Returns:
            str: Безопасная часть имени файла
        """
        if not filename_part:
            return ""
        
        # Убираем опасные символы
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        
        sanitized = filename_part
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Ограничиваем длину
        if len(sanitized) > 50:
            sanitized = sanitized[:47] + "..."
        
        return sanitized
    
    def cleanup(self):
        """Очищает все созданные временные файлы и директории"""
        # Очищаем файлы
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
        
        # Очищаем директории
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp dir: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")
        
        self.temp_files.clear()
        self.temp_dirs.clear()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()
    
    @staticmethod
    def validate_file_path(file_path: str, allowed_extensions: Optional[List[str]] = None) -> bool:
        """
        Валидирует путь к файлу на безопасность
        
        Args:
            file_path: Путь к файлу
            allowed_extensions: Разрешенные расширения (например, ['.mp4', '.webm'])
        
        Returns:
            bool: True если путь безопасный
        """
        try:
            # Проверяем на path traversal
            normalized_path = os.path.normpath(file_path)
            if '..' in normalized_path or normalized_path.startswith('/'):
                return False
            
            # Проверяем расширение файла
            if allowed_extensions:
                file_extension = Path(file_path).suffix.lower()
                if file_extension not in [ext.lower() for ext in allowed_extensions]:
                    return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> Optional[str]:
        """
        Вычисляет хэш файла для проверки целостности
        
        Args:
            file_path: Путь к файлу
            algorithm: Алгоритм хэширования
        
        Returns:
            Optional[str]: Хэш файла или None при ошибке
        """
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                # Читаем файл частями для экономии памяти
                while chunk := f.read(8192):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return None


@contextmanager
def secure_temp_context(base_dir: Optional[str] = None):
    """
    Context manager для безопасной работы с временными файлами
    
    Usage:
        with secure_temp_context() as handler:
            temp_file = handler.create_secure_temp_file(".mp4")
            # работа с файлом
            # автоматическая очистка при выходе
    """
    handler = SecureFileHandler(base_dir)
    try:
        yield handler
    finally:
        handler.cleanup()
