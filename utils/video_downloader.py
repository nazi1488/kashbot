"""
Модуль для скачивания видео с различных платформ с поддержкой ротации cookies
"""

import os
import re
import logging
import tempfile
from typing import Optional, Dict, Tuple, Any
from pathlib import Path
import yt_dlp
import cv2
import numpy as np
import asyncio
import json
from datetime import datetime
from .url_validator import URLValidator
from .secure_file_handler import SecureFileHandler, secure_temp_context
from .download_config import DownloadConfig, ErrorMessages
from .progress_tracker import VideoProcessingProgressTracker

logger = logging.getLogger(__name__)

class VideoDownloader:
    """Класс для скачивания видео с TikTok, YouTube Shorts и Instagram с поддержкой ротации cookies"""
    
    def __init__(self, cookies_manager=None, db=None, max_file_size: int = 50 * 1024 * 1024, 
                 config: Optional[DownloadConfig] = None):
        """
        Args:
            cookies_manager: Менеджер cookies для ротации
            db: База данных для логирования
            max_file_size: Максимальный размер файла в байтах (50MB по умолчанию)
            config: Конфигурация загрузчика
        """
        self.config = config or DownloadConfig.from_env()
        # Переопределяем размер файла если передан явно
        if max_file_size != 50 * 1024 * 1024:
            self.config.max_file_size = max_file_size
            
        self.cookies_manager = cookies_manager
        self.db = db
        
        # Временный файл cookies для обратной совместимости
        self.cookie_file = os.path.join(tempfile.gettempdir(), 'yt_dlp_cookies.txt')
        
        # Счетчики попыток
        self.max_retries = self.config.retries
        
        # Базовые настройки для yt-dlp
        self.base_ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': '%(title)s.%(ext)s',
            'format': self.config.video_quality,
            'max_filesize': self.config.max_file_size,
            'socket_timeout': self.config.socket_timeout,
            'retries': self.config.retries,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True
        }
        
        # Паттерны для определения платформ
        self.platform_patterns = {
            'tiktok': r'(?:tiktok\.com|vm\.tiktok\.com)',
            'youtube': r'(?:youtube\.com/shorts/|youtu\.be/)',
            'instagram': r'(?:instagram\.com|instagr\.am)',
        }
        
    def detect_platform(self, url: str) -> Optional[str]:
        """
        Определяет платформу по URL
        
        Args:
            url: URL видео
            
        Returns:
            Название платформы или None
        """
        for platform, pattern in self.platform_patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform
        return None
    
    async def download_video_async(self, url: str, message=None, output_dir: Optional[str] = None, 
                                   user_id: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Асинхронная загрузка видео с прогресс-трекингом
        
        Args:
            url: URL видео
            message: Telegram сообщение для отображения прогресса
            output_dir: Директория для сохранения
            user_id: ID пользователя для персонализации
            
        Returns:
            Tuple[путь к файлу, сообщение об ошибке]
        """
        # Валидация URL
        is_valid, error_msg = URLValidator.validate_url(url)
        if not is_valid:
            return None, ErrorMessages.get_error_message('general', 'invalid_url', error=error_msg)
        
        sanitized_url = URLValidator.sanitize_url(url)
        if not sanitized_url:
            return None, ErrorMessages.get_error_message('general', 'invalid_url')
        
        platform = self.detect_platform(sanitized_url)
        if not platform:
            return None, "Неподдерживаемая платформа. Поддерживаются: TikTok, YouTube Shorts, Instagram"
        
        # Создаем прогресс-трекер если передано сообщение
        progress_tracker = None
        if message:
            progress_tracker = VideoProcessingProgressTracker(message, platform)
            await progress_tracker.set_stage('validation')
        
        try:
            logger.info(f"Downloading video from {platform}: {sanitized_url}")
            
            if progress_tracker:
                await progress_tracker.set_stage('extracting_info')
            
            # Используем secure temp context для безопасной работы с файлами
            with secure_temp_context() as file_handler:
                if not output_dir:
                    output_dir = file_handler.create_secure_temp_dir(suffix="_video")
                
                # Применяем настройки для платформы
                opts = self._get_platform_options(platform, output_dir)
                
                # Добавляем progress callback если есть трекер
                if progress_tracker:
                    opts['progress_hooks'] = [progress_tracker.get_progress_callback()]
                    await progress_tracker.set_stage('downloading')
                
                # Выполняем загрузку в executor для избежания блокировки
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    self._download_video_sync, 
                    sanitized_url, opts
                )
                
                if result[1]:  # Если есть ошибка
                    if progress_tracker:
                        await progress_tracker.finish_error(platform, 'download_failed', error=result[1])
                    return result
                
                video_path = result[0]
                
                if progress_tracker:
                    await progress_tracker.set_stage('processing')
                
                # Проверяем и обрабатываем файл
                processed_path, error = await self._process_downloaded_file(
                    video_path, output_dir, progress_tracker
                )
                
                if error:
                    if progress_tracker:
                        await progress_tracker.finish_error(platform, 'processing_error', error=error)
                    return None, error
                
                # Завершаем с успехом
                if progress_tracker:
                    file_size = os.path.getsize(processed_path)
                    await progress_tracker.finish_success(platform, 'video', file_size)
                
                return processed_path, None
                
        except Exception as e:
            logger.error(f"Unexpected error downloading video: {e}")
            error_msg = ErrorMessages.get_error_message('general', 'processing_error')
            if progress_tracker:
                await progress_tracker.finish_error(platform, 'processing_error')
            return None, error_msg

    def download_video(self, url: str, output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Скачивает видео по URL с проверками безопасности
        
        Args:
            url: URL видео
            output_dir: Директория для сохранения (временная по умолчанию)
            
        Returns:
            Tuple[путь к файлу, сообщение об ошибке]
        """
        # Валидация URL
        is_valid, error_msg = URLValidator.validate_url(url)
        if not is_valid:
            return None, f"Недопустимый URL: {error_msg}"
        
        # Санитизация URL
        sanitized_url = URLValidator.sanitize_url(url)
        if not sanitized_url:
            return None, "Не удалось обработать URL"
        
        try:
            platform = self.detect_platform(sanitized_url)
            if not platform:
                return None, "Неподдерживаемая платформа. Поддерживаются: TikTok, YouTube Shorts, Instagram"
            
            logger.info(f"Downloading video from {platform}: {sanitized_url}")
            
            # Используем secure temp context для безопасной работы с файлами
            with secure_temp_context() as file_handler:
                if not output_dir:
                    output_dir = file_handler.create_secure_temp_dir(suffix="_video")
            
            # Специфичные настройки для платформ
            opts = self.base_ydl_opts.copy()
            opts['outtmpl'] = os.path.join(output_dir, '%(title)s.%(ext)s')
            
            # Для TikTok 
            if platform == 'tiktok':
                # TikTok часто меняет структуру, используем более гибкие настройки
                opts['format'] = 'best[ext=mp4]/best'
                opts['http_chunk_size'] = 10485760  # 10MB chunks
                
            # Для YouTube Shorts
            elif platform == 'youtube':
                opts['format'] = 'best[height<=1080][ext=mp4]/best[height<=1080]/best'
                
            # Для Instagram - используем альтернативные методы без cookies
            elif platform == 'instagram':
                opts['format'] = 'best'
                # Добавляем заголовки для имитации мобильного приложения
                opts['http_headers'] = {
                    'User-Agent': 'Instagram 219.0.0.12.117 Android (29/10; 420dpi; 1080x2137; samsung; SM-G973F; beyond2; qcom; en_US; 301484394)',
                    'Referer': 'https://www.instagram.com/',
                    'Origin': 'https://www.instagram.com'
                }
                # Используем файл cookies вместо cookiesfrombrowser
                opts['cookiefile'] = self.cookie_file
            
                # Скачиваем видео
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(sanitized_url, download=True)
                
                # Получаем имя скачанного файла
                filename = ydl.prepare_filename(info)
                # Заменяем расширение на актуальное
                base, _ = os.path.splitext(filename)
                actual_filename = f"{base}.{info.get('ext', 'mp4')}"
                
                # Проверяем существование файла
                if not os.path.exists(actual_filename):
                    # Пробуем найти файл с любым расширением
                    allowed_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov']
                    for ext in allowed_extensions:
                        test_path = f"{base}{ext}"
                        if os.path.exists(test_path):
                            # Валидируем найденный файл
                            if SecureFileHandler.validate_file_path(test_path, allowed_extensions):
                                actual_filename = test_path
                                break
                    else:
                        return None, "Файл не был скачан или имеет недопустимый формат."
                
                # Проверяем размер файла
                if not os.path.exists(actual_filename):
                    return None, "Скачанный файл не найден."
                
                file_size = os.path.getsize(actual_filename)
                if file_size == 0:
                    return None, "Скачанный файл пустой."
                
                if file_size > self.config.max_file_size:
                    # Пробуем сжать видео
                    compressed_path = self.compress_video(actual_filename, output_dir)
                    if compressed_path:
                        try:
                            os.remove(actual_filename)
                        except OSError:
                            pass  # Игнорируем ошибки удаления
                        return compressed_path, None
                    else:
                        try:
                            os.remove(actual_filename)
                        except OSError:
                            pass
                        return None, f"Видео слишком большое ({file_size // 1024 // 1024}MB). Максимум {self.config.max_file_size // 1024 // 1024}MB."
                
                # Вычисляем хэш для проверки целостности
                file_hash = SecureFileHandler.calculate_file_hash(actual_filename)
                if file_hash:
                    logger.debug(f"Downloaded file hash: {file_hash}")
                
                return actual_filename, None
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Private video" in error_msg:
                return None, "Видео приватное и недоступно для скачивания"
            elif "age-restricted" in error_msg:
                return None, "Видео имеет возрастные ограничения"
            elif "404" in error_msg or "not found" in error_msg.lower():
                return None, "Видео не найдено или было удалено"
            else:
                logger.error(f"Download error: {e}")
                return None, "Не удалось скачать видео. Проверьте ссылку и попробуйте снова."
                
        except Exception as e:
            logger.error(f"Unexpected error downloading video: {e}")
            return None, "Произошла непредвиденная ошибка при скачивании"
    
    def download_audio(self, url: str, output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Скачивает только аудио из видео с проверками безопасности
        
        Args:
            url: URL видео
            output_dir: Директория для сохранения
            
        Returns:
            Tuple[путь к файлу, сообщение об ошибке]
        """
        # Валидация URL
        is_valid, error_msg = URLValidator.validate_url(url)
        if not is_valid:
            return None, f"Недопустимый URL: {error_msg}"
        
        # Санитизация URL
        sanitized_url = URLValidator.sanitize_url(url)
        if not sanitized_url:
            return None, "Не удалось обработать URL"
        
        try:
            platform = self.detect_platform(sanitized_url)
            if not platform:
                return None, "Неподдерживаемая платформа"
            
            logger.info(f"Downloading audio from {platform}: {sanitized_url}")
            
            # Используем secure temp context
            with secure_temp_context() as file_handler:
                if not output_dir:
                    output_dir = file_handler.create_secure_temp_dir(suffix="_audio")
            
            # Настройки для извлечения аудио
            opts = self.base_ydl_opts.copy()
            opts['format'] = 'bestaudio[ext=m4a]/bestaudio'
            opts['outtmpl'] = os.path.join(output_dir, '%(title)s.%(ext)s')
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(sanitized_url, download=True)
                
                # Получаем имя файла
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                audio_filename = f"{base}.mp3"
                
                # Проверяем файл на существование и валидность
                if os.path.exists(audio_filename):
                    # Валидируем аудиофайл
                    if SecureFileHandler.validate_file_path(audio_filename, ['.mp3']):
                        file_size = os.path.getsize(audio_filename)
                        if file_size > 0:
                            logger.debug(f"Audio file size: {file_size} bytes")
                            return audio_filename, None
                        else:
                            return None, "Извлеченный аудиофайл пустой"
                    else:
                        return None, "Аудиофайл не прошел проверку безопасности"
                else:
                    return None, "Не удалось извлечь аудио"
                    
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None, "Ошибка при извлечении аудио"
    
    def compress_video(self, input_path: str, output_dir: str) -> Optional[str]:
        """
        Сжимает видео с помощью ffmpeg
        
        Args:
            input_path: Путь к исходному видео
            output_dir: Директория для сохранения
            
        Returns:
            Путь к сжатому файлу или None
        """
        try:
            import subprocess
            
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(output_dir, f"{name}_compressed.mp4")
            
            # Команда ffmpeg для сжатия
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                '-crf', str(self.config.compression_crf),
                '-preset', 'fast',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',  # Перезаписывать выходной файл
                output_path
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            
            # Проверяем размер сжатого файла
            if os.path.getsize(output_path) <= self.config.max_file_size:
                return output_path
            else:
                os.remove(output_path)
                return None
                
        except Exception as e:
            logger.error(f"Error compressing video: {e}")
            return None
    
    
    def _get_platform_options(self, platform: str, output_dir: str) -> dict:
        """Получает настройки для конкретной платформы"""
        opts = self.base_ydl_opts.copy()
        opts['outtmpl'] = os.path.join(output_dir, '%(title)s.%(ext)s')
        
        # Применяем настройки из конфигурации
        if platform in self.config.platform_settings:
            platform_config = self.config.platform_settings[platform]
            
            # Обновляем базовые параметры
            for key, value in platform_config.items():
                if key == 'headers':
                    opts['http_headers'] = value
                else:
                    opts[key] = value
        
        # Для Instagram добавляем cookies файл
        if platform == 'instagram':
            opts['cookiefile'] = self.cookie_file
        
        return opts
    
    def _download_video_sync(self, url: str, opts: dict) -> Tuple[Optional[str], Optional[str]]:
        """Синхронная загрузка видео для выполнения в executor"""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Получаем имя скачанного файла
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                actual_filename = f"{base}.{info.get('ext', 'mp4')}"
                
                # Проверяем существование файла
                if not os.path.exists(actual_filename):
                    # Пробуем найти файл с любым расширением
                    for ext in self.config.supported_video_formats:
                        test_path = f"{base}{ext}"
                        if os.path.exists(test_path):
                            if SecureFileHandler.validate_file_path(test_path, self.config.supported_video_formats):
                                actual_filename = test_path
                                break
                    else:
                        return None, "Файл не был скачан или имеет недопустимый формат."
                
                return actual_filename, None
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Private video" in error_msg or "login" in error_msg.lower():
                return None, "private"
            elif "age-restricted" in error_msg:
                return None, "age_restricted"
            elif "404" in error_msg or "not found" in error_msg.lower():
                return None, "not_found"
            elif "copyright" in error_msg.lower():
                return None, "copyright"
            elif "geo" in error_msg.lower() and "block" in error_msg.lower():
                return None, "geo_blocked"
            else:
                return None, f"download_error: {error_msg}"
                
        except Exception as e:
            logger.error(f"Unexpected error in sync download: {e}")
            return None, f"unexpected_error: {str(e)}"
    
    async def _process_downloaded_file(self, file_path: str, output_dir: str, 
                                     progress_tracker=None) -> Tuple[Optional[str], Optional[str]]:
        """Обрабатывает скачанный файл (проверка, сжатие)"""
        if not os.path.exists(file_path):
            return None, "Скачанный файл не найден."
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return None, "Скачанный файл пустой."
        
        # Проверяем размер
        if file_size > self.config.max_file_size:
            if progress_tracker:
                await progress_tracker.set_stage('compressing')
            
            # Пробуем сжать видео
            loop = asyncio.get_event_loop()
            compressed_path = await loop.run_in_executor(
                None, self.compress_video, file_path, output_dir
            )
            
            if compressed_path:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return compressed_path, None
            else:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                max_size_mb = self.config.max_file_size // 1024 // 1024
                return None, f"Видео слишком большое ({file_size // 1024 // 1024}MB). Максимум {max_size_mb}MB."
        
        # Вычисляем хэш для проверки целостности
        file_hash = SecureFileHandler.calculate_file_hash(file_path)
        if file_hash:
            logger.debug(f"Downloaded file hash: {file_hash}")
        
        return file_path, None
