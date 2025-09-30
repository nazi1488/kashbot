"""
Webhook сервер для приема обновлений от Telegram
"""

import os
import logging
import hashlib
import hmac
from typing import Optional

from aiohttp import web
from telegram import Update, Bot
from telegram.ext import Application
import orjson

logger = logging.getLogger(__name__)


class WebhookServer:
    """Сервер для приема вебхуков от Telegram"""
    
    def __init__(
        self,
        bot_token: str,
        webhook_path: str = '/telegram/webhook',
        webhook_secret: Optional[str] = None,
        port: int = 8443
    ):
        self.bot_token = bot_token
        self.webhook_path = webhook_path
        self.webhook_secret = webhook_secret or os.urandom(32).hex()
        self.port = port
        self.app = web.Application()
        self.application: Optional[Application] = None
        
        # Настройка маршрутов
        self.app.router.add_post(self.webhook_path, self.handle_webhook)
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_get('/metrics', self.handle_metrics)
        
        # Метрики
        self.metrics = {
            'webhooks_received': 0,
            'webhooks_processed': 0,
            'webhooks_failed': 0,
            'last_update_id': 0
        }
    
    def set_application(self, application: Application):
        """Установка Telegram Application"""
        self.application = application
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'service': 'telegram_webhook',
            'metrics': self.metrics
        })
    
    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Metrics endpoint для Prometheus"""
        metrics_text = f"""
# HELP telegram_webhooks_total Total number of webhooks received
# TYPE telegram_webhooks_total counter
telegram_webhooks_total{{status="received"}} {self.metrics['webhooks_received']}
telegram_webhooks_total{{status="processed"}} {self.metrics['webhooks_processed']}
telegram_webhooks_total{{status="failed"}} {self.metrics['webhooks_failed']}

# HELP telegram_last_update_id Last processed update ID
# TYPE telegram_last_update_id gauge
telegram_last_update_id {self.metrics['last_update_id']}
"""
        return web.Response(text=metrics_text, content_type='text/plain')
    
    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Обработка webhook от Telegram"""
        self.metrics['webhooks_received'] += 1
        
        try:
            # Проверка секретного токена (если настроен)
            if self.webhook_secret:
                token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
                if token != self.webhook_secret:
                    logger.warning("Invalid webhook secret token")
                    return web.Response(status=403)
            
            # Получаем данные
            data = await request.read()
            
            # Парсим JSON
            update_data = orjson.loads(data)
            
            # Создаем объект Update
            update = Update.de_json(update_data, self.application.bot)
            
            if update:
                self.metrics['last_update_id'] = update.update_id
                
                # Обрабатываем update асинхронно
                await self.application.process_update(update)
                
                self.metrics['webhooks_processed'] += 1
            
            return web.Response(status=200)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.metrics['webhooks_failed'] += 1
            return web.Response(status=500)
    
    async def setup_webhook(self, domain: str, use_https: bool = True):
        """Настройка webhook в Telegram"""
        try:
            bot = Bot(token=self.bot_token)
            
            # Формируем URL
            protocol = 'https' if use_https else 'http'
            webhook_url = f"{protocol}://{domain}{self.webhook_path}"
            
            # Устанавливаем webhook
            success = await bot.set_webhook(
                url=webhook_url,
                secret_token=self.webhook_secret,
                max_connections=100,
                allowed_updates=[
                    'message',
                    'edited_message',
                    'callback_query',
                    'inline_query',
                    'my_chat_member',
                    'chat_member'
                ]
            )
            
            if success:
                logger.info(f"Webhook set successfully: {webhook_url}")
                
                # Получаем информацию о webhook
                webhook_info = await bot.get_webhook_info()
                logger.info(f"Webhook info: {webhook_info}")
            else:
                logger.error("Failed to set webhook")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False
    
    async def remove_webhook(self):
        """Удаление webhook"""
        try:
            bot = Bot(token=self.bot_token)
            success = await bot.delete_webhook()
            logger.info(f"Webhook removed: {success}")
            return success
        except Exception as e:
            logger.error(f"Error removing webhook: {e}")
            return False
    
    def run(self):
        """Запуск webhook сервера"""
        web.run_app(
            self.app,
            host='0.0.0.0',
            port=self.port,
            access_log=logger
        )


async def init_webhook_server(
    application: Application,
    domain: str,
    port: int = 8443,
    webhook_path: str = '/telegram/webhook'
) -> WebhookServer:
    """Инициализация webhook сервера"""
    
    # Создаем сервер
    server = WebhookServer(
        bot_token=application.bot.token,
        webhook_path=webhook_path,
        port=port
    )
    
    # Привязываем application
    server.set_application(application)
    
    # Настраиваем webhook
    await server.setup_webhook(domain=domain, use_https=True)
    
    return server
