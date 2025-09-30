"""
2FA TOTP генератор
Простой генератор временных кодов для двухфакторной аутентификации
"""

import time
import hmac
import hashlib
import struct
import base64
import secrets
import string
import qrcode
from io import BytesIO
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TOTPGenerator:
    """Генератор TOTP кодов для 2FA"""
    
    def __init__(self):
        self.time_step = 30  # 30 секунд на код
        self.digits = 6      # 6-значный код
        
    def generate_secret(self, length: int = 32) -> str:
        """
        Генерирует случайный секретный ключ
        
        Args:
            length: Длина ключа в символах (по умолчанию 32)
            
        Returns:
            Base32 закодированный секретный ключ
        """
        # Генерируем случайные байты
        random_bytes = secrets.token_bytes(length)
        
        # Кодируем в base32 (стандарт для TOTP)
        secret = base64.b32encode(random_bytes).decode('utf-8')
        
        # Убираем padding символы для красоты
        return secret.rstrip('=')
    
    def generate_totp_code(self, secret: str, timestamp: Optional[int] = None) -> str:
        """
        Генерирует TOTP код для данного секрета
        
        Args:
            secret: Секретный ключ в base32 формате
            timestamp: Временная метка (по умолчанию текущее время)
            
        Returns:
            6-значный TOTP код
        """
        try:
            if timestamp is None:
                timestamp = int(time.time())
            
            # Добавляем padding если нужно
            secret = secret.upper()
            missing_padding = len(secret) % 8
            if missing_padding:
                secret += '=' * (8 - missing_padding)
            
            # Декодируем секрет из base32
            key = base64.b32decode(secret)
            
            # Вычисляем временной счетчик (каждые 30 секунд)
            counter = timestamp // self.time_step
            
            # Создаем HMAC-SHA1 хэш
            counter_bytes = struct.pack('>Q', counter)
            hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
            
            # Извлекаем 4 байта из хэша (dynamic truncation)
            offset = hmac_hash[-1] & 0x0F
            truncated = hmac_hash[offset:offset + 4]
            
            # Преобразуем в число
            code = struct.unpack('>I', truncated)[0]
            code &= 0x7FFFFFFF  # Убираем знаковый бит
            
            # Приводим к нужному количеству цифр
            code %= 10 ** self.digits
            
            return f"{code:0{self.digits}d}"
            
        except Exception as e:
            logger.error(f"Error generating TOTP code: {e}")
            return "000000"
    
    def get_remaining_time(self, timestamp: Optional[int] = None) -> int:
        """
        Получает оставшееся время до смены кода
        
        Args:
            timestamp: Временная метка (по умолчанию текущее время)
            
        Returns:
            Секунды до смены кода
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        return self.time_step - (timestamp % self.time_step)
    
    def generate_qr_code(self, secret: str, account_name: str = "User", issuer: str = "2FA Bot") -> BytesIO:
        """
        Генерирует QR код для импорта в аутентификатор
        
        Args:
            secret: Секретный ключ
            account_name: Имя аккаунта
            issuer: Название сервиса
            
        Returns:
            BytesIO с PNG изображением QR кода
        """
        try:
            # Формируем otpauth URI
            uri = f"otpauth://totp/{issuer}:{account_name}?secret={secret}&issuer={issuer}&digits={self.digits}&period={self.time_step}"
            
            # Создаем QR код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            
            # Создаем изображение
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Сохраняем в BytesIO
            img_buffer = BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            return img_buffer
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return None
    
    def validate_secret(self, secret: str) -> bool:
        """
        Проверяет корректность секретного ключа
        
        Args:
            secret: Секретный ключ для проверки
            
        Returns:
            True если ключ корректный
        """
        try:
            # Проверяем длину (должна быть разумной)
            if len(secret) < 16 or len(secret) > 128:
                return False
            
            # Проверяем что содержит только base32 символы
            allowed_chars = set(string.ascii_uppercase + '234567=')
            if not set(secret.upper()).issubset(allowed_chars):
                return False
            
            # Пытаемся декодировать
            secret_padded = secret.upper()
            missing_padding = len(secret_padded) % 8
            if missing_padding:
                secret_padded += '=' * (8 - missing_padding)
            
            base64.b32decode(secret_padded)
            return True
            
        except Exception:
            return False
    
    def format_secret_display(self, secret: str) -> str:
        """
        Форматирует секрет для красивого отображения (группы по 4 символа)
        
        Args:
            secret: Секретный ключ
            
        Returns:
            Отформатированный ключ
        """
        # Разбиваем на группы по 4 символа
        groups = [secret[i:i+4] for i in range(0, len(secret), 4)]
        return ' '.join(groups)


# Глобальный экземпляр генератора
totp_gen = TOTPGenerator()


def get_demo_data() -> Tuple[str, str, int]:
    """
    Получает демонстрационные данные (как на сайте 2fa.cn)
    
    Returns:
        Tuple: (код, секрет, оставшееся_время)
    """
    # Используем фиксированный секрет для демо (как на сайте)
    demo_secret = "JNXW24DTPEBXXX3NNFSGK2LOMRQXS3DP"
    
    current_code = totp_gen.generate_totp_code(demo_secret)
    remaining_time = totp_gen.get_remaining_time()
    
    return current_code, demo_secret, remaining_time


def generate_new_secret_with_code() -> Tuple[str, str, int]:
    """
    Генерирует новый секрет и код
    
    Returns:
        Tuple: (код, секрет, оставшееся_время)
    """
    new_secret = totp_gen.generate_secret()
    current_code = totp_gen.generate_totp_code(new_secret)
    remaining_time = totp_gen.get_remaining_time()
    
    return current_code, new_secret, remaining_time


def generate_code_for_secret(secret: str) -> Tuple[str, int]:
    """
    Генерирует код для заданного секрета
    
    Args:
        secret: Секретный ключ
        
    Returns:
        Tuple: (код, оставшееся_время)
    """
    if not totp_gen.validate_secret(secret):
        return None, 0
    
    current_code = totp_gen.generate_totp_code(secret)
    remaining_time = totp_gen.get_remaining_time()
    
    return current_code, remaining_time
