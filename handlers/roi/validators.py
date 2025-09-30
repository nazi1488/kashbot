"""
Валидация и парсинг данных для ROI-калькулятора
"""

import re
from typing import Optional, Tuple

def parse_number(text: str) -> Optional[float]:
    """
    Парсит число из текста, поддерживает разные форматы
    
    Поддерживаемые форматы:
    - 1000, 1 000, 1,000, 1000.50, 1,000.50, 1000,50
    
    Returns:
        float или None если не удалось распарсить
    """
    if not text or not text.strip():
        return None
    
    # Убираем лишние пробелы
    text = text.strip()
    
    # Заменяем запятую на точку для десятичной части (европейский формат)
    # Но только если запятая в конце (для отделения дробной части)
    if ',' in text:
        parts = text.split(',')
        if len(parts) == 2:
            # Если после запятой 1-2 цифры - это дробная часть
            if re.match(r'^\d{1,2}$', parts[1]):
                text = f"{parts[0]}.{parts[1]}"
            # Если больше цифр - это разделитель тысяч, убираем
            else:
                text = ''.join(parts)
        else:
            # Несколько запятых - убираем все (разделители тысяч)
            text = text.replace(',', '')
    
    # Убираем пробелы (разделители тысяч)
    text = text.replace(' ', '')
    
    # Убираем символы валют
    text = re.sub(r'[$€₽£¥]', '', text)
    
    try:
        number = float(text)
        return number if number >= 0 else None
    except (ValueError, TypeError):
        return None

def validate_number(text: str, field_name: str) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Валидирует числовой ввод
    
    Args:
        text: Введенный текст
        field_name: Название поля для ошибок
        
    Returns:
        (is_valid, parsed_number, error_message)
    """
    if not text or not text.strip():
        return False, None, f"Введите число для поля '{field_name}' или нажмите Пропустить"
    
    number = parse_number(text)
    
    if number is None:
        return False, None, f"Введите корректное число для '{field_name}' (можно с точкой/запятой) или нажмите Пропустить"
    
    if number < 0:
        return False, None, f"Число для '{field_name}' не может быть отрицательным. Введите положительное число или 0"
    
    return True, number, None

def format_money(amount: float) -> str:
    """Форматирует сумму денег"""
    return f"{amount:.2f}$"

def format_percent(percent: float) -> str:
    """Форматирует проценты"""
    return f"{percent:.1f}%"

def format_number(number: float) -> str:
    """Форматирует обычное число"""
    if number >= 1000000:
        return f"{number/1000000:.1f}M"
    elif number >= 1000:
        return f"{number/1000:.1f}K"
    else:
        return f"{number:.0f}"
