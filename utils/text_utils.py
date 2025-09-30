"""
Утилиты для работы с текстом
"""

import logging

logger = logging.getLogger(__name__)

# Zero-Width Space символ (невидимый)
ZERO_WIDTH_SPACE = '\u200B'


def hide_text_with_zwsp(text: str) -> str:
    """
    Вставляет Zero-Width Space между каждым символом текста
    
    Args:
        text: Исходный текст
    
    Returns:
        str: Текст с невидимыми символами между каждой буквой
    """
    if not text:
        return text
    
    # Вставляем ZWSP между каждым символом
    hidden_text = ZERO_WIDTH_SPACE.join(text)
    
    logger.info(f"Hidden text: original length {len(text)}, new length {len(hidden_text)}")
    
    return hidden_text


def remove_zwsp(text: str) -> str:
    """
    Удаляет все Zero-Width Space символы из текста
    
    Args:
        text: Текст с ZWSP
    
    Returns:
        str: Очищенный текст
    """
    return text.replace(ZERO_WIDTH_SPACE, '')


def count_zwsp(text: str) -> int:
    """
    Подсчитывает количество Zero-Width Space символов в тексте
    
    Args:
        text: Текст для проверки
    
    Returns:
        int: Количество ZWSP символов
    """
    return text.count(ZERO_WIDTH_SPACE)
