"""
Утилита для извлечения OTP кодов и ссылок из писем
"""

import re
import logging
from typing import List, Optional, Tuple
from html import unescape
from bs4 import BeautifulSoup
import urllib.parse

logger = logging.getLogger(__name__)


def clean_html(html_content: str) -> str:
    """Очистка HTML и извлечение текста"""
    if not html_content:
        return ""
    
    try:
        # Используем BeautifulSoup для парсинга HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Удаляем script и style теги
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Получаем текст
        text = soup.get_text()
        
        # Очищаем от лишних пробелов и переносов
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return unescape(text)
        
    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        return html_content


def extract_codes(content: str, subject: str = "") -> List[str]:
    """
    Извлечение OTP кодов из текста письма
    
    Args:
        content: Содержимое письма (HTML или текст)
        subject: Тема письма для дополнительного контекста
        
    Returns:
        Список найденных кодов, отсортированных по релевантности
    """
    if not content:
        return []
    
    # Очищаем HTML если есть
    clean_content = clean_html(content)
    
    # Объединяем контент и тему для поиска
    full_text = f"{subject} {clean_content}".lower()
    
    found_codes = []
    
    # Паттерны для поиска кодов
    patterns = [
        # Чисто цифровые коды (4-8 цифр)
        r'\b\d{4,8}\b',
        
        # Буквенно-цифровые коды (4-10 символов)
        r'\b[A-Z0-9]{4,10}\b',
        
        # Коды с разделителями
        r'\b\d{2,4}[-\s]\d{2,4}\b',
        r'\b[A-Z0-9]{2,4}[-\s][A-Z0-9]{2,4}\b',
        
        # Специальные форматы
        r'\b[A-Z]{2}\d{4,6}\b',  # AB123456
        r'\b\d{4}[A-Z]{2}\b',    # 1234AB
    ]
    
    # Слова-маркеры для определения релевантности
    code_markers = [
        'code', 'код', 'кود',
        'otp', 'отп',
        'verification', 'верификация', 'верифікація',
        'confirm', 'подтверждение', 'підтвердження',
        'activate', 'активация', 'активація',
        'validate', 'валидация', 'валідація',
        'pin', 'пин',
        'security', 'безопасность', 'безпека',
        'login', 'вход', 'логин', 'логін',
        'auth', 'авторизация', 'авторизація',
        'sms', 'смс'
    ]
    
    # Поиск кодов по паттернам
    for pattern in patterns:
        matches = re.findall(pattern, clean_content, re.IGNORECASE)
        for match in matches:
            # Фильтруем очевидно неподходящие коды
            if not _is_valid_code(match):
                continue
            
            # Проверяем что это не обычное слово
            if match.upper() in ['YOUR', 'CODE', 'FROM', 'DATE', 'TIME', 'YEAR']:
                continue
                
            found_codes.append(match.upper())
    
    # Удаляем дубликаты, сохраняя порядок
    unique_codes = []
    seen = set()
    for code in found_codes:
        if code not in seen:
            unique_codes.append(code)
            seen.add(code)
    
    # Сортируем по релевантности
    scored_codes = []
    for code in unique_codes:
        score = _calculate_code_relevance(code, full_text, code_markers)
        scored_codes.append((code, score))
    
    # Сортируем по убыванию релевантности
    scored_codes.sort(key=lambda x: x[1], reverse=True)
    
    # Возвращаем только коды (без скоров)
    result = [code for code, score in scored_codes]
    
    logger.info(f"Extracted {len(result)} codes from content")
    return result


def _is_valid_code(code: str) -> bool:
    """Проверка валидности кода"""
    if not code:
        return False
    
    # Слишком короткий или длинный
    if len(code) < 4 or len(code) > 10:
        return False
    
    # Исключаем очевидно неподходящие последовательности
    invalid_patterns = [
        r'^0+$',  # Только нули
        r'^1+$',  # Только единицы
        r'^(\d)\1{3,}$',  # Повторяющиеся цифры (1111, 2222, etc.)
        r'^1234$', r'^4321$', r'^0123$',  # Простые последовательности
        r'^(19|20)\d{2}$',  # Годы
        r'^(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$',  # Даты MMDD
    ]
    
    for pattern in invalid_patterns:
        if re.match(pattern, code):
            return False
    
    return True


def _calculate_code_relevance(code: str, text: str, markers: List[str]) -> float:
    """Вычисление релевантности кода"""
    score = 0.0
    
    # Базовый скор по длине (оптимальная длина 4-6 символов)
    if 4 <= len(code) <= 6:
        score += 3.0
    elif len(code) == 7 or len(code) == 8:
        score += 2.0
    else:
        score += 1.0
    
    # Поиск кода рядом с маркерами
    code_lower = code.lower()
    for marker in markers:
        # Ищем маркер рядом с кодом (в пределах 50 символов)
        pattern = f'({marker}.{{0,50}}{re.escape(code_lower)}|{re.escape(code_lower)}.{{0,50}}{marker})'
        if re.search(pattern, text, re.IGNORECASE):
            score += 5.0
            break
    
    # Бонус за смешанный контент (буквы + цифры)
    if re.search(r'[A-Z]', code) and re.search(r'\d', code):
        score += 1.0
    
    # Бонус за нахождение в начале текста
    if text.find(code_lower) < len(text) * 0.3:
        score += 1.0
    
    return score


def extract_links(content: str) -> List[str]:
    """
    Извлечение ссылок из письма
    
    Args:
        content: HTML содержимое письма
        
    Returns:
        Список найденных ссылок
    """
    if not content:
        return []
    
    links = []
    
    try:
        # Сначала всегда ищем ссылки в тексте регулярными выражениями
        url_pattern = r'https?://[^\s<>"\']+[^\s<>"\'.,;!?]'
        text_urls = re.findall(url_pattern, content)
        
        for url in text_urls:
            clean_url = _clean_url(url)
            if clean_url and _is_valid_url(clean_url):
                links.append(clean_url)
        
        # Если контент содержит HTML теги, парсим их
        if '<' in content and '>' in content:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Ищем все ссылки в HTML
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Пропускаем mailto и другие нестандартные протоколы
                if href.startswith(('http://', 'https://')):
                    # Очищаем и валидируем URL
                    clean_url = _clean_url(href)
                    if clean_url and _is_valid_url(clean_url):
                        links.append(clean_url)
        
    except Exception as e:
        logger.error(f"Error extracting links: {e}")
    
    # Удаляем дубликаты, сохраняя порядок
    unique_links = []
    seen = set()
    for link in links:
        if link not in seen:
            unique_links.append(link)
            seen.add(link)
    
    return unique_links


def _clean_url(url: str) -> str:
    """Очистка URL"""
    if not url:
        return ""
    
    # Убираем лишние символы в конце
    url = url.rstrip('.,;!?')
    
    # Убираем tracking параметры (опционально)
    try:
        parsed = urllib.parse.urlparse(url)
        
        # Список часто встречающихся tracking параметров
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
            'gclid', 'fbclid', 'msclkid', '_ga', 'mc_eid', 'mc_cid'
        }
        
        # Фильтруем параметры
        query_params = urllib.parse.parse_qs(parsed.query)
        clean_params = {k: v for k, v in query_params.items() if k not in tracking_params}
        
        # Собираем URL обратно
        clean_query = urllib.parse.urlencode(clean_params, doseq=True)
        clean_parsed = parsed._replace(query=clean_query)
        
        return urllib.parse.urlunparse(clean_parsed)
        
    except Exception:
        # Если что-то пошло не так, возвращаем исходный URL
        return url


def _is_valid_url(url: str) -> bool:
    """Проверка валидности URL"""
    if not url:
        return False
    
    try:
        parsed = urllib.parse.urlparse(url)
        
        # Должен быть HTTP/HTTPS
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Должен быть домен
        if not parsed.netloc:
            return False
        
        # Минимальная длина
        if len(url) < 10:
            return False
        
        # Исключаем подозрительные домены
        suspicious_domains = [
            'localhost', '127.0.0.1', '0.0.0.0',
            'example.com', 'test.com', 'dummy.com'
        ]
        
        for domain in suspicious_domains:
            if domain in parsed.netloc.lower():
                return False
        
        return True
        
    except Exception:
        return False


def extract_verification_info(content: str, subject: str = "") -> dict:
    """
    Извлечение всей информации для верификации из письма
    
    Args:
        content: Содержимое письма
        subject: Тема письма
        
    Returns:
        Словарь с извлеченной информацией
    """
    result = {
        'codes': extract_codes(content, subject),
        'links': extract_links(content),
        'cleaned_text': clean_html(content)[:500],  # Первые 500 символов
        'has_verification_keywords': False
    }
    
    # Проверяем наличие ключевых слов верификации
    verification_keywords = [
        'verification', 'verify', 'confirm', 'activate', 'validate',
        'верификация', 'подтверждение', 'активация', 'валидация',
        'підтвердження', 'активація', 'валідація',
        'code', 'код', 'кoud', 'otp', 'pin'
    ]
    
    full_text = f"{subject} {result['cleaned_text']}".lower()
    
    # Ищем точные вхождения ключевых слов (не подстроки)
    has_keywords = False
    for keyword in verification_keywords:
        # Используем границы слов для точного поиска
        if re.search(r'\b' + re.escape(keyword) + r'\b', full_text):
            has_keywords = True
            break
    
    result['has_verification_keywords'] = has_keywords
    
    return result
