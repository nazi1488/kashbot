"""
Улучшенный модуль для скачивания видео с поддержкой ротации cookies и логирования
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

logger = logging.getLogger(__name__)


class EnhancedVideoDownloader:
    """Улучшенный класс для скачивания видео с ротацией cookies"""
    
    def __init__(self, cookies_manager=None, db=None, max_file_size: int = 50 * 1024 * 1024):
        """
        Args:
            cookies_manager: Менеджер cookies для ротации
            db: База данных для логирования
            max_file_size: Максимальный размер файла в байтах (50MB по умолчанию)
        """
        self.max_file_size = max_file_size
        self.cookies_manager = cookies_manager
        self.db = db
        
        # Счетчики попыток
        self.max_retries = 3
        
        # Базовые настройки для yt-dlp
        self.base_ydl_opts = {
            'quiet': False,  # Показываем ошибки для отладки
            'no_warnings': False,
            'outtmpl': '%(title).100s.%(ext)s',  # Ограничиваем длину имени
            'format': 'best[ext=mp4]/best[height<=720]/best',
            'max_filesize': max_file_size,
            'socket_timeout': 30,
            'retries': 3,
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
        """Определяет платформу по URL"""
        for platform, pattern in self.platform_patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform
        return None
    
    async def download_video_with_retry(self, url: str, user_id: Optional[int] = None,
                                       output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Скачивает видео с автоматической ротацией cookies при ошибках
        
        Returns:
            Tuple[путь к файлу, сообщение об ошибке]
        """
        platform = self.detect_platform(url)
        if not platform:
            return None, "Неподдерживаемая платформа. Поддерживаются: TikTok, YouTube Shorts, Instagram"
        
        # Создаем временную директорию если не указана
        if not output_dir:
            output_dir = tempfile.mkdtemp()
        
        last_error = None
        attempts = 0
        
        # Получаем fingerprint для платформы
        from utils.cookies_manager import FingerprintGenerator
        fingerprint = FingerprintGenerator.generate(platform)
        
        while attempts < self.max_retries:
            attempts += 1
            cookie_data = None
            
            try:
                # Настройки для попытки
                opts = self.base_ydl_opts.copy()
                opts['outtmpl'] = os.path.join(output_dir, opts['outtmpl'])
                
                # Применяем fingerprint
                opts['user_agent'] = fingerprint['user_agent']
                if fingerprint.get('headers'):
                    opts['http_headers'] = fingerprint['headers']
                
                # Получаем cookies если доступны
                if self.cookies_manager:
                    cookie_data = await self.cookies_manager.get_cookies(platform)
                    if cookie_data:
                        # Создаем временный файл с cookies
                        cookie_file = self._create_temp_cookie_file(cookie_data['cookies'])
                        opts['cookiefile'] = cookie_file
                        
                        # Используем user-agent и proxy из cookies если есть
                        if cookie_data.get('user_agent'):
                            opts['user_agent'] = cookie_data['user_agent']
                        if cookie_data.get('proxy'):
                            opts['proxy'] = cookie_data['proxy']
                        
                        logger.info(f"Using cookies {cookie_data['id']} for {platform}")
                
                # Специфичные настройки для платформ
                opts = self._apply_platform_settings(opts, platform)
                
                # Пробуем скачать
                logger.info(f"Downloading video from {platform} (attempt {attempts}/{self.max_retries}): {url}")
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # Получаем имя скачанного файла
                    filename = ydl.prepare_filename(info)
                    # Заменяем расширение на актуальное
                    base, _ = os.path.splitext(filename)
                    actual_filename = f"{base}.{info.get('ext', 'mp4')}"
                    
                    # Проверяем существование файла
                    if not os.path.exists(actual_filename):
                        # Пробуем найти файл с любым расширением
                        for ext in ['mp4', 'webm', 'mkv', 'avi', 'mov', 'flv']:
                            test_path = f"{base}.{ext}"
                            if os.path.exists(test_path):
                                actual_filename = test_path
                                break
                        else:
                            raise Exception("Файл не был скачан")
                    
                    # Проверяем размер файла
                    file_size = os.path.getsize(actual_filename)
                    
                    # Логируем успешное скачивание
                    await self._log_download(
                        user_id=user_id,
                        platform=platform,
                        url=url,
                        cookie_id=cookie_data['id'] if cookie_data else None,
                        success=True,
                        file_size=file_size
                    )
                    
                    # Отмечаем успешное использование cookies
                    if cookie_data and self.cookies_manager:
                        await self.cookies_manager.mark_success(cookie_data['id'])
                    
                    # Проверяем размер и сжимаем если нужно
                    if file_size > self.max_file_size:
                        compressed_path = await self._compress_video_async(actual_filename, output_dir)
                        if compressed_path:
                            os.remove(actual_filename)
                            return compressed_path, None
                        else:
                            os.remove(actual_filename)
                            max_size_mb = self.max_file_size // (1024 * 1024)
                            return None, f"Видео слишком большое ({file_size // 1024 // 1024}MB). Максимум {max_size_mb}MB."
                    
                    return actual_filename, None
                
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                last_error = self._parse_download_error(error_msg)
                logger.warning(f"Download error (attempt {attempts}): {last_error}")
                
                # Логируем ошибку
                await self._log_download(
                    user_id=user_id,
                    platform=platform,
                    url=url,
                    cookie_id=cookie_data['id'] if cookie_data else None,
                    success=False,
                    error_message=last_error
                )
                
                # Отмечаем ошибку cookies
                if cookie_data and self.cookies_manager:
                    await self.cookies_manager.mark_error(cookie_data['id'], last_error)
                
                # Если это проблема с cookies, пробуем другие
                if any(err in error_msg.lower() for err in ['login', 'private', 'auth', 'forbidden']):
                    logger.info(f"Authentication error, trying different cookies...")
                    continue
                
            except Exception as e:
                last_error = f"Неожиданная ошибка: {str(e)}"
                logger.error(f"Unexpected error (attempt {attempts}): {e}")
                
                # Логируем ошибку
                await self._log_download(
                    user_id=user_id,
                    platform=platform,
                    url=url,
                    cookie_id=cookie_data['id'] if cookie_data else None,
                    success=False,
                    error_message=last_error
                )
                
                if cookie_data and self.cookies_manager:
                    await self.cookies_manager.mark_error(cookie_data['id'], last_error)
            
            finally:
                # Удаляем временный файл cookies
                if 'cookie_file' in locals() and os.path.exists(cookie_file):
                    try:
                        os.remove(cookie_file)
                    except:
                        pass
        
        # Все попытки исчерпаны
        return None, last_error or "Не удалось скачать видео после всех попыток"
    
    def _create_temp_cookie_file(self, cookies: list) -> str:
        """Создает временный файл с cookies в формате Netscape"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        
        # Записываем заголовок
        temp_file.write('# Netscape HTTP Cookie File\n')
        temp_file.write('# This file was generated by bot\n\n')
        
        # Записываем cookies
        for cookie in cookies:
            domain = cookie.get('domain', '')
            # Fix: Ensure proper domain format for Netscape
            if domain and not domain.startswith('.') and not cookie.get('hostOnly', False):
                domain = '.' + domain
            
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            expiry = str(int(cookie.get('expirationDate', 0)))
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            
            # Skip invalid cookies
            if not domain or not name:
                continue
                
            # Формат Netscape: domain	flag	path	secure	expiry	name	value
            line = f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n"
            temp_file.write(line)
        
        temp_file.close()
        return temp_file.name
    
    def _apply_platform_settings(self, opts: dict, platform: str) -> dict:
        """Применяет специфичные настройки для платформы"""
        
        if platform == 'tiktok':
            opts['format'] = 'best[ext=mp4]/best'
            opts['http_chunk_size'] = 10485760  # 10MB chunks
            
        elif platform == 'youtube':
            opts['format'] = 'best[height<=1080][ext=mp4]/best[height<=1080]/best'
            
        elif platform == 'instagram':
            opts['format'] = 'best'
            # Добавляем специальные заголовки для Instagram
            if 'http_headers' not in opts:
                opts['http_headers'] = {}
            opts['http_headers'].update({
                'X-IG-App-ID': '936619743392459',
                'X-IG-WWW-Claim': '0'
            })
        
        return opts
    
    def _parse_download_error(self, error_msg: str) -> str:
        """Парсит ошибку скачивания и возвращает понятное сообщение"""
        error_lower = error_msg.lower()
        
        if "private" in error_lower or "login" in error_lower:
            return "Видео приватное или требует авторизации"
        elif "age" in error_lower and "restricted" in error_lower:
            return "Видео имеет возрастные ограничения"
        elif "404" in error_lower or "not found" in error_lower:
            return "Видео не найдено или было удалено"
        elif "copyright" in error_lower:
            return "Видео заблокировано по авторским правам"
        elif "geo" in error_lower and "blocked" in error_lower:
            return "Видео недоступно в вашем регионе"
        elif "unavailable" in error_lower:
            return "Видео временно недоступно"
        else:
            return "Не удалось скачать видео. Проверьте ссылку."
    
    async def _log_download(self, user_id: Optional[int], platform: str, url: str,
                           cookie_id: Optional[int], success: bool,
                           error_message: Optional[str] = None,
                           file_size: Optional[int] = None) -> None:
        """Логирует попытку скачивания в БД"""
        if not self.db:
            return
        
        try:
            query = """
                INSERT INTO download_logs 
                (user_id, platform, url, cookie_id, success, error_message, file_size, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            await self.db.execute(
                query,
                (user_id or 0, platform, url, cookie_id, success, error_message, file_size)
            )
            
        except Exception as e:
            logger.error(f"Error logging download: {e}")
    
    async def _compress_video_async(self, input_path: str, output_dir: str) -> Optional[str]:
        """Асинхронно сжимает видео с помощью ffmpeg"""
        try:
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_path = os.path.join(output_dir, f"{name}_compressed.mp4")
            
            # Команда ffmpeg для сжатия
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                '-crf', '28',  # Качество (чем больше, тем хуже качество но меньше размер)
                '-preset', 'fast',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',  # Перезаписывать выходной файл
                output_path
            ]
            
            # Запускаем асинхронно
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg compression error: {stderr.decode()}")
                return None
            
            # Проверяем размер сжатого файла
            if os.path.getsize(output_path) <= self.max_file_size:
                return output_path
            else:
                os.remove(output_path)
                return None
                
        except Exception as e:
            logger.error(f"Error compressing video: {e}")
            return None
    
    async def download_audio(self, url: str, user_id: Optional[int] = None,
                           output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Скачивает только аудио из видео"""
        platform = self.detect_platform(url)
        if not platform:
            return None, "Неподдерживаемая платформа"
        
        if not output_dir:
            output_dir = tempfile.mkdtemp()
        
        try:
            # Получаем fingerprint
            from utils.cookies_manager import FingerprintGenerator
            fingerprint = FingerprintGenerator.generate(platform)
            
            # Настройки для извлечения аудио
            opts = self.base_ydl_opts.copy()
            opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best[height<=720]/best'
            opts['outtmpl'] = os.path.join(output_dir, '%(title).100s.%(ext)s')
            opts['user_agent'] = fingerprint['user_agent']
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            
            # Получаем cookies если доступны
            if self.cookies_manager:
                cookie_data = await self.cookies_manager.get_cookies(platform)
                if cookie_data:
                    cookie_file = self._create_temp_cookie_file(cookie_data['cookies'])
                    opts['cookiefile'] = cookie_file
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Получаем имя файла
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                audio_filename = f"{base}.mp3"
                
                if os.path.exists(audio_filename):
                    # Логируем успешное скачивание
                    await self._log_download(
                        user_id=user_id,
                        platform=platform,
                        url=url,
                        cookie_id=cookie_data['id'] if 'cookie_data' in locals() and cookie_data else None,
                        success=True,
                        file_size=os.path.getsize(audio_filename)
                    )
                    
                    return audio_filename, None
                else:
                    return None, "Не удалось извлечь аудио"
                    
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None, "Ошибка при извлечении аудио"
        
        finally:
            # Удаляем временный файл cookies
            if 'cookie_file' in locals() and os.path.exists(cookie_file):
                try:
                    os.remove(cookie_file)
                except:
                    pass
    
