"""
Gmail Aliases Generator Service

Генерирует Gmail-алиасы используя dot-trick и +tag методы.
Не сохраняет базовый email пользователя в БД.
"""

import re
import random
import string
from datetime import datetime
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class GmailAliasGenerator:
    """Генератор Gmail-алиасов"""
    
    GMAIL_DOMAINS = {'gmail.com', 'googlemail.com'}
    MAX_DAILY_QUOTA = 10
    
    @classmethod
    def normalize_email(cls, email: str) -> Tuple[str, str]:
        """
        Нормализует email к базовому виду
        
        Args:
            email: Исходный email (например john.doe+tag@gmail.com)
            
        Returns:
            Tuple[str, str]: (normalized_local_part, domain)
            
        Example:
            normalize_email("john.doe+tag@gmail.com") -> ("johndoe", "gmail.com")
        """
        email = email.lower().strip()
        
        if '@' not in email:
            raise ValueError("Invalid email format")
        
        local_part, domain = email.split('@', 1)
        
        # Удаляем все после + (если есть)
        if '+' in local_part:
            local_part = local_part.split('+')[0]
        
        # Удаляем все точки из local части (только для Gmail)
        if domain in cls.GMAIL_DOMAINS:
            local_part = local_part.replace('.', '')
        
        return local_part, domain
    
    @classmethod
    def validate_email(cls, email: str) -> Tuple[bool, str]:
        """
        Валидирует email адрес
        
        Args:
            email: Email для валидации
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        # Базовая валидация email
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_regex, email):
            return False, "Некорректный формат email адреса"
        
        try:
            local_part, domain = email.split('@', 1)
        except ValueError:
            return False, "Некорректный формат email адреса"
        
        # Проверка длины local части
        if len(local_part) > 64:
            return False, "Локальная часть email слишком длинная"
        
        # Проверка домена
        if len(domain) > 255:
            return False, "Домен слишком длинный"
        
        return True, ""
    
    @classmethod
    def is_gmail_domain(cls, email: str) -> bool:
        """Проверяет, является ли домен Gmail"""
        try:
            _, domain = email.split('@', 1)
            return domain.lower() in cls.GMAIL_DOMAINS
        except ValueError:
            return False
    
    @classmethod
    def generate_tag(cls) -> str:
        """
        Генерирует уникальный tag для +tag алиаса
        
        Returns:
            str: Сгенерированный tag (например: '250925a7')
        """
        # Формат: YYMMDD + 2 случайных символа
        date_part = datetime.now().strftime('%y%m%d')
        
        # 2 случайных символа (буквы и цифры)
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=2))
        
        return f"{date_part}{random_part}"
    
    @classmethod
    def generate_dot_variants(cls, local_base: str, max_variants: int = 5) -> List[str]:
        """
        Генерирует варианты с точками в local части
        
        Args:
            local_base: Базовая local часть без точек
            max_variants: Максимальное количество вариантов
            
        Returns:
            List[str]: Список вариантов local частей с точками
        """
        if len(local_base) < 2:
            return [local_base]  # Слишком короткая для точек
        
        variants = []
        
        # Стратегия 1: точка каждые 2 символа
        if len(local_base) >= 4:
            variant1 = ''
            for i in range(0, len(local_base), 2):
                if i > 0:
                    variant1 += '.'
                variant1 += local_base[i:i+2]
            if variant1 != local_base and variant1 not in variants:
                variants.append(variant1)
        
        # Стратегия 2: точка каждые 3 символа
        if len(local_base) >= 6:
            variant2 = ''
            for i in range(0, len(local_base), 3):
                if i > 0:
                    variant2 += '.'
                variant2 += local_base[i:i+3]
            if variant2 != local_base and variant2 not in variants:
                variants.append(variant2)
        
        # Стратегия 3: точка в середине
        if len(local_base) >= 4:
            mid = len(local_base) // 2
            variant3 = local_base[:mid] + '.' + local_base[mid:]
            if variant3 != local_base and variant3 not in variants:
                variants.append(variant3)
        
        # Стратегия 4: точки между всеми символами (только для коротких)
        if len(local_base) <= 6:
            variant4 = '.'.join(local_base)
            if variant4 != local_base and variant4 not in variants:
                variants.append(variant4)
        
        # Стратегия 5: случайное размещение точек
        if len(local_base) >= 4:
            # Вставляем точки в случайные позиции
            indices = sorted(random.sample(range(1, len(local_base)), 
                                         min(2, len(local_base) - 1)))
            variant5 = ''
            last_idx = 0
            for idx in indices:
                variant5 += local_base[last_idx:idx] + '.'
                last_idx = idx
            variant5 += local_base[last_idx:]
            if variant5 != local_base and variant5 not in variants:
                variants.append(variant5)
        
        return variants[:max_variants]
    
    @classmethod
    def generate_plus_variants(cls, local_base: str, count: int) -> List[str]:
        """
        Генерирует варианты с +tag
        
        Args:
            local_base: Базовая local часть
            count: Количество вариантов для генерации
            
        Returns:
            List[str]: Список local частей с +tag
        """
        variants = []
        
        for _ in range(count):
            tag = cls.generate_tag()
            variant = f"{local_base}+{tag}"
            variants.append(variant)
        
        return variants
    
    @classmethod
    def generate(cls, base_email: str, count: int = 5) -> List[str]:
        """
        Генерирует список Gmail-алиасов
        
        Args:
            base_email: Базовый email адрес
            count: Количество алиасов для генерации
            
        Returns:
            List[str]: Список сгенерированных алиасов
            
        Raises:
            ValueError: Если email невалидный
        """
        # Валидация
        is_valid, error = cls.validate_email(base_email)
        if not is_valid:
            raise ValueError(error)
        
        # Нормализация
        local_base, domain = cls.normalize_email(base_email)
        
        aliases = []
        remaining = count
        
        # Приоритет +tag вариантам (более надежные)
        plus_count = min(remaining, (count + 1) // 2)  # Примерно половина
        if plus_count > 0:
            plus_variants = cls.generate_plus_variants(local_base, plus_count)
            for variant in plus_variants:
                aliases.append(f"{variant}@{domain}")
            remaining -= plus_count
        
        # Добавляем dot варианты
        if remaining > 0:
            dot_variants = cls.generate_dot_variants(local_base, remaining)
            for variant in dot_variants:
                aliases.append(f"{variant}@{domain}")
                remaining -= 1
                if remaining <= 0:
                    break
        
        # Если все еще нужны алиасы, добавляем еще +tag
        while remaining > 0:
            tag = cls.generate_tag()
            alias = f"{local_base}+{tag}@{domain}"
            if alias not in aliases:
                aliases.append(alias)
                remaining -= 1
        
        return aliases[:count]


# Основная функция для использования в обработчиках
def generate_gmail_aliases(base_email: str, count: int) -> List[str]:
    """
    Основная функция для генерации Gmail-алиасов
    
    Args:
        base_email: Базовый Gmail адрес
        count: Количество алиасов для генерации (1-10)
        
    Returns:
        List[str]: Список сгенерированных алиасов
        
    Raises:
        ValueError: Если входные данные некорректны
    """
    if not isinstance(count, int) or count < 1 or count > GmailAliasGenerator.MAX_DAILY_QUOTA:
        raise ValueError(f"Количество должно быть от 1 до {GmailAliasGenerator.MAX_DAILY_QUOTA}")
    
    return GmailAliasGenerator.generate(base_email, count)


def validate_gmail_input(email: str) -> Tuple[bool, str, bool]:
    """
    Валидирует ввод пользователя для Gmail
    
    Args:
        email: Email для валидации
        
    Returns:
        Tuple[bool, str, bool]: (is_valid, error_message, is_gmail_domain)
    """
    is_valid, error = GmailAliasGenerator.validate_email(email)
    if not is_valid:
        return False, error, False
    
    is_gmail = GmailAliasGenerator.is_gmail_domain(email)
    
    return True, "", is_gmail
