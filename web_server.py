"""
Минимальный веб-сервер для приема postback от Keitaro
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from urllib.parse import parse_qs

from aiohttp import web
from telegram import Bot
from telegram.constants import ParseMode

from database import Database
from database.keitaro_models import KeitaroProfile, KeitaroRoute, KeitaroEvent, MatchByType
from features.keitaro.templates import get_message_template

logger = logging.getLogger(__name__)


class KeitaroWebServer:
    """Веб-сервер для приема postback от Keitaro"""
    
    def __init__(self, bot: Bot, database: Database, port: int = 8080):
        self.bot = bot
        self.db = database
        self.port = port
        self.app = web.Application()
        self.rate_limiter = {}  # Простой in-memory rate limiter
        
        # Регистрируем маршруты
        self.app.router.add_post('/integrations/keitaro/postback', self.handle_postback)
        self.app.router.add_get('/health', self.handle_health)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        return web.json_response({'status': 'ok', 'service': 'keitaro_integration'})
    
    async def handle_postback(self, request: web.Request) -> web.Response:
        """
        Обработчик postback от Keitaro
        Принимает application/x-www-form-urlencoded или application/json
        """
        try:
            # Получаем secret из query параметров
            secret = request.query.get('secret')
            if not secret:
                logger.warning("Postback request without secret")
                return web.json_response({'ok': False, 'error': 'forbidden'}, status=200)
            
            # Ищем профиль по secret
            profile = await self._get_profile_by_secret(secret)
            if not profile or not profile.enabled:
                logger.warning(f"Invalid or disabled secret: {secret[:8]}...")
                return web.json_response({'ok': False, 'error': 'forbidden'}, status=200)
            
            # Парсим тело запроса
            content_type = request.content_type
            if content_type == 'application/x-www-form-urlencoded':
                data = await request.post()
                payload = dict(data)
            elif content_type == 'application/json':
                payload = await request.json()
            else:
                # Пробуем как form data по умолчанию
                text = await request.text()
                payload = dict(parse_qs(text))
                # parse_qs возвращает списки, берем первые значения
                payload = {k: v[0] if isinstance(v, list) else v for k, v in payload.items()}
            
            # Извлекаем поля
            event_data = self._extract_event_data(payload)
            
            # Генерируем или извлекаем transaction_id
            tx_id = event_data.get('transaction_id') or event_data.get('click_id')
            if not tx_id:
                # Генерируем хеш от payload если нет tx_id
                tx_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
                event_data['no_tx'] = True
            
            # Проверяем дедупликацию
            is_duplicate = await self._check_duplicate(profile.id, tx_id, profile.dedup_ttl_sec)
            if is_duplicate:
                logger.info(f"Duplicate event for tx_id: {tx_id}")
                return web.json_response({'ok': True, 'dedup': True})
            
            # Проверяем rate limit
            if not self._check_rate_limit(profile.id, profile.rate_limit_rps):
                logger.warning(f"Rate limit exceeded for profile {profile.id}")
                return web.json_response({'ok': False, 'error': 'rate_limit_exceeded'})
            
            # Определяем маршрутизацию
            target_chat, target_topic = await self._route_event(profile, event_data)
            
            if not target_chat:
                logger.info(f"No matching route for event: {event_data}")
                return web.json_response({'ok': True, 'routed': False})
            
            # Формируем и отправляем сообщение
            message = get_message_template(event_data)
            
            try:
                if target_topic:
                    # Отправка в топик супергруппы
                    await self.bot.send_message(
                        chat_id=target_chat,
                        message_thread_id=target_topic,
                        text=message,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    # Обычная отправка
                    await self.bot.send_message(
                        chat_id=target_chat,
                        text=message,
                        parse_mode=ParseMode.HTML
                    )
                
                # Сохраняем событие
                await self._save_event(
                    profile.id, tx_id, event_data,
                    target_chat, target_topic, processed=True
                )
                
                logger.info(f"Event sent to {target_chat}:{target_topic} for tx {tx_id}")
                return web.json_response({'ok': True})
                
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                await self._save_event(
                    profile.id, tx_id, event_data,
                    target_chat, target_topic, 
                    processed=False, error=str(e)
                )
                return web.json_response({'ok': False, 'error': 'send_failed'})
            
        except Exception as e:
            logger.error(f"Error in postback handler: {e}", exc_info=True)
            return web.json_response({'ok': False, 'error': 'internal_error'})
    
    def _extract_event_data(self, payload: Dict) -> Dict[str, Any]:
        """Извлекает данные события из payload"""
        return {
            'status': payload.get('status', '').lower(),
            'transaction_id': payload.get('transaction_id', ''),
            'click_id': payload.get('click_id', ''),
            'campaign_id': payload.get('campaign_id', ''),
            'campaign_name': payload.get('campaign_name', ''),
            'offer_name': payload.get('offer_name', ''),
            'conversion_revenue': payload.get('conversion_revenue', ''),
            'payout': payload.get('payout', ''),
            'currency': payload.get('currency', ''),
            'country': payload.get('country', ''),
            'source': payload.get('source', ''),
            'creative_id': payload.get('creative_id', ''),
            'landing_name': payload.get('landing_name', ''),
            'sub_id_1': payload.get('sub_id_1', ''),
            'sub_id_2': payload.get('sub_id_2', ''),
            'sub_id_3': payload.get('sub_id_3', ''),
            'sub_id_4': payload.get('sub_id_4', ''),
            'sub_id_5': payload.get('sub_id_5', ''),
            'sub_id_6': payload.get('sub_id_6', ''),
            'sub_id_7': payload.get('sub_id_7', ''),
            'sub_id_8': payload.get('sub_id_8', ''),
            'sub_id_9': payload.get('sub_id_9', ''),
            'sub_id_10': payload.get('sub_id_10', ''),
        }
    
    async def _get_profile_by_secret(self, secret: str) -> Optional[KeitaroProfile]:
        """Получает профиль по secret"""
        query = """
            SELECT * FROM keitaro_profiles 
            WHERE secret = %s AND enabled = true 
            LIMIT 1
        """
        result = await self.db.execute(query, (secret,), fetch=True)
        if result:
            # Простое преобразование в объект
            profile = KeitaroProfile()
            for key, value in result[0].items():
                setattr(profile, key, value)
            return profile
        return None
    
    async def _check_duplicate(self, profile_id: int, tx_id: str, ttl_sec: int) -> bool:
        """Проверяет дупликат события"""
        query = """
            SELECT id FROM keitaro_events 
            WHERE profile_id = %s 
            AND transaction_id = %s 
            AND created_at > %s
            LIMIT 1
        """
        threshold = datetime.utcnow() - timedelta(seconds=ttl_sec)
        result = await self.db.execute(query, (profile_id, tx_id, threshold), fetch=True)
        return bool(result)
    
    def _check_rate_limit(self, profile_id: int, max_rps: int) -> bool:
        """Простая проверка rate limit"""
        import time
        now = time.time()
        
        if profile_id not in self.rate_limiter:
            self.rate_limiter[profile_id] = []
        
        # Очищаем старые записи
        self.rate_limiter[profile_id] = [
            t for t in self.rate_limiter[profile_id] 
            if now - t < 1.0
        ]
        
        # Проверяем лимит
        if len(self.rate_limiter[profile_id]) >= max_rps:
            return False
        
        # Добавляем текущий запрос
        self.rate_limiter[profile_id].append(now)
        return True
    
    async def _route_event(
        self, profile: KeitaroProfile, event_data: Dict
    ) -> tuple[Optional[int], Optional[int]]:
        """Определяет маршрутизацию события"""
        # Получаем правила маршрутизации
        query = """
            SELECT * FROM keitaro_routes 
            WHERE profile_id = %s 
            ORDER BY priority ASC, id ASC
        """
        routes = await self.db.execute(query, (profile.id,), fetch=True)
        
        for route in routes:
            # Проверяем соответствие
            if route['match_by'] == MatchByType.CAMPAIGN_ID.value:
                if not self._match_value(
                    event_data.get('campaign_id', ''), 
                    route['match_value'], 
                    route['is_regex']
                ):
                    continue
            elif route['match_by'] == MatchByType.SOURCE.value:
                if not self._match_value(
                    event_data.get('source', ''), 
                    route['match_value'], 
                    route['is_regex']
                ):
                    continue
            elif route['match_by'] != MatchByType.ANY.value:
                continue
            
            # Проверяем фильтры
            if route['status_filter']:
                if event_data.get('status') not in route['status_filter']:
                    continue
            
            if route['geo_filter']:
                if event_data.get('country') not in route['geo_filter']:
                    continue
            
            # Правило подошло
            return route['target_chat_id'], route['target_topic_id']
        
        # Используем настройки по умолчанию
        return profile.default_chat_id, profile.default_topic_id
    
    def _match_value(self, value: str, pattern: str, is_regex: bool) -> bool:
        """Проверяет соответствие значения паттерну"""
        if is_regex:
            import re
            try:
                return bool(re.match(pattern, value))
            except:
                return False
        else:
            return value == pattern
    
    async def _save_event(
        self, profile_id: int, tx_id: str, event_data: Dict,
        chat_id: Optional[int], topic_id: Optional[int],
        processed: bool, error: Optional[str] = None
    ):
        """Сохраняет событие в БД"""
        query = """
            INSERT INTO keitaro_events (
                profile_id, transaction_id, status, campaign_id, source, 
                country, revenue, processed, sent_to_chat_id, sent_to_topic_id, error
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        revenue = event_data.get('conversion_revenue') or event_data.get('payout', '')
        
        await self.db.execute(query, (
            profile_id, tx_id, event_data.get('status'),
            event_data.get('campaign_id'), event_data.get('source'),
            event_data.get('country'), revenue, processed,
            chat_id, topic_id, error
        ))
    
    async def start(self):
        """Запускает веб-сервер"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Keitaro web server started on port {self.port}")
