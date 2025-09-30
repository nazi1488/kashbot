"""
Централизованная система обработки ошибок
"""

import logging
import traceback
import asyncio
from typing import Optional, Dict, Any, Callable
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.localization import get_text
import config

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Базовый класс для ошибок бота"""

    def __init__(self, message: str, user_message: Optional[str] = None, error_code: Optional[str] = None):
        self.message = message
        self.user_message = user_message or message
        self.error_code = error_code or "UNKNOWN_ERROR"
        super().__init__(self.message)


class FileProcessingError(BotError):
    """Ошибка обработки файла"""
    pass


class ValidationError(BotError):
    """Ошибка валидации данных"""
    pass


class QueueError(BotError):
    """Ошибка очереди задач"""
    pass


class DatabaseError(BotError):
    """Ошибка базы данных"""
    pass


class ExternalServiceError(BotError):
    """Ошибка внешнего сервиса"""
    pass


class ErrorHandler:
    """Централизованный обработчик ошибок"""

    def __init__(self):
        self.error_counts = {}  # Для отслеживания повторяющихся ошибок
        self.admin_notifications = set()  # Ошибки, о которых нужно уведомить админа

    async def handle_error(
        self,
        update: Optional[Update],
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Обработать ошибку и вернуть информацию для ответа пользователю

        Returns:
            dict: {
                'user_message': str,
                'should_notify_admin': bool,
                'log_level': str,
                'error_code': str
            }
        """

        # Определяем тип ошибки
        error_type = type(error).__name__

        # Создаем контекст ошибки
        error_context = {
            'user_id': user_id or (update.effective_user.id if update and update.effective_user else None),
            'chat_id': update.effective_chat.id if update and update.effective_chat else None,
            'message_id': update.effective_message.id if update and update.effective_message else None,
            'error_type': error_type,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        }

        # Определяем уровень логирования и нужно ли уведомлять админа
        should_notify_admin = False
        log_level = 'error'

        if isinstance(error, (FileProcessingError, QueueError, DatabaseError)):
            should_notify_admin = True
            log_level = 'warning' if isinstance(error, ValidationError) else 'error'
        elif isinstance(error, ExternalServiceError):
            should_notify_admin = True
            log_level = 'error'

        # Логируем ошибку
        await self._log_error(error_context, log_level)

        # Определяем сообщение для пользователя
        user_message = await self._get_user_message(error, context)

        # Проверяем на повторяющиеся ошибки
        if should_notify_admin:
            await self._check_repeated_errors(error_context)

        return {
            'user_message': user_message,
            'should_notify_admin': should_notify_admin,
            'log_level': log_level,
            'error_code': getattr(error, 'error_code', 'UNKNOWN_ERROR')
        }

    async def _log_error(self, error_context: Dict[str, Any], level: str = 'error'):
        """Логировать ошибку с полным контекстом"""

        log_data = {
            'user_id': error_context['user_id'],
            'chat_id': error_context['chat_id'],
            'error_type': error_context['error_type'],
            'error_message': error_context['error_message']
        }

        log_message = (
            f"Error occurred: {error_context['error_type']} - {error_context['error_message']}\n"
            f"User ID: {error_context['user_id']}\n"
            f"Chat ID: {error_context['chat_id']}\n"
            f"Full traceback:\n{error_context['traceback']}"
        )

        if level == 'error':
            logger.error(log_message, extra=log_data)
        elif level == 'warning':
            logger.warning(log_message, extra=log_data)
        else:
            logger.info(log_message, extra=log_data)

    async def _get_user_message(self, error: Exception, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Получить сообщение для пользователя на основе типа ошибки"""

        if isinstance(error, ValidationError):
            return get_text(context, 'validation_error', error=error.user_message)
        elif isinstance(error, FileProcessingError):
            return get_text(context, 'file_processing_error', error=error.user_message)
        elif isinstance(error, QueueError):
            return get_text(context, 'queue_error', error=error.user_message)
        elif isinstance(error, DatabaseError):
            return get_text(context, 'database_error')
        elif isinstance(error, ExternalServiceError):
            return get_text(context, 'service_error', error=error.user_message)
        else:
            # Safely get user_message or fallback to string representation
            error_msg = getattr(error, 'user_message', str(error))
            return get_text(context, 'generic_error', error=error_msg)

    async def _check_repeated_errors(self, error_context: Dict[str, Any]):
        """Проверить на повторяющиеся ошибки"""

        error_key = f"{error_context['error_type']}_{error_context['user_id']}"

        current_time = asyncio.get_event_loop().time()
        if error_key in self.error_counts:
            last_time, count = self.error_counts[error_key]
            if current_time - last_time < 300:  # 5 минут
                count += 1
                if count >= 5:  # 5 ошибок за 5 минут
                    await self._notify_admin(error_context, repeated=True)
                    del self.error_counts[error_key]
                else:
                    self.error_counts[error_key] = (current_time, count)
            else:
                self.error_counts[error_key] = (current_time, 1)
        else:
            self.error_counts[error_key] = (current_time, 1)

    async def _notify_admin(self, error_context: Dict[str, Any], repeated: bool = False):
        """Уведомить администраторов об ошибке"""

        if not hasattr(config, 'BOT_ADMINS') or not config.BOT_ADMINS:
            return

        from telegram.ext import Application

        # Здесь должен быть код для отправки уведомления админам
        # Пока просто логируем
        if repeated:
            logger.critical(
                f"REPEATED ERROR detected for user {error_context['user_id']}: "
                f"{error_context['error_type']} - {error_context['error_message']}"
            )
        else:
            logger.warning(
                f"ADMIN NOTIFICATION: {error_context['error_type']} - {error_context['error_message']} "
                f"for user {error_context['user_id']}"
            )

    async def send_error_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_info: Dict[str, Any]
    ):
        """Отправить сообщение об ошибке пользователю"""

        # Проверяем, что у нас есть куда отправлять сообщение
        if not update or not update.effective_message:
            logger.warning("Cannot send error message: no update or effective_message")
            return

        try:
            # Создаем клавиатуру с кнопками действий
            keyboard = [
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data="retry")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
                [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.effective_message.reply_text(
                text=error_info['user_message'],
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
            # Fallback - простое текстовое сообщение
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз позже."
                )
            except:
                logger.error("Completely failed to send error message")


# Глобальный экземпляр обработчика ошибок
error_handler = ErrorHandler()
