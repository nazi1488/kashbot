"""
Обработчик 2FA TOTP генератора
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.localization import get_text
from utils.totp_generator import totp_gen, get_demo_data, generate_new_secret_with_code, generate_code_for_secret

logger = logging.getLogger(__name__)


class TOTPHandler:
    """Обработчик 2FA TOTP генератора"""
    
    def __init__(self):
        self.refresh_tasks = {}  # Словарь задач автообновления для каждого чата
    
    async def show_totp_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать главное меню 2FA генератора"""
        try:
            # Определяем источник вызова
            if update.callback_query:
                query = update.callback_query
                await query.answer()
                chat_id = query.message.chat.id
                message_id = query.message.message_id
                edit_message = True
            else:
                # Прямой вызов из главного меню
                chat_id = update.effective_chat.id
                message_id = None
                edit_message = False
            
            # Получаем демонстрационные данные
            demo_code, demo_secret, remaining_time = get_demo_data()
            
            # Форматируем секрет для отображения
            formatted_secret = totp_gen.format_secret_display(demo_secret)
            
            # Создаем текст сообщения
            text = get_text(context, 'totp_menu').format(
                code=demo_code,
                secret=formatted_secret,
                remaining_time=remaining_time
            )
            
            # Создаем клавиатуру
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_text(context, 'generate_new_secret'), 
                        callback_data="totp_generate_new"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'use_custom_secret'), 
                        callback_data="totp_custom_secret"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'refresh_code'), 
                        callback_data="totp_refresh"
                    ),
                    InlineKeyboardButton(
                        get_text(context, 'auto_refresh'), 
                        callback_data="totp_auto_refresh"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'back'), 
                        callback_data="main_menu"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if edit_message and message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"Error showing TOTP menu: {e}")
            await self._send_error_message(update, context)
    
    async def generate_new_secret(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Генерирует новый секретный ключ и код"""
        try:
            query = update.callback_query
            await query.answer()
            
            # Генерируем новый секрет
            code, secret, remaining_time = generate_new_secret_with_code()
            
            # Форматируем для отображения
            formatted_secret = totp_gen.format_secret_display(secret)
            
            # Сохраняем секрет в контексте для возможного QR кода
            context.user_data['current_secret'] = secret
            
            text = get_text(context, 'totp_new_secret').format(
                code=code,
                secret=formatted_secret,
                remaining_time=remaining_time
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_text(context, 'generate_qr_code'), 
                        callback_data="totp_generate_qr"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'refresh_code'), 
                        callback_data="totp_refresh_custom"
                    ),
                    InlineKeyboardButton(
                        get_text(context, 'auto_refresh'), 
                        callback_data="totp_auto_refresh_custom"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'back_to_totp'), 
                        callback_data="totp_menu"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error generating new secret: {e}")
            await self._send_error_message(update, context)
    
    async def request_custom_secret(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Запрашивает у пользователя собственный секретный ключ"""
        try:
            query = update.callback_query
            await query.answer()
            
            text = get_text(context, 'totp_enter_secret')
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_text(context, 'back_to_totp'), 
                        callback_data="totp_menu"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Устанавливаем флаг ожидания секрета
            context.user_data['awaiting_totp_secret'] = True
            
        except Exception as e:
            logger.error(f"Error requesting custom secret: {e}")
            await self._send_error_message(update, context)
    
    async def process_custom_secret(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает введенный пользователем секретный ключ"""
        try:
            # Проверяем, ожидаем ли мы секрет
            if not context.user_data.get('awaiting_totp_secret'):
                return
            
            # Убираем флаг ожидания
            context.user_data['awaiting_totp_secret'] = False
            
            # Получаем введенный секрет
            secret = update.message.text.strip().replace(' ', '').upper()
            
            # Проверяем корректность секрета
            if not totp_gen.validate_secret(secret):
                await update.message.reply_text(
                    get_text(context, 'totp_invalid_secret'),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Генерируем код для секрета
            code, remaining_time = generate_code_for_secret(secret)
            
            if code is None:
                await update.message.reply_text(
                    get_text(context, 'totp_invalid_secret'),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Сохраняем секрет
            context.user_data['current_secret'] = secret
            
            # Форматируем для отображения
            formatted_secret = totp_gen.format_secret_display(secret)
            
            text = get_text(context, 'totp_custom_result').format(
                code=code,
                secret=formatted_secret,
                remaining_time=remaining_time
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_text(context, 'generate_qr_code'), 
                        callback_data="totp_generate_qr"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'refresh_code'), 
                        callback_data="totp_refresh_custom"
                    ),
                    InlineKeyboardButton(
                        get_text(context, 'auto_refresh'), 
                        callback_data="totp_auto_refresh_custom"
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text(context, 'back_to_totp'), 
                        callback_data="totp_menu"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error processing custom secret: {e}")
            await update.message.reply_text(
                get_text(context, 'error_processing'),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def generate_qr_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Генерирует QR код для импорта в аутентификатор"""
        try:
            query = update.callback_query
            await query.answer()
            
            # Получаем текущий секрет
            secret = context.user_data.get('current_secret')
            if not secret:
                await query.edit_message_text(
                    get_text(context, 'totp_no_secret'),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Генерируем QR код
            username = update.effective_user.username or f"User{update.effective_user.id}"
            qr_buffer = totp_gen.generate_qr_code(secret, username, "2FA Bot")
            
            if qr_buffer is None:
                await query.edit_message_text(
                    get_text(context, 'totp_qr_error'),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Отправляем QR код
            await query.message.reply_photo(
                photo=InputFile(qr_buffer, filename="totp_qr.png"),
                caption=get_text(context, 'totp_qr_caption').format(
                    secret=totp_gen.format_secret_display(secret)
                ),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            await self._send_error_message(update, context)
    
    async def refresh_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE, use_custom: bool = False) -> None:
        """Обновляет код (демонстрационный или пользовательский)"""
        try:
            query = update.callback_query
            await query.answer("🔄 Обновляем код...")
            
            if use_custom:
                secret = context.user_data.get('current_secret')
                if not secret:
                    await query.edit_message_text(
                        get_text(context, 'totp_no_secret'),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                code, remaining_time = generate_code_for_secret(secret)
                formatted_secret = totp_gen.format_secret_display(secret)
                
                text = get_text(context, 'totp_custom_result').format(
                    code=code,
                    secret=formatted_secret,
                    remaining_time=remaining_time
                )
            else:
                code, secret, remaining_time = get_demo_data()
                formatted_secret = totp_gen.format_secret_display(secret)
                
                text = get_text(context, 'totp_menu').format(
                    code=code,
                    secret=formatted_secret,
                    remaining_time=remaining_time
                )
            
            # Сохраняем текущую клавиатуру
            current_markup = query.message.reply_markup
            
            await query.edit_message_text(
                text=text,
                reply_markup=current_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error refreshing code: {e}")
            await self._send_error_message(update, context)
    
    async def start_auto_refresh(self, update: Update, context: ContextTypes.DEFAULT_TYPE, use_custom: bool = False) -> None:
        """Запускает автоматическое обновление кода каждые 30 секунд"""
        try:
            query = update.callback_query
            await query.answer("⏰ Автообновление включено!")
            
            chat_id = query.message.chat.id
            message_id = query.message.message_id
            
            # Останавливаем предыдущую задачу если есть
            if chat_id in self.refresh_tasks:
                self.refresh_tasks[chat_id].cancel()
            
            # Создаем задачу автообновления
            task = asyncio.create_task(
                self._auto_refresh_loop(context, chat_id, message_id, use_custom)
            )
            self.refresh_tasks[chat_id] = task
            
        except Exception as e:
            logger.error(f"Error starting auto refresh: {e}")
            await self._send_error_message(update, context)
    
    async def _auto_refresh_loop(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, use_custom: bool):
        """Цикл автоматического обновления"""
        try:
            while True:
                if use_custom:
                    secret = context.user_data.get('current_secret')
                    if not secret:
                        break
                    
                    code, remaining_time = generate_code_for_secret(secret)
                    formatted_secret = totp_gen.format_secret_display(secret)
                    
                    text = get_text(context, 'totp_auto_refresh_custom').format(
                        code=code,
                        secret=formatted_secret,
                        remaining_time=remaining_time
                    )
                else:
                    code, secret, remaining_time = get_demo_data()
                    formatted_secret = totp_gen.format_secret_display(secret)
                    
                    text = get_text(context, 'totp_auto_refresh_demo').format(
                        code=code,
                        secret=formatted_secret,
                        remaining_time=remaining_time
                    )
                
                # Создаем кнопку остановки
                keyboard = [
                    [
                        InlineKeyboardButton(
                            get_text(context, 'stop_auto_refresh'), 
                            callback_data="totp_stop_auto_refresh"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            get_text(context, 'back_to_totp'), 
                            callback_data="totp_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as edit_error:
                    logger.debug(f"Message edit failed (expected): {edit_error}")
                
                # Ждем до следующего обновления (обновляем каждые 5 секунд для красоты)
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info(f"Auto refresh stopped for chat {chat_id}")
        except Exception as e:
            logger.error(f"Error in auto refresh loop: {e}")
        finally:
            # Убираем задачу из списка
            if chat_id in self.refresh_tasks:
                del self.refresh_tasks[chat_id]
    
    async def stop_auto_refresh(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Останавливает автоматическое обновление"""
        try:
            query = update.callback_query
            await query.answer("⏹ Автообновление остановлено")
            
            chat_id = query.message.chat.id
            
            # Останавливаем задачу
            if chat_id in self.refresh_tasks:
                self.refresh_tasks[chat_id].cancel()
                del self.refresh_tasks[chat_id]
            
            # Возвращаемся к обычному меню
            await self.show_totp_menu(update, context)
            
        except Exception as e:
            logger.error(f"Error stopping auto refresh: {e}")
            await self._send_error_message(update, context)
    
    async def _send_error_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет сообщение об ошибке"""
        try:
            error_text = get_text(context, 'error_processing')
            
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")


# Глобальный экземпляр обработчика
totp_handler = TOTPHandler()

# Экспортируемые функции для использования в main.py
async def totp_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для меню 2FA"""
    await totp_handler.show_totp_menu(update, context)

async def totp_generate_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для генерации нового секрета"""
    await totp_handler.generate_new_secret(update, context)

async def totp_custom_secret_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для ввода собственного секрета"""
    await totp_handler.request_custom_secret(update, context)

async def totp_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для обновления кода"""
    await totp_handler.refresh_code(update, context, use_custom=False)

async def totp_refresh_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для обновления пользовательского кода"""
    await totp_handler.refresh_code(update, context, use_custom=True)

async def totp_auto_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для автообновления демо кода"""
    await totp_handler.start_auto_refresh(update, context, use_custom=False)

async def totp_auto_refresh_custom_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для автообновления пользовательского кода"""
    await totp_handler.start_auto_refresh(update, context, use_custom=True)

async def totp_generate_qr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для генерации QR кода"""
    await totp_handler.generate_qr_code(update, context)

async def totp_stop_auto_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для остановки автообновления"""
    await totp_handler.stop_auto_refresh(update, context)

async def totp_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений для 2FA"""
    await totp_handler.process_custom_secret(update, context)
