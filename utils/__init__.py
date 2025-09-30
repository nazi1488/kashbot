"""
Пакет утилит для бота уникализации
"""

from .subscription_check import check_subscription, ensure_bot_can_check_subscription
from .image_utils import create_multiple_unique_images
from .ffmpeg_utils import create_multiple_unique_videos, check_ffmpeg_installed
from .localization import get_text
from .text_utils import hide_text_with_zwsp
from .compress_utils import (
    compress_image_for_facebook,
    compress_video_for_facebook,
    is_video_file,
    is_image_file
)
from .queue_manager import compression_queue, QueueManager

__all__ = [
    'check_subscription',
    'ensure_bot_can_check_subscription',
    'create_multiple_unique_images',
    'create_multiple_unique_videos',
    'check_ffmpeg_installed',
    'get_text',
    'hide_text_with_zwsp',
    'compress_image_for_facebook',
    'compress_video_for_facebook',
    'is_video_file',
    'is_image_file',
    'compression_queue',
    'QueueManager'
]
