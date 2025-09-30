"""
Конфигурационный файл для Telegram-бота уникализации медиафайлов
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Загружаем переменные окружения
load_dotenv()


class Settings(BaseSettings):
    """Настройки приложения через pydantic"""
    
    # Random Face настройки
    FACE_QUOTA_PER_DAY: int = 10
    REDIS_URL: str = "redis://localhost:6379/0"
    
    model_config = {
        'env_file': '.env',
        'extra': 'ignore'  # Игнорировать дополнительные переменные
    }


# Глобальный экземпляр настроек
settings = Settings()

# Основные настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@channel_username")  # Канал для подписки

# Self-hosted Bot API настройки
USE_LOCAL_BOT_API = os.getenv("USE_LOCAL_BOT_API", "false").lower() == "true"
LOCAL_BOT_API_URL = os.getenv("LOCAL_BOT_API_URL", "http://localhost:8081")

# Настройки обработки
# С self-hosted API можем обрабатывать до 2GB, но ограничиваем до 500MB для пользователей
if USE_LOCAL_BOT_API:
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 500 * 1024 * 1024))  # 500 MB для self-hosted
else:
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 20 * 1024 * 1024))  # 20 MB для обычного API
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']

# Временная директория для обработки файлов
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Настройки уникализации видео
VIDEO_UNIQUENESS_PARAMS = {
    "rotation_range": (0.1, 0.5),  # Диапазон поворота в градусах
    "brightness_range": (0.98, 1.02),  # Диапазон изменения яркости
    "contrast_range": (0.98, 1.02),  # Диапазон изменения контраста
    "noise_level_range": (0.001, 0.005),  # Уровень шума
    "speed_range": (0.99, 1.01),  # Диапазон изменения скорости
    "crf_range": (18, 23),  # Диапазон CRF для кодирования
}

# Настройки уникализации изображений
IMAGE_UNIQUENESS_PARAMS = {
    "brightness_range": (0.95, 1.05),
    "contrast_range": (0.95, 1.05),
    "noise_range": (1, 5),  # Интенсивность шума
    "crop_pixels": (1, 5),  # Количество пикселей для обрезки
}

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "bot.log"

# Языки
SUPPORTED_LANGUAGES = ["uk", "ru", "en"]
DEFAULT_LANGUAGE = "ru"

# Администраторы бота (добавьте свои Telegram ID)
BOT_ADMINS = [int(id) for id in os.getenv("BOT_ADMINS", "").split(",") if id]

# Настройки очереди сжатия
COMPRESSION_MAX_CONCURRENT = int(os.getenv("COMPRESSION_MAX_CONCURRENT", "2"))
COMPRESSION_MAX_QUEUE_SIZE = int(os.getenv("COMPRESSION_MAX_QUEUE_SIZE", "10"))
COMPRESSION_CPU_THRESHOLD = float(os.getenv("COMPRESSION_CPU_THRESHOLD", "80.0"))
COMPRESSION_TASK_TIMEOUT = int(os.getenv("COMPRESSION_TASK_TIMEOUT", "300"))

# База данных
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Настройки KashMail
KASHMAIL_WAIT_TIMEOUT = int(os.getenv("KASHMAIL_WAIT_TIMEOUT", "200"))
KASHMAIL_POLL_BASE_SEC = int(os.getenv("KASHMAIL_POLL_BASE_SEC", "2"))
KASHMAIL_POLL_MAX_SEC = int(os.getenv("KASHMAIL_POLL_MAX_SEC", "5"))
KASHMAIL_ENABLE_DAILY_LIMIT = os.getenv("KASHMAIL_ENABLE_DAILY_LIMIT", "true").lower() == "true"
KASHMAIL_DAILY_LIMIT = int(os.getenv("KASHMAIL_DAILY_LIMIT", "10"))

# Настройки Random Face Generator
FACE_QUOTA_PER_DAY = int(os.getenv("FACE_QUOTA_PER_DAY", "10"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Настройки Keitaro интеграции
KEITARO_WEBHOOK_PORT = int(os.getenv("KEITARO_WEBHOOK_PORT", "8080"))
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN", "YOUR_DOMAIN.COM")
