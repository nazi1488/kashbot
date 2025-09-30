"""
Модуль для работы с локализацией
"""

import json
import logging
from pathlib import Path
from typing import Dict
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)


def load_translations() -> Dict[str, Dict[str, str]]:
    """Загружает все файлы локализации"""
    translations = {}
    locales_dir = Path(__file__).parent.parent / 'locales'
    
    for lang in config.SUPPORTED_LANGUAGES:
        try:
            with open(locales_dir / f'{lang}.json', 'r', encoding='utf-8') as f:
                translations[lang] = json.load(f)
                logger.info(f"Loaded {lang} translations successfully")
        except Exception as e:
            logger.error(f"Failed to load {lang} translations: {e}")
            translations[lang] = {}
    
    return translations


# Глобальная переменная для хранения переводов
TRANSLATIONS = load_translations()


def get_text(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    """
    Получает локализованный текст
    
    Args:
        context: Контекст телеграм
        key: Ключ перевода
        **kwargs: Параметры для форматирования
    
    Returns:
        str: Локализованный текст
    """
    # Безопасно получаем user_data
    user_data = context.user_data if context and hasattr(context, 'user_data') and context.user_data else {}
    lang = user_data.get('language', config.DEFAULT_LANGUAGE) if user_data else config.DEFAULT_LANGUAGE
    
    # Проверяем, что язык поддерживается
    if lang not in TRANSLATIONS:
        logger.warning(f"Language {lang} not found in translations, using default")
        lang = config.DEFAULT_LANGUAGE
    
    # Получаем текст
    text = TRANSLATIONS.get(lang, {}).get(key, f"[{key}]")
    
    # Если текст не найден, пробуем получить из языка по умолчанию
    if text == f"[{key}]" and lang != config.DEFAULT_LANGUAGE:
        text = TRANSLATIONS.get(config.DEFAULT_LANGUAGE, {}).get(key, f"[{key}]")
        logger.warning(f"Key '{key}' not found in {lang}, using default language")
    
    # Форматируем текст если есть параметры
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception as e:
            logger.error(f"Error formatting text for key '{key}': {e}")
    
    return text
