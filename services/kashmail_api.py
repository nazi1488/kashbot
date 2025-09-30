"""
API клиент для Mail.tm - временная почта
"""

import asyncio
import logging
import random
import secrets
import string
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Структура данных для письма"""
    id: str
    from_email: str
    subject: str
    date: datetime
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    attachments: List[Dict] = None


class RateLimiter:
    """Ограничитель скорости запросов"""
    
    def __init__(self, max_requests_per_second: float = 1.0):
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0.0
        
    async def wait_if_needed(self):
        """Ожидание если нужно для соблюдения лимита"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)
            
        self.last_request_time = time.time()


class MailTmApi:
    """API клиент для Mail.tm"""
    
    BASE_URL = "https://api.mail.tm"
    
    def __init__(self, timeout_seconds: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.rate_limiter = RateLimiter(max_requests_per_second=1.0)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _ensure_session(self):
        """Создает сессию если её нет"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
    
    async def close(self):
        """Закрыть HTTP сессию"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retries: int = 3
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Выполняет HTTP запрос с обработкой ошибок и ретраями
        
        Returns:
            Tuple[success: bool, response_data: Optional[Dict]]
        """
        await self._ensure_session()
        await self.rate_limiter.wait_if_needed()
        
        url = f"{self.BASE_URL}{endpoint}"
        request_headers = headers or {}
        
        logger.info(f"Making {method} request to {url}")
        
        for attempt in range(retries + 1):
            try:
                async with self.session.request(
                    method, 
                    url, 
                    json=data, 
                    headers=request_headers
                ) as response:
                    
                    # Обработка rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 1))
                        # Экспоненциальный бэкофф с джиттером
                        wait_time = min(retry_after + random.uniform(0, 1), 30)
                        logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Обработка серверных ошибок
                    if response.status >= 500:
                        if attempt < retries:
                            wait_time = (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"Server error {response.status}, retrying in {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Server error {response.status} after {retries} retries")
                            return False, None
                    
                    # Обработка клиентских ошибок
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(f"Client error {response.status}: {error_text}")
                        return False, None
                    
                    # Успешный ответ
                    if 'json' in response.content_type:
                        response_data = await response.json()
                    else:
                        response_data = {"text": await response.text()}
                    
                    return True, response_data
                    
            except asyncio.TimeoutError:
                if attempt < retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Timeout on attempt {attempt + 1}, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request timeout after {retries} retries")
                    return False, None
                    
            except Exception as e:
                if attempt < retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Request error: {e}, retrying in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request failed after {retries} retries: {e}")
                    return False, None
        
        return False, None
    
    async def get_domains(self) -> Optional[List[str]]:
        """Получить список доступных доменов"""
        logger.info("Requesting domains from Mail.tm API...")
        success, data = await self._make_request("GET", "/domains")
        
        if success and data:
            logger.info(f"API response successful. Data: {data}")
            domains = [domain["domain"] for domain in data.get("hydra:member", [])]
            if domains:
                logger.info(f"Got {len(domains)} domains: {domains}")
                return domains
            else:
                logger.error(f"No domains found in response. Full data: {data}")
        else:
            logger.error(f"Failed to get domains. Success: {success}, Data: {data}")
        
        return None
    
    def _generate_email_parts(self, domain: str) -> Tuple[str, str]:
        """Генерирует локальную часть email и пароль"""
        # Генерируем случайную локальную часть
        length = random.randint(8, 12)
        local_part = ''.join(random.choices(
            string.ascii_lowercase + string.digits, 
            k=length
        ))
        
        # Генерируем пароль
        password = secrets.token_urlsafe(16)
        
        return local_part, password
    
    async def create_account(self, domain: str) -> Optional[Tuple[str, str, str]]:
        """
        Создать временный email аккаунт
        
        Returns:
            Tuple[email, password, account_id] или None при ошибке
        """
        local_part, password = self._generate_email_parts(domain)
        email = f"{local_part}@{domain}"
        
        account_data = {
            "address": email,
            "password": password
        }
        
        success, data = await self._make_request("POST", "/accounts", data=account_data)
        
        if success and data:
            account_id = data.get("id")
            logger.info(f"Created account: {email}")
            return email, password, account_id
        
        logger.error(f"Failed to create account for domain {domain}")
        return None
    
    async def get_jwt_token(self, email: str, password: str) -> Optional[str]:
        """Получить JWT токен для доступа к аккаунту"""
        auth_data = {
            "address": email,
            "password": password
        }
        
        success, data = await self._make_request("POST", "/token", data=auth_data)
        
        if success and data:
            jwt_token = data.get("token")
            if jwt_token:
                logger.info(f"Got JWT token for {email}")
                return jwt_token
        
        logger.error(f"Failed to get JWT token for {email}")
        return None
    
    async def get_messages(self, jwt_token: str) -> Optional[List[Dict]]:
        """Получить список сообщений"""
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        success, data = await self._make_request("GET", "/messages", headers=headers)
        
        if success and data:
            messages = data.get("hydra:member", [])
            logger.info(f"Got {len(messages)} messages")
            return messages
        
        logger.error("Failed to get messages")
        return None
    
    async def get_message_detail(self, message_id: str, jwt_token: str) -> Optional[EmailMessage]:
        """Получить детальную информацию о сообщении"""
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        success, data = await self._make_request(
            "GET", 
            f"/messages/{message_id}", 
            headers=headers
        )
        
        if success and data:
            try:
                # Парсим дату
                date_str = data.get("createdAt", "")
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                
                message = EmailMessage(
                    id=data.get("id", ""),
                    from_email=data.get("from", {}).get("address", ""),
                    subject=data.get("subject", ""),
                    date=date,
                    html_content=data.get("html", [None])[0] if data.get("html") else None,
                    text_content=data.get("text", ""),
                    attachments=data.get("attachments", [])
                )
                
                logger.info(f"Got message details for {message_id}")
                return message
                
            except Exception as e:
                logger.error(f"Failed to parse message data: {e}")
                return None
        
        logger.error(f"Failed to get message {message_id}")
        return None
    
    async def create_temporary_email(self) -> Optional[Tuple[str, str, datetime]]:
        """
        Создать временный email адрес со всей необходимой информацией
        
        Returns:
            Tuple[email, jwt_token, expires_at] или None при ошибке
        """
        try:
            # Получаем домены
            domains = await self.get_domains()
            if not domains:
                return None
            
            # Выбираем случайный домен
            domain = random.choice(domains)
            
            # Создаем аккаунт
            account_result = await self.create_account(domain)
            if not account_result:
                return None
            
            email, password, account_id = account_result
            
            # Получаем JWT токен
            jwt_token = await self.get_jwt_token(email, password)
            if not jwt_token:
                return None
            
            # Токен действует 24 часа (по документации Mail.tm)
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
            return email, jwt_token, expires_at
            
        except Exception as e:
            logger.error(f"Failed to create temporary email: {e}")
            return None


class KashmailEmailWatcher:
    """Мониторинг входящих писем для KashMail"""
    
    def __init__(self, api: MailTmApi):
        self.api = api
        self.is_watching = False
        self.watch_task: Optional[asyncio.Task] = None
    
    async def watch_for_new_messages(
        self, 
        jwt_token: str, 
        timeout_seconds: int = 200,
        callback=None
    ) -> Optional[List[EmailMessage]]:
        """
        Ожидание новых сообщений с настраиваемым таймаутом
        
        Args:
            jwt_token: JWT токен для доступа
            timeout_seconds: Максимальное время ожидания
            callback: Функция обратного вызова при получении сообщения
            
        Returns:
            Список новых сообщений или None при таймауте
        """
        self.is_watching = True
        start_time = time.time()
        known_message_ids = set()
        
        # Базовый интервал поллинга
        poll_intervals = [2, 2, 3, 5]  # Прогрессивное увеличение интервала
        poll_index = 0
        
        try:
            # Получаем начальный список сообщений
            initial_messages = await self.api.get_messages(jwt_token)
            if initial_messages:
                known_message_ids = {msg.get("id") for msg in initial_messages}
            
            while self.is_watching and (time.time() - start_time) < timeout_seconds:
                try:
                    # Получаем текущие сообщения
                    current_messages = await self.api.get_messages(jwt_token)
                    
                    if current_messages:
                        # Ищем новые сообщения
                        new_messages = []
                        for msg in current_messages:
                            msg_id = msg.get("id")
                            if msg_id and msg_id not in known_message_ids:
                                # Получаем детали нового сообщения
                                detail = await self.api.get_message_detail(msg_id, jwt_token)
                                if detail:
                                    new_messages.append(detail)
                                    known_message_ids.add(msg_id)
                        
                        # Если есть новые сообщения
                        if new_messages:
                            if callback:
                                await callback(new_messages)
                            return new_messages
                    
                    # Вычисляем интервал для следующего поллинга
                    current_interval = poll_intervals[min(poll_index, len(poll_intervals) - 1)]
                    poll_index += 1
                    
                    # Ждем перед следующим запросом
                    await asyncio.sleep(current_interval)
                    
                except Exception as e:
                    logger.error(f"Error during message polling: {e}")
                    # При ошибке увеличиваем интервал
                    await asyncio.sleep(5)
            
            # Таймаут достигнут
            return None
            
        except Exception as e:
            logger.error(f"Error in message watcher: {e}")
            return None
        finally:
            self.is_watching = False
    
    def stop_watching(self):
        """Остановить мониторинг"""
        self.is_watching = False
        if self.watch_task and not self.watch_task.done():
            self.watch_task.cancel()
