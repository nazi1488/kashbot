"""
Трекер прогресса для операций загрузки и обработки видео
"""

import asyncio
import time
from typing import Optional, Callable, Dict, Any
from telegram import Message
import logging

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Трекер прогресса для длительных операций"""
    
    def __init__(self, message: Message, operation_name: str = "Обработка"):
        """
        Args:
            message: Telegram сообщение для обновления
            operation_name: Название операции
        """
        self.message = message
        self.operation_name = operation_name
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 2  # Обновляем каждые 2 секунды
        
        # Эмодзи для анимации
        self.progress_emojis = ["⏳", "⌛", "🔄", "⚙️", "🛠️", "⏱️"]
        self.current_emoji_index = 0
        
    async def update_progress(self, stage: str, progress: Optional[float] = None):
        """
        Обновляет прогресс операции
        
        Args:
            stage: Текущая стадия операции
            progress: Прогресс в процентах (0-100), необязательно
        """
        current_time = time.time()
        
        # Обновляем только если прошло достаточно времени
        if current_time - self.last_update < self.update_interval:
            return
        
        try:
            elapsed_time = int(current_time - self.start_time)
            
            # Создаем сообщение о прогрессе
            emoji = self.progress_emojis[self.current_emoji_index]
            self.current_emoji_index = (self.current_emoji_index + 1) % len(self.progress_emojis)
            
            message_text = f"{emoji} {self.operation_name}...\n"
            message_text += f"📍 {stage}\n"
            message_text += f"⏰ Прошло времени: {elapsed_time}с"
            
            if progress is not None:
                progress_bar = self._create_progress_bar(progress)
                message_text += f"\n{progress_bar} {progress:.1f}%"
            
            await self.message.edit_text(message_text)
            self.last_update = current_time
            
        except Exception as e:
            # Игнорируем ошибки обновления (например, если сообщение слишком старое)
            logger.debug(f"Failed to update progress: {e}")
    
    def _create_progress_bar(self, progress: float, length: int = 10) -> str:
        """Создает текстовый прогресс-бар"""
        filled = int(progress / 100 * length)
        empty = length - filled
        return "🟩" * filled + "⬜" * empty
    
    async def finish_success(self, result_message: str):
        """Завершает операцию с успехом"""
        try:
            elapsed_time = int(time.time() - self.start_time)
            final_message = f"✅ {self.operation_name} завершена!\n"
            final_message += f"⏱️ Время выполнения: {elapsed_time}с\n\n"
            final_message += result_message
            
            await self.message.edit_text(final_message)
        except Exception as e:
            logger.error(f"Failed to finish progress with success: {e}")
    
    async def finish_error(self, error_message: str):
        """Завершает операцию с ошибкой"""
        try:
            elapsed_time = int(time.time() - self.start_time)
            final_message = f"❌ {self.operation_name} не удалась\n"
            final_message += f"⏱️ Время выполнения: {elapsed_time}с\n\n"
            final_message += error_message
            
            await self.message.edit_text(final_message)
        except Exception as e:
            logger.error(f"Failed to finish progress with error: {e}")


class DownloadProgressCallback:
    """Callback для отслеживания прогресса загрузки yt-dlp"""
    
    def __init__(self, progress_tracker: ProgressTracker):
        self.tracker = progress_tracker
        self.last_update = 0
        
    def __call__(self, d: Dict[str, Any]):
        """Callback функция для yt-dlp"""
        try:
            if d['status'] == 'downloading':
                # Получаем информацию о прогрессе
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total > 0:
                    progress = (downloaded / total) * 100
                    
                    # Форматируем размеры
                    downloaded_mb = downloaded / 1024 / 1024
                    total_mb = total / 1024 / 1024
                    
                    stage = f"Загрузка: {downloaded_mb:.1f}MB / {total_mb:.1f}MB"
                    
                    # Обновляем асинхронно (создаем задачу)
                    asyncio.create_task(self.tracker.update_progress(stage, progress))
                    
            elif d['status'] == 'finished':
                filename = d.get('filename', 'файл')
                stage = f"Загрузка завершена: {filename}"
                asyncio.create_task(self.tracker.update_progress(stage))
                
        except Exception as e:
            logger.debug(f"Progress callback error: {e}")


class VideoProcessingProgressTracker:
    """Специализированный трекер для обработки видео"""
    
    STAGES = {
        'validation': 'Проверка URL',
        'extracting_info': 'Получение информации о видео',
        'downloading': 'Загрузка видео',
        'processing': 'Обработка видео',
        'compressing': 'Сжатие видео',
        'removing_watermark': 'Удаление водяных знаков',
        'uploading': 'Подготовка к отправке',
        'extracting_audio': 'Извлечение аудио'
    }
    
    def __init__(self, message: Message, platform: str):
        self.tracker = ProgressTracker(message, f"Загрузка с {platform}")
        self.current_stage = None
        
    async def set_stage(self, stage_key: str, progress: Optional[float] = None):
        """Устанавливает текущую стадию обработки"""
        self.current_stage = stage_key
        stage_name = self.STAGES.get(stage_key, stage_key)
        await self.tracker.update_progress(stage_name, progress)
    
    async def update_progress(self, progress: float):
        """Обновляет прогресс текущей стадии"""
        if self.current_stage:
            stage_name = self.STAGES.get(self.current_stage, self.current_stage)
            await self.tracker.update_progress(stage_name, progress)
    
    async def finish_success(self, platform: str, file_type: str, 
                           file_size: int, watermark_removed: bool = False):
        """Завершает с успехом и красивым сообщением"""
        from .download_config import ErrorMessages
        
        success_message = ErrorMessages.get_success_message(
            platform, file_type, file_size, watermark_removed
        )
        await self.tracker.finish_success(success_message)
    
    async def finish_error(self, platform: str, error_type: str, **kwargs):
        """Завершает с ошибкой и информативным сообщением"""
        from .download_config import ErrorMessages
        
        error_message = ErrorMessages.get_error_message(platform, error_type, **kwargs)
        await self.tracker.finish_error(error_message)
    
    def get_progress_callback(self) -> DownloadProgressCallback:
        """Возвращает callback для yt-dlp"""
        return DownloadProgressCallback(self.tracker)
