"""
Интеграционные тесты для KashMail с моками Mail.tm API
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from services.kashmail_api import MailTmApi, KashmailEmailWatcher, EmailMessage
from repos.kashmail_sessions import KashmailRepository
from database.models import Database


class TestMailTmApiMocked(unittest.IsolatedAsyncioTestCase):
    """Тесты Mail.tm API с моками"""
    
    def setUp(self):
        """Настройка тестов"""
        self.api = MailTmApi(timeout_seconds=10)
    
    async def asyncTearDown(self):
        """Очистка после тестов"""
        await self.api.close()
    
    @patch('aiohttp.ClientSession.request')
    async def test_get_domains_success(self, mock_request):
        """Тест успешного получения доменов"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = 'application/json'
        mock_response.json.return_value = {
            "hydra:member": [
                {"domain": "1secmail.com"},
                {"domain": "1secmail.org"}
            ]
        }
        
        mock_request.return_value.__aenter__.return_value = mock_response
        
        domains = await self.api.get_domains()
        
        self.assertIsNotNone(domains)
        self.assertIn("1secmail.com", domains)
        self.assertIn("1secmail.org", domains)
    
    @patch('aiohttp.ClientSession.request')
    async def test_create_account_success(self, mock_request):
        """Тест успешного создания аккаунта"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = 'application/json'
        mock_response.json.return_value = {
            "id": "test-account-id",
            "address": "test@1secmail.com"
        }
        
        mock_request.return_value.__aenter__.return_value = mock_response
        
        result = await self.api.create_account("1secmail.com")
        
        self.assertIsNotNone(result)
        email, password, account_id = result
        self.assertTrue(email.endswith("@1secmail.com"))
        self.assertIsNotNone(password)
        self.assertEqual(account_id, "test-account-id")
    
    @patch('aiohttp.ClientSession.request')
    async def test_get_jwt_token_success(self, mock_request):
        """Тест успешного получения JWT токена"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = 'application/json'
        mock_response.json.return_value = {
            "token": "test.jwt.token"
        }
        
        mock_request.return_value.__aenter__.return_value = mock_response
        
        token = await self.api.get_jwt_token("test@1secmail.com", "password")
        
        self.assertEqual(token, "test.jwt.token")
    
    @patch('aiohttp.ClientSession.request')
    async def test_get_messages_success(self, mock_request):
        """Тест успешного получения сообщений"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = 'application/json'
        mock_response.json.return_value = {
            "hydra:member": [
                {
                    "id": "msg1",
                    "from": {"address": "sender@example.com"},
                    "subject": "Test message",
                    "createdAt": "2024-01-01T12:00:00Z"
                }
            ]
        }
        
        mock_request.return_value.__aenter__.return_value = mock_response
        
        messages = await self.api.get_messages("test.jwt.token")
        
        self.assertIsNotNone(messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["id"], "msg1")
    
    @patch('aiohttp.ClientSession.request')
    async def test_get_message_detail_success(self, mock_request):
        """Тест получения деталей сообщения"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = 'application/json'
        mock_response.json.return_value = {
            "id": "msg1",
            "from": {"address": "sender@example.com"},
            "subject": "Verification Code",
            "createdAt": "2024-01-01T12:00:00Z",
            "text": "Your code is 123456",
            "html": ["<p>Your code is <strong>123456</strong></p>"]
        }
        
        mock_request.return_value.__aenter__.return_value = mock_response
        
        message = await self.api.get_message_detail("msg1", "test.jwt.token")
        
        self.assertIsNotNone(message)
        self.assertIsInstance(message, EmailMessage)
        self.assertEqual(message.id, "msg1")
        self.assertEqual(message.subject, "Verification Code")
        self.assertIn("123456", message.text_content)
    
    @patch('aiohttp.ClientSession.request')
    async def test_rate_limiting_handling(self, mock_request):
        """Тест обработки rate limiting"""
        # Первый запрос - 429 ошибка
        mock_response_429 = AsyncMock()
        mock_response_429.status = 429
        mock_response_429.headers = {'Retry-After': '1'}
        
        # Второй запрос - успешный
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.content_type = 'application/json'
        mock_response_200.json.return_value = {"hydra:member": []}
        
        mock_request.return_value.__aenter__.side_effect = [
            mock_response_429,
            mock_response_200
        ]
        
        # Патчим sleep чтобы тест выполнялся быстрее
        with patch('asyncio.sleep'):
            messages = await self.api.get_messages("test.jwt.token")
        
        self.assertIsNotNone(messages)
        self.assertEqual(len(messages), 0)
    
    @patch('aiohttp.ClientSession.request')
    async def test_server_error_retry(self, mock_request):
        """Тест повторных попыток при серверных ошибках"""
        # Первый запрос - 500 ошибка
        mock_response_500 = AsyncMock()
        mock_response_500.status = 500
        
        # Второй запрос - успешный
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.content_type = 'application/json'
        mock_response_200.json.return_value = {"hydra:member": []}
        
        mock_request.return_value.__aenter__.side_effect = [
            mock_response_500,
            mock_response_200
        ]
        
        with patch('asyncio.sleep'):
            messages = await self.api.get_messages("test.jwt.token")
        
        self.assertIsNotNone(messages)


class TestKashmailEmailWatcher(unittest.IsolatedAsyncioTestCase):
    """Тесты наблюдателя за email"""
    
    def setUp(self):
        """Настройка тестов"""
        self.api = MailTmApi(timeout_seconds=10)
        self.watcher = KashmailEmailWatcher(self.api)
    
    async def asyncTearDown(self):
        """Очистка после тестов"""
        await self.api.close()
    
    @patch.object(MailTmApi, 'get_messages')
    @patch.object(MailTmApi, 'get_message_detail')
    async def test_watch_for_new_messages_found(self, mock_get_detail, mock_get_messages):
        """Тест обнаружения новых сообщений"""
        # Первый вызов - нет сообщений
        # Второй вызов - есть новое сообщение
        mock_get_messages.side_effect = [
            [],  # Изначально нет сообщений
            [{"id": "new_msg1"}]  # Появилось новое сообщение
        ]
        
        # Детали нового сообщения
        new_message = EmailMessage(
            id="new_msg1",
            from_email="test@example.com",
            subject="Test",
            date=datetime.now(),
            text_content="Test message"
        )
        mock_get_detail.return_value = new_message
        
        # Патчим sleep для ускорения теста
        with patch('asyncio.sleep'):
            messages = await self.watcher.watch_for_new_messages(
                "test.jwt.token",
                timeout_seconds=5
            )
        
        self.assertIsNotNone(messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, "new_msg1")
    
    @patch.object(MailTmApi, 'get_messages')
    async def test_watch_timeout(self, mock_get_messages):
        """Тест таймаута ожидания"""
        # Всегда возвращаем пустой список
        mock_get_messages.return_value = []
        
        with patch('asyncio.sleep'):
            with patch('time.time', side_effect=[0, 0, 10]):  # Симулируем истечение времени
                messages = await self.watcher.watch_for_new_messages(
                    "test.jwt.token",
                    timeout_seconds=5
                )
        
        self.assertIsNone(messages)  # Таймаут должен вернуть None
    
    async def test_stop_watching(self):
        """Тест остановки наблюдения"""
        self.watcher.is_watching = True
        self.watcher.stop_watching()
        self.assertFalse(self.watcher.is_watching)


class TestKashmailRepositoryMocked(unittest.IsolatedAsyncioTestCase):
    """Тесты репозитория с мок базой данных"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_db = MagicMock(spec=Database)
        self.repo = KashmailRepository(self.mock_db)
    
    async def test_create_session_success(self):
        """Тест успешного создания сессии"""
        self.mock_db.execute = AsyncMock(return_value=True)
        
        result = await self.repo.sessions.create_session(
            user_id=123,
            address="test@example.com",
            jwt="test.jwt.token",
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
        self.assertTrue(result)
        self.mock_db.execute.assert_called_once()
    
    async def test_get_session_exists(self):
        """Тест получения существующей сессии"""
        mock_session_data = [{
            'user_id': 123,
            'address': 'test@example.com',
            'jwt': 'test.jwt.token',
            'status': 'active'
        }]
        self.mock_db.execute = AsyncMock(return_value=mock_session_data)
        
        session = await self.repo.sessions.get_session(123)
        
        self.assertIsNotNone(session)
        self.assertEqual(session['address'], 'test@example.com')
    
    async def test_get_session_not_exists(self):
        """Тест получения несуществующей сессии"""
        self.mock_db.execute = AsyncMock(return_value=[])
        
        session = await self.repo.sessions.get_session(123)
        
        self.assertIsNone(session)
    
    async def test_update_session_status(self):
        """Тест обновления статуса сессии"""
        self.mock_db.execute = AsyncMock(return_value=True)
        
        result = await self.repo.sessions.update_session_status(123, 'burned')
        
        self.assertTrue(result)
        self.mock_db.execute.assert_called_once()
    
    async def test_daily_usage_increment(self):
        """Тест увеличения дневного счетчика"""
        self.mock_db.execute = AsyncMock(return_value=True)
        
        result = await self.repo.counters.increment_daily_usage(123, 1)
        
        self.assertTrue(result)
        self.mock_db.execute.assert_called_once()
    
    async def test_get_remaining_quota(self):
        """Тест получения оставшейся квоты"""
        # Мокаем что пользователь использовал 3 адреса сегодня
        self.mock_db.execute = AsyncMock(return_value=[{'count': 3}])
        
        remaining = await self.repo.counters.get_remaining_quota(123, daily_limit=10)
        
        self.assertEqual(remaining, 7)
    
    async def test_can_create_email_within_limit(self):
        """Тест возможности создания email в пределах лимита"""
        # Мокаем проверки
        self.mock_db.execute = AsyncMock(side_effect=[
            [{'count': 5}],  # Использовано 5 из 10
            []  # Нет активной сессии
        ])
        
        can_create, reason = await self.repo.can_user_create_email(123, daily_limit=10)
        
        self.assertTrue(can_create)
        self.assertEqual(reason, "OK")
    
    async def test_can_create_email_exceed_limit(self):
        """Тест превышения лимита"""
        # Мокаем что пользователь использовал 10 из 10
        self.mock_db.execute = AsyncMock(return_value=[{'count': 10}])
        
        can_create, reason = await self.repo.can_user_create_email(123, daily_limit=10)
        
        self.assertFalse(can_create)
        self.assertIn("Превышен дневной лимит", reason)
    
    async def test_can_create_email_has_active_session(self):
        """Тест наличия активной сессии"""
        self.mock_db.execute = AsyncMock(side_effect=[
            [{'count': 2}],  # В пределах лимита
            [{'status': 'active'}]  # Есть активная сессия
        ])
        
        can_create, reason = await self.repo.can_user_create_email(123, daily_limit=10)
        
        self.assertFalse(can_create)
        self.assertIn("активная сессия", reason)


class TestKashmailIntegration(unittest.IsolatedAsyncioTestCase):
    """Интеграционные тесты полного процесса"""
    
    @patch('services.kashmail_api.MailTmApi.get_domains')
    @patch('services.kashmail_api.MailTmApi.create_account')
    @patch('services.kashmail_api.MailTmApi.get_jwt_token')
    async def test_create_temporary_email_flow(self, mock_get_jwt, mock_create_account, mock_get_domains):
        """Тест полного процесса создания временного email"""
        # Мокаем API вызовы
        mock_get_domains.return_value = ["1secmail.com"]
        mock_create_account.return_value = ("test@1secmail.com", "password123", "account_id")
        mock_get_jwt.return_value = "test.jwt.token"
        
        api = MailTmApi()
        
        try:
            result = await api.create_temporary_email()
            
            self.assertIsNotNone(result)
            email, jwt_token, expires_at = result
            self.assertTrue(email.endswith("@1secmail.com"))
            self.assertEqual(jwt_token, "test.jwt.token")
            self.assertIsInstance(expires_at, datetime)
        finally:
            await api.close()


if __name__ == '__main__':
    unittest.main()
