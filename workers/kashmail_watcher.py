"""
Фоновый воркер для мониторинга писем KashMail
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from dataclasses import dataclass

from services.kashmail_api import MailTmApi, KashmailEmailWatcher, EmailMessage
from repos.kashmail_sessions import KashmailRepository

logger = logging.getLogger(__name__)


@dataclass
class WatchSession:
    """Сессия наблюдения за письмами"""
    user_id: int
    jwt_token: str
    address: str
    chat_id: int
    started_at: datetime
    timeout_seconds: int
    known_message_ids: Set[str]
    callback_handler: Optional[callable] = None


class KashmailWatcherService:
    """Сервис фонового мониторинга писем KashMail"""
    
    def __init__(self, database, bot_context):
        self.db = database
        self.bot_context = bot_context
        self.api = MailTmApi(timeout_seconds=30)
        
        # Активные сессии наблюдения
        self.active_sessions: Dict[int, WatchSession] = {}
        
        # Задачи для каждого пользователя
        self.watch_tasks: Dict[int, asyncio.Task] = {}
        
        # Флаг для остановки сервиса
        self.is_running = False
        
        # Основная задача сервиса
        self.main_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запуск сервиса"""
        if self.is_running:
            return
        
        self.is_running = True
        self.main_task = asyncio.create_task(self._main_loop())
        logger.info("KashMail watcher service started")
    
    async def stop(self):
        """Остановка сервиса"""
        self.is_running = False
        
        # Останавливаем все активные задачи
        for task in self.watch_tasks.values():
            if not task.done():
                task.cancel()
        
        # Останавливаем главную задачу
        if self.main_task and not self.main_task.done():
            self.main_task.cancel()
        
        # Закрываем API
        await self.api.close()
        
        logger.info("KashMail watcher service stopped")
    
    async def add_watch_session(
        self, 
        user_id: int, 
        jwt_token: str, 
        address: str, 
        chat_id: int,
        timeout_seconds: int = 200,
        callback_handler: Optional[callable] = None
    ) -> bool:
        """
        Добавить сессию наблюдения за письмами
        
        Args:
            user_id: ID пользователя Telegram
            jwt_token: JWT токен для Mail.tm API
            address: Email адрес для мониторинга
            chat_id: ID чата для отправки уведомлений
            timeout_seconds: Таймаут ожидания в секундах
            callback_handler: Функция обратного вызова при получении письма
        """
        try:
            # Останавливаем предыдущую сессию если есть
            await self.remove_watch_session(user_id)
            
            # Получаем начальный список сообщений
            initial_messages = await self.api.get_messages(jwt_token)
            known_ids = set()
            if initial_messages:
                known_ids = {msg.get("id", "") for msg in initial_messages}
            
            # Создаем новую сессию
            session = WatchSession(
                user_id=user_id,
                jwt_token=jwt_token,
                address=address,
                chat_id=chat_id,
                started_at=datetime.utcnow(),
                timeout_seconds=timeout_seconds,
                known_message_ids=known_ids,
                callback_handler=callback_handler
            )
            
            self.active_sessions[user_id] = session
            
            # Запускаем задачу наблюдения
            task = asyncio.create_task(self._watch_user_emails(session))
            self.watch_tasks[user_id] = task
            
            logger.info(f"Started watching emails for user {user_id}: {address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add watch session for user {user_id}: {e}")
            return False
    
    async def remove_watch_session(self, user_id: int) -> bool:
        """Удалить сессию наблюдения"""
        try:
            # Останавливаем задачу
            if user_id in self.watch_tasks:
                task = self.watch_tasks[user_id]
                if not task.done():
                    task.cancel()
                del self.watch_tasks[user_id]
            
            # Удаляем сессию
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
            
            logger.info(f"Removed watch session for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove watch session for user {user_id}: {e}")
            return False
    
    async def _main_loop(self):
        """Основной цикл сервиса"""
        try:
            while self.is_running:
                # Очищаем завершенные задачи
                completed_users = []
                for user_id, task in self.watch_tasks.items():
                    if task.done():
                        completed_users.append(user_id)
                
                for user_id in completed_users:
                    await self.remove_watch_session(user_id)
                
                # Очищаем истекшие сессии
                await self._cleanup_expired_sessions()
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            logger.info("KashMail watcher main loop cancelled")
        except Exception as e:
            logger.error(f"Error in KashMail watcher main loop: {e}")
    
    async def _cleanup_expired_sessions(self):
        """Очистка истекших сессий"""
        try:
            current_time = datetime.utcnow()
            expired_users = []
            
            for user_id, session in self.active_sessions.items():
                session_duration = (current_time - session.started_at).total_seconds()
                if session_duration > session.timeout_seconds:
                    expired_users.append(user_id)
            
            for user_id in expired_users:
                logger.info(f"Session expired for user {user_id}")
                
                # Отправляем уведомление о таймауте
                await self._send_timeout_notification(user_id)
                
                # Удаляем сессию
                await self.remove_watch_session(user_id)
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
    
    async def _watch_user_emails(self, session: WatchSession):
        """Наблюдение за письмами конкретного пользователя"""
        try:
            watcher = KashmailEmailWatcher(self.api)
            poll_interval = 2.0
            max_poll_interval = 5.0
            
            while self.is_running:
                try:
                    # Проверяем таймаут
                    elapsed = (datetime.utcnow() - session.started_at).total_seconds()
                    if elapsed > session.timeout_seconds:
                        logger.info(f"Watch timeout reached for user {session.user_id}")
                        break
                    
                    # Получаем текущие сообщения
                    messages = await self.api.get_messages(session.jwt_token)
                    
                    if messages:
                        new_messages = []
                        
                        for msg in messages:
                            msg_id = msg.get("id", "")
                            if msg_id and msg_id not in session.known_message_ids:
                                # Получаем детали нового сообщения
                                detail = await self.api.get_message_detail(msg_id, session.jwt_token)
                                if detail:
                                    new_messages.append(detail)
                                    session.known_message_ids.add(msg_id)
                        
                        # Если есть новые сообщения
                        if new_messages:
                            await self._handle_new_messages(session, new_messages)
                            # Прекращаем наблюдение после первого письма
                            break
                    
                    # Ждем перед следующей проверкой
                    await asyncio.sleep(poll_interval)
                    
                    # Увеличиваем интервал поллинга постепенно
                    poll_interval = min(poll_interval * 1.1, max_poll_interval)
                    
                except Exception as e:
                    logger.error(f"Error checking messages for user {session.user_id}: {e}")
                    # При ошибке увеличиваем интервал
                    poll_interval = min(poll_interval * 2, max_poll_interval)
                    await asyncio.sleep(poll_interval)
            
        except asyncio.CancelledError:
            logger.info(f"Email watching cancelled for user {session.user_id}")
        except Exception as e:
            logger.error(f"Error in _watch_user_emails for user {session.user_id}: {e}")
        finally:
            # Обновляем статус сессии в БД
            await self._update_session_status(session.user_id)
    
    async def _handle_new_messages(self, session: WatchSession, messages: list[EmailMessage]):
        """Обработка новых сообщений"""
        try:
            from utils.localization import get_text
            from utils.otp_extract import extract_codes, extract_links
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.constants import ParseMode
            
            for message in messages:
                # Формируем уведомление
                notification_text = f"📨 **Новое письмо в Временной Почте!**\n\n"
                notification_text += f"📧 **To:** `{session.address}`\n"
                notification_text += f"📤 **From:** `{message.from_email}`\n"
                notification_text += f"📋 **Subject:** {message.subject}\n"
                notification_text += f"🕐 **Date:** {message.date.strftime('%H:%M %d.%m.%Y')}"
                
                # Извлекаем коды и ссылки
                text_content = message.text_content or ""
                html_content = message.html_content or ""
                full_content = f"{text_content} {html_content}"
                
                codes = extract_codes(full_content, message.subject)
                links = extract_links(html_content or text_content)
                
                if codes:
                    notification_text += f"\n\n🔑 **Найден код:** `{codes[0]}`"
                
                # Создаем клавиатуру
                keyboard = []
                
                if text_content.strip():
                    keyboard.append([InlineKeyboardButton("📄 Показать тело письма", callback_data=f"kashmail_show_{message.id}")])
                
                if codes:
                    keyboard.append([InlineKeyboardButton("📋 Скопировать код", callback_data=f"kashmail_copy_code_{codes[0]}")])
                
                if links:
                    keyboard.append([InlineKeyboardButton("🔗 Открыть ссылки", callback_data=f"kashmail_links_{message.id}")])
                
                keyboard.extend([
                    [InlineKeyboardButton("🔥 Сжечь адрес", callback_data="kashmail_burn")],
                    [InlineKeyboardButton("📩 Временная Почта меню", callback_data="kashmail_menu")]
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Отправляем уведомление
                await self.bot_context.bot.send_message(
                    chat_id=session.chat_id,
                    text=notification_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Вызываем callback если есть
                if session.callback_handler:
                    await session.callback_handler(message)
                
            # Обновляем статус сессии на 'done'
            if self.db:
                repo = KashmailRepository(self.db)
                await repo.sessions.update_session_status(session.user_id, 'done')
                
        except Exception as e:
            logger.error(f"Error handling new messages for user {session.user_id}: {e}")
    
    async def _send_timeout_notification(self, user_id: int):
        """Отправка уведомления о таймауте"""
        try:
            session = self.active_sessions.get(user_id)
            if not session:
                return
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.constants import ParseMode
            
            timeout_text = f"⏰ **Время ожидания истекло**\n\n"
            timeout_text += f"📧 **Email:** `{session.address}`\n"
            timeout_text += f"🕐 **Время ожидания:** {session.timeout_seconds} секунд\n\n"
            timeout_text += f"Письма не поступили. Попробуйте позже или создайте новый адрес."
            
            keyboard = [
                [InlineKeyboardButton("📧 Новый адрес", callback_data="kashmail_generate")],
                [InlineKeyboardButton("🔄 Назад", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_context.bot.send_message(
                chat_id=session.chat_id,
                text=timeout_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error sending timeout notification to user {user_id}: {e}")
    
    async def _update_session_status(self, user_id: int):
        """Обновление статуса сессии в БД"""
        try:
            if self.db:
                repo = KashmailRepository(self.db)
                await repo.sessions.update_session_status(user_id, 'active')
        except Exception as e:
            logger.error(f"Error updating session status for user {user_id}: {e}")
    
    def get_active_sessions_count(self) -> int:
        """Получить количество активных сессий"""
        return len(self.active_sessions)
    
    def is_user_watching(self, user_id: int) -> bool:
        """Проверить, наблюдает ли пользователь за письмами"""
        return user_id in self.active_sessions
    
    async def get_session_info(self, user_id: int) -> Optional[Dict]:
        """Получить информацию о сессии пользователя"""
        session = self.active_sessions.get(user_id)
        if not session:
            return None
        
        elapsed = (datetime.utcnow() - session.started_at).total_seconds()
        remaining = max(0, session.timeout_seconds - elapsed)
        
        return {
            'address': session.address,
            'started_at': session.started_at,
            'elapsed_seconds': elapsed,
            'remaining_seconds': remaining,
            'timeout_seconds': session.timeout_seconds,
            'known_messages_count': len(session.known_message_ids)
        }


# Глобальный экземпляр сервиса
_watcher_service: Optional[KashmailWatcherService] = None


async def get_watcher_service(database, bot_context) -> KashmailWatcherService:
    """Получить глобальный экземпляр сервиса наблюдения"""
    global _watcher_service
    
    if _watcher_service is None:
        _watcher_service = KashmailWatcherService(database, bot_context)
        await _watcher_service.start()
    
    return _watcher_service


async def cleanup_watcher_service():
    """Очистка ресурсов сервиса при завершении"""
    global _watcher_service
    
    if _watcher_service:
        await _watcher_service.stop()
        _watcher_service = None
