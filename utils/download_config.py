"""
Конфигурация для загрузчика видео с настраиваемыми параметрами
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import os


@dataclass
class DownloadConfig:
    """Конфигурация для загрузчика видео"""
    
    # Размеры файлов
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # Читается из .env
    max_video_size: int = 100 * 1024 * 1024  # 100MB для premium пользователей
    max_audio_size: int = 25 * 1024 * 1024  # 25MB для аудио
    
    # Качество
    video_quality: str = "best[height<=1080]"
    audio_quality: str = "192"
    compression_crf: int = 23  # 18-28, чем выше - тем больше сжатие
    
    # Таймауты
    socket_timeout: int = 30
    retries: int = 3
    max_download_time: int = 300  # 5 минут
    
    # Поддерживаемые форматы
    supported_video_formats: List[str] = None
    supported_audio_formats: List[str] = None
    
    # Настройки платформ
    platform_settings: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.supported_video_formats is None:
            self.supported_video_formats = ['.mp4', '.webm', '.mkv', '.avi', '.mov']
        
        if self.supported_audio_formats is None:
            self.supported_audio_formats = ['.mp3', '.m4a', '.ogg']
        
        if self.platform_settings is None:
            self.platform_settings = {
                'tiktok': {
                    'format': 'best[ext=mp4]/best',
                    'http_chunk_size': 10485760,  # 10MB chunks
                    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15'
                },
                'youtube': {
                    'format': 'best[height<=1080][ext=mp4]/best[height<=1080]/best',
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                'instagram': {
                    'format': 'best',
                    'user_agent': 'Instagram 219.0.0.12.117 Android (29/10; 420dpi; 1080x2137; samsung; SM-G973F; beyond2; qcom; en_US; 301484394)',
                    'headers': {
                        'Referer': 'https://www.instagram.com/',
                        'Origin': 'https://www.instagram.com',
                        'X-IG-App-ID': '936619743392459',
                        'X-IG-WWW-Claim': '0'
                    }
                }
            }
    
    @classmethod
    def for_user(cls, user_id: int, is_premium: bool = False) -> 'DownloadConfig':
        """
        Создает конфигурацию для конкретного пользователя
        
        Args:
            user_id: ID пользователя
            is_premium: Является ли пользователь премиум
        """
        config = cls()
        
        if is_premium:
            config.max_file_size = config.max_video_size
            config.video_quality = "best[height<=1440]"  # 1440p для premium
            config.audio_quality = "320"  # Высокое качество аудио
            config.compression_crf = 20  # Лучшее качество сжатия
        
        return config
    
    @classmethod
    def from_env(cls) -> 'DownloadConfig':
        """Создает конфигурацию из переменных окружения"""
        config = cls()
        
        # Читаем из переменных окружения
        if max_size := os.getenv('MAX_FILE_SIZE'):
            config.max_file_size = int(max_size)
        
        if video_quality := os.getenv('VIDEO_QUALITY'):
            config.video_quality = video_quality
        
        if audio_quality := os.getenv('AUDIO_QUALITY'):
            config.audio_quality = audio_quality
        
        if socket_timeout := os.getenv('SOCKET_TIMEOUT'):
            config.socket_timeout = int(socket_timeout)
        
        return config


class ErrorMessages:
    """Улучшенные сообщения об ошибках"""
    
    PLATFORM_MESSAGES = {
        'tiktok': {
            'private': "Это видео TikTok приватное. Попросите автора сделать его публичным.",
            'age_restricted': "Видео TikTok имеет возрастные ограничения.",
            'not_found': "Видео TikTok не найдено. Возможно, оно было удалено.",
            'geo_blocked': "Это видео TikTok недоступно в вашем регионе."
        },
        'youtube': {
            'private': "Это видео YouTube приватное или удалено.",
            'age_restricted': "Видео YouTube имеет возрастные ограничения. Войдите в аккаунт YouTube для просмотра.",
            'not_found': "Видео YouTube не найдено по этой ссылке.",
            'geo_blocked': "Это видео YouTube заблокировано в вашем регионе.",
            'copyright': "Видео YouTube заблокировано по авторским правам."
        },
        'instagram': {
            'private': "Этот пост Instagram из приватного аккаунта. Подпишитесь на автора для доступа.",
            'not_found': "Пост Instagram не найден. Возможно, он был удален.",
            'login_required': "Для загрузки этого контента Instagram требуется авторизация."
        }
    }
    
    GENERAL_MESSAGES = {
        'network_error': "Проблемы с сетью. Проверьте подключение к интернету и попробуйте снова.",
        'server_error': "Сервер видеоплатформы временно недоступен. Попробуйте позже.",
        'file_too_large': "Файл слишком большой для отправки. Максимальный размер: {max_size}MB.",
        'invalid_format': "Неподдерживаемый формат файла.",
        'download_timeout': "Превышено время ожидания загрузки. Попробуйте загрузить более короткое видео.",
        'processing_error': "Ошибка при обработке файла. Попробуйте другое видео.",
        'compression_failed': "Не удалось сжать видео до нужного размера."
    }
    
    @classmethod
    def get_error_message(cls, platform: str, error_type: str, **kwargs) -> str:
        """
        Получает подходящее сообщение об ошибке
        
        Args:
            platform: Платформа (tiktok, youtube, instagram)
            error_type: Тип ошибки
            **kwargs: Дополнительные параметры для форматирования
        """
        if platform in cls.PLATFORM_MESSAGES:
            platform_msgs = cls.PLATFORM_MESSAGES[platform]
            if error_type in platform_msgs:
                return platform_msgs[error_type].format(**kwargs)
        
        if error_type in cls.GENERAL_MESSAGES:
            return cls.GENERAL_MESSAGES[error_type].format(**kwargs)
        
        return "Произошла неизвестная ошибка при загрузке видео."
    
    @classmethod
    def get_success_message(cls, platform: str, file_type: str, file_size: int, 
                          watermark_removed: bool = False) -> str:
        """Получает сообщение об успешной загрузке"""
        size_mb = file_size / 1024 / 1024
        
        platform_names = {
            'tiktok': 'TikTok',
            'youtube': 'YouTube',
            'instagram': 'Instagram'
        }
        
        platform_name = platform_names.get(platform, platform)
        file_type_name = "видео" if file_type == "video" else "аудио"
        
        message = f"✅ {file_type_name.capitalize()} с {platform_name} загружено успешно!"
        message += f"\n📁 Размер: {size_mb:.1f} MB"
        
        if watermark_removed:
            message += "\n🎨 Водяные знаки удалены"
        
        return message
