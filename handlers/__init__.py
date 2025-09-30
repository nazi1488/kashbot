"""
Пакет обработчиков команд и событий бота
"""

from .start import start_command, language_callback
from .subscription import check_subscription_callback, show_main_menu
from .uniqizer import (
    start_uniqizer,
    copies_input_handler,
    file_handler,
    wrong_media_handler,
    cancel_handler,
    main_menu_callback,
    WAITING_FOR_COPIES,
    WAITING_FOR_FILE
)
from .text_hider import (
    hide_text_callback,
    text_handler,
    WAITING_FOR_TEXT
)
from .compressor import (
    smart_compress_callback,
    compress_file_handler,
    wrong_media_handler_compress,
    WAITING_FOR_COMPRESS_FILE
)
from .roi_calculator import (
    roi_calculator_callback,
    roi_start,
    input_spend,
    input_income,
    input_shows,
    input_clicks,
    input_leads,
    input_sales,
    cancel_roi
)
from .roi.states import ROIStates

# Админ панель экспортируется отдельно при необходимости

__all__ = [
    'start_command',
    'language_callback',
    'check_subscription_callback',
    'show_main_menu',
    'uniqueness_tool_callback',
    'copies_input_handler',
    'file_handler',
    'wrong_media_handler',
    'cancel_handler',
    'main_menu_callback',
    'WAITING_FOR_COPIES',
    'WAITING_FOR_FILE',
    'hide_text_callback',
    'text_handler',
    'WAITING_FOR_TEXT',
    'smart_compress_callback',
    'compress_file_handler',
    'wrong_media_handler_compress',
    'WAITING_FOR_COMPRESS_FILE',
    'roi_calculator_callback',
    'roi_start',
    'input_spend',
    'input_income',
    'input_shows',
    'input_clicks',
    'input_leads',
    'input_sales',
    'cancel_roi',
    'ROIStates'
]
