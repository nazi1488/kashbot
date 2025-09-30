"""
Модуль для валидации и санитизации URL
"""

import re
import urllib.parse
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class URLValidator:
    """Класс для валидации и очистки URL"""
    
    # Белый список доменов
    ALLOWED_DOMAINS = {
        'tiktok.com', 'www.tiktok.com', 'vm.tiktok.com',
        'youtube.com', 'www.youtube.com', 'youtu.be',
        'instagram.com', 'www.instagram.com', 'instagr.am'
    }
    
    # Опасные схемы
    BLOCKED_SCHEMES = {'file', 'ftp', 'javascript', 'data'}
    
    @classmethod
    def validate_url(cls, url: str) -> tuple[bool, Optional[str]]:
        """
        Валидирует URL на безопасность и соответствие требованиям
        
        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not url or not isinstance(url, str):
            return False, "URL не может быть пустым"
        
        url = url.strip()
        
        # Проверяем длину
        if len(url) > 2048:
            return False, "URL слишком длинный"
        
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            logger.warning(f"Failed to parse URL {url}: {e}")
            return False, "Некорректный формат URL"
        
        # Проверяем схему
        if parsed.scheme.lower() in cls.BLOCKED_SCHEMES:
            return False, f"Схема {parsed.scheme} запрещена"
        
        if parsed.scheme.lower() not in ['http', 'https']:
            return False, "Поддерживаются только HTTP и HTTPS"
        
        # Проверяем домен
        domain = parsed.netloc.lower()
        if not domain:
            return False, "Отсутствует доменное имя"
        
        # Убираем порт для проверки
        domain_without_port = domain.split(':')[0]
        
        if not any(domain_without_port == allowed or domain_without_port.endswith('.' + allowed) 
                  for allowed in cls.ALLOWED_DOMAINS):
            return False, f"Домен {domain_without_port} не поддерживается"
        
        # Проверяем на подозрительные паттерны
        if cls._has_suspicious_patterns(url):
            return False, "URL содержит подозрительные элементы"
        
        return True, None
    
    @classmethod
    def _has_suspicious_patterns(cls, url: str) -> bool:
        """Проверяет на подозрительные паттерны в URL"""
        suspicious_patterns = [
            r'\.\./',  # Path traversal
            r'%2e%2e/',  # Encoded path traversal
            r'<script',  # XSS attempt
            r'javascript:',  # JavaScript injection
            r'vbscript:',  # VBScript injection
        ]
        
        url_lower = url.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, url_lower):
                return True
        
        return False
    
    @classmethod
    def sanitize_url(cls, url: str) -> Optional[str]:
        """
        Санитизирует URL
        
        Returns:
            Optional[str]: Очищенный URL или None если невалидный
        """
        is_valid, error = cls.validate_url(url)
        if not is_valid:
            logger.warning(f"Invalid URL rejected: {url} - {error}")
            return None
        
        # Базовая очистка
        url = url.strip()
        
        # Убираем потенциально опасные параметры
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Фильтруем query параметры
            if parsed.query:
                query_params = urllib.parse.parse_qs(parsed.query)
                safe_params = {}
                
                # Список разрешенных параметров
                allowed_params = {'v', 't', 'feature', 'list', 'index'}
                
                for param, values in query_params.items():
                    if param.lower() in allowed_params and values:
                        safe_params[param] = values[0]
                
                new_query = urllib.parse.urlencode(safe_params)
                parsed = parsed._replace(query=new_query)
            
            # Убираем fragment для безопасности
            parsed = parsed._replace(fragment='')
            
            return urllib.parse.urlunparse(parsed)
            
        except Exception as e:
            logger.error(f"Error sanitizing URL {url}: {e}")
            return None
