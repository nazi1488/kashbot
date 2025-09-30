"""
Тесты для Keitaro интеграции
"""

import pytest
import asyncio
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock

from features.keitaro.templates import (
    normalize_status, format_amount, get_message_template, escape_html
)


class TestKeitaroTemplates:
    """Тесты шаблонов сообщений"""
    
    def test_normalize_status(self):
        """Тест нормализации статусов"""
        assert normalize_status("registration") == "registration"
        assert normalize_status("lead") == "registration"
        assert normalize_status("signup") == "registration"
        assert normalize_status("DEPOSIT") == "deposit"
        assert normalize_status("sale") == "deposit"
        assert normalize_status("ftd") == "deposit"
        assert normalize_status("rejected") == "rejected"
        assert normalize_status("trash") == "rejected"
        assert normalize_status("unknown") == "registration"  # По умолчанию
    
    def test_format_amount(self):
        """Тест форматирования суммы"""
        assert format_amount("100", "", "USD") == "100 USD"
        assert format_amount("100.00", "", "EUR") == "100 EUR"
        assert format_amount("100.50", "", "USD") == "100.50 USD"
        assert format_amount("", "50", "RUB") == "50 RUB"
        assert format_amount("", "50.00", "") == "50"
        assert format_amount("", "", "") == "0"
    
    def test_escape_html(self):
        """Тест экранирования HTML"""
        assert escape_html("<script>") == "&lt;script&gt;"
        assert escape_html("Test & Co") == "Test &amp; Co"
        assert escape_html("Normal text") == "Normal text"
        assert escape_html("") == ""
        assert escape_html(None) == ""
    
    def test_registration_template(self):
        """Тест шаблона регистрации"""
        event = {
            'status': 'registration',
            'campaign_name': 'Test Campaign',
            'offer_name': 'Test Offer',
            'country': 'US',
            'sub_id_1': 'sub1',
            'transaction_id': 'tx123'
        }
        
        message = get_message_template(event)
        assert "📝 <b>Регистрация</b>" in message
        assert "Test Campaign" in message
        assert "Test Offer" in message
        assert "US" in message
        assert "sub1" in message
        assert "tx123" in message
    
    def test_deposit_template(self):
        """Тест шаблона депозита"""
        event = {
            'status': 'deposit',
            'campaign_name': 'Campaign 1',
            'creative_id': 'cr123',
            'offer_name': 'Landing 1',
            'conversion_revenue': '100',
            'currency': 'USD',
            'country': 'UK',
            'sub_id_1': 'test',
            'transaction_id': 'tx456'
        }
        
        message = get_message_template(event)
        assert "💰 <b>Депозит</b>" in message
        assert "Campaign 1" in message
        assert "cr123" in message
        assert "Landing 1" in message
        assert "100 USD" in message
        assert "UK" in message
        assert "test" in message
        assert "tx456" in message
    
    def test_rejected_template(self):
        """Тест шаблона отказа"""
        event = {
            'status': 'rejected',
            'campaign_name': 'Campaign X',
            'sub_id_2': 'invalid_geo',  # Причина часто в sub_id_2
            'transaction_id': 'tx789'
        }
        
        message = get_message_template(event)
        assert "⛔️ <b>Отказ</b>" in message
        assert "Campaign X" in message
        assert "invalid_geo" in message
        assert "tx789" in message


class TestKeitaroDuplication:
    """Тесты дедупликации событий"""
    
    @pytest.fixture
    def mock_db(self):
        """Мок базы данных"""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_dedup_check(self, mock_db):
        """Тест проверки дубликатов"""
        from web_server import KeitaroWebServer
        from telegram import Bot
        
        mock_bot = Mock(spec=Bot)
        server = KeitaroWebServer(mock_bot, mock_db, 8080)
        
        # Первая проверка - нет дубликата
        mock_db.execute.return_value = []
        is_dup = await server._check_duplicate(1, "tx123", 3600)
        assert is_dup is False
        
        # Вторая проверка - есть дубликат
        mock_db.execute.return_value = [{'id': 1}]
        is_dup = await server._check_duplicate(1, "tx123", 3600)
        assert is_dup is True


class TestKeitaroRouting:
    """Тесты маршрутизации событий"""
    
    @pytest.fixture
    def mock_db(self):
        """Мок базы данных"""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_profile(self):
        """Мок профиля"""
        from database.keitaro_models import KeitaroProfile
        profile = KeitaroProfile()
        profile.id = 1
        profile.default_chat_id = -1001234567890
        profile.default_topic_id = None
        profile.enabled = True
        profile.rate_limit_rps = 27
        profile.dedup_ttl_sec = 3600
        return profile
    
    @pytest.mark.asyncio
    async def test_route_by_campaign_id(self, mock_db, mock_profile):
        """Тест маршрутизации по campaign_id"""
        from web_server import KeitaroWebServer
        from telegram import Bot
        
        mock_bot = Mock(spec=Bot)
        server = KeitaroWebServer(mock_bot, mock_db, 8080)
        
        # Настраиваем правила маршрутизации
        routes = [
            {
                'match_by': 'campaign_id',
                'match_value': 'camp123',
                'is_regex': False,
                'target_chat_id': -1009999999999,
                'target_topic_id': None,
                'status_filter': None,
                'geo_filter': None
            }
        ]
        mock_db.execute.return_value = routes
        
        # Тестируем событие с подходящим campaign_id
        event_data = {'campaign_id': 'camp123'}
        chat_id, topic_id = await server._route_event(mock_profile, event_data)
        
        assert chat_id == -1009999999999
        assert topic_id is None
    
    @pytest.mark.asyncio
    async def test_route_with_filters(self, mock_db, mock_profile):
        """Тест маршрутизации с фильтрами"""
        from web_server import KeitaroWebServer
        from telegram import Bot
        
        mock_bot = Mock(spec=Bot)
        server = KeitaroWebServer(mock_bot, mock_db, 8080)
        
        # Правило с фильтром по статусу
        routes = [
            {
                'match_by': 'any',
                'match_value': '*',
                'is_regex': False,
                'target_chat_id': -1008888888888,
                'target_topic_id': None,
                'status_filter': ['deposit', 'sale'],
                'geo_filter': ['US', 'UK']
            }
        ]
        mock_db.execute.return_value = routes
        
        # Событие проходит фильтры
        event_data = {'status': 'deposit', 'country': 'US'}
        chat_id, topic_id = await server._route_event(mock_profile, event_data)
        assert chat_id == -1008888888888
        
        # Событие НЕ проходит фильтр по статусу
        event_data = {'status': 'registration', 'country': 'US'}
        chat_id, topic_id = await server._route_event(mock_profile, event_data)
        assert chat_id == mock_profile.default_chat_id  # Fallback на дефолт
    
    @pytest.mark.asyncio
    async def test_route_fallback_to_default(self, mock_db, mock_profile):
        """Тест fallback на настройки по умолчанию"""
        from web_server import KeitaroWebServer
        from telegram import Bot
        
        mock_bot = Mock(spec=Bot)
        server = KeitaroWebServer(mock_bot, mock_db, 8080)
        
        # Нет подходящих правил
        mock_db.execute.return_value = []
        
        event_data = {'campaign_id': 'unknown'}
        chat_id, topic_id = await server._route_event(mock_profile, event_data)
        
        assert chat_id == mock_profile.default_chat_id
        assert topic_id == mock_profile.default_topic_id


class TestKeitaroRateLimit:
    """Тесты rate limiting"""
    
    def test_rate_limit_basic(self):
        """Базовый тест rate limit"""
        from web_server import KeitaroWebServer
        from telegram import Bot
        
        mock_bot = Mock(spec=Bot)
        mock_db = Mock()
        server = KeitaroWebServer(mock_bot, mock_db, 8080)
        
        profile_id = 1
        max_rps = 3
        
        # Первые 3 запроса должны пройти
        for i in range(3):
            assert server._check_rate_limit(profile_id, max_rps) is True
        
        # 4-й запрос должен быть заблокирован
        assert server._check_rate_limit(profile_id, max_rps) is False
    
    def test_rate_limit_time_window(self):
        """Тест временного окна rate limit"""
        import time
        from web_server import KeitaroWebServer
        from telegram import Bot
        
        mock_bot = Mock(spec=Bot)
        mock_db = Mock()
        server = KeitaroWebServer(mock_bot, mock_db, 8080)
        
        profile_id = 2
        max_rps = 2
        
        # Заполняем лимит
        assert server._check_rate_limit(profile_id, max_rps) is True
        assert server._check_rate_limit(profile_id, max_rps) is True
        assert server._check_rate_limit(profile_id, max_rps) is False
        
        # Ждем > 1 секунды
        time.sleep(1.1)
        
        # Теперь должно снова работать
        assert server._check_rate_limit(profile_id, max_rps) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
